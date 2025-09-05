#ifndef CONFIG_MANAGER_H
#define CONFIG_MANAGER_H

#include <string>
#include <map>
#include <fstream>
#include <sstream>
#include <iostream>

class ConfigManager {
public:
    struct DockInfoManagerConfig {
        int check_interval_seconds = 5;
        int batch_size = 10;
        int max_retry_attempts = 3;
        int retry_delay_seconds = 1;
        int connection_pool_size = 5;
        bool enable_connection_reuse = true;
        int sqlite_busy_timeout_ms = 30000;
        bool enable_detailed_logging = false;
    };
    
    // 断点续传配置结构
    struct DockTransferConfig {
        // 数据库配置
        std::string database_path = "/data/temp/dji/dock_transfer_status.db";
        bool enable_wal_mode = true;
        int connection_timeout_seconds = 30;
        int max_retries = 3;
        int backup_interval_hours = 24;
        int cleanup_old_records_days = 30;
        
        // 分块传输配置
        int chunk_size_mb = 10;
        int max_concurrent_chunks = 3;
        int retry_attempts = 5;
        int retry_delay_seconds = 2;
        int heartbeat_interval_seconds = 30;
        int zombie_task_timeout_minutes = 60;
        bool enable_integrity_check = true;
        std::string temp_chunk_prefix = ".chunk_";
        
        // 性能配置
        int max_concurrent_transfers = 2;
        int bandwidth_limit_mbps = 0;
        bool enable_compression = false;
        int buffer_size_kb = 64;
        int sync_frequency_seconds = 5;
        
        // 监控配置
        bool enable_progress_tracking = true;
        int progress_report_interval_seconds = 10;
        bool enable_speed_calculation = true;
        bool enable_eta_calculation = true;
        std::string log_level = "INFO";
    };

    static ConfigManager& getInstance() {
        static ConfigManager instance;
        return instance;
    }

    bool loadConfig(const std::string& config_path = "/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/unified_config.json");
    const DockInfoManagerConfig& getDockInfoManagerConfig() const { return dock_config_; }
    const DockTransferConfig& getDockTransferConfig() const { return dock_transfer_config_; }
    const std::string& getMediaPath() const { return media_path_; }

private:
    ConfigManager() = default;
    DockInfoManagerConfig dock_config_;
    DockTransferConfig dock_transfer_config_;
    std::string media_path_ = "/data/temp/dji/media/"; // 默认路径
    
    // 简单的JSON解析函数
    std::string extractStringValue(const std::string& json, const std::string& key);
    int extractIntValue(const std::string& json, const std::string& key, int defaultValue);
    bool extractBoolValue(const std::string& json, const std::string& key, bool defaultValue);
    std::string findJsonSection(const std::string& json, const std::string& section);
};

#endif // CONFIG_MANAGER_H