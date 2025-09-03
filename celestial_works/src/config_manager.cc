#include "config_manager.h"
#include <algorithm>
#include <cctype>

bool ConfigManager::loadConfig(const std::string& config_path) {
    std::ifstream file(config_path);
    if (!file.is_open()) {
        std::cerr << "Warning: Cannot open config file: " << config_path << std::endl;
        std::cerr << "Using default configuration values." << std::endl;
        return false;
    }

    std::stringstream buffer;
    buffer << file.rdbuf();
    std::string json_content = buffer.str();
    file.close();

    // 查找dock_info_manager配置段
    std::string dock_section = findJsonSection(json_content, "dock_info_manager");
    if (dock_section.empty()) {
        std::cerr << "Warning: dock_info_manager section not found in config file." << std::endl;
        std::cerr << "Using default configuration values." << std::endl;
        return false;
    }

    // 解析配置值
    dock_config_.check_interval_seconds = extractIntValue(dock_section, "check_interval_seconds", 5);
    dock_config_.batch_size = extractIntValue(dock_section, "batch_size", 10);
    dock_config_.max_retry_attempts = extractIntValue(dock_section, "max_retry_attempts", 3);
    dock_config_.retry_delay_seconds = extractIntValue(dock_section, "retry_delay_seconds", 1);
    dock_config_.connection_pool_size = extractIntValue(dock_section, "connection_pool_size", 5);
    dock_config_.enable_connection_reuse = extractBoolValue(dock_section, "enable_connection_reuse", true);
    dock_config_.sqlite_busy_timeout_ms = extractIntValue(dock_section, "sqlite_busy_timeout_ms", 30000);
    dock_config_.enable_detailed_logging = extractBoolValue(dock_section, "enable_detailed_logging", false);

    // 解析local_settings配置段
    std::string local_settings_section = findJsonSection(json_content, "local_settings");
    if (!local_settings_section.empty()) {
        std::string media_path = extractStringValue(local_settings_section, "media_path");
        if (!media_path.empty()) {
            media_path_ = media_path;
        }
    }

    std::cout << "Configuration loaded successfully:" << std::endl;
    std::cout << "  check_interval_seconds: " << dock_config_.check_interval_seconds << std::endl;
    std::cout << "  batch_size: " << dock_config_.batch_size << std::endl;
    std::cout << "  max_retry_attempts: " << dock_config_.max_retry_attempts << std::endl;
    std::cout << "  retry_delay_seconds: " << dock_config_.retry_delay_seconds << std::endl;
    std::cout << "  connection_pool_size: " << dock_config_.connection_pool_size << std::endl;
    std::cout << "  enable_connection_reuse: " << (dock_config_.enable_connection_reuse ? "true" : "false") << std::endl;
    std::cout << "  sqlite_busy_timeout_ms: " << dock_config_.sqlite_busy_timeout_ms << std::endl;
    std::cout << "  enable_detailed_logging: " << (dock_config_.enable_detailed_logging ? "true" : "false") << std::endl;
    std::cout << "  media_path: " << media_path_ << std::endl;

    return true;
}

std::string ConfigManager::findJsonSection(const std::string& json, const std::string& section) {
    std::string search_key = "\"" + section + "\"";
    size_t start_pos = json.find(search_key);
    if (start_pos == std::string::npos) {
        return "";
    }

    // 找到冒号
    size_t colon_pos = json.find(':', start_pos);
    if (colon_pos == std::string::npos) {
        return "";
    }

    // 找到开始的大括号
    size_t brace_start = json.find('{', colon_pos);
    if (brace_start == std::string::npos) {
        return "";
    }

    // 找到匹配的结束大括号
    int brace_count = 1;
    size_t pos = brace_start + 1;
    while (pos < json.length() && brace_count > 0) {
        if (json[pos] == '{') {
            brace_count++;
        } else if (json[pos] == '}') {
            brace_count--;
        }
        pos++;
    }

    if (brace_count == 0) {
        return json.substr(brace_start, pos - brace_start);
    }

    return "";
}

int ConfigManager::extractIntValue(const std::string& json, const std::string& key, int defaultValue) {
    std::string search_key = "\"" + key + "\"";
    size_t start_pos = json.find(search_key);
    if (start_pos == std::string::npos) {
        return defaultValue;
    }

    size_t colon_pos = json.find(':', start_pos);
    if (colon_pos == std::string::npos) {
        return defaultValue;
    }

    // 跳过空白字符
    size_t value_start = colon_pos + 1;
    while (value_start < json.length() && std::isspace(json[value_start])) {
        value_start++;
    }

    // 找到数字的结束位置
    size_t value_end = value_start;
    while (value_end < json.length() && (std::isdigit(json[value_end]) || json[value_end] == '-')) {
        value_end++;
    }

    if (value_start == value_end) {
        return defaultValue;
    }

    try {
        return std::stoi(json.substr(value_start, value_end - value_start));
    } catch (...) {
        return defaultValue;
    }
}

bool ConfigManager::extractBoolValue(const std::string& json, const std::string& key, bool defaultValue) {
    std::string search_key = "\"" + key + "\"";
    size_t start_pos = json.find(search_key);
    if (start_pos == std::string::npos) {
        return defaultValue;
    }

    size_t colon_pos = json.find(':', start_pos);
    if (colon_pos == std::string::npos) {
        return defaultValue;
    }

    // 查找true或false
    size_t true_pos = json.find("true", colon_pos);
    size_t false_pos = json.find("false", colon_pos);
    
    // 找到最近的一个
    if (true_pos != std::string::npos && (false_pos == std::string::npos || true_pos < false_pos)) {
        // 确保true不是在其他字符串中
        size_t next_comma = json.find(',', true_pos);
        size_t next_brace = json.find('}', true_pos);
        size_t next_delimiter = std::min(next_comma, next_brace);
        if (next_delimiter == std::string::npos || true_pos + 4 <= next_delimiter) {
            return true;
        }
    }
    
    if (false_pos != std::string::npos) {
        // 确保false不是在其他字符串中
        size_t next_comma = json.find(',', false_pos);
        size_t next_brace = json.find('}', false_pos);
        size_t next_delimiter = std::min(next_comma, next_brace);
        if (next_delimiter == std::string::npos || false_pos + 5 <= next_delimiter) {
            return false;
        }
    }

    return defaultValue;
}

std::string ConfigManager::extractStringValue(const std::string& json, const std::string& key) {
    std::string search_key = "\"" + key + "\"";
    size_t start_pos = json.find(search_key);
    if (start_pos == std::string::npos) {
        return "";
    }

    size_t colon_pos = json.find(':', start_pos);
    if (colon_pos == std::string::npos) {
        return "";
    }

    size_t quote_start = json.find('"', colon_pos);
    if (quote_start == std::string::npos) {
        return "";
    }

    size_t quote_end = json.find('"', quote_start + 1);
    if (quote_end == std::string::npos) {
        return "";
    }

    return json.substr(quote_start + 1, quote_end - quote_start - 1);
}