#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置集成测试脚本

测试所有优化功能的配置项是否正确集成到统一配置管理系统中

作者: Celestial
日期: 2025-01-02
"""

import os
import sys
import json
import tempfile
from pathlib import Path

# 添加项目路径
sys.path.append(os.path.dirname(__file__))

from config_manager import ConfigManager

def test_config_integration():
    """测试配置集成"""
    print("=== 配置集成测试 ===")
    
    # 使用统一配置文件
    config_file = os.path.join(os.path.dirname(__file__), 'unified_config.json')
    config_manager = ConfigManager(config_file)
    
    test_results = []
    
    # 测试1: 并发控制配置
    print("\n1. 测试并发控制配置...")
    try:
        enable_lock = config_manager.get('concurrency_control.enable_file_lock', False)
        lock_timeout = config_manager.get('concurrency_control.lock_timeout_seconds', 3600)
        lock_dir = config_manager.get('concurrency_control.lock_dir', '')
        max_concurrent = config_manager.get('concurrency_control.max_concurrent_syncs', 1)
        
        print(f"   启用文件锁: {enable_lock}")
        print(f"   锁超时时间: {lock_timeout}秒")
        print(f"   锁目录: {lock_dir}")
        print(f"   最大并发数: {max_concurrent}")
        
        if enable_lock and lock_timeout > 0 and lock_dir:
            print("✓ 并发控制配置正确")
            test_results.append(True)
        else:
            print("✗ 并发控制配置缺失或错误")
            test_results.append(False)
            
    except Exception as e:
        print(f"✗ 并发控制配置测试失败: {e}")
        test_results.append(False)
    
    # 测试2: 原子性传输配置
    print("\n2. 测试原子性传输配置...")
    try:
        enable_atomic = config_manager.get('sync_settings.enable_atomic_transfer', False)
        temp_prefix = config_manager.get('sync_settings.temp_file_prefix', '.tmp_')
        enable_checksum = config_manager.get('sync_settings.enable_checksum', False)
        verify_remote = config_manager.get('sync_settings.verify_remote_before_delete', False)
        
        print(f"   启用原子传输: {enable_atomic}")
        print(f"   临时文件前缀: {temp_prefix}")
        print(f"   启用校验和: {enable_checksum}")
        print(f"   删除前验证远程: {verify_remote}")
        
        if enable_atomic and temp_prefix and enable_checksum:
            print("✓ 原子性传输配置正确")
            test_results.append(True)
        else:
            print("✗ 原子性传输配置缺失或错误")
            test_results.append(False)
            
    except Exception as e:
        print(f"✗ 原子性传输配置测试失败: {e}")
        test_results.append(False)
    
    # 测试3: 存储管理配置
    print("\n3. 测试存储管理配置...")
    try:
        enable_storage_check = config_manager.get('storage_management.enable_storage_check', False)
        enable_auto_cleanup = config_manager.get('storage_management.enable_auto_cleanup', False)
        warning_threshold = config_manager.get('storage_management.warning_threshold_percent', 80)
        critical_threshold = config_manager.get('storage_management.critical_threshold_percent', 90)
        cleanup_target = config_manager.get('storage_management.cleanup_target_percent', 70)
        cleanup_rules = config_manager.get('storage_management.cleanup_rules', [])
        
        print(f"   启用存储检查: {enable_storage_check}")
        print(f"   启用自动清理: {enable_auto_cleanup}")
        print(f"   警告阈值: {warning_threshold}%")
        print(f"   严重阈值: {critical_threshold}%")
        print(f"   清理目标: {cleanup_target}%")
        print(f"   清理规则数量: {len(cleanup_rules)}")
        
        if (enable_storage_check and warning_threshold > 0 and 
            critical_threshold > warning_threshold and len(cleanup_rules) > 0):
            print("✓ 存储管理配置正确")
            test_results.append(True)
        else:
            print("✗ 存储管理配置缺失或错误")
            test_results.append(False)
            
    except Exception as e:
        print(f"✗ 存储管理配置测试失败: {e}")
        test_results.append(False)
    
    # 测试4: 安全删除配置
    print("\n4. 测试安全删除配置...")
    try:
        delete_after_sync = config_manager.get('sync_settings.delete_after_sync', False)
        safe_delete_delay = config_manager.get('sync_settings.safe_delete_delay_minutes', 30)
        verify_remote = config_manager.get('sync_settings.verify_remote_before_delete', False)
        
        print(f"   同步后删除: {delete_after_sync}")
        print(f"   安全删除延迟: {safe_delete_delay}分钟")
        print(f"   删除前验证远程: {verify_remote}")
        
        if delete_after_sync and safe_delete_delay > 0:
            print("✓ 安全删除配置正确")
            test_results.append(True)
        else:
            print("✗ 安全删除配置缺失或错误")
            test_results.append(False)
            
    except Exception as e:
        print(f"✗ 安全删除配置测试失败: {e}")
        test_results.append(False)
    
    # 测试5: 配置文件完整性
    print("\n5. 测试配置文件完整性...")
    try:
        # 检查必需的配置段
        required_sections = [
            'nas_settings',
            'local_settings', 
            'sync_settings',
            'concurrency_control',
            'storage_management',
            'logging'
        ]
        
        missing_sections = []
        for section in required_sections:
            if not config_manager.get_section(section):
                missing_sections.append(section)
        
        if not missing_sections:
            print("✓ 配置文件完整性检查通过")
            test_results.append(True)
        else:
            print(f"✗ 缺失配置段: {missing_sections}")
            test_results.append(False)
            
    except Exception as e:
        print(f"✗ 配置文件完整性测试失败: {e}")
        test_results.append(False)
    
    # 输出测试结果
    print("\n=== 测试结果 ===")
    passed = sum(test_results)
    total = len(test_results)
    success_rate = (passed / total) * 100 if total > 0 else 0
    
    print(f"通过: {passed}/{total}")
    print(f"成功率: {success_rate:.1f}%")
    
    if success_rate == 100:
        print("🎉 所有配置集成测试通过！")
        return True
    else:
        print("❌ 部分配置集成测试失败")
        return False

def test_config_manager_methods():
    """测试配置管理器的方法"""
    print("\n=== 配置管理器方法测试 ===")
    
    config_file = os.path.join(os.path.dirname(__file__), 'unified_config.json')
    config_manager = ConfigManager(config_file)
    
    # 测试get方法
    print("\n1. 测试get方法...")
    host = config_manager.get('nas_settings.host')
    print(f"   NAS主机: {host}")
    
    # 测试get_section方法
    print("\n2. 测试get_section方法...")
    sync_settings = config_manager.get_section('sync_settings')
    print(f"   同步设置项数: {len(sync_settings)}")
    
    # 测试默认值
    print("\n3. 测试默认值...")
    non_existent = config_manager.get('non_existent.key', 'default_value')
    print(f"   不存在的配置项: {non_existent}")
    
    print("✓ 配置管理器方法测试完成")

if __name__ == '__main__':
    print("开始配置集成测试...\n")
    
    # 运行配置集成测试
    integration_success = test_config_integration()
    
    # 运行配置管理器方法测试
    test_config_manager_methods()
    
    print("\n配置集成测试完成！")
    
    # 返回适当的退出码
    sys.exit(0 if integration_success else 1)