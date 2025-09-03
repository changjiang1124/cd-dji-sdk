/**
 * @file test_db_concurrency.cc
 * @brief 数据库并发压力测试程序
 * @author Celestial Works
 * @date 2024
 * 
 * 该程序用于测试MediaStatusDB在高并发情况下的性能和稳定性，
 * 验证SQLITE_BUSY重试机制是否有效解决数据库锁定问题。
 */

#include "media_status_db.h"
#include "config_manager.h"
#include <iostream>
#include <thread>
#include <vector>
#include <chrono>
#include <atomic>
#include <random>
#include <iomanip>

using namespace celestial;

// 全局统计变量
std::atomic<int> g_success_count(0);
std::atomic<int> g_failure_count(0);
std::atomic<int> g_retry_count(0);

/**
 * @brief 工作线程函数
 * @param thread_id 线程ID
 * @param db_path 数据库路径
 * @param operations_per_thread 每个线程执行的操作数
 * @param config 数据库配置
 */
void WorkerThread(int thread_id, const std::string& db_path, 
                 int operations_per_thread, 
                 const ConfigManager::DockInfoManagerConfig& config) {
    
    // 每个线程创建自己的数据库连接
    MediaStatusDB db(db_path, 
                    config.max_retry_attempts,
                    config.retry_delay_seconds,
                    config.sqlite_busy_timeout_ms);
    
    if (!db.Initialize()) {
        std::cerr << "线程 " << thread_id << " 数据库初始化失败: " 
                  << db.GetLastError() << std::endl;
        g_failure_count += operations_per_thread;
        return;
    }
    
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<> dis(1, 1000000);
    
    for (int i = 0; i < operations_per_thread; ++i) {
        std::string file_path = "/test/thread_" + std::to_string(thread_id) 
                              + "_file_" + std::to_string(i) + ".jpg";
        std::string file_name = "thread_" + std::to_string(thread_id) 
                              + "_file_" + std::to_string(i) + ".jpg";
        int64_t file_size = dis(gen);
        
        // 执行数据库操作
        bool success = true;
        
        // 插入文件记录
        if (!db.InsertMediaFile(file_path, file_name, file_size)) {
            success = false;
        }
        
        // 更新下载状态
        if (success && !db.UpdateDownloadStatus(file_path, FileStatus::COMPLETED, "")) {
            success = false;
        }
        
        // 更新传输状态
        if (success && !db.UpdateTransferStatus(file_path, FileStatus::COMPLETED, "")) {
            success = false;
        }
        
        // 查询文件信息
        if (success) {
            MediaFileInfo info;
            if (!db.GetFileInfo(file_path, info)) {
                success = false;
            }
        }
        
        if (success) {
            g_success_count++;
        } else {
            g_failure_count++;
            std::cerr << "线程 " << thread_id << " 操作失败: " 
                      << db.GetLastError() << std::endl;
        }
        
        // 模拟一些处理时间
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    
    db.Close();
}

/**
 * @brief 打印测试结果
 * @param duration 测试持续时间
 * @param thread_count 线程数
 * @param operations_per_thread 每线程操作数
 */
void PrintResults(std::chrono::milliseconds duration, int thread_count, int operations_per_thread) {
    int total_operations = thread_count * operations_per_thread;
    double success_rate = (double)g_success_count / total_operations * 100.0;
    double ops_per_second = (double)total_operations / (duration.count() / 1000.0);
    
    std::cout << "\n=== 并发压力测试结果 ===" << std::endl;
    std::cout << "测试配置:" << std::endl;
    std::cout << "  - 线程数: " << thread_count << std::endl;
    std::cout << "  - 每线程操作数: " << operations_per_thread << std::endl;
    std::cout << "  - 总操作数: " << total_operations << std::endl;
    std::cout << "  - 测试时长: " << duration.count() << " ms" << std::endl;
    std::cout << std::endl;
    
    std::cout << "测试结果:" << std::endl;
    std::cout << "  - 成功操作: " << g_success_count << std::endl;
    std::cout << "  - 失败操作: " << g_failure_count << std::endl;
    std::cout << "  - 成功率: " << std::fixed << std::setprecision(2) 
              << success_rate << "%" << std::endl;
    std::cout << "  - 平均TPS: " << std::fixed << std::setprecision(2) 
              << ops_per_second << " ops/sec" << std::endl;
    
    if (success_rate >= 95.0) {
        std::cout << "\n✓ 测试通过: 成功率达到95%以上" << std::endl;
    } else {
        std::cout << "\n✗ 测试失败: 成功率低于95%" << std::endl;
    }
}

int main(int argc, char* argv[]) {
    std::cout << "=== MediaStatusDB 并发压力测试 ===" << std::endl;
    
    // 解析命令行参数
    int thread_count = 10;  // 默认10个线程
    int operations_per_thread = 100;  // 默认每线程100个操作
    
    if (argc >= 2) {
        thread_count = std::atoi(argv[1]);
    }
    if (argc >= 3) {
        operations_per_thread = std::atoi(argv[2]);
    }
    
    // 加载配置
    ConfigManager& config_manager = ConfigManager::getInstance();
    if (!config_manager.loadConfig("/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/unified_config.json")) {
        std::cerr << "Failed to load configuration" << std::endl;
        return -1;
    }
    
    auto config = config_manager.getDockInfoManagerConfig();
    
    std::cout << "配置参数:" << std::endl;
    std::cout << "  - 最大重试次数: " << config.max_retry_attempts << std::endl;
    std::cout << "  - 重试延迟: " << config.retry_delay_seconds << " 秒" << std::endl;
    std::cout << "  - BUSY超时: " << config.sqlite_busy_timeout_ms << " ms" << std::endl;
    std::cout << std::endl;
    
    // 测试数据库路径
    std::string test_db_path = "./test_concurrency.db";
    
    // 清理旧的测试数据库
    std::remove(test_db_path.c_str());
    
    std::cout << "开始并发压力测试..." << std::endl;
    std::cout << "线程数: " << thread_count << ", 每线程操作数: " << operations_per_thread << std::endl;
    
    // 记录开始时间
    auto start_time = std::chrono::high_resolution_clock::now();
    
    // 创建并启动工作线程
    std::vector<std::thread> threads;
    for (int i = 0; i < thread_count; ++i) {
        threads.emplace_back(WorkerThread, i, test_db_path, operations_per_thread, config);
    }
    
    // 等待所有线程完成
    for (auto& thread : threads) {
        thread.join();
    }
    
    // 记录结束时间
    auto end_time = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time);
    
    // 打印测试结果
    PrintResults(duration, thread_count, operations_per_thread);
    
    // 清理测试数据库
    std::remove(test_db_path.c_str());
    
    return (g_success_count >= thread_count * operations_per_thread * 0.95) ? 0 : 1;
}