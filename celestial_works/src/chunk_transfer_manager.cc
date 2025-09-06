#include "chunk_transfer_manager.h"
#include <iostream>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <algorithm>
#if __cplusplus >= 201703L
#include <filesystem>
namespace fs = std::filesystem;
#else
#include <experimental/filesystem>
namespace fs = std::experimental::filesystem;
#endif
#include <openssl/md5.h>
#include <chrono>
#include <thread>

ChunkTransferManager::ChunkTransferManager() 
    : db_manager_(nullptr), config_manager_(nullptr),
      shutdown_flag_(false), initialized_(false),
      chunk_size_(1024 * 1024), // 默认1MB
      max_concurrent_transfers_(3),
      max_retries_(3),
      worker_thread_count_(4),
      timeout_seconds_(300), // 5分钟超时
      active_transfers_(0),
      total_transfers_(0),
      completed_transfers_(0),
      failed_transfers_(0),
      heartbeat_running_(false),
      start_time_(std::chrono::system_clock::now()),
      last_heartbeat_(0),
      zombie_tasks_cleaned_(0),
      total_bytes_transferred_(0) {
}

ChunkTransferManager::~ChunkTransferManager() {
    Shutdown();
}

bool ChunkTransferManager::Initialize() {
    if (initialized_) {
        return true;
    }
    
    std::cout << "初始化分块传输管理器..." << std::endl;
    
    // 初始化数据库管理器
    db_manager_ = std::make_unique<TransferStatusDB>();
    if (!db_manager_->Initialize("")) {  // 使用空字符串，让数据库管理器从配置读取路径
        std::cerr << "数据库管理器初始化失败" << std::endl;
        return false;
    }
    
    // 加载配置
    if (!LoadConfiguration()) {
        std::cerr << "配置加载失败" << std::endl;
        return false;
    }
    
    // 恢复未完成的任务
    if (!RecoverUnfinishedTasks()) {
        std::cerr << "恢复未完成任务失败" << std::endl;
        // 不返回false，允许继续运行
    }
    
    // 启动工作线程
    shutdown_flag_ = false;
    for (int i = 0; i < worker_thread_count_; ++i) {
        worker_threads_.emplace_back(&ChunkTransferManager::WorkerThread, this);
    }
    
    // 启动心跳监控
    StartHeartbeatMonitor();
    
    initialized_ = true;
    std::cout << "分块传输管理器初始化成功" << std::endl;
    return true;
}

void ChunkTransferManager::Shutdown() {
    if (!initialized_) {
        return;
    }
    
    std::cout << "关闭分块传输管理器..." << std::endl;
    
    // 停止心跳监控
    StopHeartbeatMonitor();
    
    // 设置关闭标志
    shutdown_flag_ = true;
    
    // 通知所有工作线程
    queue_cv_.notify_all();
    
    // 等待工作线程结束
    for (auto& thread : worker_threads_) {
        if (thread.joinable()) {
            thread.join();
        }
    }
    worker_threads_.clear();
    
    // 清理资源
    {
        std::lock_guard<std::mutex> lock(tasks_mutex_);
        transfer_tasks_.clear();
    }
    
    {
        std::lock_guard<std::mutex> lock(queue_mutex_);
        while (!task_queue_.empty()) {
            task_queue_.pop();
        }
    }
    
    initialized_ = false;
    std::cout << "分块传输管理器已关闭" << std::endl;
}

bool ChunkTransferManager::LoadConfiguration() {
    config_manager_ = &ConfigManager::getInstance();
    if (!config_manager_->loadConfig()) {
        std::cerr << "配置文件加载失败" << std::endl;
        return false;
    }
    
    const auto& config = config_manager_->getDockTransferConfig();
    
    // 更新配置参数
    chunk_size_ = config.chunk_size_mb * 1024 * 1024;
    max_concurrent_transfers_ = config.max_concurrent_transfers;
    worker_thread_count_ = 4;  // 使用默认值，配置中暂未定义
    timeout_seconds_ = 300;    // 使用默认值，配置中暂未定义
    max_retries_ = config.retry_attempts;
    
    std::cout << "配置加载完成:" << std::endl;
    std::cout << "  分块大小: " << chunk_size_ / (1024 * 1024) << "MB" << std::endl;
    std::cout << "  最大并发数: " << max_concurrent_transfers_ << std::endl;
    std::cout << "  工作线程数: " << worker_thread_count_ << std::endl;
    std::cout << "  传输超时: " << timeout_seconds_ << "秒" << std::endl;
    std::cout << "  最大重试次数: " << max_retries_ << std::endl;
    
    return true;
}

bool ChunkTransferManager::StartTransfer(const std::string& task_id,
                                       const std::string& source_path,
                                       const std::string& dest_path,
                                       ProgressCallback progress_cb,
                                       CompletionCallback completion_cb) {
    if (!initialized_) {
        std::cerr << "管理器未初始化" << std::endl;
        return false;
    }
    
    // 检查源文件是否存在
    if (!fs::exists(source_path)) {
        std::cerr << "源文件不存在: " << source_path << std::endl;
        return false;
    }
    
    // 检查是否已存在相同任务
    {
        std::lock_guard<std::mutex> lock(tasks_mutex_);
        auto it = transfer_tasks_.find(task_id);
        if (it != transfer_tasks_.end()) {
            // 如果任务已存在且处于暂停状态，则直接恢复：设置回调并重新入队
            if (it->second->status == TransferStatus::PAUSED) {
                it->second->progress_callback = progress_cb;
                it->second->completion_callback = completion_cb;
                {
                    std::lock_guard<std::mutex> qlock(queue_mutex_);
                    task_queue_.push(task_id);
                }
                queue_cv_.notify_one();
                std::cout << "恢复暂停任务: " << task_id << std::endl;
                total_transfers_++;
                return true;
            }
            std::cerr << "任务已存在: " << task_id << std::endl;
            return false;
        }
    }
    
    // 创建传输任务
    if (!CreateTransferTask(task_id, source_path, dest_path)) {
        std::cerr << "创建传输任务失败: " << task_id << std::endl;
        return false;
    }
    
    // 设置回调函数
    {
        std::lock_guard<std::mutex> lock(tasks_mutex_);
        auto it = transfer_tasks_.find(task_id);
        if (it != transfer_tasks_.end()) {
            it->second->progress_callback = progress_cb;
            it->second->completion_callback = completion_cb;
        }
    }
    
    // 添加到任务队列
    {
        std::lock_guard<std::mutex> lock(queue_mutex_);
        task_queue_.push(task_id);
    }
    queue_cv_.notify_one();
    
    total_transfers_++;
    std::cout << "传输任务已启动: " << task_id << std::endl;
    return true;
}

bool ChunkTransferManager::CreateTransferTask(const std::string& task_id,
                                            const std::string& source_path,
                                            const std::string& dest_path) {
    try {
        // 获取文件信息
        auto file_size = fs::file_size(source_path);
        auto file_name = fs::path(source_path).filename().string();
        
        // 在数据库中创建任务记录
        int db_task_id = db_manager_->CreateTransferTask(source_path, file_name, file_size, chunk_size_);
        if (db_task_id <= 0) {
            std::cerr << "数据库创建任务失败" << std::endl;
            return false;
        }
        
        // 创建内存中的任务对象
        auto task = std::make_unique<TransferTaskInfo>();
        task->task_id = task_id;
        task->db_task_id = db_task_id;  // 设置数据库任务ID
        task->source_path = source_path;
        task->dest_path = dest_path;
        task->file_size = file_size;
        task->status = TransferStatus::PENDING;
        task->transferred_bytes = 0;
        
        // 分析文件并创建分块
        if (!AnalyzeFileAndCreateChunks(*task)) {
            std::cerr << "文件分析和分块创建失败" << std::endl;
            return false;
        }
        
        // 计算文件校验和
        task->file_checksum = CalculateFileChecksum(source_path);
        
        // 注意：数据库中的分块记录已经在CreateTransferTask中创建了
        // 这里不需要重复创建
        
        // 添加到任务映射表
        {
            std::lock_guard<std::mutex> lock(tasks_mutex_);
            transfer_tasks_[task_id] = std::move(task);
        }
        
        return true;
    } catch (const std::exception& e) {
        std::cerr << "创建传输任务异常: " << e.what() << std::endl;
        return false;
    }
}

bool ChunkTransferManager::AnalyzeFileAndCreateChunks(TransferTaskInfo& task) {
    size_t file_size = task.file_size;
    size_t current_offset = 0;
    int chunk_index = 0;
    
    task.chunks.clear();
    
    while (current_offset < file_size) {
        ExtendedChunkInfo chunk;
        chunk.chunk_id = chunk_index;
        chunk.task_id = 0; // 将在数据库创建时设置
        chunk.chunk_index = chunk_index;
        chunk.offset = current_offset;
        chunk.chunk_size = std::min(chunk_size_, file_size - current_offset);
        chunk.actual_size = chunk.chunk_size;
        chunk.status = ChunkStatus::PENDING;
        chunk.retry_count = 0;
        
        // 计算分块校验和
        chunk.md5_hash = CalculateChunkChecksum(task.source_path, current_offset, chunk.chunk_size);
        
        task.chunks.push_back(chunk);
        
        current_offset += chunk.chunk_size;
        chunk_index++;
    }
    
    std::cout << "文件分析完成: " << task.source_path << std::endl;
    std::cout << "  文件大小: " << file_size << " 字节" << std::endl;
    std::cout << "  分块数量: " << task.chunks.size() << std::endl;
    std::cout << "  分块大小: " << chunk_size_ / (1024 * 1024) << "MB" << std::endl;
    
    return true;
}

std::string ChunkTransferManager::CalculateFileChecksum(const std::string& file_path) {
    std::ifstream file(file_path, std::ios::binary);
    if (!file.is_open()) {
        std::cerr << "无法打开文件计算校验和: " << file_path << std::endl;
        return "";
    }
    
    MD5_CTX md5_ctx;
    MD5_Init(&md5_ctx);
    
    char buffer[8192];
    while (file.read(buffer, sizeof(buffer)) || file.gcount() > 0) {
        MD5_Update(&md5_ctx, buffer, file.gcount());
    }
    
    unsigned char digest[MD5_DIGEST_LENGTH];
    MD5_Final(digest, &md5_ctx);
    
    std::stringstream ss;
    for (int i = 0; i < MD5_DIGEST_LENGTH; ++i) {
        ss << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(digest[i]);
    }
    
    return ss.str();
}

std::string ChunkTransferManager::CalculateChunkChecksum(const std::string& file_path, 
                                                       size_t offset, size_t size) {
    std::ifstream file(file_path, std::ios::binary);
    if (!file.is_open()) {
        std::cerr << "无法打开文件计算分块校验和: " << file_path << std::endl;
        return "";
    }
    
    file.seekg(offset);
    if (file.fail()) {
        std::cerr << "文件定位失败: offset=" << offset << std::endl;
        return "";
    }
    
    MD5_CTX md5_ctx;
    MD5_Init(&md5_ctx);
    
    char buffer[8192];
    size_t remaining = size;
    
    while (remaining > 0 && file.good()) {
        size_t to_read = std::min(remaining, sizeof(buffer));
        file.read(buffer, to_read);
        size_t actually_read = file.gcount();
        
        if (actually_read > 0) {
            MD5_Update(&md5_ctx, buffer, actually_read);
            remaining -= actually_read;
        } else {
            break;
        }
    }
    
    unsigned char digest[MD5_DIGEST_LENGTH];
    MD5_Final(digest, &md5_ctx);
    
    std::stringstream ss;
    for (int i = 0; i < MD5_DIGEST_LENGTH; ++i) {
        ss << std::hex << std::setw(2) << std::setfill('0') << static_cast<int>(digest[i]);
    }
    
    return ss.str();
}

void ChunkTransferManager::WorkerThread() {
    std::cout << "工作线程启动: " << std::this_thread::get_id() << std::endl;
    
    while (!shutdown_flag_) {
        std::string task_id;
        
        // 从队列获取任务
        {
            std::unique_lock<std::mutex> lock(queue_mutex_);
            queue_cv_.wait(lock, [this] { return !task_queue_.empty() || shutdown_flag_; });
            
            if (shutdown_flag_) {
                break;
            }
            
            if (!task_queue_.empty()) {
                task_id = task_queue_.front();
                task_queue_.pop();
            }
        }
        
        if (!task_id.empty()) {
            ProcessTransferTask(task_id);
        }
    }
    
    std::cout << "工作线程退出: " << std::this_thread::get_id() << std::endl;
}

void ChunkTransferManager::ProcessTransferTask(const std::string& task_id) {
    std::cout << "开始处理传输任务: " << task_id << std::endl;
    
    TransferTaskInfo* task = nullptr;
    {
        std::lock_guard<std::mutex> lock(tasks_mutex_);
        auto it = transfer_tasks_.find(task_id);
        if (it == transfer_tasks_.end()) {
            std::cerr << "任务不存在: " << task_id << std::endl;
            return;
        }
        task = it->second.get();
    }
    
    if (!task) {
        std::cerr << "任务指针为空: " << task_id << std::endl;
        return;
    }
    
    active_transfers_++;
    UpdateTaskStatus(task_id, TransferStatus::DOWNLOADING);
    
    bool success = true;
    bool paused_requested = false;  // 标记是否收到暂停请求
    std::string error_message;
    
    try {
        // 创建目标目录
        fs::path dest_dir = fs::path(task->dest_path).parent_path();
        if (!fs::exists(dest_dir)) {
            fs::create_directories(dest_dir);
        }
        
        // 传输所有分块
        for (auto& chunk : task->chunks) {
            // 检查是否收到暂停请求
            {
                std::lock_guard<std::mutex> lock(tasks_mutex_);
                auto it = transfer_tasks_.find(task_id);
                if (it != transfer_tasks_.end() && it->second->status == TransferStatus::PAUSED) {
                    paused_requested = true;
                    success = false;  // 非完成态退出，但不视为失败，仅作为中断
                    break;
                }
            }
            
            if (shutdown_flag_) {
                error_message = "传输被中断";
                success = false;
                break;
            }
            
            if (chunk.status == ChunkStatus::COMPLETED) {
                continue; // 跳过已完成的分块
            }
            
            bool chunk_success = false;
            for (int retry = 0; retry <= max_retries_ && !chunk_success; ++retry) {
                if (retry > 0) {
                    std::cout << "重试分块传输: " << task_id << ", chunk " << chunk.chunk_index 
                             << ", 重试次数: " << retry << std::endl;
                    std::this_thread::sleep_for(std::chrono::seconds(1 << (retry - 1))); // 指数退避
                }
                
                chunk_success = TransferChunk(*task, chunk);
                if (chunk_success) {
                    chunk_success = VerifyChunk(*task, chunk);
                }
                
                if (!chunk_success) {
                    chunk.retry_count++;
                    UpdateChunkStatus(task_id, chunk.chunk_index, ChunkStatus::FAILED);
                }
            }
            
            if (!chunk_success) {
                error_message = "分块传输失败: chunk " + std::to_string(chunk.chunk_index);
                success = false;
                break;
            }
            
            // 更新进度
            task->transferred_bytes += chunk.actual_size;
            NotifyProgress(*task);
        }
        
        // 若用户请求了暂停，直接跳过后续合并与最终校验
        if (paused_requested) {
            std::cout << "任务被用户暂停，保持现场以便断点续传: " << task_id << std::endl;
        } else {
            // 如果所有分块传输成功，合并文件
            if (success) {
                success = MergeChunks(*task);
                if (!success) {
                    error_message = "分块合并失败";
                }
            }
            
            // 验证最终文件
            if (success) {
                success = VerifyFinalFile(*task);
                if (!success) {
                    error_message = "最终文件验证失败";
                }
            }
        }
        
    } catch (const std::exception& e) {
        success = false;
        error_message = "传输异常: " + std::string(e.what());
    }
    
    // 根据不同情形进行收尾
    if (paused_requested) {
        // 任务已处于 PAUSED 状态：不修改状态，不清理临时文件，也不触发完成回调
        active_transfers_--;
        std::cout << "传输任务已暂停: " << task_id << std::endl;
        return;
    }
    
    // 更新任务状态
    TransferStatus final_status = success ? TransferStatus::COMPLETED : TransferStatus::FAILED;
    UpdateTaskStatus(task_id, final_status);
    
    // 清理临时文件（仅在完成/失败时清理，暂停不清理）
    CleanupTempFiles(*task);
    
    // 通知完成
    NotifyCompletion(*task, success, error_message);
    
    active_transfers_--;
    if (success) {
        completed_transfers_++;
    } else {
        failed_transfers_++;
    }
    
    std::cout << "传输任务处理完成: " << task_id << ", 结果: " 
             << (success ? "成功" : "失败") << std::endl;
}

bool ChunkTransferManager::TransferChunk(TransferTaskInfo& task, ExtendedChunkInfo& chunk) {
    // 这里实现具体的分块传输逻辑
    // 由于这是一个框架实现，这里使用文件复制来模拟传输
    
    try {
        // 创建临时分块文件路径
        std::string temp_chunk_path = task.dest_path + ".chunk." + std::to_string(chunk.chunk_index);
        
        // 打开源文件
        std::ifstream src_file(task.source_path, std::ios::binary);
        if (!src_file.is_open()) {
            std::cerr << "无法打开源文件: " << task.source_path << std::endl;
            return false;
        }
        
        // 定位到分块起始位置
        src_file.seekg(chunk.offset);
        if (src_file.fail()) {
            std::cerr << "源文件定位失败: offset=" << chunk.offset << std::endl;
            return false;
        }
        
        // 创建临时分块文件
        std::ofstream dest_file(temp_chunk_path, std::ios::binary);
        if (!dest_file.is_open()) {
            std::cerr << "无法创建临时分块文件: " << temp_chunk_path << std::endl;
            return false;
        }
        
        // 复制分块数据
        char buffer[8192];
        size_t remaining = chunk.actual_size;
        
        while (remaining > 0 && src_file.good()) {
            size_t to_read = std::min(remaining, sizeof(buffer));
            src_file.read(buffer, to_read);
            size_t actually_read = src_file.gcount();
            
            if (actually_read > 0) {
                dest_file.write(buffer, actually_read);
                remaining -= actually_read;
            } else {
                break;
            }
        }
        
        dest_file.close();
        src_file.close();
        
        if (remaining > 0) {
            std::cerr << "分块传输不完整: " << remaining << " 字节未传输" << std::endl;
            fs::remove(temp_chunk_path);
            return false;
        }
        
        chunk.status = ChunkStatus::COMPLETED;
        chunk.last_update = std::chrono::system_clock::now();
        UpdateChunkStatus(task.task_id, chunk.chunk_index, ChunkStatus::COMPLETED);
        
        return true;
        
    } catch (const std::exception& e) {
        std::cerr << "分块传输异常: " << e.what() << std::endl;
        return false;
    }
}

bool ChunkTransferManager::VerifyChunk(const TransferTaskInfo& task, const ExtendedChunkInfo& chunk) {
    std::string temp_chunk_path = task.dest_path + ".chunk." + std::to_string(chunk.chunk_index);
    
    // 检查文件是否存在
    if (!fs::exists(temp_chunk_path)) {
        std::cerr << "临时分块文件不存在: " << temp_chunk_path << std::endl;
        return false;
    }
    
    // 检查文件大小
    auto file_size = fs::file_size(temp_chunk_path);
    if (file_size != chunk.actual_size) {
        std::cerr << "分块文件大小不匹配: 期望 " << chunk.actual_size 
                 << ", 实际 " << file_size << std::endl;
        return false;
    }
    
    // 计算并验证校验和
    std::string calculated_checksum = CalculateFileChecksum(temp_chunk_path);
    if (calculated_checksum != chunk.md5_hash) {
        std::cerr << "分块校验和不匹配: 期望 " << chunk.md5_hash 
                 << ", 实际 " << calculated_checksum << std::endl;
        return false;
    }
    
    return true;
}

bool ChunkTransferManager::MergeChunks(TransferTaskInfo& task) {
    std::cout << "开始合并分块文件: " << task.task_id << std::endl;
    
    try {
        // 创建最终文件
        std::ofstream final_file(task.dest_path, std::ios::binary);
        if (!final_file.is_open()) {
            std::cerr << "无法创建最终文件: " << task.dest_path << std::endl;
            return false;
        }
        
        // 按顺序合并所有分块
        for (const auto& chunk : task.chunks) {
            std::string temp_chunk_path = task.dest_path + ".chunk." + std::to_string(chunk.chunk_index);
            
            std::ifstream chunk_file(temp_chunk_path, std::ios::binary);
            if (!chunk_file.is_open()) {
                std::cerr << "无法打开分块文件: " << temp_chunk_path << std::endl;
                return false;
            }
            
            // 复制分块内容到最终文件
            final_file << chunk_file.rdbuf();
            chunk_file.close();
            
            if (final_file.fail()) {
                std::cerr << "分块合并失败: " << temp_chunk_path << std::endl;
                return false;
            }
        }
        
        final_file.close();
        std::cout << "分块合并完成: " << task.dest_path << std::endl;
        return true;
        
    } catch (const std::exception& e) {
        std::cerr << "分块合并异常: " << e.what() << std::endl;
        return false;
    }
}

bool ChunkTransferManager::VerifyFinalFile(const TransferTaskInfo& task) {
    std::cout << "验证最终文件: " << task.dest_path << std::endl;
    
    // 检查文件是否存在
    if (!fs::exists(task.dest_path)) {
        std::cerr << "最终文件不存在: " << task.dest_path << std::endl;
        return false;
    }
    
    // 检查文件大小
    auto file_size = fs::file_size(task.dest_path);
    if (file_size != task.file_size) {
        std::cerr << "最终文件大小不匹配: 期望 " << task.file_size 
                 << ", 实际 " << file_size << std::endl;
        return false;
    }
    
    // 计算并验证校验和
    std::string calculated_checksum = CalculateFileChecksum(task.dest_path);
    if (calculated_checksum != task.file_checksum) {
        std::cerr << "最终文件校验和不匹配: 期望 " << task.file_checksum 
                 << ", 实际 " << calculated_checksum << std::endl;
        return false;
    }
    
    std::cout << "最终文件验证成功" << std::endl;
    return true;
}

void ChunkTransferManager::CleanupTempFiles(const TransferTaskInfo& task) {
    std::cout << "清理临时文件: " << task.task_id << std::endl;
    
    for (const auto& chunk : task.chunks) {
        std::string temp_chunk_path = task.dest_path + ".chunk." + std::to_string(chunk.chunk_index);
        
        if (fs::exists(temp_chunk_path)) {
            try {
                fs::remove(temp_chunk_path);
            } catch (const std::exception& e) {
                std::cerr << "删除临时文件失败: " << temp_chunk_path 
                         << ", 错误: " << e.what() << std::endl;
            }
        }
    }
}

void ChunkTransferManager::UpdateTaskStatus(const std::string& task_id, TransferStatus status) {
    // 根据task_id找到对应的数据库task_id
    std::lock_guard<std::mutex> lock(tasks_mutex_);
    auto it = transfer_tasks_.find(task_id);
    if (it != transfer_tasks_.end()) {
        // 更新数据库状态
        if (it->second->db_task_id > 0) {
            db_manager_->UpdateTransferStatus(it->second->db_task_id, status);
            db_manager_->UpdateTransferHeartbeat(it->second->db_task_id);
        }
        
        // 更新内存中的状态
        it->second->status = status;
        it->second->last_update = std::chrono::system_clock::now();
    } else {
        std::cerr << "更新任务状态失败: 未找到任务 " << task_id << std::endl;
    }
}

void ChunkTransferManager::UpdateChunkStatus(const std::string& task_id, int chunk_id, ChunkStatus status) {
    std::lock_guard<std::mutex> lock(tasks_mutex_);
    auto it = transfer_tasks_.find(task_id);
    if (it != transfer_tasks_.end() && it->second->db_task_id > 0) {
        db_manager_->UpdateChunkStatus(it->second->db_task_id, chunk_id, status);
    } else {
        std::cerr << "更新分块状态失败: 未找到任务 " << task_id << std::endl;
    }
}

void ChunkTransferManager::NotifyProgress(const TransferTaskInfo& task) {
    if (task.progress_callback) {
        double progress = (task.file_size > 0) ? 
            (static_cast<double>(task.transferred_bytes) / task.file_size * 100.0) : 0.0;
        task.progress_callback(task.task_id, task.transferred_bytes, task.file_size, progress);
    }
}

void ChunkTransferManager::NotifyCompletion(const TransferTaskInfo& task, bool success, const std::string& error) {
    if (task.completion_callback) {
        task.completion_callback(task.task_id, success, error);
    }
}

bool ChunkTransferManager::RecoverUnfinishedTasks() {
    std::cout << "恢复未完成的传输任务..." << std::endl;
    
    try {
        auto incomplete_tasks = db_manager_->GetIncompleteTransfers();
        
        for (const auto& db_task : incomplete_tasks) {
            std::cout << "发现未完成任务: " << db_task.file_name 
                     << ", 状态: " << static_cast<int>(db_task.status) << std::endl;
            
            // 这里可以实现任务恢复逻辑
            // 暂时跳过，等待用户手动重启
        }
        
        std::cout << "任务恢复检查完成，发现 " << incomplete_tasks.size() << " 个未完成任务" << std::endl;
        return true;
        
    } catch (const std::exception& e) {
        std::cerr << "任务恢复失败: " << e.what() << std::endl;
        return false;
    }
}

// 其他接口方法的简单实现
bool ChunkTransferManager::PauseTransfer(const std::string& task_id) {
    // 先检查任务是否存在（短暂加锁），避免在持锁状态下调用 UpdateTaskStatus 造成死锁
    {
        std::lock_guard<std::mutex> lock(tasks_mutex_);
        if (transfer_tasks_.find(task_id) == transfer_tasks_.end()) {
            return false;
        }
    }
    // 释放锁后再更新状态
    UpdateTaskStatus(task_id, TransferStatus::PAUSED);
    return true;
}

bool ChunkTransferManager::ResumeTransfer(const std::string& task_id) {
    // 先检查任务是否存在（短暂加锁）
    {
        std::lock_guard<std::mutex> lock(tasks_mutex_);
        if (transfer_tasks_.find(task_id) == transfer_tasks_.end()) {
            return false;
        }
    }
    // 更新状态为进行中
    UpdateTaskStatus(task_id, TransferStatus::DOWNLOADING);
    // 重新加入队列
    {
        std::lock_guard<std::mutex> queue_lock(queue_mutex_);
        task_queue_.push(task_id);
    }
    queue_cv_.notify_one();
    return true;
}

bool ChunkTransferManager::CancelTransfer(const std::string& task_id) {
    // 为支持断点续传，取消操作视为“请求暂停”
    {
        std::lock_guard<std::mutex> lock(tasks_mutex_);
        if (transfer_tasks_.find(task_id) == transfer_tasks_.end()) {
            return false;
        }
    }
    // 释放锁后更新为暂停，避免死锁
    UpdateTaskStatus(task_id, TransferStatus::PAUSED);
    return true;
}

double ChunkTransferManager::GetTransferProgress(const std::string& task_id) {
    std::lock_guard<std::mutex> lock(tasks_mutex_);
    auto it = transfer_tasks_.find(task_id);
    if (it != transfer_tasks_.end()) {
        const auto& task = *it->second;
        return (task.file_size > 0) ? 
            (static_cast<double>(task.transferred_bytes) / task.file_size * 100.0) : 0.0;
    }
    return 0.0;
}

TransferStatus ChunkTransferManager::GetTransferStatus(const std::string& task_id) {
    std::lock_guard<std::mutex> lock(tasks_mutex_);
    auto it = transfer_tasks_.find(task_id);
    if (it != transfer_tasks_.end()) {
        return it->second->status;
    }
    return TransferStatus::FAILED;
}

std::vector<std::string> ChunkTransferManager::GetActiveTransfers() {
    std::vector<std::string> active_tasks;
    std::lock_guard<std::mutex> lock(tasks_mutex_);
    
    for (const auto& pair : transfer_tasks_) {
        if (pair.second->status == TransferStatus::DOWNLOADING || 
            pair.second->status == TransferStatus::PENDING) {
            active_tasks.push_back(pair.first);
        }
    }
    
    return active_tasks;
}

bool ChunkTransferManager::GetTransferInfo(const std::string& task_id, TransferTaskInfo& info) {
    std::lock_guard<std::mutex> lock(tasks_mutex_);
    auto it = transfer_tasks_.find(task_id);
    if (it != transfer_tasks_.end()) {
        info = *it->second;
        return true;
    }
    return false;
}

void ChunkTransferManager::SetMaxConcurrentTransfers(int max_concurrent) {
    max_concurrent_transfers_ = max_concurrent;
}

void ChunkTransferManager::SetChunkSize(size_t chunk_size) {
    chunk_size_ = chunk_size;
}

void ChunkTransferManager::SetMaxRetries(int max_retries) {
    max_retries_ = max_retries;
}

// 占位符实现，后续可以扩展
bool ChunkTransferManager::CanResumeTask(const std::string& task_id) {
    return true;
}

bool ChunkTransferManager::GetNextPendingChunk(TransferTaskInfo& task, ExtendedChunkInfo*& chunk) {
    for (auto& c : task.chunks) {
        if (c.status == ChunkStatus::PENDING || c.status == ChunkStatus::FAILED) {
            chunk = &c;
            return true;
        }
    }
    return false;
}

void ChunkTransferManager::CheckTimeoutTasks() {
    // 实现超时任务检查逻辑
}

void ChunkTransferManager::CheckFailedRetries() {
    // TODO: 实现失败重试检查逻辑
}

// ==================== 监控和运维功能实现 ====================

std::string ChunkTransferManager::GetHealthReport() const {
    std::lock_guard<std::mutex> lock(health_mutex_);
    return GenerateHealthJson();
}

std::string ChunkTransferManager::GetTransferStatistics() const {
    std::lock_guard<std::mutex> lock(health_mutex_);
    return GenerateStatisticsJson();
}

int ChunkTransferManager::CleanupZombieTasks() {
    auto zombie_tasks = DetectZombieTasks();
    int cleaned_count = 0;
    
    for (const auto& task_id : zombie_tasks) {
        std::cout << "清理僵尸任务: " << task_id << std::endl;
        
        // 取消僵尸任务
        if (CancelTransfer(task_id)) {
            cleaned_count++;
        }
    }
    
    zombie_tasks_cleaned_ += cleaned_count;
    return cleaned_count;
}

void ChunkTransferManager::StartHeartbeatMonitor() {
    if (heartbeat_running_) {
        return;
    }
    
    heartbeat_running_ = true;
    heartbeat_thread_ = std::thread(&ChunkTransferManager::HeartbeatMonitorThread, this);
    std::cout << "心跳监控已启动" << std::endl;
}

void ChunkTransferManager::StopHeartbeatMonitor() {
    if (!heartbeat_running_) {
        return;
    }
    
    heartbeat_running_ = false;
    if (heartbeat_thread_.joinable()) {
        heartbeat_thread_.join();
    }
    std::cout << "心跳监控已停止" << std::endl;
}

int64_t ChunkTransferManager::GetUptimeSeconds() const {
    auto now = std::chrono::system_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::seconds>(now - start_time_);
    return duration.count();
}

void ChunkTransferManager::HeartbeatMonitorThread() {
    const int heartbeat_interval_seconds = 30; // 30秒心跳间隔
    const int cleanup_interval_minutes = 10;   // 10分钟清理间隔
    
    auto last_cleanup = std::chrono::system_clock::now();
    
    while (heartbeat_running_) {
        // 更新心跳时间戳
        auto now = std::chrono::system_clock::now();
        last_heartbeat_ = std::chrono::duration_cast<std::chrono::seconds>(
            now.time_since_epoch()).count();
        
        // 定期清理僵尸任务
        auto time_since_cleanup = std::chrono::duration_cast<std::chrono::minutes>(
            now - last_cleanup);
        if (time_since_cleanup.count() >= cleanup_interval_minutes) {
            CleanupZombieTasks();
            last_cleanup = now;
        }
        
        // 检查超时任务
        CheckTimeoutTasks();
        
        // 检查失败重试
        CheckFailedRetries();
        
        // 等待下一个心跳间隔
        std::this_thread::sleep_for(std::chrono::seconds(heartbeat_interval_seconds));
    }
}

std::vector<std::string> ChunkTransferManager::DetectZombieTasks(int zombie_timeout_minutes) {
    std::vector<std::string> zombie_tasks;
    auto now = std::chrono::system_clock::now();
    auto timeout_duration = std::chrono::minutes(zombie_timeout_minutes);
    
    std::lock_guard<std::mutex> lock(tasks_mutex_);
    
    for (const auto& task_pair : transfer_tasks_) {
        const std::string& task_id = task_pair.first;
        const auto& task_info_ptr = task_pair.second;
        if (!task_info_ptr) continue;
        
        const auto& task_info = *task_info_ptr;
        // 检查任务是否长时间无响应
        auto task_duration = now - task_info.start_time;
        
        if (task_duration > timeout_duration && 
            task_info.status == TransferStatus::DOWNLOADING) {
            
            // 检查是否有活跃的分块传输
            bool has_active_chunks = false;
            for (const auto& chunk : task_info.chunks) {
                if (chunk.status == ChunkStatus::DOWNLOADING) {
                    auto chunk_duration = now - chunk.last_update;
                    if (chunk_duration < std::chrono::minutes(5)) { // 5分钟内有活动
                        has_active_chunks = true;
                        break;
                    }
                }
            }
            
            if (!has_active_chunks) {
                zombie_tasks.push_back(task_id);
            }
        }
    }
    
    return zombie_tasks;
}

std::string ChunkTransferManager::GenerateHealthJson() const {
    std::ostringstream json;
    json << "{";
    json << "\"system_status\":\"" << (initialized_ ? "running" : "stopped") << "\",";
    json << "\"uptime_seconds\":" << GetUptimeSeconds() << ",";
    json << "\"last_heartbeat\":" << last_heartbeat_.load() << ",";
    json << "\"active_transfers\":" << active_transfers_.load() << ",";
    json << "\"worker_threads\":" << worker_threads_.size() << ",";
    json << "\"heartbeat_running\":" << (heartbeat_running_ ? "true" : "false") << ",";
    json << "\"zombie_tasks_cleaned\":" << zombie_tasks_cleaned_.load() << ",";
    json << "\"memory_usage\":{";
    json << "\"active_tasks\":" << transfer_tasks_.size() << ",";
    json << "\"queue_size\":" << task_queue_.size();
    json << "}";
    json << "}";
    return json.str();
}

std::string ChunkTransferManager::GenerateStatisticsJson() const {
    std::ostringstream json;
    json << "{";
    json << "\"total_transfers\":" << total_transfers_.load() << ",";
    json << "\"completed_transfers\":" << completed_transfers_.load() << ",";
    json << "\"failed_transfers\":" << failed_transfers_.load() << ",";
    json << "\"active_transfers\":" << active_transfers_.load() << ",";
    json << "\"total_bytes_transferred\":" << total_bytes_transferred_.load() << ",";
    json << "\"success_rate\":";
    
    size_t total = total_transfers_.load();
    if (total > 0) {
        double success_rate = (double)completed_transfers_.load() / total * 100.0;
        json << std::fixed << std::setprecision(2) << success_rate;
    } else {
        json << "0.00";
    }
    
    json << ",";
    json << "\"configuration\":{";
    json << "\"chunk_size\":" << chunk_size_ << ",";
    json << "\"max_concurrent_transfers\":" << max_concurrent_transfers_ << ",";
    json << "\"max_retries\":" << max_retries_ << ",";
    json << "\"timeout_seconds\":" << timeout_seconds_;
    json << "}";
    json << "}";
    return json.str();
}