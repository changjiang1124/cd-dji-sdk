#include "transfer_status_db.h"
#include "config_manager.h"
#include <iostream>
#include <sstream>
#include <chrono>
#include <iomanip>
#include <cstring>

TransferStatusDB::TransferStatusDB() : db_(nullptr), initialized_(false) {
}

TransferStatusDB::~TransferStatusDB() {
    Close();
}

bool TransferStatusDB::Initialize(const std::string& db_path) {
    std::lock_guard<std::mutex> lock(db_mutex_);
    
    if (initialized_) {
        return true;
    }
    
    // 如果没有提供路径，从配置管理器获取
    std::string actual_db_path = db_path;
    if (actual_db_path.empty()) {
        ConfigManager& config = ConfigManager::getInstance();
        if (!config.loadConfig()) {
            std::cerr << "无法加载配置文件，使用默认数据库路径" << std::endl;
        }
        actual_db_path = config.getDockTransferConfig().database_path;
    }
    
    // 打开数据库
    int rc = sqlite3_open(actual_db_path.c_str(), &db_);
    if (rc != SQLITE_OK) {
        std::cerr << "无法打开数据库: " << sqlite3_errmsg(db_) << std::endl;
        return false;
    }
    
    // 启用外键约束
    if (!ExecuteSQL("PRAGMA foreign_keys = ON;")) {
        std::cerr << "启用外键约束失败" << std::endl;
        return false;
    }
    
    // 创建表
    if (!CreateTables()) {
        std::cerr << "创建数据库表失败" << std::endl;
        return false;
    }
    
    initialized_ = true;
    std::cout << "传输状态数据库初始化成功: " << actual_db_path << std::endl;
    return true;
}

void TransferStatusDB::Close() {
    std::lock_guard<std::mutex> lock(db_mutex_);
    
    if (db_) {
        sqlite3_close(db_);
        db_ = nullptr;
    }
    initialized_ = false;
}

bool TransferStatusDB::CreateTables() {
    // 创建传输任务表
    const std::string create_tasks_table = R"(
        CREATE TABLE IF NOT EXISTS transfer_tasks (
            task_id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL UNIQUE,
            file_name TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            chunk_size INTEGER NOT NULL,
            total_chunks INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_heartbeat TEXT NOT NULL,
            error_message TEXT DEFAULT ''
        );
    )";
    
    if (!ExecuteSQL(create_tasks_table)) {
        return false;
    }
    
    // 创建分块信息表
    const std::string create_chunks_table = R"(
        CREATE TABLE IF NOT EXISTS transfer_chunks (
            chunk_id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            chunk_index INTEGER NOT NULL,
            chunk_size INTEGER NOT NULL,
            offset INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING',
            md5_hash TEXT DEFAULT '',
            retry_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (task_id) REFERENCES transfer_tasks(task_id) ON DELETE CASCADE,
            UNIQUE(task_id, chunk_index)
        );
    )";
    
    if (!ExecuteSQL(create_chunks_table)) {
        return false;
    }
    
    // 创建索引以提高查询性能
    const std::vector<std::string> indexes = {
        "CREATE INDEX IF NOT EXISTS idx_tasks_status ON transfer_tasks(status);",
        "CREATE INDEX IF NOT EXISTS idx_tasks_heartbeat ON transfer_tasks(last_heartbeat);",
        "CREATE INDEX IF NOT EXISTS idx_chunks_task_status ON transfer_chunks(task_id, status);",
        "CREATE INDEX IF NOT EXISTS idx_chunks_status ON transfer_chunks(status);"
    };
    
    for (const auto& index_sql : indexes) {
        if (!ExecuteSQL(index_sql)) {
            return false;
        }
    }
    
    return true;
}

bool TransferStatusDB::ExecuteSQL(const std::string& sql) {
    char* error_msg = nullptr;
    int rc = sqlite3_exec(db_, sql.c_str(), nullptr, nullptr, &error_msg);
    
    if (rc != SQLITE_OK) {
        std::cerr << "SQL执行失败: " << error_msg << std::endl;
        std::cerr << "SQL: " << sql << std::endl;
        sqlite3_free(error_msg);
        return false;
    }
    
    return true;
}

std::string TransferStatusDB::GetCurrentTimestamp() {
    auto now = std::chrono::system_clock::now();
    auto time_t = std::chrono::system_clock::to_time_t(now);
    
    std::stringstream ss;
    ss << std::put_time(std::gmtime(&time_t), "%Y-%m-%d %H:%M:%S");
    return ss.str();
}

int TransferStatusDB::CreateTransferTask(const std::string& file_path,
                                       const std::string& file_name,
                                       size_t file_size,
                                       size_t chunk_size) {
    std::lock_guard<std::mutex> lock(db_mutex_);
    
    if (!initialized_) {
        std::cerr << "数据库未初始化" << std::endl;
        return -1;
    }
    
    // 计算总分块数
    int total_chunks = (file_size + chunk_size - 1) / chunk_size;
    std::string timestamp = GetCurrentTimestamp();
    
    const std::string sql = R"(
        INSERT INTO transfer_tasks 
        (file_path, file_name, file_size, chunk_size, total_chunks, 
         status, created_at, updated_at, last_heartbeat)
        VALUES (?, ?, ?, ?, ?, 'PENDING', ?, ?, ?);
    )";
    
    sqlite3_stmt* stmt;
    int rc = sqlite3_prepare_v2(db_, sql.c_str(), -1, &stmt, nullptr);
    
    if (rc != SQLITE_OK) {
        std::cerr << "准备SQL语句失败: " << sqlite3_errmsg(db_) << std::endl;
        return -1;
    }
    
    // 绑定参数
    sqlite3_bind_text(stmt, 1, file_path.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 2, file_name.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_int64(stmt, 3, file_size);
    sqlite3_bind_int64(stmt, 4, chunk_size);
    sqlite3_bind_int(stmt, 5, total_chunks);
    sqlite3_bind_text(stmt, 6, timestamp.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 7, timestamp.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 8, timestamp.c_str(), -1, SQLITE_STATIC);
    
    rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);
    
    if (rc != SQLITE_DONE) {
        std::cerr << "插入传输任务失败: " << sqlite3_errmsg(db_) << std::endl;
        return -1;
    }
    
    int task_id = sqlite3_last_insert_rowid(db_);
    
    // 创建分块记录
    if (!CreateChunks(task_id, total_chunks, chunk_size)) {
        std::cerr << "创建分块记录失败" << std::endl;
        DeleteTransferTask(task_id);
        return -1;
    }
    
    std::cout << "创建传输任务成功: ID=" << task_id 
              << ", 文件=" << file_name 
              << ", 大小=" << file_size << " bytes"
              << ", 分块数=" << total_chunks << std::endl;
    
    return task_id;
}

bool TransferStatusDB::CreateChunks(int task_id, int total_chunks, size_t chunk_size) {
    const std::string sql = R"(
        INSERT INTO transfer_chunks 
        (task_id, chunk_index, chunk_size, offset, status, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'PENDING', ?, ?);
    )";
    
    sqlite3_stmt* stmt;
    int rc = sqlite3_prepare_v2(db_, sql.c_str(), -1, &stmt, nullptr);
    
    if (rc != SQLITE_OK) {
        std::cerr << "准备分块插入语句失败: " << sqlite3_errmsg(db_) << std::endl;
        return false;
    }
    
    std::string timestamp = GetCurrentTimestamp();
    
    // 批量插入分块记录
    for (int i = 0; i < total_chunks; ++i) {
        size_t offset = i * chunk_size;
        
        sqlite3_bind_int(stmt, 1, task_id);
        sqlite3_bind_int(stmt, 2, i);
        sqlite3_bind_int64(stmt, 3, chunk_size);
        sqlite3_bind_int64(stmt, 4, offset);
        sqlite3_bind_text(stmt, 5, timestamp.c_str(), -1, SQLITE_STATIC);
        sqlite3_bind_text(stmt, 6, timestamp.c_str(), -1, SQLITE_STATIC);
        
        rc = sqlite3_step(stmt);
        if (rc != SQLITE_DONE) {
            std::cerr << "插入分块记录失败: " << sqlite3_errmsg(db_) << std::endl;
            sqlite3_finalize(stmt);
            return false;
        }
        
        sqlite3_reset(stmt);
    }
    
    sqlite3_finalize(stmt);
    return true;
}

bool TransferStatusDB::UpdateTransferStatus(int task_id, TransferStatus status, 
                                          const std::string& error_message) {
    std::lock_guard<std::mutex> lock(db_mutex_);
    
    if (!initialized_) {
        return false;
    }
    
    std::string status_str = TransferStatusToString(status);
    std::string timestamp = GetCurrentTimestamp();
    
    const std::string sql = R"(
        UPDATE transfer_tasks 
        SET status = ?, updated_at = ?, last_heartbeat = ?, error_message = ?
        WHERE task_id = ?;
    )";
    
    sqlite3_stmt* stmt;
    int rc = sqlite3_prepare_v2(db_, sql.c_str(), -1, &stmt, nullptr);
    
    if (rc != SQLITE_OK) {
        std::cerr << "准备更新状态语句失败: " << sqlite3_errmsg(db_) << std::endl;
        return false;
    }
    
    sqlite3_bind_text(stmt, 1, status_str.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 2, timestamp.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 3, timestamp.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 4, error_message.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_int(stmt, 5, task_id);
    
    rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);
    
    if (rc != SQLITE_DONE) {
        std::cerr << "更新传输状态失败: " << sqlite3_errmsg(db_) << std::endl;
        return false;
    }
    
    return true;
}

bool TransferStatusDB::UpdateTransferHeartbeat(int task_id) {
    std::lock_guard<std::mutex> lock(db_mutex_);
    
    if (!initialized_) {
        return false;
    }
    
    std::string timestamp = GetCurrentTimestamp();
    
    const std::string sql = "UPDATE transfer_tasks SET last_heartbeat = ? WHERE task_id = ?;";
    
    sqlite3_stmt* stmt;
    int rc = sqlite3_prepare_v2(db_, sql.c_str(), -1, &stmt, nullptr);
    
    if (rc != SQLITE_OK) {
        return false;
    }
    
    sqlite3_bind_text(stmt, 1, timestamp.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_int(stmt, 2, task_id);
    
    rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);
    
    return rc == SQLITE_DONE;
}

bool TransferStatusDB::UpdateChunkStatus(int task_id, int chunk_index, 
                                       ChunkStatus status, const std::string& md5_hash) {
    std::lock_guard<std::mutex> lock(db_mutex_);
    
    if (!initialized_) {
        return false;
    }
    
    std::string status_str = ChunkStatusToString(status);
    std::string timestamp = GetCurrentTimestamp();
    
    const std::string sql = R"(
        UPDATE transfer_chunks 
        SET status = ?, md5_hash = ?, updated_at = ?
        WHERE task_id = ? AND chunk_index = ?;
    )";
    
    sqlite3_stmt* stmt;
    int rc = sqlite3_prepare_v2(db_, sql.c_str(), -1, &stmt, nullptr);
    
    if (rc != SQLITE_OK) {
        return false;
    }
    
    sqlite3_bind_text(stmt, 1, status_str.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 2, md5_hash.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 3, timestamp.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_int(stmt, 4, task_id);
    sqlite3_bind_int(stmt, 5, chunk_index);
    
    rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);
    
    return rc == SQLITE_DONE;
}

std::vector<TransferTask> TransferStatusDB::GetIncompleteTransfers() {
    std::lock_guard<std::mutex> lock(db_mutex_);
    std::vector<TransferTask> tasks;
    
    if (!initialized_) {
        return tasks;
    }
    
    const std::string sql = R"(
        SELECT task_id, file_path, file_name, file_size, chunk_size, 
               total_chunks, status, created_at, updated_at, last_heartbeat, error_message
        FROM transfer_tasks 
        WHERE status IN ('PENDING', 'DOWNLOADING', 'PAUSED');
    )";
    
    sqlite3_stmt* stmt;
    int rc = sqlite3_prepare_v2(db_, sql.c_str(), -1, &stmt, nullptr);
    
    if (rc != SQLITE_OK) {
        return tasks;
    }
    
    while ((rc = sqlite3_step(stmt)) == SQLITE_ROW) {
        TransferTask task;
        task.task_id = sqlite3_column_int(stmt, 0);
        task.file_path = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1));
        task.file_name = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 2));
        task.file_size = sqlite3_column_int64(stmt, 3);
        task.chunk_size = sqlite3_column_int64(stmt, 4);
        task.total_chunks = sqlite3_column_int(stmt, 5);
        task.status = StringToTransferStatus(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 6)));
        task.created_at = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 7));
        task.updated_at = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 8));
        task.last_heartbeat = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 9));
        task.error_message = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 10));
        
        tasks.push_back(task);
    }
    
    sqlite3_finalize(stmt);
    return tasks;
}

// 状态转换辅助函数
std::string TransferStatusDB::TransferStatusToString(TransferStatus status) {
    switch (status) {
        case TransferStatus::PENDING: return "PENDING";
        case TransferStatus::DOWNLOADING: return "DOWNLOADING";
        case TransferStatus::PAUSED: return "PAUSED";
        case TransferStatus::COMPLETED: return "COMPLETED";
        case TransferStatus::FAILED: return "FAILED";
        default: return "UNKNOWN";
    }
}

TransferStatus TransferStatusDB::StringToTransferStatus(const std::string& status_str) {
    if (status_str == "PENDING") return TransferStatus::PENDING;
    if (status_str == "DOWNLOADING") return TransferStatus::DOWNLOADING;
    if (status_str == "PAUSED") return TransferStatus::PAUSED;
    if (status_str == "COMPLETED") return TransferStatus::COMPLETED;
    if (status_str == "FAILED") return TransferStatus::FAILED;
    return TransferStatus::PENDING;
}

std::string TransferStatusDB::ChunkStatusToString(ChunkStatus status) {
    switch (status) {
        case ChunkStatus::PENDING: return "PENDING";
        case ChunkStatus::DOWNLOADING: return "DOWNLOADING";
        case ChunkStatus::COMPLETED: return "COMPLETED";
        case ChunkStatus::FAILED: return "FAILED";
        default: return "UNKNOWN";
    }
}

ChunkStatus TransferStatusDB::StringToChunkStatus(const std::string& status_str) {
    if (status_str == "PENDING") return ChunkStatus::PENDING;
    if (status_str == "DOWNLOADING") return ChunkStatus::DOWNLOADING;
    if (status_str == "COMPLETED") return ChunkStatus::COMPLETED;
    if (status_str == "FAILED") return ChunkStatus::FAILED;
    return ChunkStatus::PENDING;
}

bool TransferStatusDB::DeleteTransferTask(int task_id) {
    std::lock_guard<std::mutex> lock(db_mutex_);
    
    if (!initialized_) {
        return false;
    }
    
    const std::string sql = "DELETE FROM transfer_tasks WHERE task_id = ?;";
    
    sqlite3_stmt* stmt;
    int rc = sqlite3_prepare_v2(db_, sql.c_str(), -1, &stmt, nullptr);
    
    if (rc != SQLITE_OK) {
        return false;
    }
    
    sqlite3_bind_int(stmt, 1, task_id);
    rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);
    
    return rc == SQLITE_DONE;
}