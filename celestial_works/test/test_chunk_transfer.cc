#include <iostream>
#include <fstream>
#include <filesystem>
#include <chrono>
#include <thread>
#include "../src/chunk_transfer_manager.h"

namespace fs = std::filesystem;

// 测试用的回调函数
void progressCallback(const std::string& task_id, size_t transferred, size_t total, double percentage) {
    std::cout << "[进度] 任务 " << task_id << ": " << transferred << "/" << total 
              << " (" << std::fixed << std::setprecision(2) << percentage << "%)" << std::endl;
}

void completionCallback(const std::string& task_id, bool success, const std::string& error) {
    std::cout << "[完成] 任务 " << task_id << ": " 
              << (success ? "成功" : "失败") << std::endl;
    if (!success && !error.empty()) {
        std::cout << "  错误信息: " << error << std::endl;
    }
}

// 创建测试文件
bool createTestFile(const std::string& path, size_t size_mb) {
    std::cout << "创建测试文件: " << path << " (" << size_mb << "MB)" << std::endl;
    
    std::ofstream file(path, std::ios::binary);
    if (!file.is_open()) {
        std::cerr << "无法创建测试文件: " << path << std::endl;
        return false;
    }
    
    // 写入随机数据
    const size_t buffer_size = 1024 * 1024; // 1MB buffer
    std::vector<char> buffer(buffer_size);
    
    // 填充随机数据
    for (size_t i = 0; i < buffer_size; ++i) {
        buffer[i] = static_cast<char>(rand() % 256);
    }
    
    for (size_t i = 0; i < size_mb; ++i) {
        file.write(buffer.data(), buffer_size);
        if (file.fail()) {
            std::cerr << "写入测试文件失败" << std::endl;
            return false;
        }
    }
    
    file.close();
    std::cout << "测试文件创建成功" << std::endl;
    return true;
}

int main() {
    std::cout << "=== 分块传输管理器测试 ===" << std::endl;
    
    // 设置测试目录
    std::string test_dir = "/tmp/chunk_transfer_test";
    std::string source_file = test_dir + "/test_source.dat";
    std::string dest_file = test_dir + "/test_dest.dat";
    
    try {
        // 创建测试目录
        if (fs::exists(test_dir)) {
            fs::remove_all(test_dir);
        }
        fs::create_directories(test_dir);
        
        // 创建测试文件 (10MB)
        if (!createTestFile(source_file, 10)) {
            std::cerr << "创建测试文件失败" << std::endl;
            return 1;
        }
        
        // 初始化传输管理器
        std::cout << "\n初始化分块传输管理器..." << std::endl;
        ChunkTransferManager manager;
        
        if (!manager.Initialize()) {
            std::cerr << "传输管理器初始化失败" << std::endl;
            return 1;
        }
        
        std::cout << "传输管理器初始化成功" << std::endl;
        
        // 设置传输参数
        manager.SetChunkSize(1024 * 1024); // 1MB 分块
        manager.SetMaxConcurrentTransfers(2);
        manager.SetMaxRetries(3);
        
        // 开始传输测试
        std::cout << "\n开始传输测试..." << std::endl;
        
        // 生成唯一的任务ID和文件路径，避免数据库约束冲突
        auto now = std::chrono::system_clock::now();
        auto timestamp = std::chrono::duration_cast<std::chrono::milliseconds>(now.time_since_epoch()).count();
        std::string unique_task_id = "test_task_" + std::to_string(timestamp);
        std::string unique_dest_file = test_dir + "/test_dest_" + std::to_string(timestamp) + ".dat";
        
        bool transfer_started = manager.StartTransfer(
            unique_task_id,
            source_file,
            unique_dest_file,
            progressCallback,
            completionCallback
        );
        
        if (!transfer_started) {
            std::cerr << "传输启动失败" << std::endl;
            return 1;
        }
        
        std::cout << "传输已启动，等待完成..." << std::endl;
        
        // 监控传输进度
        bool transfer_completed = false;
        int check_count = 0;
        const int max_checks = 60; // 最多等待60秒
        
        while (!transfer_completed && check_count < max_checks) {
            std::this_thread::sleep_for(std::chrono::seconds(1));
            
            TransferStatus status = manager.GetTransferStatus(unique_task_id);
            double progress = manager.GetTransferProgress(unique_task_id);
            
            std::cout << "[监控] 状态: " << static_cast<int>(status) 
                     << ", 进度: " << std::fixed << std::setprecision(2) << progress << "%" << std::endl;
            
            if (status == TransferStatus::COMPLETED || status == TransferStatus::FAILED) {
                transfer_completed = true;
            }
            
            check_count++;
        }
        
        // 检查传输结果
        if (transfer_completed) {
            TransferStatus final_status = manager.GetTransferStatus(unique_task_id);
            
            if (final_status == TransferStatus::COMPLETED) {
                std::cout << "\n=== 传输成功 ===" << std::endl;
                
                // 验证文件
                if (fs::exists(unique_dest_file)) {
                    auto src_size = fs::file_size(source_file);
                    auto dest_size = fs::file_size(unique_dest_file);
                    
                    std::cout << "源文件大小: " << src_size << " 字节" << std::endl;
                    std::cout << "目标文件大小: " << dest_size << " 字节" << std::endl;
                    
                    if (src_size == dest_size) {
                        std::cout << "文件大小验证: 通过" << std::endl;
                    } else {
                        std::cout << "文件大小验证: 失败" << std::endl;
                    }
                } else {
                    std::cout << "目标文件不存在" << std::endl;
                }
            } else {
                std::cout << "\n=== 传输失败 ===" << std::endl;
                std::cout << "最终状态: " << static_cast<int>(final_status) << std::endl;
            }
        } else {
            std::cout << "\n=== 传输超时 ===" << std::endl;
            std::cout << "传输未在预期时间内完成" << std::endl;
        }
        
        // 获取活跃传输列表
        auto active_transfers = manager.GetActiveTransfers();
        std::cout << "\n当前活跃传输数量: " << active_transfers.size() << std::endl;
        
        // 关闭管理器
        std::cout << "\n关闭传输管理器..." << std::endl;
        manager.Shutdown();
        
        std::cout << "测试完成" << std::endl;
        
    } catch (const std::exception& e) {
        std::cerr << "测试异常: " << e.what() << std::endl;
        return 1;
    }
    
    return 0;
}