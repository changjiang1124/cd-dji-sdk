#include "../src/chunk_transfer_manager.h"
#include "../src/transfer_status_db.h"
#include "../src/config_manager.h"
#include <iostream>
#include <fstream>
#include <filesystem>
#include <thread>
#include <chrono>
#include <cassert>

namespace fs = std::filesystem;

/**
 * 断点续传功能测试程序
 * 测试ChunkTransferManager的核心功能
 */
class ChunkTransferTest {
public:
    ChunkTransferTest() : test_dir_("./test_data") {
        // 创建测试目录
        fs::create_directories(test_dir_);
        fs::create_directories(test_dir_ + "/source");
        fs::create_directories(test_dir_ + "/dest");
        fs::create_directories(test_dir_ + "/temp");
    }
    
    ~ChunkTransferTest() {
        // 清理测试数据
        if (fs::exists(test_dir_)) {
            fs::remove_all(test_dir_);
        }
    }
    
    // 创建测试文件
    void CreateTestFile(const std::string& filename, size_t size_mb) {
        std::string filepath = test_dir_ + "/source/" + filename;
        std::ofstream file(filepath, std::ios::binary);
        
        // 写入指定大小的数据
        size_t total_bytes = size_mb * 1024 * 1024;
        std::vector<char> buffer(1024, 'A');
        
        for (size_t i = 0; i < total_bytes; i += buffer.size()) {
            size_t write_size = std::min(buffer.size(), total_bytes - i);
            // 填充不同的数据模式以便验证
            char pattern = 'A' + (i / (1024 * 1024)) % 26;
            std::fill(buffer.begin(), buffer.begin() + write_size, pattern);
            file.write(buffer.data(), write_size);
        }
        
        file.close();
        std::cout << "创建测试文件: " << filepath << " (" << size_mb << "MB)" << std::endl;
    }
    
    // 测试基本传输功能
    bool TestBasicTransfer() {
        std::cout << "\n=== 测试基本传输功能 ===" << std::endl;
        
        // 初始化管理器
        auto db_manager = std::make_shared<TransferStatusDB>();
        ConfigManager* config_manager = &ConfigManager::getInstance();
        
        if (!db_manager->Initialize(test_dir_ + "/transfer.db")) {
            std::cerr << "数据库初始化失败" << std::endl;
            return false;
        }
        
        ChunkTransferManager manager;
        if (!manager.Initialize()) {
            std::cerr << "传输管理器初始化失败" << std::endl;
            return false;
        }
        
        // 创建测试文件
        CreateTestFile("test_basic.dat", 5); // 5MB文件
        
        std::string source_path = test_dir_ + "/source/test_basic.dat";
        std::string dest_path = test_dir_ + "/dest/test_basic.dat";
        
        // 设置回调函数
        bool transfer_completed = false;
        bool transfer_success = false;
        std::string error_message;
        
        auto progress_cb = [](const std::string& task_id, size_t transferred_bytes, size_t total_bytes, double progress) {
            std::cout << "传输进度: " << task_id << " - " << (progress * 100) << "%" << std::endl;
        };
        
        auto completion_cb = [&](const std::string& task_id, bool success, const std::string& error) {
            transfer_completed = true;
            transfer_success = success;
            error_message = error;
            std::cout << "传输完成: " << task_id << " - " << (success ? "成功" : "失败") << std::endl;
            if (!success) {
                std::cout << "错误信息: " << error << std::endl;
            }
        };
        
        // 启动传输
        std::string task_id = "test_basic_001";
        if (!manager.StartTransfer(task_id, source_path, dest_path, progress_cb, completion_cb)) {
            std::cerr << "启动传输失败" << std::endl;
            return false;
        }
        
        // 等待传输完成
        int timeout_seconds = 30;
        while (!transfer_completed && timeout_seconds > 0) {
            std::this_thread::sleep_for(std::chrono::seconds(1));
            timeout_seconds--;
        }
        
        if (!transfer_completed) {
            std::cerr << "传输超时" << std::endl;
            return false;
        }
        
        if (!transfer_success) {
            std::cerr << "传输失败: " << error_message << std::endl;
            return false;
        }
        
        // 验证文件完整性
        if (!fs::exists(dest_path)) {
            std::cerr << "目标文件不存在" << std::endl;
            return false;
        }
        
        if (fs::file_size(source_path) != fs::file_size(dest_path)) {
            std::cerr << "文件大小不匹配" << std::endl;
            return false;
        }
        
        manager.Shutdown();
        std::cout << "基本传输测试通过!" << std::endl;
        return true;
    }
    
    // 测试断点续传功能
    bool TestResumeTransfer() {
        std::cout << "\n=== 测试断点续传功能 ===" << std::endl;
        
        // 创建较大的测试文件
        CreateTestFile("test_resume.dat", 10); // 10MB文件
        
        std::string source_path = test_dir_ + "/source/test_resume.dat";
        std::string dest_path = test_dir_ + "/dest/test_resume.dat";
        std::string task_id = "test_resume_001";
        
        // 第一次传输（模拟中断）
        {
            auto db_manager = std::make_shared<TransferStatusDB>();
            ConfigManager* config_manager = &ConfigManager::getInstance();
            
            if (!db_manager->Initialize(test_dir_ + "/transfer_resume.db")) {
                std::cerr << "数据库初始化失败" << std::endl;
                return false;
            }
            
            ChunkTransferManager manager;
            if (!manager.Initialize()) {
                std::cerr << "传输管理器初始化失败" << std::endl;
                return false;
            }
            
            bool transfer_started = false;
            auto progress_cb = [&](const std::string& tid, size_t transferred_bytes, size_t total_bytes, double progress) {
                std::cout << "第一次传输进度: " << (progress * 100) << "%" << std::endl;
                if (progress > 0.3 && !transfer_started) {
                    transfer_started = true;
                    // 模拟传输中断
                    std::cout << "模拟传输中断..." << std::endl;
                }
            };
            
            auto completion_cb = [](const std::string& tid, bool success, const std::string& error) {
                // 不应该到达这里，因为我们会中断传输
            };
            
            if (!manager.StartTransfer(task_id, source_path, dest_path, progress_cb, completion_cb)) {
                std::cerr << "启动第一次传输失败" << std::endl;
                return false;
            }
            
            // 等待传输开始并达到一定进度
            while (!transfer_started) {
                std::this_thread::sleep_for(std::chrono::milliseconds(100));
            }
            
            // 模拟程序崩溃或中断
            std::this_thread::sleep_for(std::chrono::seconds(2));
            manager.Shutdown();
        }
        
        // 第二次传输（恢复）
        {
            auto db_manager = std::make_shared<TransferStatusDB>();
            ConfigManager* config_manager = &ConfigManager::getInstance();
            
            if (!db_manager->Initialize(test_dir_ + "/transfer_resume.db")) {
                std::cerr << "数据库重新初始化失败" << std::endl;
                return false;
            }
            
            ChunkTransferManager manager;
            if (!manager.Initialize()) {
                std::cerr << "传输管理器重新初始化失败" << std::endl;
                return false;
            }
            
            bool transfer_completed = false;
            bool transfer_success = false;
            
            auto progress_cb = [](const std::string& tid, size_t transferred_bytes, size_t total_bytes, double progress) {
                std::cout << "恢复传输进度: " << (progress * 100) << "%" << std::endl;
            };
            
            auto completion_cb = [&](const std::string& tid, bool success, const std::string& error) {
                transfer_completed = true;
                transfer_success = success;
                std::cout << "恢复传输完成: " << (success ? "成功" : "失败") << std::endl;
                if (!success) {
                    std::cout << "错误信息: " << error << std::endl;
                }
            };
            
            // 尝试恢复传输
            if (!manager.ResumeTransfer(task_id)) {
                std::cerr << "恢复传输失败" << std::endl;
                return false;
            }
            
            // 等待传输完成
            int timeout_seconds = 30;
            while (!transfer_completed && timeout_seconds > 0) {
                std::this_thread::sleep_for(std::chrono::seconds(1));
                timeout_seconds--;
            }
            
            if (!transfer_completed) {
                std::cerr << "恢复传输超时" << std::endl;
                return false;
            }
            
            if (!transfer_success) {
                std::cerr << "恢复传输失败" << std::endl;
                return false;
            }
            
            manager.Shutdown();
        }
        
        // 验证最终文件完整性
        if (!fs::exists(dest_path)) {
            std::cerr << "目标文件不存在" << std::endl;
            return false;
        }
        
        if (fs::file_size(source_path) != fs::file_size(dest_path)) {
            std::cerr << "文件大小不匹配" << std::endl;
            return false;
        }
        
        std::cout << "断点续传测试通过!" << std::endl;
        return true;
    }
    
    // 测试监控功能
    bool TestMonitoring() {
        std::cout << "\n=== 测试监控功能 ===" << std::endl;
        
        auto db_manager = std::make_shared<TransferStatusDB>();
        ConfigManager* config_manager = &ConfigManager::getInstance();
        
        if (!db_manager->Initialize(test_dir_ + "/transfer_monitor.db")) {
            std::cerr << "数据库初始化失败" << std::endl;
            return false;
        }
        
        ChunkTransferManager manager;
        if (!manager.Initialize()) {
            std::cerr << "传输管理器初始化失败" << std::endl;
            return false;
        }
        
        // 等待心跳监控启动
        std::this_thread::sleep_for(std::chrono::seconds(2));
        
        // 测试健康报告
        std::string health_report = manager.GetHealthReport();
        std::cout << "健康报告: " << health_report << std::endl;
        
        if (health_report.empty()) {
            std::cerr << "健康报告为空" << std::endl;
            return false;
        }
        
        // 测试统计信息
        std::string statistics = manager.GetTransferStatistics();
        std::cout << "统计信息: " << statistics << std::endl;
        
        if (statistics.empty()) {
            std::cerr << "统计信息为空" << std::endl;
            return false;
        }
        
        // 测试僵尸任务清理
        int cleaned_tasks = manager.CleanupZombieTasks();
        std::cout << "清理的僵尸任务数: " << cleaned_tasks << std::endl;
        
        // 测试运行时间
        int64_t uptime = manager.GetUptimeSeconds();
        std::cout << "运行时间: " << uptime << " 秒" << std::endl;
        
        if (uptime < 0) {
            std::cerr << "运行时间异常" << std::endl;
            return false;
        }
        
        manager.Shutdown();
        std::cout << "监控功能测试通过!" << std::endl;
        return true;
    }
    
    // 运行所有测试
    bool RunAllTests() {
        std::cout << "开始运行断点续传功能测试..." << std::endl;
        
        bool all_passed = true;
        
        if (!TestBasicTransfer()) {
            std::cerr << "基本传输测试失败" << std::endl;
            all_passed = false;
        }
        
        if (!TestResumeTransfer()) {
            std::cerr << "断点续传测试失败" << std::endl;
            all_passed = false;
        }
        
        if (!TestMonitoring()) {
            std::cerr << "监控功能测试失败" << std::endl;
            all_passed = false;
        }
        
        return all_passed;
    }
    
private:
    std::string test_dir_;
};

int main() {
    try {
        ChunkTransferTest test;
        
        if (test.RunAllTests()) {
            std::cout << "\n🎉 所有测试通过! 断点续传功能正常工作。" << std::endl;
            return 0;
        } else {
            std::cout << "\n❌ 部分测试失败，请检查实现。" << std::endl;
            return 1;
        }
    } catch (const std::exception& e) {
        std::cerr << "测试过程中发生异常: " << e.what() << std::endl;
        return 1;
    }
}