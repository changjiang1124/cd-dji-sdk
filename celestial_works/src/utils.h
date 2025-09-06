#ifndef UTILS_H
#define UTILS_H

#include <string>
#include <vector>
#include <fstream>
#include <memory>
#include <chrono>

#if __cplusplus >= 201703L
#include <filesystem>
namespace fs = std::filesystem;
#else
#include <experimental/filesystem>
namespace fs = std::experimental::filesystem;
#endif

/**
 * 工具类库 - 提供MD5计算、文件操作、网络工具等辅助功能
 * 替代chunk_transfer_manager中的内联实现，提供更好的模块化和可测试性
 */

namespace utils {

// ============================================================================
// 哈希计算工具类
// ============================================================================

class HashCalculator {
public:
    /**
     * 计算文件的MD5哈希值
     * @param file_path 文件路径
     * @return MD5哈希值的十六进制字符串，失败返回空字符串
     */
    static std::string CalculateFileMD5(const std::string& file_path);
    
    /**
     * 计算文件指定范围的MD5哈希值
     * @param file_path 文件路径
     * @param offset 起始偏移量
     * @param size 计算大小
     * @return MD5哈希值的十六进制字符串，失败返回空字符串
     */
    static std::string CalculateRangeMD5(const std::string& file_path, 
                                         size_t offset, size_t size);
    
    /**
     * 计算数据块的MD5哈希值
     * @param data 数据指针
     * @param size 数据大小
     * @return MD5哈希值的十六进制字符串
     */
    static std::string CalculateDataMD5(const void* data, size_t size);
    
    /**
     * 验证文件的MD5哈希值
     * @param file_path 文件路径
     * @param expected_hash 期望的哈希值
     * @return 验证是否通过
     */
    static bool VerifyFileMD5(const std::string& file_path, 
                              const std::string& expected_hash);

private:
    // 内部MD5计算实现（使用现代C++替代OpenSSL deprecated接口）
    static std::string MD5ToHexString(const unsigned char* digest);
};

// ============================================================================
// 文件操作工具类
// ============================================================================

class FileUtils {
public:
    /**
     * 安全地创建目录（递归创建）
     * @param dir_path 目录路径
     * @return 创建是否成功
     */
    static bool CreateDirectories(const std::string& dir_path);
    
    /**
     * 检查文件是否存在且可读
     * @param file_path 文件路径
     * @return 文件是否存在且可读
     */
    static bool IsFileReadable(const std::string& file_path);
    
    /**
     * 检查目录是否存在且可写
     * @param dir_path 目录路径
     * @return 目录是否存在且可写
     */
    static bool IsDirectoryWritable(const std::string& dir_path);
    
    /**
     * 获取文件大小
     * @param file_path 文件路径
     * @return 文件大小，失败返回0
     */
    static size_t GetFileSize(const std::string& file_path);
    
    /**
     * 复制文件
     * @param source_path 源文件路径
     * @param dest_path 目标文件路径
     * @param overwrite 是否覆盖已存在的文件
     * @return 复制是否成功
     */
    static bool CopyFile(const std::string& source_path, 
                        const std::string& dest_path, 
                        bool overwrite = false);
    
    /**
     * 移动文件
     * @param source_path 源文件路径
     * @param dest_path 目标文件路径
     * @return 移动是否成功
     */
    static bool MoveFile(const std::string& source_path, 
                        const std::string& dest_path);
    
    /**
     * 删除文件
     * @param file_path 文件路径
     * @return 删除是否成功
     */
    static bool DeleteFile(const std::string& file_path);
    
    /**
     * 读取文件内容到内存
     * @param file_path 文件路径
     * @param offset 起始偏移量
     * @param size 读取大小，0表示读取到文件末尾
     * @return 文件内容，失败返回空vector
     */
    static std::vector<char> ReadFileContent(const std::string& file_path, 
                                            size_t offset = 0, 
                                            size_t size = 0);
    
    /**
     * 将数据写入文件
     * @param file_path 文件路径
     * @param data 数据指针
     * @param size 数据大小
     * @param append 是否追加模式
     * @return 写入是否成功
     */
    static bool WriteFileContent(const std::string& file_path, 
                               const void* data, 
                               size_t size, 
                               bool append = false);
    
    /**
     * 获取临时文件路径
     * @param prefix 文件名前缀
     * @param suffix 文件名后缀
     * @return 临时文件路径
     */
    static std::string GetTempFilePath(const std::string& prefix = "temp", 
                                      const std::string& suffix = ".tmp");
    
    /**
     * 清理匹配模式的文件
     * @param directory 目录路径
     * @param pattern 文件名模式（支持通配符）
     * @return 清理的文件数量
     */
    static int CleanupFiles(const std::string& directory, 
                           const std::string& pattern);
};

// ============================================================================
// 网络工具类
// ============================================================================

class NetworkUtils {
public:
    /**
     * 检查网络连接是否可用
     * @param host 主机地址
     * @param port 端口号
     * @param timeout_ms 超时时间（毫秒）
     * @return 连接是否可用
     */
    static bool IsNetworkReachable(const std::string& host, 
                                  int port, 
                                  int timeout_ms = 5000);
    
    /**
     * 获取本机IP地址
     * @return IP地址列表
     */
    static std::vector<std::string> GetLocalIPAddresses();
    
    /**
     * 解析URL
     * @param url 完整URL
     * @param protocol 协议（输出参数）
     * @param host 主机（输出参数）
     * @param port 端口（输出参数）
     * @param path 路径（输出参数）
     * @return 解析是否成功
     */
    static bool ParseURL(const std::string& url, 
                        std::string& protocol, 
                        std::string& host, 
                        int& port, 
                        std::string& path);
    
    /**
     * 计算网络传输速度
     * @param bytes_transferred 已传输字节数
     * @param start_time 开始时间
     * @return 传输速度（字节/秒）
     */
    static double CalculateTransferSpeed(size_t bytes_transferred, 
                                       const std::chrono::steady_clock::time_point& start_time);
    
    /**
     * 格式化传输速度为人类可读格式
     * @param bytes_per_second 字节/秒
     * @return 格式化的速度字符串（如 "1.5 MB/s"）
     */
    static std::string FormatTransferSpeed(double bytes_per_second);
};

// ============================================================================
// 字符串工具类
// ============================================================================

class StringUtils {
public:
    /**
     * 去除字符串首尾空白字符
     * @param str 输入字符串
     * @return 处理后的字符串
     */
    static std::string Trim(const std::string& str);
    
    /**
     * 分割字符串
     * @param str 输入字符串
     * @param delimiter 分隔符
     * @return 分割后的字符串列表
     */
    static std::vector<std::string> Split(const std::string& str, 
                                         const std::string& delimiter);
    
    /**
     * 连接字符串列表
     * @param strings 字符串列表
     * @param delimiter 分隔符
     * @return 连接后的字符串
     */
    static std::string Join(const std::vector<std::string>& strings, 
                           const std::string& delimiter);
    
    /**
     * 字符串转小写
     * @param str 输入字符串
     * @return 小写字符串
     */
    static std::string ToLower(const std::string& str);
    
    /**
     * 字符串转大写
     * @param str 输入字符串
     * @return 大写字符串
     */
    static std::string ToUpper(const std::string& str);
    
    /**
     * 检查字符串是否以指定前缀开始
     * @param str 输入字符串
     * @param prefix 前缀
     * @return 是否以前缀开始
     */
    static bool StartsWith(const std::string& str, const std::string& prefix);
    
    /**
     * 检查字符串是否以指定后缀结束
     * @param str 输入字符串
     * @param suffix 后缀
     * @return 是否以后缀结束
     */
    static bool EndsWith(const std::string& str, const std::string& suffix);
    
    /**
     * 格式化文件大小为人类可读格式
     * @param bytes 字节数
     * @return 格式化的大小字符串（如 "1.5 GB"）
     */
    static std::string FormatFileSize(size_t bytes);
    
    /**
     * 格式化时间间隔为人类可读格式
     * @param seconds 秒数
     * @return 格式化的时间字符串（如 "2h 30m 15s"）
     */
    static std::string FormatDuration(int seconds);
};

// ============================================================================
// 时间工具类
// ============================================================================

class TimeUtils {
public:
    /**
     * 获取当前时间戳字符串
     * @param format 时间格式，默认为 ISO 8601 格式
     * @return 时间戳字符串
     */
    static std::string GetCurrentTimestamp(const std::string& format = "%Y-%m-%d %H:%M:%S");
    
    /**
     * 获取当前Unix时间戳
     * @return Unix时间戳（秒）
     */
    static int64_t GetCurrentUnixTimestamp();
    
    /**
     * 计算时间差（毫秒）
     * @param start_time 开始时间
     * @param end_time 结束时间，默认为当前时间
     * @return 时间差（毫秒）
     */
    static int64_t GetElapsedMilliseconds(
        const std::chrono::steady_clock::time_point& start_time,
        const std::chrono::steady_clock::time_point& end_time = std::chrono::steady_clock::now());
    
    /**
     * 休眠指定毫秒数
     * @param milliseconds 毫秒数
     */
    static void SleepMilliseconds(int milliseconds);
};

} // namespace utils

#endif // UTILS_H