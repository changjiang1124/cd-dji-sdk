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

    static ConfigManager& getInstance() {
        static ConfigManager instance;
        return instance;
    }

    bool loadConfig(const std::string& config_path = "/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/unified_config.json");
    const DockInfoManagerConfig& getDockInfoManagerConfig() const { return dock_config_; }

private:
    ConfigManager() = default;
    DockInfoManagerConfig dock_config_;
    
    // 简单的JSON解析函数
    std::string extractStringValue(const std::string& json, const std::string& key);
    int extractIntValue(const std::string& json, const std::string& key, int defaultValue);
    bool extractBoolValue(const std::string& json, const std::string& key, bool defaultValue);
    std::string findJsonSection(const std::string& json, const std::string& section);
};

#endif // CONFIG_MANAGER_H