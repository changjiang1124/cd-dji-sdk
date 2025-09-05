#include <iostream>
#include <fstream>
#include <filesystem>
#include <chrono>
#include <thread>
#include <signal.h>
#include "../src/chunk_transfer_manager.h"

namespace fs = std::filesystem;

// 全局变量用于控制测试流程
static bool interrupt_transfer = false;
static std::string global_task_id;
static ChunkTransferManager* global_manager = nullptr;

// 进度回调函数
void progressCallback(const std::string& task_id, size_t transferred, size_t total, double percentage) {
    std::cout << "[进度] 任务 " << task_id << ": " << transferred << "/" << total 
              << " (" << std::fixed << std::setprecision(2) << percentage << "%)" << std::endl;
    
    // 当传输到50%时模拟中断
    if (percentage >= 50.0 && !interrupt_transfer) {
        std::cout << "\n=== 模拟传输中断 ===" << std::endl;
        interrupt_transfer = true;
        
        // 停止当前传输
        if (global_manager) {
            global_manager->CancelTransfer(task_id);
        }
    }
}

// 完成回调函数
void completionCallback(const std::string& task_id, bool success, const std::string& error) {
    if (success) {
        std::cout << "[完成] 任务 " << task_id << ": 成功" << std::endl;
    } else {
        std::cout << "[完成] 任务 " << task_id << ": 失败 - " << error << std::endl;
    }
}

/**
 * 创建测试文件
 * @param path 文件路径
 * @param size_mb 文件大小(MB)
 * @return 创建是否成功
 */
bool createTestFile(const std::string& path, size_t size_mb) {
    try {
        // 确保目录存在
        fs::path file_path(path);
        fs::create_directories(file_path.parent_path());
        
        std::ofstream file(path, std::ios::binary);
        if (!file) {
            std::cerr << "无法创建文件: " << path << std::endl;
            return false;
        }
        
        // 写入测试数据
        const size_t buffer_size = 1024 * 1024; // 1MB buffer
        std::vector<char> buffer(buffer_size, 'A');
        
        for (size_t i = 0; i < size_mb; ++i) {
            // 每MB使用不同的字符，便于验证
            char fill_char = 'A' + (i % 26);
            std::fill(buffer.begin(), buffer.end(), fill_char);
            
            file.write(buffer.data(), buffer_size);
            if (!file) {
                std::cerr << "写入文件失败: " << path << std::endl;
                return false;
            }
        }
        
        file.close();
        std::cout << "测试文件创建成功: " << path << " (" << size_mb << "MB)" << std::endl;
        return true;
        
    } catch (const std::exception& e) {
        std::cerr << "创建测试文件异常: " << e.what() << std::endl;
        return false;
    }
}

int main() {
    std::cout << "=== 断点续传测试 ===" << std::endl;
    
    try {
        // 创建测试目录和文件
        const std::string test_dir = "/tmp/resume_transfer_test";
        const std::string source_file = test_dir + "/test_source.dat";
        
        // 生成唯一的任务ID和目标文件
        auto timestamp = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::system_clock::now().time_since_epoch()).count();
        global_task_id = "resume_task_" + std::to_string(timestamp);
        const std::string dest_file = test_dir + "/test_dest_" + std::to_string(timestamp) + ".dat";
        
        std::cout << "创建测试文件: " << source_file << " (20MB)" << std::endl;
        if (!createTestFile(source_file, 20)) {
            std::cerr << "测试文件创建失败" << std::endl;
            return 1;
        }
        
        // 初始化传输管理器
        std::cout << "\n初始化分块传输管理器..." << std::endl;
        ChunkTransferManager manager;
        global_manager = &manager;
        
        if (!manager.Initialize()) {
            std::cerr << "传输管理器初始化失败" << std::endl;
            return 1;
        }
        std::cout << "传输管理器初始化成功" << std::endl;
        
        // 清理可能存在的旧任务记录
        std::cout << "\n=== 清理旧任务记录 ===" << std::endl;
        std::string cleanup_cmd = "sqlite3 /data/temp/dji/dock_transfer_status.db \"DELETE FROM transfer_tasks WHERE file_path = '" + source_file + "';\";";
        system(cleanup_cmd.c_str());
        std::cout << "旧任务记录清理完成" << std::endl;
        
        // 第一次传输（会被中断）
        std::cout << "\n=== 第一次传输（将被中断） ===" << std::endl;
        bool transfer_started = manager.StartTransfer(
            global_task_id,
            source_file,
            dest_file,
            progressCallback,
            completionCallback
        );
        
        if (!transfer_started) {
            std::cerr << "传输启动失败" << std::endl;
            return 1;
        }
        
        std::cout << "传输已启动，等待中断..." << std::endl;
        
        // 等待传输被中断
        bool transfer_interrupted = false;
        int check_count = 0;
        const int max_checks = 60; // 最多等待60秒
        
        while (!transfer_interrupted && check_count < max_checks) {
            std::this_thread::sleep_for(std::chrono::seconds(1));
            
            // 检查传输进度，当达到50%时自动中断
            double current_progress = manager.GetTransferProgress(global_task_id);
            if (current_progress >= 50.0 || interrupt_transfer) {
                // 模拟中断传输
                manager.CancelTransfer(global_task_id);
                transfer_interrupted = true;
                std::cout << "=== 模拟传输中断 ===" << std::endl;
                std::cout << "传输已中断，当前进度: " << std::fixed << std::setprecision(2) << current_progress << "%" << std::endl;
                break;
            }
            
            check_count++;
        }
        
        if (!transfer_interrupted) {
            std::cout << "传输未按预期中断，测试失败" << std::endl;
            return 1;
        }
        
        // 等待一段时间确保中断处理完成
        std::this_thread::sleep_for(std::chrono::seconds(2));
        
        // 检查传输状态
        TransferStatus status = manager.GetTransferStatus(global_task_id);
        double progress = manager.GetTransferProgress(global_task_id);
        
        std::cout << "\n中断后状态检查:" << std::endl;
        std::cout << "状态: " << static_cast<int>(status) << std::endl;
        std::cout << "进度: " << std::fixed << std::setprecision(2) << progress << "%" << std::endl;
        
        // 重置中断标志
        interrupt_transfer = false;
        
        // 第二次传输（断点续传）
        std::cout << "\n=== 断点续传测试 ===" << std::endl;
        std::cout << "重新启动传输，应该从中断点继续..." << std::endl;
        
        bool resume_started = manager.StartTransfer(
            global_task_id,
            source_file,
            dest_file,
            progressCallback,
            completionCallback
        );
        
        if (!resume_started) {
            std::cerr << "断点续传启动失败" << std::endl;
            return 1;
        }
        
        std::cout << "断点续传已启动，等待完成..." << std::endl;
        
        // 等待传输完成
        bool transfer_completed = false;
        check_count = 0;
        const int max_resume_checks = 120; // 最多等待120秒
        
        while (!transfer_completed && check_count < max_resume_checks) {
            std::this_thread::sleep_for(std::chrono::seconds(1));
            
            TransferStatus current_status = manager.GetTransferStatus(global_task_id);
            double current_progress = manager.GetTransferProgress(global_task_id);
            
            std::cout << "[监控] 状态: " << static_cast<int>(current_status) 
                      << ", 进度: " << std::fixed << std::setprecision(2) 
                      << current_progress << "%" << std::endl;
            
            if (current_status == TransferStatus::COMPLETED || current_status == TransferStatus::FAILED) {
                transfer_completed = true;
            }
            
            check_count++;
        }
        
        // 检查最终结果
        if (transfer_completed) {
            TransferStatus final_status = manager.GetTransferStatus(global_task_id);
            
            if (final_status == TransferStatus::COMPLETED) {
                std::cout << "\n=== 断点续传成功 ===" << std::endl;
                
                // 验证文件
                if (fs::exists(dest_file)) {
                    auto src_size = fs::file_size(source_file);
                    auto dest_size = fs::file_size(dest_file);
                    
                    std::cout << "源文件大小: " << src_size << " 字节" << std::endl;
                    std::cout << "目标文件大小: " << dest_size << " 字节" << std::endl;
                    
                    if (src_size == dest_size) {
                        std::cout << "文件大小验证: 通过" << std::endl;
                        
                        // 简单的内容验证
                        std::ifstream src(source_file, std::ios::binary);
                        std::ifstream dst(dest_file, std::ios::binary);
                        
                        if (src && dst) {
                            // 比较文件内容（采样检查）
                            bool content_match = true;
                            const size_t sample_size = 1024;
                            std::vector<char> src_buffer(sample_size);
                            std::vector<char> dst_buffer(sample_size);
                            
                            // 检查文件开头
                            src.read(src_buffer.data(), sample_size);
                            dst.read(dst_buffer.data(), sample_size);
                            
                            if (src_buffer != dst_buffer) {
                                content_match = false;
                            }
                            
                            // 检查文件中间
                            if (content_match && src_size > sample_size * 2) {
                                src.seekg(src_size / 2);
                                dst.seekg(src_size / 2);
                                src.read(src_buffer.data(), sample_size);
                                dst.read(dst_buffer.data(), sample_size);
                                
                                if (src_buffer != dst_buffer) {
                                    content_match = false;
                                }
                            }
                            
                            // 检查文件结尾
                            if (content_match && src_size > sample_size) {
                                src.seekg(-static_cast<long>(sample_size), std::ios::end);
                                dst.seekg(-static_cast<long>(sample_size), std::ios::end);
                                src.read(src_buffer.data(), sample_size);
                                dst.read(dst_buffer.data(), sample_size);
                                
                                if (src_buffer != dst_buffer) {
                                    content_match = false;
                                }
                            }
                            
                            if (content_match) {
                                std::cout << "文件内容验证: 通过" << std::endl;
                                std::cout << "\n*** 断点续传测试完全成功! ***" << std::endl;
                            } else {
                                std::cout << "文件内容验证: 失败" << std::endl;
                            }
                        }
                    } else {
                        std::cout << "文件大小验证: 失败" << std::endl;
                    }
                } else {
                    std::cout << "目标文件不存在" << std::endl;
                }
            } else {
                std::cout << "\n=== 断点续传失败 ===" << std::endl;
                std::cout << "最终状态: " << static_cast<int>(final_status) << std::endl;
            }
        } else {
            std::cout << "\n=== 断点续传超时 ===" << std::endl;
            std::cout << "传输未在预期时间内完成" << std::endl;
        }
        
        // 关闭管理器
        std::cout << "\n关闭传输管理器..." << std::endl;
        manager.Shutdown();
        
        std::cout << "断点续传测试完成" << std::endl;
        
    } catch (const std::exception& e) {
        std::cerr << "测试异常: " << e.what() << std::endl;
        return 1;
    }
    
    return 0;
}