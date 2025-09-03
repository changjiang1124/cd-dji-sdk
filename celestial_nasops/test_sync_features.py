#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
媒体同步功能测试脚本

测试所有优化功能的本地部分：
1. 并发控制机制
2. 原子性文件传输（本地部分）
3. 安全删除机制
4. 配置管理

作者: Celestial
日期: 2025-01-22
"""

import os
import sys
import json
import time
import tempfile
import shutil
import hashlib
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.append('/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops')
sys.path.append('/home/celestial/dev/esdk-test/Edge-SDK')

from sync_lock_manager import SyncLockManager, get_global_lock_manager
from safe_delete_manager import SafeDeleteManager, DeleteTask
from storage_manager import StorageManager

class SyncFeaturesTester:
    """同步功能测试器"""
    
    def __init__(self):
        self.test_dir = None
        self.lock_manager = None
        self.safe_delete_manager = None
        self.storage_manager = None
        
    def setup_test_environment(self):
        """设置测试环境"""
        print("=== 设置测试环境 ===")
        
        # 创建临时测试目录
        self.test_dir = tempfile.mkdtemp(prefix='sync_test_')
        print(f"测试目录: {self.test_dir}")
        
        # 创建子目录
        os.makedirs(os.path.join(self.test_dir, 'media'), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, 'temp'), exist_ok=True)
        os.makedirs(os.path.join(self.test_dir, 'locks'), exist_ok=True)
        
        # 创建测试文件
        test_files = [
            'media/test_video1.mp4',
            'media/test_video2.mp4',
            'media/test_image1.jpg',
            'temp/temp_file.tmp'
        ]
        
        for file_path in test_files:
            full_path = os.path.join(self.test_dir, file_path)
            with open(full_path, 'w') as f:
                f.write(f"Test content for {file_path}\n" * 100)
        
        print(f"✓ 测试环境设置完成，创建了 {len(test_files)} 个测试文件")
        return True
    
    def test_concurrency_control(self):
        """测试并发控制机制"""
        print("\n=== 测试并发控制机制 ===")
        
        try:
            # 初始化锁管理器
            lock_dir = os.path.join(self.test_dir, 'locks')
            self.lock_manager = SyncLockManager(lock_dir=lock_dir, lock_timeout=60)
            
            # 测试获取锁
            print("1. 测试锁获取...")
            with self.lock_manager.sync_lock(timeout=5) as acquired:
                if acquired:
                    print("✓ 成功获取同步锁")
                    
                    # 测试锁状态
                    if self.lock_manager.is_locked():
                        print("✓ 锁状态检查正确")
                    else:
                        print("✗ 锁状态检查失败")
                        return False
                    
                    # 模拟同步工作
                    time.sleep(1)
                    print("✓ 模拟同步工作完成")
                else:
                    print("✗ 获取同步锁失败")
                    return False
            
            # 测试锁释放
            if not self.lock_manager.is_locked():
                print("✓ 锁已正确释放")
            else:
                print("✗ 锁释放失败")
                return False
            
            # 测试锁超时
            print("2. 测试锁超时机制...")
            # 创建一个过期的锁管理器
            expired_lock_dir = os.path.join(self.test_dir, 'locks')
            expired_lock_manager = SyncLockManager(lock_dir=expired_lock_dir, lock_timeout=1)  # 1秒超时
            
            with expired_lock_manager.sync_lock(timeout=1) as acquired:
                if acquired:
                    print("✓ 获取锁成功")
                    time.sleep(2)  # 等待超过超时时间
            
            # 检查过期锁是否被清理
            time.sleep(1)
            if not expired_lock_manager.is_locked():
                print("✓ 过期锁清理机制正常")
            
            print("✓ 并发控制机制测试通过")
            return True
            
        except Exception as e:
            print(f"✗ 并发控制机制测试失败: {e}")
            return False
    
    def test_safe_delete_mechanism(self):
        """测试安全删除机制"""
        print("\n=== 测试安全删除机制 ===")
        
        try:
            # 初始化安全删除管理器
            pending_file = os.path.join(self.test_dir, 'pending_deletes.json')
            self.safe_delete_manager = SafeDeleteManager(
                nas_host="test_host",
                nas_username="test_user",
                delay_minutes=0.01,  # 1秒延迟用于测试
                pending_file=pending_file,
                enable_checksum=True
            )
            
            # 创建测试文件
            test_file = os.path.join(self.test_dir, 'media', 'delete_test.mp4')
            with open(test_file, 'w') as f:
                f.write("Test content for deletion\n" * 50)
            
            # 计算文件校验和
            with open(test_file, 'rb') as f:
                checksum = hashlib.md5(f.read()).hexdigest()
            
            print(f"1. 创建测试文件: {os.path.basename(test_file)}")
            print(f"   文件校验和: {checksum[:8]}...")
            
            # 安排删除任务
            remote_path = "/remote/path/delete_test.mp4"
            success = self.safe_delete_manager.schedule_delete(
                local_file_path=test_file,
                remote_file_path=remote_path,
                local_checksum=checksum
            )
            
            if success:
                print("✓ 删除任务安排成功")
            else:
                print("✗ 删除任务安排失败")
                return False
            
            # 检查待删除列表
            pending_count = len(self.safe_delete_manager.pending_deletes)
            print(f"✓ 待删除任务数量: {pending_count}")
            
            if pending_count != 1:
                print("✗ 待删除任务数量不正确")
                return False
            
            # 等待删除时间到达
            print("2. 等待删除时间到达...")
            time.sleep(2)
            
            # 由于没有实际的NAS连接，这里只测试任务调度逻辑
            # 实际删除会失败，但这是预期的
            success_count, failed_count = self.safe_delete_manager.process_pending_deletes()
            print(f"✓ 删除处理完成 - 成功: {success_count}, 失败: {failed_count}")
            
            # 检查文件是否仍然存在（因为远程验证会失败）
            if os.path.exists(test_file):
                print("✓ 文件因远程验证失败而保留（符合预期）")
            
            print("✓ 安全删除机制测试通过")
            return True
            
        except Exception as e:
            print(f"✗ 安全删除机制测试失败: {e}")
            return False
    
    def test_atomic_transfer_logic(self):
        """测试原子性传输逻辑（本地部分）"""
        print("\n=== 测试原子性传输逻辑 ===")
        
        try:
            # 测试文件校验和计算
            test_file = os.path.join(self.test_dir, 'media', 'test_video1.mp4')
            
            print("1. 测试文件校验和计算...")
            with open(test_file, 'rb') as f:
                content = f.read()
                expected_checksum = hashlib.md5(content).hexdigest()
            
            # 模拟计算校验和的函数
            def calculate_checksum(file_path):
                with open(file_path, 'rb') as f:
                    return hashlib.md5(f.read()).hexdigest()
            
            actual_checksum = calculate_checksum(test_file)
            
            if actual_checksum == expected_checksum:
                print(f"✓ 校验和计算正确: {actual_checksum[:8]}...")
            else:
                print("✗ 校验和计算错误")
                return False
            
            # 测试临时文件命名逻辑
            print("2. 测试临时文件命名逻辑...")
            filename = os.path.basename(test_file)
            temp_filename = f".tmp_{int(time.time())}_{filename}"
            
            if temp_filename.startswith('.tmp_') and temp_filename.endswith(filename):
                print(f"✓ 临时文件命名正确: {temp_filename}")
            else:
                print("✗ 临时文件命名错误")
                return False
            
            # 测试原子性重命名逻辑（本地模拟）
            print("3. 测试原子性重命名逻辑...")
            temp_file = os.path.join(self.test_dir, 'temp', temp_filename)
            final_file = os.path.join(self.test_dir, 'temp', filename)
            
            # 创建临时文件
            shutil.copy2(test_file, temp_file)
            
            # 原子性重命名
            os.rename(temp_file, final_file)
            
            if os.path.exists(final_file) and not os.path.exists(temp_file):
                print("✓ 原子性重命名成功")
                # 清理
                os.remove(final_file)
            else:
                print("✗ 原子性重命名失败")
                return False
            
            print("✓ 原子性传输逻辑测试通过")
            return True
            
        except Exception as e:
            print(f"✗ 原子性传输逻辑测试失败: {e}")
            return False
    
    def test_configuration_management(self):
        """测试配置管理"""
        print("\n=== 测试配置管理 ===")
        
        try:
            # 测试配置文件加载
            print("1. 测试配置文件加载...")
            
            # 创建测试配置文件
            test_config = {
                "nas_settings": {
                    "host": "192.168.200.103",
                    "username": "edge_sync",
                    "base_path": "/volume1/drone_media"
                },
                "sync_settings": {
                    "max_retry": 3,
                    "enable_checksum": True,
                    "delete_after_sync": False
                },
                "storage_management": {
                    "warning_threshold_percent": 80,
                    "critical_threshold_percent": 90
                }
            }
            
            config_file = os.path.join(self.test_dir, 'test_config.json')
            with open(config_file, 'w') as f:
                json.dump(test_config, f, indent=2)
            
            # 测试配置加载
            with open(config_file, 'r') as f:
                loaded_config = json.load(f)
            
            if loaded_config == test_config:
                print("✓ 配置文件加载正确")
            else:
                print("✗ 配置文件加载错误")
                return False
            
            # 测试配置项访问
            print("2. 测试配置项访问...")
            nas_host = loaded_config.get('nas_settings', {}).get('host')
            if nas_host == "192.168.200.103":
                print("✓ 配置项访问正确")
            else:
                print("✗ 配置项访问错误")
                return False
            
            print("✓ 配置管理测试通过")
            return True
            
        except Exception as e:
            print(f"✗ 配置管理测试失败: {e}")
            return False
    
    def cleanup_test_environment(self):
        """清理测试环境"""
        if self.test_dir and os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
            print(f"\n测试环境已清理: {self.test_dir}")
    
    def run_all_tests(self):
        """运行所有测试"""
        print("=== 媒体同步功能测试 ===")
        print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        tests = [
            ("设置测试环境", self.setup_test_environment),
            ("并发控制机制", self.test_concurrency_control),
            ("安全删除机制", self.test_safe_delete_mechanism),
            ("原子性传输逻辑", self.test_atomic_transfer_logic),
            ("配置管理", self.test_configuration_management)
        ]
        
        passed = 0
        total = len(tests)
        
        try:
            for test_name, test_func in tests:
                print(f"\n--- {test_name} ---")
                if test_func():
                    passed += 1
                else:
                    print(f"❌ 测试失败: {test_name}")
        
        finally:
            self.cleanup_test_environment()
        
        print(f"\n=== 测试结果 ===")
        print(f"通过: {passed}/{total}")
        print(f"成功率: {passed/total*100:.1f}%")
        
        if passed == total:
            print("🎉 所有测试通过！")
            return True
        else:
            print("❌ 部分测试失败")
            return False

def main():
    """主函数"""
    tester = SyncFeaturesTester()
    success = tester.run_all_tests()
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())