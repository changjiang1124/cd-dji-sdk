#ifndef CHUNK_TRANSFER_MANAGER_H
#define CHUNK_TRANSFER_MANAGER_H

#include "transfer_status_db.h"
#include "config_manager.h"
#include <string>
#include <vector>
#include <memory>
#include <functional>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <atomic>
#include <queue>
#include <unordered_map>

// 传输进度回调函数类型
using ProgressCallback = std::function<void(const std::string& task_id, 
                                          size_t transferred_bytes, 
                                          size_t total_bytes, 
                                          double progress_percent)>;

// 传输完成回调函数类型
using CompletionCallback = std::function<void(const std::string& task_id, 
                                            bool success, 
                                            const std::string& error_message)>;

// 扩展分块信息结构（基于数据库中的ChunkInfo）
struct ExtendedChunkInfo : public ChunkInfo {
    size_t actual_size;              // 实际大小（最后一块可能小于chunk_size）
    std::chrono::system_clock::time_point last_update; // 最后更新时间
    
    ExtendedChunkInfo() : ChunkInfo(), actual_size(0), 
                         last_update(std::chrono::system_clock::now()) {}
    
    // 从数据库ChunkInfo构造
    ExtendedChunkInfo(const ChunkInfo& db_chunk) : ChunkInfo(db_chunk), 
                     actual_size(db_chunk.chunk_size),
                     last_update(std::chrono::system_clock::now()) {}
};

// 传输任务信息结构
struct TransferTaskInfo {
    std::string task_id;             // 任务ID
    int db_task_id;                  // 数据库中的任务ID
    std::string source_path;         // 源文件路径
    std::string dest_path;           // 目标文件路径
    size_t file_size;                // 文件总大小
    std::string file_checksum;       // 文件校验和
    TransferStatus status;           // 任务状态
    std::vector<ExtendedChunkInfo> chunks;   // 分块信息列表
    size_t transferred_bytes;        // 已传输字节数
    std::chrono::system_clock::time_point start_time;   // 开始时间
    std::chrono::system_clock::time_point last_update;  // 最后更新时间
    ProgressCallback progress_callback;     // 进度回调
    CompletionCallback completion_callback; // 完成回调
    
    TransferTaskInfo() : db_task_id(0), file_size(0), status(TransferStatus::PENDING), 
                        transferred_bytes(0),
                        start_time(std::chrono::system_clock::now()),
                        last_update(std::chrono::system_clock::now()) {}
};

// 分块传输管理器类
class ChunkTransferManager {
public:
    // 构造函数和析构函数
    ChunkTransferManager();
    ~ChunkTransferManager();
    
    // 初始化管理器
    bool Initialize();
    
    // 关闭管理器
    void Shutdown();
    
    // 启动传输任务
    bool StartTransfer(const std::string& task_id,
                      const std::string& source_path,
                      const std::string& dest_path,
                      ProgressCallback progress_cb = nullptr,
                      CompletionCallback completion_cb = nullptr);
    
    // 暂停传输任务
    bool PauseTransfer(const std::string& task_id);
    
    // 恢复传输任务
    bool ResumeTransfer(const std::string& task_id);
    
    // 取消传输任务
    bool CancelTransfer(const std::string& task_id);
    
    // 获取传输进度
    double GetTransferProgress(const std::string& task_id);
    
    // 获取传输状态
    TransferStatus GetTransferStatus(const std::string& task_id);
    
    // 获取活跃任务列表
    std::vector<std::string> GetActiveTransfers();
    
    // 获取任务详细信息
    bool GetTransferInfo(const std::string& task_id, TransferTaskInfo& info);
    
    // 设置最大并发传输数
    void SetMaxConcurrentTransfers(int max_concurrent);
    
    // 设置分块大小
    void SetChunkSize(size_t chunk_size);
    
    // 设置最大重试次数
    void SetMaxRetries(int max_retries);
    
    /**
     * @brief 获取系统健康状态报告
     * @return JSON格式的健康状态字符串
     */
    std::string GetHealthReport() const;
    
    /**
     * @brief 获取传输统计信息
     * @return JSON格式的统计信息字符串
     */
    std::string GetTransferStatistics() const;
    
    /**
     * @brief 检测并清理僵尸任务
     * @return 清理的僵尸任务数量
     */
    int CleanupZombieTasks();
    
    /**
     * @brief 启动心跳监控
     */
    void StartHeartbeatMonitor();
    
    /**
     * @brief 停止心跳监控
     */
    void StopHeartbeatMonitor();
    
    /**
     * @brief 获取系统运行时间（秒）
     */
    int64_t GetUptimeSeconds() const;
    
private:
    // 初始化配置
    bool LoadConfiguration();
    
    // 创建传输任务
    bool CreateTransferTask(const std::string& task_id,
                           const std::string& source_path,
                           const std::string& dest_path);
    
    // 分析文件并创建分块
    bool AnalyzeFileAndCreateChunks(TransferTaskInfo& task);
    
    // 计算文件校验和
    std::string CalculateFileChecksum(const std::string& file_path);
    
    // 计算分块校验和
    std::string CalculateChunkChecksum(const std::string& file_path, 
                                      size_t offset, size_t size);
    
    // 工作线程函数
    void WorkerThread();
    
    // 处理传输任务
    void ProcessTransferTask(const std::string& task_id);
    
    // 传输单个分块
    bool TransferChunk(TransferTaskInfo& task, ExtendedChunkInfo& chunk);
    
    // 验证分块完整性
    bool VerifyChunk(const TransferTaskInfo& task, const ExtendedChunkInfo& chunk);
    
    // 合并分块文件
    bool MergeChunks(TransferTaskInfo& task);
    
    // 验证最终文件
    bool VerifyFinalFile(const TransferTaskInfo& task);
    
    // 清理临时文件
    void CleanupTempFiles(const TransferTaskInfo& task);
    
    // 更新任务状态
    void UpdateTaskStatus(const std::string& task_id, TransferStatus status);
    
    // 更新分块状态
    void UpdateChunkStatus(const std::string& task_id, int chunk_id, ChunkStatus status);
    
    // 通知进度更新
    void NotifyProgress(const TransferTaskInfo& task);
    
    // 通知任务完成
    void NotifyCompletion(const TransferTaskInfo& task, bool success, const std::string& error);
    
    // 恢复未完成的任务
    bool RecoverUnfinishedTasks();
    
    // 检查任务是否可以恢复
    bool CanResumeTask(const std::string& task_id);
    
    // 获取下一个待处理的分块
    bool GetNextPendingChunk(TransferTaskInfo& task, ExtendedChunkInfo*& chunk);
    
    // 检查并处理超时任务
    void CheckTimeoutTasks();
    
    // 检查并处理失败重试
    void CheckFailedRetries();
    
    /**
     * @brief 心跳监控线程函数
     */
    void HeartbeatMonitorThread();
    
    /**
     * @brief 检测僵尸任务
     * @param zombie_timeout_minutes 僵尸任务超时时间（分钟）
     * @return 检测到的僵尸任务列表
     */
    std::vector<std::string> DetectZombieTasks(int zombie_timeout_minutes = 30);
    
    /**
     * @brief 生成健康状态JSON
     */
    std::string GenerateHealthJson() const;
    
    /**
     * @brief 生成统计信息JSON
     */
    std::string GenerateStatisticsJson() const;

private:
    // 数据库管理器
    std::unique_ptr<TransferStatusDB> db_manager_;
    
    // 配置管理器
    ConfigManager* config_manager_;
    
    // 传输任务映射表
    std::unordered_map<std::string, std::unique_ptr<TransferTaskInfo>> transfer_tasks_;
    
    // 任务队列
    std::queue<std::string> task_queue_;
    
    // 工作线程池
    std::vector<std::thread> worker_threads_;
    
    // 同步原语
    std::mutex tasks_mutex_;         // 任务映射表互斥锁
    std::mutex queue_mutex_;         // 任务队列互斥锁
    std::condition_variable queue_cv_; // 队列条件变量
    
    // 控制标志
    std::atomic<bool> shutdown_flag_; // 关闭标志
    std::atomic<bool> initialized_;   // 初始化标志
    
    // 配置参数
    size_t chunk_size_;              // 分块大小
    int max_concurrent_transfers_;   // 最大并发传输数
    int max_retries_;                // 最大重试次数
    int worker_thread_count_;        // 工作线程数量
    int timeout_seconds_;            // 超时时间（秒）
    
    // 统计信息
    std::atomic<size_t> active_transfers_;  // 活跃传输数
    std::atomic<size_t> total_transfers_;   // 总传输数
    std::atomic<size_t> completed_transfers_; // 完成传输数
    std::atomic<size_t> failed_transfers_;    // 失败传输数
    
    // 监控相关
    std::thread heartbeat_thread_;          // 心跳监控线程
    std::atomic<bool> heartbeat_running_;   // 心跳监控运行标志
    std::chrono::system_clock::time_point start_time_; // 系统启动时间
    mutable std::mutex health_mutex_;       // 健康状态互斥锁
    std::atomic<int64_t> last_heartbeat_;   // 最后心跳时间戳
    std::atomic<size_t> zombie_tasks_cleaned_; // 清理的僵尸任务数
    std::atomic<size_t> total_bytes_transferred_; // 总传输字节数
};

#endif // CHUNK_TRANSFER_MANAGER_H