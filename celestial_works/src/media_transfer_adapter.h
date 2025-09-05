#ifndef MEDIA_TRANSFER_ADAPTER_H
#define MEDIA_TRANSFER_ADAPTER_H

#include "chunk_transfer_manager.h"
#include "utils.h"
#include "media_status_db.h"
#include "../../include/media_manager/media_file.h"
#include "../../include/media_manager/media_files_reader.h"
#include "../../include/error_code.h"
#include <memory>
#include <string>
#include <functional>
#include <thread>
#include <atomic>
#include <unordered_map>
#include <mutex>

namespace celestial {

/**
 * @brief 媒体传输适配器 - 连接DJI SDK与分块传输管理器
 * 
 * 功能说明：
 * 1. 接收DJI SDK的媒体文件更新通知
 * 2. 将SDK的MediaFile转换为分块传输任务
 * 3. 管理异步下载流程
 * 4. 提供进度监控和错误处理
 * 5. 与现有数据库系统集成
 */
class MediaTransferAdapter {
public:
    /**
     * @brief 构造函数
     */
    MediaTransferAdapter();
    
    /**
     * @brief 析构函数
     */
    ~MediaTransferAdapter();
    
    /**
     * @brief 初始化适配器
     * @param chunk_manager 分块传输管理器实例
     * @param media_db 媒体状态数据库实例
     * @return 初始化成功返回true
     */
    bool Initialize(std::shared_ptr<ChunkTransferManager> chunk_manager,
                   std::shared_ptr<MediaStatusDB> media_db);
    
    /**
     * @brief 关闭适配器
     */
    void Shutdown();
    
    /**
     * @brief 处理媒体文件更新通知（替代原OnMediaFileUpdate）
     * @param file DJI SDK媒体文件信息
     * @return 错误码
     */
    edge_sdk::ErrorCode HandleMediaFileUpdate(const edge_sdk::MediaFile& file);
    
    /**
     * @brief 设置传输完成回调
     * @param callback 完成回调函数
     */
    void SetTransferCompletionCallback(std::function<void(const std::string& file_path, bool success)> callback);
    
    /**
     * @brief 获取传输统计信息
     * @return 统计信息字符串
     */
    std::string GetTransferStatistics() const;
    
    /**
     * @brief 获取活跃传输数量
     * @return 活跃传输数量
     */
    size_t GetActiveTransferCount() const;
    
    /**
     * @brief 检查是否有传输任务正在进行
     * @return 有活跃任务返回true
     */
    bool HasActiveTransfers() const;
    
private:
    /**
     * @brief 生成传输任务ID
     * @param file_path 文件路径
     * @return 任务ID
     */
    std::string GenerateTaskId(const std::string& file_path);
    
    /**
     * @brief 创建SDK文件读取器任务
     * @param file 媒体文件信息
     * @param task_id 任务ID
     */
    void CreateSDKReaderTask(const edge_sdk::MediaFile& file, const std::string& task_id);
    
    /**
     * @brief SDK文件读取线程函数
     * @param file 媒体文件信息
     * @param task_id 任务ID
     * @param temp_file_path 临时文件路径
     */
    void SDKReaderThread(const edge_sdk::MediaFile& file, 
                        const std::string& task_id,
                        const std::string& temp_file_path);
    
    /**
     * @brief 传输进度回调
     * @param task_id 任务ID
     * @param transferred_bytes 已传输字节数
     * @param total_bytes 总字节数
     * @param progress_percent 进度百分比
     */
    void OnTransferProgress(const std::string& task_id, 
                           size_t transferred_bytes, 
                           size_t total_bytes, 
                           double progress_percent);
    
    /**
     * @brief 传输完成回调
     * @param task_id 任务ID
     * @param success 是否成功
     * @param error_message 错误信息
     */
    void OnTransferCompletion(const std::string& task_id, 
                             bool success, 
                             const std::string& error_message);
    
    /**
     * @brief 清理临时文件
     * @param task_id 任务ID
     */
    void CleanupTempFile(const std::string& task_id);
    
    /**
     * @brief 更新数据库状态
     * @param file_path 文件路径
     * @param status 状态
     * @param error_message 错误信息
     */
    void UpdateDatabaseStatus(const std::string& file_path, 
                             FileStatus status, 
                             const std::string& error_message = "");

private:
    // 核心组件
    std::shared_ptr<ChunkTransferManager> chunk_manager_;  ///< 分块传输管理器
    std::shared_ptr<MediaStatusDB> media_db_;              ///< 媒体状态数据库
    std::unique_ptr<utils::FileUtils> file_utils_;        ///< 文件工具类
    std::unique_ptr<utils::HashCalculator> hash_calculator_; ///< 哈希计算器
    
    // 状态管理
    std::atomic<bool> initialized_;                        ///< 初始化标志
    std::atomic<bool> shutdown_flag_;                      ///< 关闭标志
    
    // 任务管理
    std::unordered_map<std::string, std::string> task_to_filepath_; ///< 任务ID到文件路径映射
    std::unordered_map<std::string, std::string> task_to_tempfile_; ///< 任务ID到临时文件映射
    std::mutex task_map_mutex_;                            ///< 任务映射互斥锁
    
    // 回调函数
    std::function<void(const std::string&, bool)> completion_callback_; ///< 完成回调
    
    // 统计信息
    std::atomic<size_t> total_files_processed_;            ///< 处理的文件总数
    std::atomic<size_t> successful_transfers_;             ///< 成功传输数
    std::atomic<size_t> failed_transfers_;                 ///< 失败传输数
    std::atomic<size_t> total_bytes_transferred_;          ///< 总传输字节数
};

} // namespace celestial

#endif // MEDIA_TRANSFER_ADAPTER_H