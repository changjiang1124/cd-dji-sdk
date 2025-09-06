#include "media_transfer_adapter.h"
#include "../../include/logger.h"
#include "../../include/media_manager/media_manager.h"
#include "config_manager.h"
#if __cplusplus >= 201703L
#include <filesystem>
namespace fs = std::filesystem;
#else
#include <experimental/filesystem>
namespace fs = std::experimental::filesystem;
#endif
#include <sstream>
#include <iomanip>
#include <chrono>

namespace celestial {

MediaTransferAdapter::MediaTransferAdapter()
    : initialized_(false)
    , shutdown_flag_(false)
    , total_files_processed_(0)
    , successful_transfers_(0)
    , failed_transfers_(0)
    , total_bytes_transferred_(0) {
    
    // 初始化工具类
    file_utils_ = std::make_unique<utils::FileUtils>();
    hash_calculator_ = std::make_unique<utils::HashCalculator>();
}

MediaTransferAdapter::~MediaTransferAdapter() {
    Shutdown();
}

bool MediaTransferAdapter::Initialize(std::shared_ptr<ChunkTransferManager> chunk_manager,
                                     std::shared_ptr<MediaStatusDB> media_db) {
    if (initialized_.load()) {
        WARN("MediaTransferAdapter already initialized");
        return true;
    }
    
    if (!chunk_manager || !media_db) {
        ERROR("Invalid parameters: chunk_manager or media_db is null");
        return false;
    }
    
    chunk_manager_ = chunk_manager;
    media_db_ = media_db;
    
    // 初始化分块传输管理器
    if (!chunk_manager_->Initialize()) {
        ERROR("Failed to initialize ChunkTransferManager");
        return false;
    }
    
    initialized_.store(true);
    INFO("MediaTransferAdapter initialized successfully");
    return true;
}

void MediaTransferAdapter::Shutdown() {
    if (!initialized_.load()) {
        return;
    }
    
    shutdown_flag_.store(true);
    
    // 等待所有传输完成
    while (HasActiveTransfers()) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    
    // 关闭分块传输管理器
    if (chunk_manager_) {
        chunk_manager_->Shutdown();
    }
    
    // 清理任务映射
    {
        std::lock_guard<std::mutex> lock(task_map_mutex_);
        task_to_filepath_.clear();
        task_to_tempfile_.clear();
    }
    
    initialized_.store(false);
    INFO("MediaTransferAdapter shutdown completed");
}

edge_sdk::ErrorCode MediaTransferAdapter::HandleMediaFileUpdate(const edge_sdk::MediaFile& file) {
    if (!initialized_.load() || shutdown_flag_.load()) {
        ERROR("MediaTransferAdapter not initialized or shutting down");
        return edge_sdk::ErrorCode::kErrorSystemError;
    }
    
    INFO("收到媒体文件更新通知:");
    INFO("  文件名: %s", file.file_name.c_str());
    INFO("  文件大小: %llu bytes (%.2f MB)", file.file_size, file.file_size / (1024.0 * 1024.0));
    INFO("  创建时间: %ld", file.create_time);
    INFO("  文件类型: %d", static_cast<int>(file.file_type));
    
    // 检查文件是否已存在于数据库中
    if (media_db_->FileExists(file.file_path)) {
        INFO("文件已存在于数据库中，跳过: %s", file.file_name.c_str());
        return edge_sdk::ErrorCode::kOk;
    }
    
    // 在数据库中记录新文件
    if (!media_db_->InsertMediaFile(file.file_path, file.file_name, file.file_size)) {
        ERROR("数据库插入失败: %s - %s", file.file_name.c_str(), media_db_->GetLastError().c_str());
        return edge_sdk::ErrorCode::kErrorSystemError;
    }
    
    // 更新状态为正在下载
    UpdateDatabaseStatus(file.file_path, FileStatus::DOWNLOADING);
    
    // 生成任务ID
    std::string task_id = GenerateTaskId(file.file_path);
    
    // 创建SDK文件读取任务（异步执行）
    CreateSDKReaderTask(file, task_id);
    
    total_files_processed_.fetch_add(1);
    INFO("✓ 媒体文件传输任务已创建: %s (任务ID: %s)", file.file_name.c_str(), task_id.c_str());
    
    return edge_sdk::ErrorCode::kOk;
}

void MediaTransferAdapter::SetTransferCompletionCallback(
    std::function<void(const std::string&, bool)> callback) {
    completion_callback_ = callback;
}

std::string MediaTransferAdapter::GetTransferStatistics() const {
    std::stringstream ss;
    ss << "传输统计信息:\n";
    ss << "  处理文件总数: " << total_files_processed_.load() << "\n";
    ss << "  成功传输: " << successful_transfers_.load() << "\n";
    ss << "  失败传输: " << failed_transfers_.load() << "\n";
    ss << "  活跃传输: " << GetActiveTransferCount() << "\n";
    ss << "  总传输字节: " << std::fixed << std::setprecision(2) 
       << (total_bytes_transferred_.load() / (1024.0 * 1024.0)) << " MB";
    return ss.str();
}

size_t MediaTransferAdapter::GetActiveTransferCount() const {
    if (!chunk_manager_) {
        return 0;
    }
    return chunk_manager_->GetActiveTransfers().size();
}

bool MediaTransferAdapter::HasActiveTransfers() const {
    return GetActiveTransferCount() > 0;
}

std::string MediaTransferAdapter::GenerateTaskId(const std::string& file_path) {
    // 使用文件路径的哈希值作为任务ID的一部分
    auto hash = hash_calculator_->CalculateDataMD5(file_path.c_str(), file_path.length());
    auto timestamp = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    
    std::stringstream ss;
    ss << "media_" << hash.substr(0, 8) << "_" << timestamp;
    return ss.str();
}

void MediaTransferAdapter::CreateSDKReaderTask(const edge_sdk::MediaFile& file, 
                                              const std::string& task_id) {
    // 生成临时文件路径
    std::string temp_dir = "/tmp/celestial_media_transfer/";
    file_utils_->CreateDirectories(temp_dir);
    
    std::string temp_file_path = temp_dir + task_id + "_" + file.file_name;
    
    // 记录任务映射
    {
        std::lock_guard<std::mutex> lock(task_map_mutex_);
        task_to_filepath_[task_id] = file.file_path;
        task_to_tempfile_[task_id] = temp_file_path;
    }
    
    // 启动异步SDK读取线程
    std::thread reader_thread(&MediaTransferAdapter::SDKReaderThread, this, 
                             file, task_id, temp_file_path);
    reader_thread.detach();
}

void MediaTransferAdapter::SDKReaderThread(const edge_sdk::MediaFile& file,
                                          const std::string& task_id,
                                          const std::string& temp_file_path) {
    try {
        INFO("开始SDK文件读取: %s -> %s", file.file_name.c_str(), temp_file_path.c_str());
        
        // 获取MediaManager和创建读取器
        auto media_manager = edge_sdk::MediaManager::Instance();
        if (!media_manager) {
            ERROR("获取MediaManager实例失败");
            UpdateDatabaseStatus(file.file_path, FileStatus::FAILED, "获取MediaManager失败");
            CleanupTempFile(task_id);
            return;
        }
        
        auto reader = media_manager->CreateMediaFilesReader();
        if (!reader || reader->Init() != edge_sdk::ErrorCode::kOk) {
            ERROR("创建媒体文件读取器失败: %s", file.file_name.c_str());
            UpdateDatabaseStatus(file.file_path, FileStatus::FAILED, "创建文件读取器失败");
            CleanupTempFile(task_id);
            return;
        }
        
        // 打开远程文件
        auto fd = reader->Open(file.file_path);
        if (fd < 0) {
            ERROR("打开远程文件失败: %s", file.file_path.c_str());
            UpdateDatabaseStatus(file.file_path, FileStatus::FAILED, "打开远程文件失败");
            reader->DeInit();
            CleanupTempFile(task_id);
            return;
        }
        
        // 创建临时文件
        std::ofstream temp_file(temp_file_path, std::ios::binary);
        if (!temp_file.is_open()) {
            ERROR("创建临时文件失败: %s", temp_file_path.c_str());
            UpdateDatabaseStatus(file.file_path, FileStatus::FAILED, "创建临时文件失败");
            reader->Close(fd);
            reader->DeInit();
            CleanupTempFile(task_id);
            return;
        }
        
        // 分块读取并写入临时文件
        char buffer[64 * 1024]; // 64KB缓冲区
        size_t total_read = 0;
        
        while (true) {
            if (shutdown_flag_.load()) {
                INFO("收到关闭信号，停止文件读取: %s", file.file_name.c_str());
                break;
            }
            
            auto nread = reader->Read(fd, buffer, sizeof(buffer));
            if (nread <= 0) {
                break; // 读取完成或出错
            }
            
            temp_file.write(buffer, nread);
            total_read += nread;
            
            // 定期报告进度
            if (total_read % (1024 * 1024) == 0) { // 每1MB报告一次
                double progress = (double)total_read / file.file_size * 100.0;
                INFO("SDK读取进度: %s - %.1f%% (%zu/%llu bytes)", 
                     file.file_name.c_str(), progress, total_read, file.file_size);
            }
        }
        
        temp_file.close();
        reader->Close(fd);
        reader->DeInit();
        
        // 验证文件大小
        if (total_read != file.file_size) {
            ERROR("文件大小不匹配: 期望 %llu, 实际 %zu", file.file_size, total_read);
            UpdateDatabaseStatus(file.file_path, FileStatus::FAILED, "文件大小不匹配");
            CleanupTempFile(task_id);
            return;
        }
        
        INFO("✓ SDK文件读取完成: %s (%zu bytes)", file.file_name.c_str(), total_read);
        
        // 获取最终目标路径
        ConfigManager& config_manager = ConfigManager::getInstance();
        std::string final_path = config_manager.getMediaPath() + file.file_name;
        
        // 启动分块传输（从临时文件到最终位置）
        bool transfer_started = chunk_manager_->StartTransfer(
            task_id,
            temp_file_path,
            final_path,
            std::bind(&MediaTransferAdapter::OnTransferProgress, this, 
                     std::placeholders::_1, std::placeholders::_2, 
                     std::placeholders::_3, std::placeholders::_4),
            std::bind(&MediaTransferAdapter::OnTransferCompletion, this,
                     std::placeholders::_1, std::placeholders::_2, std::placeholders::_3)
        );
        
        if (!transfer_started) {
            ERROR("启动分块传输失败: %s", task_id.c_str());
            UpdateDatabaseStatus(file.file_path, FileStatus::FAILED, "启动分块传输失败");
            CleanupTempFile(task_id);
            return;
        }
        
        INFO("✓ 分块传输已启动: %s -> %s", temp_file_path.c_str(), final_path.c_str());
        
    } catch (const std::exception& e) {
        ERROR("SDK读取线程异常: %s - %s", file.file_name.c_str(), e.what());
        UpdateDatabaseStatus(file.file_path, FileStatus::FAILED, std::string("SDK读取异常: ") + e.what());
        CleanupTempFile(task_id);
    }
}

void MediaTransferAdapter::OnTransferProgress(const std::string& task_id,
                                             size_t transferred_bytes,
                                             size_t total_bytes,
                                             double progress_percent) {
    // 更新总传输字节数
    total_bytes_transferred_.store(transferred_bytes);
    
    // 定期输出进度日志（避免日志过多）
    static std::unordered_map<std::string, double> last_reported_progress;
    double last_progress = last_reported_progress[task_id];
    
    if (progress_percent - last_progress >= 10.0) { // 每10%报告一次
        INFO("传输进度: %s - %.1f%% (%zu/%zu bytes)", 
             task_id.c_str(), progress_percent, transferred_bytes, total_bytes);
        last_reported_progress[task_id] = progress_percent;
    }
}

void MediaTransferAdapter::OnTransferCompletion(const std::string& task_id,
                                               bool success,
                                               const std::string& error_message) {
    std::string file_path;
    
    // 获取文件路径
    {
        std::lock_guard<std::mutex> lock(task_map_mutex_);
        auto it = task_to_filepath_.find(task_id);
        if (it != task_to_filepath_.end()) {
            file_path = it->second;
        }
    }
    
    if (success) {
        INFO("✓ 传输完成: %s", task_id.c_str());
        UpdateDatabaseStatus(file_path, FileStatus::COMPLETED);
        successful_transfers_.fetch_add(1);
    } else {
        ERROR("✗ 传输失败: %s - %s", task_id.c_str(), error_message.c_str());
        UpdateDatabaseStatus(file_path, FileStatus::FAILED, error_message);
        failed_transfers_.fetch_add(1);
    }
    
    // 清理临时文件
    CleanupTempFile(task_id);
    
    // 调用外部完成回调
    if (completion_callback_) {
        completion_callback_(file_path, success);
    }
    
    // 清理任务映射
    {
        std::lock_guard<std::mutex> lock(task_map_mutex_);
        task_to_filepath_.erase(task_id);
        task_to_tempfile_.erase(task_id);
    }
}

void MediaTransferAdapter::CleanupTempFile(const std::string& task_id) {
    std::string temp_file_path;
    
    {
        std::lock_guard<std::mutex> lock(task_map_mutex_);
        auto it = task_to_tempfile_.find(task_id);
        if (it != task_to_tempfile_.end()) {
            temp_file_path = it->second;
        }
    }
    
    if (!temp_file_path.empty() && fs::exists(temp_file_path)) {
        try {
            fs::remove(temp_file_path);
            INFO("临时文件已清理: %s", temp_file_path.c_str());
        } catch (const std::exception& e) {
            WARN("清理临时文件失败: %s - %s", temp_file_path.c_str(), e.what());
        }
    }
}

void MediaTransferAdapter::UpdateDatabaseStatus(const std::string& file_path,
                                               FileStatus status,
                                               const std::string& error_message) {
    if (!media_db_) {
        return;
    }
    
    if (!media_db_->UpdateDownloadStatus(file_path, status, error_message)) {
        ERROR("更新数据库状态失败: %s - %s", file_path.c_str(), media_db_->GetLastError().c_str());
    }
}

} // namespace celestial