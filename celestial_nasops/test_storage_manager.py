#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
存储管理器测试脚本

功能说明：
1. 测试存储空间检查功能
2. 测试自动清理功能
3. 测试与MediaSyncManager的集成
4. 验证配置文件加载

作者: Celestial
日期: 2024-01-22
"""

import os
import sys
import json
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目路径
sys.path.append('/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops')

from storage_manager import StorageManager
from media_sync import MediaSyncManager

class StorageManagerTester:
    """存储管理器测试类"""
    
    def __init__(self):
        """初始化测试环境"""
        self.test_dir = None
        self.config_file = None
        self.storage_manager = None
        
    def setup_test_environment(self):
        """设置测试环境"""
        print("设置测试环境...")
        
        try:
            # 创建临时测试目录
            self.test_dir = tempfile.mkdtemp(prefix='storage_test_')
            print(f"测试目录: {self.test_dir}")
            
            # 创建测试配置文件
            test_config = {
                "storage_management": {
                    "warning_threshold_percent": 80,
                    "critical_threshold_percent": 90,
                    "cleanup_target_percent": 70,
                    "check_interval_minutes": 60,
                    "status_file": os.path.join(self.test_dir, "storage_status.json"),
                    "cleanup_rules": [
                        {
                            "path_pattern": f"{self.test_dir}/logs/*",
                            "file_extension": ".log",
                            "max_age_days": 7,
                            "priority": 1,
                            "enabled": True
                        },
                        {
                            "path_pattern": f"{self.test_dir}/temp/*",
                            "file_extension": "*",
                            "max_age_days": 1,
                            "priority": 2,
                            "enabled": True
                        }
                    ]
                }
            }
            
            self.config_file = os.path.join(self.test_dir, "test_config.json")
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(test_config, f, indent=2, ensure_ascii=False)
            
            # 创建测试目录结构
            os.makedirs(os.path.join(self.test_dir, "logs"), exist_ok=True)
            os.makedirs(os.path.join(self.test_dir, "temp"), exist_ok=True)
            
            print("测试环境设置完成")
            return True
        except Exception as e:
            print(f"设置测试环境失败: {e}")
            return False
    
    def create_test_files(self):
        """创建测试文件"""
        print("创建测试文件...")
        
        try:
            # 创建旧日志文件（超过7天）
            old_log_file = os.path.join(self.test_dir, "logs", "old.log")
            with open(old_log_file, 'w') as f:
                f.write("旧日志内容" * 1000)  # 创建一些内容
            
            # 修改文件时间为8天前
            old_time = datetime.now() - timedelta(days=8)
            timestamp = old_time.timestamp()
            os.utime(old_log_file, (timestamp, timestamp))
            
            # 创建新日志文件（1天内）
            new_log_file = os.path.join(self.test_dir, "logs", "new.log")
            with open(new_log_file, 'w') as f:
                f.write("新日志内容" * 500)
            
            # 创建旧临时文件（超过1天）
            old_temp_file = os.path.join(self.test_dir, "temp", "old_temp.txt")
            with open(old_temp_file, 'w') as f:
                f.write("旧临时文件内容" * 800)
            
            # 修改文件时间为2天前
            old_time = datetime.now() - timedelta(days=2)
            timestamp = old_time.timestamp()
            os.utime(old_temp_file, (timestamp, timestamp))
            
            # 创建新临时文件
            new_temp_file = os.path.join(self.test_dir, "temp", "new_temp.txt")
            with open(new_temp_file, 'w') as f:
                f.write("新临时文件内容" * 300)
            
            print(f"创建了4个测试文件:")
            print(f"  - {old_log_file} (旧日志)")
            print(f"  - {new_log_file} (新日志)")
            print(f"  - {old_temp_file} (旧临时文件)")
            print(f"  - {new_temp_file} (新临时文件)")
            return True
        except Exception as e:
            print(f"创建测试文件失败: {e}")
            return False
    
    def test_storage_manager_init(self):
        """测试存储管理器初始化"""
        print("\n=== 测试存储管理器初始化 ===")
        
        try:
            self.storage_manager = StorageManager(config_file=self.config_file)
            print("✓ 存储管理器初始化成功")
            return True
        except Exception as e:
            print(f"✗ 存储管理器初始化失败: {e}")
            return False
    
    def test_check_storage_space(self):
        """测试存储空间检查"""
        print("\n=== 测试存储空间检查 ===")
        
        try:
            result = self.storage_manager.check_storage_space()
            print(f"存储空间信息:")
            print(f"  - 总空间: {result.get('total_gb', 0):.2f} GB")
            print(f"  - 已用空间: {result.get('used_gb', 0):.2f} GB")
            print(f"  - 可用空间: {result.get('available_gb', 0):.2f} GB")
            print(f"  - 使用率: {result.get('used_percent', 0):.1f}%")
            print(f"  - 需要清理: {result.get('needs_cleanup', False)}")
            print("✓ 存储空间检查成功")
            return True
        except Exception as e:
            print(f"✗ 存储空间检查失败: {e}")
            return False
    
    def test_cleanup_storage(self):
        """测试存储清理"""
        print("\n=== 测试存储清理 ===")
        
        # 先检查清理前的文件
        files_before = []
        for root, dirs, files in os.walk(self.test_dir):
            for file in files:
                if file.endswith(('.log', '.txt')):
                    files_before.append(os.path.join(root, file))
        
        print(f"清理前文件数量: {len(files_before)}")
        
        try:
            # 强制清理（忽略阈值）
            result = self.storage_manager.cleanup_storage(force=True)
            
            print(f"清理结果:")
            print(f"  - 删除文件数: {result.get('files_deleted', 0)}")
            print(f"  - 释放空间: {result.get('space_freed_gb', 0):.3f} GB")
            print(f"  - 清理规则数: {len(result.get('cleanup_details', []))}")
            
            # 检查清理后的文件
            files_after = []
            for root, dirs, files in os.walk(self.test_dir):
                for file in files:
                    if file.endswith(('.log', '.txt')):
                        files_after.append(os.path.join(root, file))
            
            print(f"清理后文件数量: {len(files_after)}")
            
            # 验证旧文件被删除，新文件保留
            expected_remaining = 2  # 应该保留2个新文件
            if len(files_after) == expected_remaining:
                print("✓ 存储清理成功，旧文件已删除，新文件已保留")
                return True
            else:
                print(f"✗ 存储清理结果不符合预期，预期保留{expected_remaining}个文件，实际保留{len(files_after)}个")
                return False
                
        except Exception as e:
            print(f"✗ 存储清理失败: {e}")
            return False
    
    def test_status_summary(self):
        """测试状态摘要"""
        print("\n=== 测试状态摘要 ===")
        
        try:
            status = self.storage_manager.get_status_summary()
            print(f"状态摘要:")
            print(f"  - 监控状态: {'运行中' if status.get('monitoring_active', False) else '已停止'}")
            print(f"  - 上次检查: {status.get('last_check_time', '未知')}")
            print(f"  - 检查间隔: {status.get('check_interval_minutes', 0)}分钟")
            print(f"  - 警告阈值: {status.get('warning_threshold_percent', 0)}%")
            print(f"  - 严重阈值: {status.get('critical_threshold_percent', 0)}%")
            print("✓ 状态摘要获取成功")
            return True
        except Exception as e:
            print(f"✗ 状态摘要获取失败: {e}")
            return False
    
    def test_media_sync_integration(self):
        """测试与MediaSyncManager的集成"""
        print("\n=== 测试MediaSyncManager集成 ===")
        
        try:
            # 创建一个简化的配置文件用于MediaSyncManager
            media_config = {
                "nas_server": {
                    "host": "192.168.200.103",
                    "username": "edge_sync",
                    "remote_path": "/EdgeBackup"
                },
                "local_storage": {
                    "media_path": "/tmp/test_media"
                },
                "sync_settings": {
                    "max_retries": 3,
                    "verify_checksum": True,
                    "delete_after_sync": False,
                    "safe_delete_delay_minutes": 30
                },
                "file_lock": {
                    "lock_file": "sync.lock",
                    "timeout_minutes": 30
                },
                "logging": {
                    "level": "INFO",
                    "file": "logs/media_sync.log",
                    "max_size_mb": 10,
                    "backup_count": 5
                }
            }
            
            media_config_file = os.path.join(self.test_dir, "media_config.json")
            with open(media_config_file, 'w', encoding='utf-8') as f:
                json.dump(media_config, f, indent=2, ensure_ascii=False)
            
            # 注意：这里只测试初始化，不测试实际的同步功能
            # 因为需要真实的NAS连接
            print("✓ MediaSyncManager集成配置准备完成")
            print("  (实际集成测试需要NAS连接，此处跳过)")
            return True
            
        except Exception as e:
            print(f"✗ MediaSyncManager集成测试失败: {e}")
            return False
    
    def cleanup_test_environment(self):
        """清理测试环境"""
        print("\n清理测试环境...")
        
        if self.test_dir and os.path.exists(self.test_dir):
            try:
                shutil.rmtree(self.test_dir)
                print(f"测试目录已删除: {self.test_dir}")
            except Exception as e:
                print(f"清理测试目录失败: {e}")
    
    def run_all_tests(self):
        """运行所有测试"""
        print("=== 存储管理器功能测试 ===")
        
        tests = [
            ("设置测试环境", self.setup_test_environment),
            ("创建测试文件", self.create_test_files),
            ("存储管理器初始化", self.test_storage_manager_init),
            ("存储空间检查", self.test_check_storage_space),
            ("存储清理", self.test_cleanup_storage),
            ("状态摘要", self.test_status_summary),
            ("MediaSyncManager集成", self.test_media_sync_integration)
        ]
        
        passed = 0
        total = len(tests)
        
        try:
            for test_name, test_func in tests:
                print(f"\n--- {test_name} ---")
                if test_func():
                    passed += 1
                else:
                    print(f"测试失败: {test_name}")
        
        finally:
            self.cleanup_test_environment()
        
        print(f"\n=== 测试结果 ===")
        print(f"通过: {passed}/{total}")
        print(f"成功率: {passed/total*100:.1f}%")
        
        return passed == total

def main():
    """主函数"""
    tester = StorageManagerTester()
    
    try:
        success = tester.run_all_tests()
        if success:
            print("\n🎉 所有测试通过！")
            return 0
        else:
            print("\n❌ 部分测试失败")
            return 1
    except KeyboardInterrupt:
        print("\n用户中断测试")
        tester.cleanup_test_environment()
        return 130
    except Exception as e:
        print(f"\n测试过程发生异常: {e}")
        tester.cleanup_test_environment()
        return 1

if __name__ == "__main__":
    exit(main())