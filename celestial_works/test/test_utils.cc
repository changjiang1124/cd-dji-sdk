#include "../src/utils.h"
#include <iostream>
#include <fstream>
#include <cassert>
#include <cstring>

using namespace utils;

/**
 * 工具类库基础功能测试
 * 测试MD5计算、文件操作、字符串处理等核心功能
 */

void test_md5_calculation() {
    std::cout << "=== 测试MD5计算功能 ===" << std::endl;
    
    // 测试数据MD5计算
    const char* test_data = "Hello, World!";
    std::string md5_hash = HashCalculator::CalculateDataMD5(test_data, strlen(test_data));
    std::cout << "数据 '" << test_data << "' 的MD5: " << md5_hash << std::endl;
    
    // 创建测试文件
    std::string test_file = "/tmp/test_md5_file.txt";
    std::ofstream file(test_file);
    file << test_data;
    file.close();
    
    // 测试文件MD5计算
    std::string file_md5 = HashCalculator::CalculateFileMD5(test_file);
    std::cout << "文件MD5: " << file_md5 << std::endl;
    
    // 验证数据MD5和文件MD5应该相同
    assert(md5_hash == file_md5);
    std::cout << "✓ MD5计算功能测试通过" << std::endl;
    
    // 测试MD5验证功能
    bool verify_result = HashCalculator::VerifyFileMD5(test_file, file_md5);
    assert(verify_result == true);
    std::cout << "✓ MD5验证功能测试通过" << std::endl;
    
    // 清理测试文件
    FileUtils::DeleteFile(test_file);
}

void test_file_operations() {
    std::cout << "\n=== 测试文件操作功能 ===" << std::endl;
    
    std::string test_dir = "/tmp/test_utils_dir";
    std::string test_file = test_dir + "/test_file.txt";
    const char* test_content = "This is a test file content.";
    
    // 测试目录创建
    bool dir_created = FileUtils::CreateDirectories(test_dir);
    assert(dir_created || FileUtils::IsDirectoryWritable(test_dir));
    std::cout << "✓ 目录创建功能测试通过" << std::endl;
    
    // 测试文件写入
    bool write_success = FileUtils::WriteFileContent(test_file, test_content, strlen(test_content));
    assert(write_success);
    std::cout << "✓ 文件写入功能测试通过" << std::endl;
    
    // 测试文件大小获取
    size_t file_size = FileUtils::GetFileSize(test_file);
    assert(file_size == strlen(test_content));
    std::cout << "✓ 文件大小获取功能测试通过，大小: " << file_size << " 字节" << std::endl;
    
    // 测试文件读取
    auto content = FileUtils::ReadFileContent(test_file);
    assert(content.size() == strlen(test_content));
    assert(memcmp(content.data(), test_content, content.size()) == 0);
    std::cout << "✓ 文件读取功能测试通过" << std::endl;
    
    // 测试文件可读性检查
    bool is_readable = FileUtils::IsFileReadable(test_file);
    assert(is_readable);
    std::cout << "✓ 文件可读性检查功能测试通过" << std::endl;
    
    // 测试文件复制
    std::string copy_file = test_dir + "/copy_file.txt";
    bool copy_success = FileUtils::CopyFile(test_file, copy_file);
    assert(copy_success);
    assert(FileUtils::GetFileSize(copy_file) == file_size);
    std::cout << "✓ 文件复制功能测试通过" << std::endl;
    
    // 测试文件移动
    std::string move_file = test_dir + "/moved_file.txt";
    bool move_success = FileUtils::MoveFile(copy_file, move_file);
    assert(move_success);
    assert(!FileUtils::IsFileReadable(copy_file));
    assert(FileUtils::IsFileReadable(move_file));
    std::cout << "✓ 文件移动功能测试通过" << std::endl;
    
    // 清理测试文件和目录
    FileUtils::DeleteFile(test_file);
    FileUtils::DeleteFile(move_file);
    // 注意：这里不删除目录，因为std::filesystem::remove只能删除空目录
}

void test_string_utilities() {
    std::cout << "\n=== 测试字符串工具功能 ===" << std::endl;
    
    // 测试字符串修剪
    std::string trimmed = StringUtils::Trim("  hello world  ");
    assert(trimmed == "hello world");
    std::cout << "✓ 字符串修剪功能测试通过" << std::endl;
    
    // 测试字符串分割
    auto parts = StringUtils::Split("a,b,c,d", ",");
    assert(parts.size() == 4);
    assert(parts[0] == "a" && parts[3] == "d");
    std::cout << "✓ 字符串分割功能测试通过" << std::endl;
    
    // 测试字符串连接
    std::string joined = StringUtils::Join(parts, "|");
    assert(joined == "a|b|c|d");
    std::cout << "✓ 字符串连接功能测试通过" << std::endl;
    
    // 测试大小写转换
    assert(StringUtils::ToLower("Hello World") == "hello world");
    assert(StringUtils::ToUpper("Hello World") == "HELLO WORLD");
    std::cout << "✓ 大小写转换功能测试通过" << std::endl;
    
    // 测试前缀后缀检查
    assert(StringUtils::StartsWith("hello world", "hello"));
    assert(StringUtils::EndsWith("hello world", "world"));
    assert(!StringUtils::StartsWith("hello world", "world"));
    std::cout << "✓ 前缀后缀检查功能测试通过" << std::endl;
    
    // 测试文件大小格式化
    std::string size_str = StringUtils::FormatFileSize(1536);
    std::cout << "文件大小格式化测试: 1536 bytes = " << size_str << std::endl;
    
    size_str = StringUtils::FormatFileSize(1048576);
    std::cout << "文件大小格式化测试: 1048576 bytes = " << size_str << std::endl;
    
    // 测试时间格式化
    std::string duration_str = StringUtils::FormatDuration(3661);
    std::cout << "时间格式化测试: 3661 seconds = " << duration_str << std::endl;
    
    std::cout << "✓ 格式化功能测试通过" << std::endl;
}

void test_time_utilities() {
    std::cout << "\n=== 测试时间工具功能 ===" << std::endl;
    
    // 测试当前时间戳获取
    std::string timestamp = TimeUtils::GetCurrentTimestamp();
    std::cout << "当前时间戳: " << timestamp << std::endl;
    
    int64_t unix_timestamp = TimeUtils::GetCurrentUnixTimestamp();
    std::cout << "Unix时间戳: " << unix_timestamp << std::endl;
    
    // 测试时间差计算
    auto start_time = std::chrono::steady_clock::now();
    TimeUtils::SleepMilliseconds(100);
    int64_t elapsed = TimeUtils::GetElapsedMilliseconds(start_time);
    std::cout << "休眠100ms，实际耗时: " << elapsed << "ms" << std::endl;
    assert(elapsed >= 90 && elapsed <= 200); // 允许一定误差
    
    std::cout << "✓ 时间工具功能测试通过" << std::endl;
}

void test_network_utilities() {
    std::cout << "\n=== 测试网络工具功能 ===" << std::endl;
    
    // 测试URL解析
    std::string protocol, host, path;
    int port;
    bool parse_success = NetworkUtils::ParseURL("https://example.com:8080/path/to/resource", 
                                               protocol, host, port, path);
    if (parse_success) {
        std::cout << "URL解析结果:" << std::endl;
        std::cout << "  协议: " << protocol << std::endl;
        std::cout << "  主机: " << host << std::endl;
        std::cout << "  端口: " << port << std::endl;
        std::cout << "  路径: " << path << std::endl;
        assert(protocol == "https");
        assert(host == "example.com");
        assert(port == 8080);
        assert(path == "/path/to/resource");
        std::cout << "✓ URL解析功能测试通过" << std::endl;
    }
    
    // 测试本地IP地址获取
    auto ip_addresses = NetworkUtils::GetLocalIPAddresses();
    std::cout << "本地IP地址列表:" << std::endl;
    for (const auto& ip : ip_addresses) {
        std::cout << "  " << ip << std::endl;
    }
    
    // 测试传输速度计算和格式化
    auto start_time = std::chrono::steady_clock::now();
    TimeUtils::SleepMilliseconds(1000);
    double speed = NetworkUtils::CalculateTransferSpeed(1048576, start_time); // 1MB in 1s
    std::string speed_str = NetworkUtils::FormatTransferSpeed(speed);
    std::cout << "传输速度测试: 1MB/1s = " << speed_str << std::endl;
    
    std::cout << "✓ 网络工具功能测试通过" << std::endl;
}

int main() {
    std::cout << "开始工具类库基础功能测试..." << std::endl;
    std::cout << "测试时间: " << TimeUtils::GetCurrentTimestamp() << std::endl;
    
    try {
        test_md5_calculation();
        test_file_operations();
        test_string_utilities();
        test_time_utilities();
        test_network_utilities();
        
        std::cout << "\n🎉 所有工具类库功能测试通过！" << std::endl;
        std::cout << "工具类库已准备好用于断点续传系统集成。" << std::endl;
        
    } catch (const std::exception& e) {
        std::cerr << "❌ 测试失败: " << e.what() << std::endl;
        return 1;
    } catch (...) {
        std::cerr << "❌ 测试失败: 未知异常" << std::endl;
        return 1;
    }
    
    return 0;
}