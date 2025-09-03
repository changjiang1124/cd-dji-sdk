#!/usr/bin/env python3
"""
Media Finding Daemon 测试脚本

功能：
1. 文件过滤策略测试
2. 传输流程测试
3. 性能基准测试
4. 配置文件验证
5. 数据库操作测试

作者: Edge-SDK Team
版本: 1.0.0
"""

import os
import sys
import time
import json
import tempfile
import shutil
import sqlite3
import hashlib
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from media_finding_daemon import MediaFindingDaemon, FileStatus
from config_manager import ConfigManager
from media_status_db import MediaStatusDB

class TestMediaFindingDaemon(unittest.TestCase):
    """Media Finding Daemon 测试类"""
    
    def setUp(self):
        """测试前准备"""
        # 创建临时目录
        self.test_dir = tempfile.mkdtemp(prefix='media_daemon_test_')
        self.media_dir = os.path.join(self.test_dir, 'media')
        self.log_dir = os.path.join(self.test_dir, 'logs')
        self.db_path = os.path.join(self.test_dir, 'test_media.db')
        
        os.makedirs(self.media_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)
        
        # 创建测试配置
        self.config_path = os.path.join(self.test_dir, 'test_config.json')
        self._create_test_config()
        
        # 创建daemon实例
        self.daemon = MediaFindingDaemon(config_path=self.config_path)
    
    def tearDown(self):
        """测试后清理"""
        # 关闭数据库连接
        if hasattr(self.daemon, 'db'):
            self.daemon.db.close()
        
        # 删除临时目录
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def _create_test_config(self):
        """创建测试配置文件"""
        config = {
            "local_settings": {
                "media_directory": self.media_dir,
                "media_path": self.media_dir,
                "temp_path": "/tmp/media",
                "log_path": self.log_dir
            },
            "database": {
                "path": self.db_path
            },
            "logging": {
                "media_finding_log": os.path.join(self.log_dir, "test.log"),
                "level": "DEBUG"
            },
            "file_sync": {
                "filter_strategy": "extended",
                "custom_extensions": [".mp4", ".jpg", ".txt"],
                "exclude_patterns": [".*", ".tmp_*", "*.tmp"]
            },
            "transfer": {
                "scan_interval": 1,
                "batch_size": 5
            },
            "nas": {
                "host": "test-nas",
                "username": "test",
                "password": "test",
                "destination_path": "/test"
            }
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)
    
    def _create_test_file(self, filename: str, content: str = "test content") -> str:
        """创建测试文件"""
        file_path = os.path.join(self.media_dir, filename)
        with open(file_path, 'w') as f:
            f.write(content)
        return file_path
    
    def _create_binary_test_file(self, filename: str, size_mb: int = 1) -> str:
        """创建二进制测试文件"""
        file_path = os.path.join(self.media_dir, filename)
        with open(file_path, 'wb') as f:
            # 写入指定大小的随机数据
            data = os.urandom(size_mb * 1024 * 1024)
            f.write(data)
        return file_path

class TestFileFiltering(TestMediaFindingDaemon):
    """文件过滤策略测试"""
    
    def test_media_only_strategy(self):
        """测试仅媒体文件策略"""
        self.daemon.filter_strategy = 'media_only'
        
        # 应该被处理的文件
        self.assertTrue(self.daemon._should_process_file('video.mp4'))
        self.assertTrue(self.daemon._should_process_file('photo.jpg'))
        self.assertTrue(self.daemon._should_process_file('image.png'))
        
        # 不应该被处理的文件
        self.assertFalse(self.daemon._should_process_file('document.txt'))
        self.assertFalse(self.daemon._should_process_file('data.csv'))
        self.assertFalse(self.daemon._should_process_file('archive.zip'))
    
    def test_extended_strategy(self):
        """测试扩展文件类型策略"""
        self.daemon.filter_strategy = 'extended'
        
        # 媒体文件
        self.assertTrue(self.daemon._should_process_file('video.mp4'))
        self.assertTrue(self.daemon._should_process_file('photo.jpg'))
        
        # 文档文件
        self.assertTrue(self.daemon._should_process_file('document.txt'))
        self.assertTrue(self.daemon._should_process_file('data.csv'))
        
        # 数据文件
        self.assertTrue(self.daemon._should_process_file('survey.las'))
        self.assertTrue(self.daemon._should_process_file('config.json'))
        
        # 无扩展名文件
        self.assertTrue(self.daemon._should_process_file('README'))
    
    def test_all_files_strategy(self):
        """测试同步所有文件策略"""
        self.daemon.filter_strategy = 'all_files'
        
        # 所有文件都应该被处理（除了排除模式）
        self.assertTrue(self.daemon._should_process_file('video.mp4'))
        self.assertTrue(self.daemon._should_process_file('document.txt'))
        self.assertTrue(self.daemon._should_process_file('unknown.xyz'))
        self.assertTrue(self.daemon._should_process_file('no_extension'))
    
    def test_exclude_patterns(self):
        """测试排除模式"""
        # 隐藏文件
        self.assertFalse(self.daemon._should_process_file('.hidden'))
        self.assertFalse(self.daemon._should_process_file('.DS_Store'))
        
        # 临时文件
        self.assertFalse(self.daemon._should_process_file('.tmp_video.mp4'))
        self.assertFalse(self.daemon._should_process_file('temp.tmp'))
        
        # 系统文件
        self.assertFalse(self.daemon._should_process_file('Thumbs.db'))
        self.assertFalse(self.daemon._should_process_file('desktop.ini'))
    
    def test_custom_strategy(self):
        """测试自定义扩展名策略"""
        self.daemon.filter_strategy = 'custom'
        self.daemon.custom_extensions = {'.mp4', '.txt', '.las'}
        
        # 自定义扩展名
        self.assertTrue(self.daemon._should_process_file('video.mp4'))
        self.assertTrue(self.daemon._should_process_file('document.txt'))
        self.assertTrue(self.daemon._should_process_file('survey.las'))
        
        # 非自定义扩展名
        self.assertFalse(self.daemon._should_process_file('photo.jpg'))
        self.assertFalse(self.daemon._should_process_file('data.csv'))

class TestFileDiscovery(TestMediaFindingDaemon):
    """文件发现测试"""
    
    def test_scan_empty_directory(self):
        """测试扫描空目录"""
        # 使用已存在的测试配置创建daemon
        daemon = MediaFindingDaemon(self.config_path)
        files = daemon._scan_media_directory()
        self.assertEqual(len(files), 0)
    
    def test_scan_with_files(self):
        """测试扫描包含文件的目录"""
        # 创建测试文件
        self._create_test_file('video.mp4')
        self._create_test_file('photo.jpg')
        self._create_test_file('document.txt')
        self._create_test_file('.hidden.mp4')  # 应该被排除
        
        # 使用已存在的测试配置创建daemon
        daemon = MediaFindingDaemon(self.config_path)
        files = daemon._scan_media_directory()
        
        # 验证文件数量（排除隐藏文件）
        self.assertEqual(len(files), 3)
        
        # 验证文件路径
        filenames = [os.path.basename(f) for f in files]
        self.assertIn('video.mp4', filenames)
        self.assertIn('photo.jpg', filenames)
        self.assertIn('document.txt', filenames)
        self.assertNotIn('.hidden.mp4', filenames)

class TestHashCalculation(TestMediaFindingDaemon):
    """哈希计算测试"""
    
    def test_small_file_hash(self):
        """测试小文件哈希计算"""
        content = "test content for small file"
        file_path = self._create_test_file('small.txt', content)
        
        # 使用已存在的测试配置创建daemon
        daemon = MediaFindingDaemon(self.config_path)
        
        # 计算哈希
        file_hash = daemon._calculate_file_hash(file_path)
        
        # 验证哈希不为空
        self.assertIsNotNone(file_hash)
        self.assertTrue(len(file_hash) > 0)
        
        # 验证哈希一致性
        file_hash2 = daemon._calculate_file_hash(file_path)
        self.assertEqual(file_hash, file_hash2)
    
    def test_large_file_hash(self):
        """测试大文件哈希计算（采样模式）"""
        # 创建大文件（150MB，触发采样哈希）
        file_path = self._create_binary_test_file('large.bin', 150)
        
        # 使用已存在的测试配置创建daemon
        daemon = MediaFindingDaemon(self.config_path)
        
        start_time = time.time()
        file_hash = daemon._calculate_file_hash(file_path)
        duration = time.time() - start_time
        
        # 验证哈希计算成功
        self.assertIsNotNone(file_hash)
        self.assertTrue(len(file_hash) > 0)
        
        # 验证计算时间合理（应该很快，因为是采样哈希）
        self.assertLess(duration, 5.0)  # 应该在5秒内完成
        
        print(f"大文件哈希计算耗时: {duration:.2f}秒")
    
    def test_hash_consistency(self):
        """测试哈希一致性"""
        content = "consistent content"
        file_path1 = self._create_test_file('file1.txt', content)
        file_path2 = self._create_test_file('file2.txt', content)
        
        # 使用已存在的测试配置创建daemon
        daemon = MediaFindingDaemon(self.config_path)
        
        hash1 = daemon._calculate_file_hash(file_path1)
        hash2 = daemon._calculate_file_hash(file_path2)
        
        # 相同内容应该产生相同哈希
        self.assertEqual(hash1, hash2)

class TestDatabaseOperations(TestMediaFindingDaemon):
    """数据库操作测试"""
    
    def test_file_registration(self):
        """测试文件注册"""
        # 创建测试文件
        file_path = self._create_test_file('test.mp4')
        
        # 模拟文件发现和注册过程
        with patch.object(self.daemon, '_transfer_file_to_nas', return_value=True):
            self.daemon.discover_and_register_files()
        
        # 验证文件已注册到数据库
        pending_files = self.daemon.db.get_files_by_status(FileStatus.PENDING.value)
        self.assertEqual(len(pending_files), 1)
        self.assertEqual(pending_files[0]['filename'], 'test.mp4')
    
    def test_duplicate_file_handling(self):
        """测试重复文件处理"""
        # 创建测试文件
        file_path = self._create_test_file('duplicate.mp4')
        
        # 第一次注册
        with patch.object(self.daemon, '_transfer_file_to_nas', return_value=True):
            self.daemon.discover_and_register_files()
        
        # 第二次注册（应该跳过）
        with patch.object(self.daemon, '_transfer_file_to_nas', return_value=True):
            self.daemon.discover_and_register_files()
        
        # 验证只有一条记录
        all_files = self.daemon.db.get_all_files()
        duplicate_files = [f for f in all_files if f['filename'] == 'duplicate.mp4']
        self.assertEqual(len(duplicate_files), 1)
    
    def test_transfer_status_update(self):
        """测试传输状态更新"""
        # 创建测试文件并注册
        file_path = self._create_test_file('status_test.mp4')
        
        with patch.object(self.daemon, '_transfer_file_to_nas', return_value=True):
            self.daemon.discover_and_register_files()
            self.daemon.process_pending_files()
        
        # 验证状态已更新为TRANSFERRED
        transferred_files = self.daemon.db.get_files_by_status(FileStatus.TRANSFERRED.value)
        self.assertEqual(len(transferred_files), 1)
        self.assertEqual(transferred_files[0]['filename'], 'status_test.mp4')

class TestPerformance(TestMediaFindingDaemon):
    """性能测试"""
    
    def test_batch_processing_performance(self):
        """测试批量处理性能"""
        # 创建多个测试文件
        file_count = 20
        for i in range(file_count):
            self._create_test_file(f'batch_test_{i:03d}.mp4')
        
        # 测试文件发现性能
        start_time = time.time()
        files = self.daemon._scan_media_directory()
        scan_duration = time.time() - start_time
        
        self.assertEqual(len(files), file_count)
        print(f"扫描{file_count}个文件耗时: {scan_duration:.3f}秒")
        
        # 测试批量注册性能
        start_time = time.time()
        with patch.object(self.daemon, '_transfer_file_to_nas', return_value=True):
            self.daemon.discover_and_register_files()
        register_duration = time.time() - start_time
        
        print(f"注册{file_count}个文件耗时: {register_duration:.3f}秒")
        
        # 验证性能合理
        self.assertLess(scan_duration, 2.0)  # 扫描应该在2秒内完成
        self.assertLess(register_duration, 10.0)  # 注册应该在10秒内完成

class TestConfigValidation(TestMediaFindingDaemon):
    """配置验证测试"""
    
    def test_config_loading(self):
        """测试配置加载"""
        # 验证配置正确加载
        self.assertEqual(self.daemon.media_directory, self.media_dir)
        self.assertEqual(self.daemon.db_path, self.db_path)
        self.assertEqual(self.daemon.filter_strategy, 'extended')
        
        # 验证配置管理器
        self.assertIsNotNone(self.daemon.config_manager)
        
        # 验证关键配置项
        media_dir = self.daemon.config_manager.get('local_settings.media_directory')
        self.assertEqual(media_dir, self.media_dir)
    
    def test_invalid_config(self):
        """测试无效配置处理"""
        # 创建无效配置文件
        invalid_config_path = os.path.join(self.test_dir, 'invalid_config.json')
        with open(invalid_config_path, 'w') as f:
            f.write('{invalid json}')
        
        # ConfigManager 会使用默认配置，不会抛出异常
        # 验证daemon可以正常创建（使用默认配置）
        try:
            daemon = MediaFindingDaemon(config_path=invalid_config_path)
            self.assertIsNotNone(daemon)
            # 关闭数据库连接
            daemon.db.close()
        except Exception as e:
            # 如果配置文件无效，应该能够处理异常
            self.assertIsInstance(e, (json.JSONDecodeError, FileNotFoundError))

def run_integration_test():
    """运行集成测试"""
    print("\n=== Media Finding Daemon 集成测试 ===")
    
    # 创建临时测试环境
    test_dir = tempfile.mkdtemp(prefix='integration_test_')
    media_dir = os.path.join(test_dir, 'media')
    os.makedirs(media_dir, exist_ok=True)
    
    try:
        # 创建测试配置
        config_path = os.path.join(test_dir, 'config.json')
        config = {
            "local_settings": {
                "media_directory": media_dir,
                "media_path": media_dir,
                "temp_path": "/tmp/media",
                "log_path": os.path.join(test_dir, "logs")
            },
            "database": {"path": os.path.join(test_dir, "test.db")},
            "logging": {
                "media_finding_log": os.path.join(test_dir, "test.log"),
                "level": "INFO"
            },
            "file_sync": {"filter_strategy": "extended"},
            "transfer": {"scan_interval": 1, "batch_size": 5},
            "nas": {"host": "test", "username": "test", "password": "", "destination_path": "/test"}
        }
        
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        # 创建测试文件
        test_files = [
            'video1.mp4', 'video2.mov', 'photo1.jpg', 'photo2.png',
            'document.txt', 'data.csv', 'survey.las', '.hidden.mp4'
        ]
        
        for filename in test_files:
            file_path = os.path.join(media_dir, filename)
            with open(file_path, 'w') as f:
                f.write(f"Test content for {filename}")
        
        # 创建daemon并运行一次周期
        daemon = MediaFindingDaemon(config_path=config_path)
        
        with patch.object(daemon, '_transfer_file_to_nas', return_value=True):
            daemon.run_cycle()
        
        # 验证结果
        all_files = daemon.db.get_all_files()
        processed_files = [f['filename'] for f in all_files]
        
        print(f"处理的文件: {processed_files}")
        
        # 验证隐藏文件被排除
        assert '.hidden.mp4' not in processed_files, "隐藏文件应该被排除"
        
        # 验证其他文件被处理
        expected_files = ['video1.mp4', 'video2.mov', 'photo1.jpg', 'photo2.png', 'document.txt', 'data.csv', 'survey.las']
        for expected_file in expected_files:
            assert expected_file in processed_files, f"文件 {expected_file} 应该被处理"
        
        print("✅ 集成测试通过")
        
        # 关闭数据库连接
        daemon.db.close()
        
    finally:
        # 清理测试环境
        shutil.rmtree(test_dir, ignore_errors=True)

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Media Finding Daemon 测试脚本')
    parser.add_argument('--unit', action='store_true', help='运行单元测试')
    parser.add_argument('--integration', action='store_true', help='运行集成测试')
    parser.add_argument('--all', action='store_true', help='运行所有测试')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    if args.all or (not args.unit and not args.integration):
        args.unit = True
        args.integration = True
    
    if args.unit:
        print("运行单元测试...")
        # 设置测试详细程度
        verbosity = 2 if args.verbose else 1
        
        # 创建测试套件
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        
        # 添加测试类
        test_classes = [
            TestFileFiltering,
            TestFileDiscovery,
            TestHashCalculation,
            TestDatabaseOperations,
            TestPerformance,
            TestConfigValidation
        ]
        
        for test_class in test_classes:
            tests = loader.loadTestsFromTestCase(test_class)
            suite.addTests(tests)
        
        # 运行测试
        runner = unittest.TextTestRunner(verbosity=verbosity)
        result = runner.run(suite)
        
        if not result.wasSuccessful():
            print(f"\n❌ 单元测试失败: {len(result.failures)} 个失败, {len(result.errors)} 个错误")
            return 1
        else:
            print("\n✅ 所有单元测试通过")
    
    if args.integration:
        try:
            run_integration_test()
        except Exception as e:
            print(f"\n❌ 集成测试失败: {str(e)}")
            return 1
    
    print("\n🎉 所有测试完成！")
    return 0

if __name__ == '__main__':
    sys.exit(main())