/**
 * @file media_status_db.h
 * @brief 媒体文件传输状态数据库操作类
 * @author Celestial
 * @date 2025-01-22
 * 
 * 功能说明：
 * 1. 提供SQLite数据库连接和操作接口
 * 2. 管理媒体文件下载和传输状态
 * 3. 支持状态查询、更新和统计
 * 4. 线程安全的数据库操作
 */

#ifndef MEDIA_STATUS_DB_H
#define MEDIA_STATUS_DB_H

#include <string>
#include <vector>
#include <memory>
#include <mutex>
#include <sqlite3.h>

namespace celestial {

/**
 * @brief 媒体文件状态枚举
 */
enum class FileStatus {
    PENDING = 0,     // 等待中
    DOWNLOADING,     // 下载中
    COMPLETED,       // 已完成
    FAILED          // 失败
};

/**
 * @brief 媒体文件信息结构体
 */
struct MediaFileInfo {
    int64_t id;
    std::string file_path;
    std::string file_name;
    int64_t file_size;
    std::string file_hash;
    
    FileStatus download_status;
    std::string download_start_time;
    std::string download_end_time;
    int download_retry_count;
    
    FileStatus transfer_status;
    std::string transfer_start_time;
    std::string transfer_end_time;
    int transfer_retry_count;
    
    std::string last_error_message;
    std::string created_at;
    std::string updated_at;
};

/**
 * @brief 媒体文件传输状态数据库操作类
 */
class MediaStatusDB {
public:
    /**
     * @brief 构造函数
     * @param db_path 数据库文件路径
     * @param max_retry_attempts 最大重试次数
     * @param retry_delay_seconds 重试延迟秒数
     * @param busy_timeout_ms SQLITE_BUSY超时毫秒数
     */
    explicit MediaStatusDB(const std::string& db_path, 
                          int max_retry_attempts = 3,
                          int retry_delay_seconds = 1,
                          int busy_timeout_ms = 30000);
    
    /**
     * @brief 析构函数
     */
    ~MediaStatusDB();
    
    /**
     * @brief 初始化数据库连接
     * @return true 成功，false 失败
     */
    bool Initialize();
    
    /**
     * @brief 关闭数据库连接
     */
    void Close();
    
    /**
     * @brief 插入新的媒体文件记录
     * @param file_path 文件路径
     * @param file_name 文件名
     * @param file_size 文件大小
     * @return true 成功，false 失败
     */
    bool InsertMediaFile(const std::string& file_path, 
                        const std::string& file_name, 
                        int64_t file_size = 0);
    
    /**
     * @brief 更新下载状态
     * @param file_path 文件路径
     * @param status 下载状态
     * @param error_message 错误信息（可选）
     * @return true 成功，false 失败
     */
    bool UpdateDownloadStatus(const std::string& file_path, 
                             FileStatus status, 
                             const std::string& error_message = "");
    
    /**
     * @brief 更新传输状态
     * @param file_path 文件路径
     * @param status 传输状态
     * @param error_message 错误信息（可选）
     * @return true 成功，false 失败
     */
    bool UpdateTransferStatus(const std::string& file_path, 
                             FileStatus status, 
                             const std::string& error_message = "");
    
    /**
     * @brief 获取准备传输的文件列表
     * @return 文件信息列表
     */
    std::vector<MediaFileInfo> GetReadyToTransferFiles();
    
    /**
     * @brief 获取文件信息
     * @param file_path 文件路径
     * @param info 输出的文件信息
     * @return true 成功，false 失败
     */
    bool GetFileInfo(const std::string& file_path, MediaFileInfo& info);
    
    /**
     * @brief 检查文件是否存在
     * @param file_path 文件路径
     * @return true 存在，false 不存在
     */
    bool FileExists(const std::string& file_path);
    
    /**
     * @brief 获取统计信息
     * @param total_files 总文件数
     * @param downloaded_files 已下载文件数
     * @param transferred_files 已传输文件数
     * @param failed_files 失败文件数
     * @return true 成功，false 失败
     */
    bool GetStatistics(int& total_files, int& downloaded_files, 
                      int& transferred_files, int& failed_files);
    
    /**
     * @brief 清理旧记录
     * @param days_old 保留天数
     * @return 清理的记录数
     */
    int CleanupOldRecords(int days_old = 30);
    
    /**
     * @brief 获取错误信息
     * @return 最后一次错误信息
     */
    std::string GetLastError() const { return last_error_; }

private:
    /**
     * @brief 执行SQL语句（带重试机制）
     * @param sql SQL语句
     * @return true 成功，false 失败
     */
    bool ExecuteSQL(const std::string& sql);
    
    /**
     * @brief 执行SQL语句（带重试机制的内部实现）
     * @param sql SQL语句
     * @param retry_count 当前重试次数
     * @return true 成功，false 失败
     */
    bool ExecuteSQLWithRetry(const std::string& sql, int retry_count = 0);
    
    /**
     * @brief 准备SQL语句
     * @param sql SQL语句
     * @param stmt 输出的语句句柄
     * @return true 成功，false 失败
     */
    bool PrepareStatement(const std::string& sql, sqlite3_stmt** stmt);
    
    /**
     * @brief 状态枚举转字符串
     * @param status 状态枚举
     * @return 状态字符串
     */
    std::string StatusToString(FileStatus status);
    
    /**
     * @brief 字符串转状态枚举
     * @param status_str 状态字符串
     * @return 状态枚举
     */
    FileStatus StringToStatus(const std::string& status_str);
    
    /**
     * @brief 获取当前时间戳
     * @return ISO格式时间戳字符串
     */
    std::string GetCurrentTimestamp();
    
    /**
     * @brief 设置错误信息
     * @param error 错误信息
     */
    void SetError(const std::string& error);

private:
    std::string db_path_;           // 数据库文件路径
    sqlite3* db_;                   // SQLite数据库句柄
    std::mutex db_mutex_;           // 数据库操作互斥锁
    std::string last_error_;        // 最后一次错误信息
    bool initialized_;              // 初始化状态
    
    // 重试机制配置
    int max_retry_attempts_;        // 最大重试次数
    int retry_delay_seconds_;       // 重试延迟秒数
    int busy_timeout_ms_;           // SQLITE_BUSY超时毫秒数
};

} // namespace celestial

#endif // MEDIA_STATUS_DB_H