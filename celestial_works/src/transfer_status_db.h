#ifndef TRANSFER_STATUS_DB_H
#define TRANSFER_STATUS_DB_H

#include <string>
#include <vector>
#include <mutex>
#include <sqlite3.h>
#include <cstdint>

// 传输任务状态枚举
enum class TransferStatus {
    PENDING,     // 等待开始
    DOWNLOADING, // 下载中
    PAUSED,      // 暂停
    COMPLETED,   // 完成
    FAILED       // 失败
};

// 分块状态枚举
enum class ChunkStatus {
    PENDING,     // 等待下载
    DOWNLOADING, // 下载中
    COMPLETED,   // 完成
    FAILED       // 失败
};

// 传输任务信息结构
struct TransferTask {
    int task_id;
    std::string file_path;
    std::string file_name;
    size_t file_size;
    size_t chunk_size;
    int total_chunks;
    TransferStatus status;
    std::string created_at;
    std::string updated_at;
    std::string last_heartbeat;
    std::string error_message;
};

// 分块信息结构
struct ChunkInfo {
    int chunk_id;
    int task_id;
    int chunk_index;
    size_t chunk_size;
    size_t offset;
    ChunkStatus status;
    std::string md5_hash;
    int retry_count;
    std::string created_at;
    std::string updated_at;
};

// 传输状态数据库管理类
class TransferStatusDB {
public:
    TransferStatusDB();
    ~TransferStatusDB();

    // 初始化数据库
    bool Initialize(const std::string& db_path);
    
    // 关闭数据库
    void Close();

    // 传输任务管理
    int CreateTransferTask(const std::string& file_path, 
                          const std::string& file_name,
                          size_t file_size, 
                          size_t chunk_size);
    bool UpdateTransferStatus(int task_id, TransferStatus status, 
                             const std::string& error_message = "");
    bool UpdateTransferHeartbeat(int task_id);
    bool DeleteTransferTask(int task_id);
    
    // 分块管理
    bool CreateChunks(int task_id, int total_chunks, size_t chunk_size);
    bool UpdateChunkStatus(int task_id, int chunk_index, ChunkStatus status, 
                          const std::string& md5_hash = "");
    bool UpdateChunkRetryCount(int task_id, int chunk_index);
    
    // 查询接口
    std::vector<TransferTask> GetIncompleteTransfers();
    std::vector<TransferTask> GetStaleTransfers(int timeout_seconds = 60);
    TransferTask GetTransferTask(int task_id);
    std::vector<ChunkInfo> GetTaskChunks(int task_id);
    std::vector<ChunkInfo> GetIncompleteChunks(int task_id);
    
    // 统计接口
    int GetTotalTransferCount();
    int GetCompletedTransferCount();
    int GetFailedTransferCount();
    size_t GetTotalBytesTransferred();
    
    // 清理接口
    bool CleanupCompletedTasks(int days_old = 7);
    bool CleanupFailedTasks(int days_old = 3);

private:
    sqlite3* db_;
    std::mutex db_mutex_;  // 数据库操作线程安全保护
    bool initialized_;
    
    // 内部辅助方法
    bool CreateTables();
    bool ExecuteSQL(const std::string& sql);
    std::string GetCurrentTimestamp();
    std::string TransferStatusToString(TransferStatus status);
    TransferStatus StringToTransferStatus(const std::string& status_str);
    std::string ChunkStatusToString(ChunkStatus status);
    ChunkStatus StringToChunkStatus(const std::string& status_str);
};

#endif // TRANSFER_STATUS_DB_H