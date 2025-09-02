/**
 * @file media_status_db.cc
 * @brief 媒体文件传输状态数据库操作类实现
 * @author Celestial
 * @date 2025-01-22
 */

#include "media_status_db.h"
#include <iostream>
#include <sstream>
#include <chrono>
#include <iomanip>
#include <cstring>

namespace celestial {

MediaStatusDB::MediaStatusDB(const std::string& db_path)
    : db_path_(db_path), db_(nullptr), initialized_(false) {
}

MediaStatusDB::~MediaStatusDB() {
    Close();
}

bool MediaStatusDB::Initialize() {
    std::lock_guard<std::mutex> lock(db_mutex_);
    
    if (initialized_) {
        return true;
    }
    
    int rc = sqlite3_open(db_path_.c_str(), &db_);
    if (rc != SQLITE_OK) {
        SetError("无法打开数据库: " + std::string(sqlite3_errmsg(db_)));
        sqlite3_close(db_);
        db_ = nullptr;
        return false;
    }
    
    // 启用外键约束
    if (!ExecuteSQL("PRAGMA foreign_keys = ON;")) {
        Close();
        return false;
    }
    
    // 设置WAL模式以提高并发性能
    if (!ExecuteSQL("PRAGMA journal_mode = WAL;")) {
        Close();
        return false;
    }
    
    initialized_ = true;
    return true;
}

void MediaStatusDB::Close() {
    std::lock_guard<std::mutex> lock(db_mutex_);
    
    if (db_) {
        sqlite3_close(db_);
        db_ = nullptr;
    }
    initialized_ = false;
}

bool MediaStatusDB::InsertMediaFile(const std::string& file_path, 
                                   const std::string& file_name, 
                                   int64_t file_size) {
    if (!initialized_) {
        SetError("数据库未初始化");
        return false;
    }
    
    std::lock_guard<std::mutex> lock(db_mutex_);
    
    const char* sql = R"(
        INSERT OR IGNORE INTO media_transfer_status 
        (file_path, file_name, file_size, download_status, transfer_status) 
        VALUES (?, ?, ?, 'pending', 'pending')
    )";
    
    sqlite3_stmt* stmt;
    if (!PrepareStatement(sql, &stmt)) {
        return false;
    }
    
    sqlite3_bind_text(stmt, 1, file_path.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 2, file_name.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_int64(stmt, 3, file_size);
    
    int rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);
    
    if (rc != SQLITE_DONE) {
        SetError("插入媒体文件记录失败: " + std::string(sqlite3_errmsg(db_)));
        return false;
    }
    
    return true;
}

bool MediaStatusDB::UpdateDownloadStatus(const std::string& file_path, 
                                        FileStatus status, 
                                        const std::string& error_message) {
    if (!initialized_) {
        SetError("数据库未初始化");
        return false;
    }
    
    std::lock_guard<std::mutex> lock(db_mutex_);
    
    std::string sql = "UPDATE media_transfer_status SET download_status = ?, ";
    
    if (status == FileStatus::DOWNLOADING) {
        sql += "download_start_time = CURRENT_TIMESTAMP, ";
    } else if (status == FileStatus::COMPLETED) {
        sql += "download_end_time = CURRENT_TIMESTAMP, ";
    } else if (status == FileStatus::FAILED) {
        sql += "download_retry_count = download_retry_count + 1, ";
    }
    
    sql += "last_error_message = ? WHERE file_path = ?";
    
    sqlite3_stmt* stmt;
    if (!PrepareStatement(sql, &stmt)) {
        return false;
    }
    
    sqlite3_bind_text(stmt, 1, StatusToString(status).c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 2, error_message.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 3, file_path.c_str(), -1, SQLITE_STATIC);
    
    int rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);
    
    if (rc != SQLITE_DONE) {
        SetError("更新下载状态失败: " + std::string(sqlite3_errmsg(db_)));
        return false;
    }
    
    return true;
}

bool MediaStatusDB::UpdateTransferStatus(const std::string& file_path, 
                                        FileStatus status, 
                                        const std::string& error_message) {
    if (!initialized_) {
        SetError("数据库未初始化");
        return false;
    }
    
    std::lock_guard<std::mutex> lock(db_mutex_);
    
    std::string sql = "UPDATE media_transfer_status SET transfer_status = ?, ";
    
    if (status == FileStatus::DOWNLOADING) {  // 这里用DOWNLOADING表示TRANSFERRING
        sql += "transfer_start_time = CURRENT_TIMESTAMP, ";
    } else if (status == FileStatus::COMPLETED) {
        sql += "transfer_end_time = CURRENT_TIMESTAMP, ";
    } else if (status == FileStatus::FAILED) {
        sql += "transfer_retry_count = transfer_retry_count + 1, ";
    }
    
    sql += "last_error_message = ? WHERE file_path = ?";
    
    sqlite3_stmt* stmt;
    if (!PrepareStatement(sql, &stmt)) {
        return false;
    }
    
    sqlite3_bind_text(stmt, 1, StatusToString(status).c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 2, error_message.c_str(), -1, SQLITE_STATIC);
    sqlite3_bind_text(stmt, 3, file_path.c_str(), -1, SQLITE_STATIC);
    
    int rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);
    
    if (rc != SQLITE_DONE) {
        SetError("更新传输状态失败: " + std::string(sqlite3_errmsg(db_)));
        return false;
    }
    
    return true;
}

std::vector<MediaFileInfo> MediaStatusDB::GetReadyToTransferFiles() {
    std::vector<MediaFileInfo> files;
    
    if (!initialized_) {
        SetError("数据库未初始化");
        return files;
    }
    
    std::lock_guard<std::mutex> lock(db_mutex_);
    
    const char* sql = R"(
        SELECT id, file_path, file_name, file_size, file_hash,
               download_status, download_start_time, download_end_time, download_retry_count,
               transfer_status, transfer_start_time, transfer_end_time, transfer_retry_count,
               last_error_message, created_at, updated_at
        FROM media_transfer_status 
        WHERE download_status = 'completed' AND transfer_status = 'pending'
        ORDER BY created_at ASC
    )";
    
    sqlite3_stmt* stmt;
    if (!PrepareStatement(sql, &stmt)) {
        return files;
    }
    
    while (sqlite3_step(stmt) == SQLITE_ROW) {
        MediaFileInfo info;
        info.id = sqlite3_column_int64(stmt, 0);
        info.file_path = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1));
        info.file_name = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 2));
        info.file_size = sqlite3_column_int64(stmt, 3);
        
        const char* hash = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 4));
        info.file_hash = hash ? hash : "";
        
        info.download_status = StringToStatus(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 5)));
        
        const char* download_start = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 6));
        info.download_start_time = download_start ? download_start : "";
        
        const char* download_end = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 7));
        info.download_end_time = download_end ? download_end : "";
        
        info.download_retry_count = sqlite3_column_int(stmt, 8);
        
        info.transfer_status = StringToStatus(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 9)));
        
        const char* transfer_start = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 10));
        info.transfer_start_time = transfer_start ? transfer_start : "";
        
        const char* transfer_end = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 11));
        info.transfer_end_time = transfer_end ? transfer_end : "";
        
        info.transfer_retry_count = sqlite3_column_int(stmt, 12);
        
        const char* error_msg = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 13));
        info.last_error_message = error_msg ? error_msg : "";
        
        info.created_at = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 14));
        info.updated_at = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 15));
        
        files.push_back(info);
    }
    
    sqlite3_finalize(stmt);
    return files;
}

bool MediaStatusDB::GetFileInfo(const std::string& file_path, MediaFileInfo& info) {
    if (!initialized_) {
        SetError("数据库未初始化");
        return false;
    }
    
    std::lock_guard<std::mutex> lock(db_mutex_);
    
    const char* sql = R"(
        SELECT id, file_path, file_name, file_size, file_hash,
               download_status, download_start_time, download_end_time, download_retry_count,
               transfer_status, transfer_start_time, transfer_end_time, transfer_retry_count,
               last_error_message, created_at, updated_at
        FROM media_transfer_status WHERE file_path = ?
    )";
    
    sqlite3_stmt* stmt;
    if (!PrepareStatement(sql, &stmt)) {
        return false;
    }
    
    sqlite3_bind_text(stmt, 1, file_path.c_str(), -1, SQLITE_STATIC);
    
    bool found = false;
    if (sqlite3_step(stmt) == SQLITE_ROW) {
        // 填充info结构体（代码与GetReadyToTransferFiles类似）
        info.id = sqlite3_column_int64(stmt, 0);
        info.file_path = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 1));
        info.file_name = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 2));
        info.file_size = sqlite3_column_int64(stmt, 3);
        
        const char* hash = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 4));
        info.file_hash = hash ? hash : "";
        
        info.download_status = StringToStatus(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 5)));
        
        const char* download_start = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 6));
        info.download_start_time = download_start ? download_start : "";
        
        const char* download_end = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 7));
        info.download_end_time = download_end ? download_end : "";
        
        info.download_retry_count = sqlite3_column_int(stmt, 8);
        
        info.transfer_status = StringToStatus(reinterpret_cast<const char*>(sqlite3_column_text(stmt, 9)));
        
        const char* transfer_start = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 10));
        info.transfer_start_time = transfer_start ? transfer_start : "";
        
        const char* transfer_end = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 11));
        info.transfer_end_time = transfer_end ? transfer_end : "";
        
        info.transfer_retry_count = sqlite3_column_int(stmt, 12);
        
        const char* error_msg = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 13));
        info.last_error_message = error_msg ? error_msg : "";
        
        info.created_at = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 14));
        info.updated_at = reinterpret_cast<const char*>(sqlite3_column_text(stmt, 15));
        
        found = true;
    }
    
    sqlite3_finalize(stmt);
    return found;
}

bool MediaStatusDB::FileExists(const std::string& file_path) {
    if (!initialized_) {
        return false;
    }
    
    std::lock_guard<std::mutex> lock(db_mutex_);
    
    const char* sql = "SELECT COUNT(*) FROM media_transfer_status WHERE file_path = ?";
    
    sqlite3_stmt* stmt;
    if (!PrepareStatement(sql, &stmt)) {
        return false;
    }
    
    sqlite3_bind_text(stmt, 1, file_path.c_str(), -1, SQLITE_STATIC);
    
    bool exists = false;
    if (sqlite3_step(stmt) == SQLITE_ROW) {
        exists = sqlite3_column_int(stmt, 0) > 0;
    }
    
    sqlite3_finalize(stmt);
    return exists;
}

bool MediaStatusDB::GetStatistics(int& total_files, int& downloaded_files, 
                                 int& transferred_files, int& failed_files) {
    if (!initialized_) {
        SetError("数据库未初始化");
        return false;
    }
    
    std::lock_guard<std::mutex> lock(db_mutex_);
    
    const char* sql = R"(
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN download_status = 'completed' THEN 1 ELSE 0 END) as downloaded,
            SUM(CASE WHEN transfer_status = 'completed' THEN 1 ELSE 0 END) as transferred,
            SUM(CASE WHEN download_status = 'failed' OR transfer_status = 'failed' THEN 1 ELSE 0 END) as failed
        FROM media_transfer_status
        WHERE file_path != '__INIT_MARKER__'
    )";
    
    sqlite3_stmt* stmt;
    if (!PrepareStatement(sql, &stmt)) {
        return false;
    }
    
    bool success = false;
    if (sqlite3_step(stmt) == SQLITE_ROW) {
        total_files = sqlite3_column_int(stmt, 0);
        downloaded_files = sqlite3_column_int(stmt, 1);
        transferred_files = sqlite3_column_int(stmt, 2);
        failed_files = sqlite3_column_int(stmt, 3);
        success = true;
    }
    
    sqlite3_finalize(stmt);
    return success;
}

int MediaStatusDB::CleanupOldRecords(int days_old) {
    if (!initialized_) {
        SetError("数据库未初始化");
        return -1;
    }
    
    std::lock_guard<std::mutex> lock(db_mutex_);
    
    const char* sql = R"(
        DELETE FROM media_transfer_status 
        WHERE created_at < datetime('now', '-' || ? || ' days')
        AND file_path != '__INIT_MARKER__'
    )";
    
    sqlite3_stmt* stmt;
    if (!PrepareStatement(sql, &stmt)) {
        return -1;
    }
    
    sqlite3_bind_int(stmt, 1, days_old);
    
    int rc = sqlite3_step(stmt);
    sqlite3_finalize(stmt);
    
    if (rc != SQLITE_DONE) {
        SetError("清理旧记录失败: " + std::string(sqlite3_errmsg(db_)));
        return -1;
    }
    
    return sqlite3_changes(db_);
}

bool MediaStatusDB::ExecuteSQL(const std::string& sql) {
    char* error_msg = nullptr;
    int rc = sqlite3_exec(db_, sql.c_str(), nullptr, nullptr, &error_msg);
    
    if (rc != SQLITE_OK) {
        std::string error = "SQL执行失败: ";
        if (error_msg) {
            error += error_msg;
            sqlite3_free(error_msg);
        }
        SetError(error);
        return false;
    }
    
    return true;
}

bool MediaStatusDB::PrepareStatement(const std::string& sql, sqlite3_stmt** stmt) {
    int rc = sqlite3_prepare_v2(db_, sql.c_str(), -1, stmt, nullptr);
    if (rc != SQLITE_OK) {
        SetError("SQL语句准备失败: " + std::string(sqlite3_errmsg(db_)));
        return false;
    }
    return true;
}

std::string MediaStatusDB::StatusToString(FileStatus status) {
    switch (status) {
        case FileStatus::PENDING: return "pending";
        case FileStatus::DOWNLOADING: return "downloading";
        case FileStatus::COMPLETED: return "completed";
        case FileStatus::FAILED: return "failed";
        default: return "unknown";
    }
}

FileStatus MediaStatusDB::StringToStatus(const std::string& status_str) {
    if (status_str == "pending") return FileStatus::PENDING;
    if (status_str == "downloading") return FileStatus::DOWNLOADING;
    if (status_str == "completed") return FileStatus::COMPLETED;
    if (status_str == "failed") return FileStatus::FAILED;
    return FileStatus::PENDING;
}

std::string MediaStatusDB::GetCurrentTimestamp() {
    auto now = std::chrono::system_clock::now();
    auto time_t = std::chrono::system_clock::to_time_t(now);
    std::stringstream ss;
    ss << std::put_time(std::gmtime(&time_t), "%Y-%m-%d %H:%M:%S");
    return ss.str();
}

void MediaStatusDB::SetError(const std::string& error) {
    last_error_ = error;
    std::cerr << "[MediaStatusDB Error] " << error << std::endl;
}

} // namespace celestial