/**
 * @file dock_info_manager.cc
 * @brief 机场信息管理器 - 获取机场设备信息并设置媒体文件策略
 * @author Celestial
 * @date 2024
 * 
 * 功能说明：
 * 1. 初始化 DJI Edge SDK
 * 2. 获取机场设备信息（产品名称、固件版本、序列号等）
 * 3. 设置媒体文件策略：上传到云端后保留本地数据
 * 4. 显示机场详细信息
 * 5. 监控媒体文件更新通知
 */

#include <stdio.h>
#include <chrono>
#include <iostream>
#include <thread>
#include <string>
#include <memory>
#include <fstream>
#include <ctime>
#include <iomanip>
#include <sstream>
#include <vector>
#include <list>

// DJI Edge SDK 头文件
#include "../../include/logger.h"
#include "../../include/init/esdk_init.h"
#include "../../include/error_code/error_code.h"
#include "../../include/media_manager/media_manager.h"
#include "../../include/media_manager/media_file.h"
#include "../../include/media_manager/media_files_reader.h"

using namespace edge_sdk;

/**
 * @brief 获取当前时间戳字符串
 * @return 格式化的时间戳字符串
 */
std::string GetCurrentTimestamp() {
    auto now = std::chrono::system_clock::now();
    auto time_t = std::chrono::system_clock::to_time_t(now);
    std::stringstream ss;
    ss << std::put_time(std::localtime(&time_t), "%Y-%m-%d %H:%M:%S");
    return ss.str();
}

/**
 * @brief 将机场设备信息写入单独的文件
 * @param esdk_init SDK初始化实例
 * @param filename 输出文件名
 */
void WriteDockInfoToFile(edge_sdk::ESDKInit* esdk_init, const std::string& filename) {
    if (!esdk_init) {
        ERROR("ESDKInit instance is null");
        return;
    }

    std::ofstream info_file(filename);
    if (!info_file.is_open()) {
        ERROR("无法创建机场信息文件: %s", filename.c_str());
        return;
    }

    // 写入文件头部信息
    info_file << "=== DJI 机场设备初始化信息 ===" << std::endl;
    info_file << "生成时间: " << GetCurrentTimestamp() << std::endl;
    info_file << "程序版本: dock_info_manager v1.0" << std::endl;
    info_file << std::endl;
    
    // 获取并写入产品名称
    auto product_name = esdk_init->GetProductName();
    info_file << "产品名称: " << product_name << std::endl;

    // 获取并写入固件版本
    auto firmware_version = esdk_init->GetFirmwareVersion();
    info_file << "固件版本: " << static_cast<int>(firmware_version.major_version) << "."
              << static_cast<int>(firmware_version.minor_version) << "."
              << static_cast<int>(firmware_version.modify_version) << "."
              << static_cast<int>(firmware_version.debug_version) << std::endl;

    // 获取并写入序列号
    auto serial_number = esdk_init->GetSerialNumber();
    info_file << "序列号: " << serial_number << std::endl;

    // 获取并写入厂商名称
    auto vendor_name = esdk_init->GetVendorName();
    info_file << "厂商名称: " << vendor_name << std::endl;

    info_file << std::endl;
    info_file << "=== 设备信息获取完成 ===" << std::endl;
    info_file.close();

    INFO("机场设备信息已保存到文件: %s", filename.c_str());
}

/**
 * @brief 显示机场设备信息（控制台输出）
 * @param esdk_init SDK初始化实例
 */
void DisplayDockInfo(edge_sdk::ESDKInit* esdk_init) {
    if (!esdk_init) {
        ERROR("ESDKInit instance is null");
        return;
    }

    INFO("=== 机场设备信息 ===");
    
    // 获取产品名称
    auto product_name = esdk_init->GetProductName();
    INFO("产品名称: %s", product_name.c_str());

    // 获取固件版本
    auto firmware_version = esdk_init->GetFirmwareVersion();
    INFO("固件版本: %d.%d.%d.%d", 
         firmware_version.major_version,
         firmware_version.minor_version, 
         firmware_version.modify_version,
         firmware_version.debug_version);

    // 获取序列号
    auto serial_number = esdk_init->GetSerialNumber();
    INFO("序列号: %s", serial_number.c_str());

    // 获取厂商名称
    auto vendor_name = esdk_init->GetVendorName();
    INFO("厂商名称: %s", vendor_name.c_str());

    INFO("=== 设备信息获取完成 ===");
}

/**
 * @brief 设置媒体文件策略 - 上传到云端后保留本地数据
 */
void SetMediaFilePolicy() {
    INFO("=== 设置媒体文件策略 ===");
    
    auto media_manager = edge_sdk::MediaManager::Instance();
    if (!media_manager) {
        ERROR("获取MediaManager实例失败");
        return;
    }

    // 设置上传到云端策略：启用上传
    auto rc = media_manager->SetDroneNestUploadCloud(true);
    if (rc == edge_sdk::ErrorCode::kOk) {
        INFO("✓ 已启用媒体文件上传到云端");
    } else {
        ERROR("设置上传云端策略失败: %d", rc);
    }

    // 设置自动删除策略：禁用自动删除（保留本地数据）
    rc = media_manager->SetDroneNestAutoDelete(false);
    if (rc == edge_sdk::ErrorCode::kOk) {
        INFO("✓ 已禁用自动删除，本地数据将被保留");
    } else {
        ERROR("设置自动删除策略失败: %d", rc);
    }

    INFO("=== 媒体文件策略设置完成 ===");
}

/**
 * @brief 将媒体文件保存到指定目录
 * @param filename 文件名
 * @param data 文件数据
 */
void SaveMediaFileToDirectory(const std::string& filename, const std::vector<uint8_t>& data) {
    // 使用 /data/temp/dji/media/ 作为媒体文件存储路径（688G 大容量分区）
    std::string filepath = "/data/temp/dji/media/" + filename;
    FILE* f = fopen(filepath.c_str(), "wb");
    if (f) {
        fwrite(data.data(), data.size(), 1, f);
        fclose(f);
        INFO("媒体文件已保存: %s", filepath.c_str());
    } else {
        ERROR("保存媒体文件失败: %s", filepath.c_str());
    }
}

/**
 * @brief 读取媒体文件内容
 * @param file 媒体文件信息
 * @param image 输出的文件数据
 * @param reader 媒体文件读取器
 * @return 错误码
 */
edge_sdk::ErrorCode ReadMediaFileContent(const edge_sdk::MediaFile& file, 
                                        std::vector<uint8_t>& image,
                                        std::shared_ptr<edge_sdk::MediaFilesReader> reader) {
    char buf[1024 * 1024];
    auto fd = reader->Open(file.file_path);
    if (fd < 0) {
        return edge_sdk::ErrorCode::kErrorSystemError;
    }
    
    do {
        auto nread = reader->Read(fd, buf, sizeof(buf));
        if (nread > 0) {
            image.insert(image.end(), (uint8_t*)buf, (uint8_t*)(buf + nread));
        } else {
            reader->Close(fd);
            break;
        }
    } while (1);
    
    INFO("文件大小: %llu, 读取大小: %zu", file.file_size, image.size());
    return edge_sdk::ErrorCode::kOk;
}

/**
 * @brief 简洁的媒体文件监控日志输出
 * @param file_list 媒体文件列表
 */
void WriteMediaFileLog(const std::list<std::shared_ptr<edge_sdk::MediaFile>>& file_list) {
    std::ofstream log_file("/home/celestial/dev/esdk-test/Edge-SDK/celestial_works/logs/media_monitor.log", std::ios::app);
    if (!log_file.is_open()) {
        ERROR("无法打开媒体监控日志文件");
        return;
    }
    
    log_file << GetCurrentTimestamp() << " - ";
    
    if (file_list.empty()) {
        log_file << "no media files found" << std::endl;
    } else {
        log_file << "媒体文件列表: ";
        bool first = true;
        for (const auto& file_ptr : file_list) {
            if (!first) log_file << ", ";
            log_file << file_ptr->file_name;
            first = false;
        }
        log_file << std::endl;
    }
    
    log_file.close();
}

edge_sdk::ErrorCode OnMediaFileUpdate(const edge_sdk::MediaFile& file) {
    INFO("媒体文件更新通知:");
    INFO("  文件名: %s", file.file_name.c_str());
    INFO("  文件大小: %llu bytes", file.file_size);
    INFO("  创建时间: %ld", file.create_time);
    INFO("  文件类型: %d", static_cast<int>(file.file_type));
    
    // 下载并保存媒体文件到celestial_works/media/目录
    auto media_manager = edge_sdk::MediaManager::Instance();
    if (media_manager) {
        auto reader = media_manager->CreateMediaFilesReader();
        if (reader && reader->Init() == edge_sdk::ErrorCode::kOk) {
            std::vector<uint8_t> file_data;
            auto rc = ReadMediaFileContent(file, file_data, reader);
            if (rc == edge_sdk::ErrorCode::kOk && !file_data.empty()) {
                SaveMediaFileToDirectory(file.file_name, file_data);
                INFO("✓ 媒体文件已下载并保存: %s", file.file_name.c_str());
            } else {
                ERROR("读取媒体文件内容失败: %s", file.file_name.c_str());
            }
            reader->DeInit();
        }
    }
    
    return edge_sdk::ErrorCode::kOk;
}

/**
 * @brief 监控媒体文件更新
 */
void MonitorMediaFiles() {
    INFO("=== 开始监控媒体文件更新 ===");
    
    auto media_manager = edge_sdk::MediaManager::Instance();
    if (!media_manager) {
        ERROR("获取MediaManager实例失败");
        return;
    }

    // 注册媒体文件更新回调
    auto rc = media_manager->RegisterMediaFilesObserver(OnMediaFileUpdate);
    if (rc == edge_sdk::ErrorCode::kOk) {
        INFO("✓ 媒体文件更新监控已启动");
    } else {
        ERROR("注册媒体文件更新回调失败: %d", rc);
    }

    // 获取当前媒体文件列表
    auto reader = media_manager->CreateMediaFilesReader();
    if (reader) {
        reader->Init();
        std::list<std::shared_ptr<edge_sdk::MediaFile>> file_list;
        int32_t file_count = reader->FileList(file_list);
        if (file_count >= 0) {
            INFO("当前媒体文件数量: %d", file_count);
            for (const auto& file_ptr : file_list) {
                INFO("  - %s (%llu bytes)", file_ptr->file_name.c_str(), file_ptr->file_size);
            }
            // 写入简洁的媒体文件监控日志
            WriteMediaFileLog(file_list);
        } else {
            ERROR("获取媒体文件列表失败: %d", file_count);
            // 即使获取失败，也记录到日志
            std::list<std::shared_ptr<edge_sdk::MediaFile>> empty_list;
            WriteMediaFileLog(empty_list);
        }
        reader->DeInit();
    }
}

/**
 * @brief 主函数
 */
int main(int argc, char** argv) {
    INFO("=== DJI 机场信息管理器启动 ===");

    // 初始化 SDK
    auto esdk_init = edge_sdk::ESDKInit::Instance();
    if (!esdk_init) {
        ERROR("获取ESDKInit实例失败");
        return -1;
    }

    // 调用外部的ESDKInit函数进行初始化
    extern edge_sdk::ErrorCode ESDKInit();
    auto rc = ESDKInit();
    if (rc != edge_sdk::ErrorCode::kOk) {
        ERROR("SDK初始化失败: %d", rc);
        return -1;
    }
    INFO("✓ SDK初始化成功");

    // 将机场设备信息写入单独文件（输出到logs目录）
    WriteDockInfoToFile(esdk_init, "/home/celestial/dev/esdk-test/Edge-SDK/celestial_works/logs/dock_init_info.txt");
    
    // 同时在控制台显示机场设备信息
    DisplayDockInfo(esdk_init);

    // 设置媒体文件策略
    SetMediaFilePolicy();

    // 监控媒体文件更新
    MonitorMediaFiles();

    // 保持程序运行，持续监控媒体文件更新
    INFO("程序正在运行中，持续监控媒体文件更新...");
    INFO("按 Ctrl+C 退出程序");
    auto media_manager = edge_sdk::MediaManager::Instance();
    
    int monitor_count = 0;
    while (true) {
        std::this_thread::sleep_for(std::chrono::seconds(5));
        monitor_count++;
        INFO("系统运行正常，继续监控中... (第%d次检查)", monitor_count);
        
        // 每5秒检查一次媒体文件并记录到简洁日志
        if (media_manager) {
            auto reader = media_manager->CreateMediaFilesReader();
            if (reader) {
                reader->Init();
                std::list<std::shared_ptr<edge_sdk::MediaFile>> file_list;
                int32_t file_count = reader->FileList(file_list);
                if (file_count >= 0) {
                    WriteMediaFileLog(file_list);
                } else {
                    std::list<std::shared_ptr<edge_sdk::MediaFile>> empty_list;
                    WriteMediaFileLog(empty_list);
                }
                reader->DeInit();
            }
        }
    }

    INFO("=== 程序退出 ===");
    
    // 注意：MediaManager没有提供取消注册回调的方法
    // 参考官方示例，不调用ESDKDeInit()以避免SDK内部线程清理时序问题
    // SDK会在程序退出时自动清理资源，包括已注册的回调函数
    
    return 0;
}