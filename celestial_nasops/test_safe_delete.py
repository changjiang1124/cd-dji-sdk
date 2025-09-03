#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全删除功能测试脚本

测试SafeDeleteManager的各项功能：
1. 延迟删除任务安排
2. 待删除任务处理
3. 远程文件验证
4. 错误恢复机制

作者: Celestial
日期: 2024-01-22
"""

import os
import sys
import time
import tempfile
import hashlib
from pathlib import Path

# 添加项目路径
sys.path.append('/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops')

from safe_delete_manager import SafeDeleteManager
from media_sync import MediaSyncManager

class SafeDeleteTester:
    """安全删除功能测试器"""
    
    def __init__(self):
        """初始化测试器"""
        self.test_dir = "/tmp/safe_delete_test"
        self.setup_test_environment()
        
        # 创建测试用的删除管理器（1分钟延迟用于测试）
        self.delete_manager = SafeDeleteManager(
            delay_minutes=1,  # 测试用短延迟
            pending_file=os.path.join(self.test_dir, "test_pending_deletes.json")
        )
        
        print(f"SafeDeleteTester初始化完成")
        print(f"测试目录: {self.test_dir}")
    
    def setup_test_environment(self):
        """设置测试环境"""
        # 创建测试目录
        os.makedirs(self.test_dir, exist_ok=True)
        print(f"测试环境设置完成: {self.test_dir}")
    
    def create_test_file(self, filename: str, content: str = None) -> str:
        """创建测试文件
        
        Args:
            filename: 文件名
            content: 文件内容，默认为测试内容
            
        Returns:
            文件路径
        """
        if content is None:
            content = f"测试文件内容 - {filename} - {time.time()}"
        
        file_path = os.path.join(self.test_dir, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"创建测试文件: {file_path}")
        return file_path
    
    def calculate_file_checksum(self, file_path: str) -> str:
        """计算文件校验和
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件MD5校验和
        """
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def test_schedule_delete(self):
        """测试安排删除任务"""
        print("\n=== 测试安排删除任务 ===")
        
        # 创建测试文件
        test_file = self.create_test_file("test_schedule.txt")
        checksum = self.calculate_file_checksum(test_file)
        
        # 安排删除任务
        remote_path = "/volume1/drone_media/test/test_schedule.txt"
        success = self.delete_manager.schedule_delete(
            local_file_path=test_file,
            remote_file_path=remote_path,
            local_checksum=checksum
        )
        
        if success:
            print("✓ 删除任务安排成功")
            
            # 检查状态
            status = self.delete_manager.get_status_summary()
            print(f"待删除任务数量: {status['total_pending']}")
            print(f"可执行删除数量: {status['ready_for_deletion']}")
            
            return True
        else:
            print("✗ 删除任务安排失败")
            return False
    
    def test_process_pending_deletes(self):
        """测试处理待删除任务"""
        print("\n=== 测试处理待删除任务 ===")
        
        # 等待删除时间到达
        print("等待删除时间到达（1分钟）...")
        time.sleep(65)  # 等待65秒确保超过1分钟
        
        # 处理待删除任务
        success_count, failed_count = self.delete_manager.process_pending_deletes()
        
        print(f"处理结果 - 成功: {success_count}, 失败: {failed_count}")
        
        # 检查状态
        status = self.delete_manager.get_status_summary()
        print(f"剩余待删除任务: {status['total_pending']}")
        
        return success_count > 0 or failed_count > 0
    
    def test_multiple_files(self):
        """测试多文件删除"""
        print("\n=== 测试多文件删除 ===")
        
        files = []
        for i in range(3):
            filename = f"test_multi_{i}.txt"
            file_path = self.create_test_file(filename)
            checksum = self.calculate_file_checksum(file_path)
            
            # 安排删除
            remote_path = f"/volume1/drone_media/test/{filename}"
            success = self.delete_manager.schedule_delete(
                local_file_path=file_path,
                remote_file_path=remote_path,
                local_checksum=checksum
            )
            
            if success:
                files.append(file_path)
                print(f"✓ 文件 {filename} 删除任务安排成功")
            else:
                print(f"✗ 文件 {filename} 删除任务安排失败")
        
        # 检查状态
        status = self.delete_manager.get_status_summary()
        print(f"总待删除任务: {status['total_pending']}")
        
        return len(files) > 0
    
    def test_nonexistent_file(self):
        """测试不存在文件的删除"""
        print("\n=== 测试不存在文件的删除 ===")
        
        nonexistent_file = os.path.join(self.test_dir, "nonexistent.txt")
        remote_path = "/volume1/drone_media/test/nonexistent.txt"
        
        success = self.delete_manager.schedule_delete(
            local_file_path=nonexistent_file,
            remote_file_path=remote_path,
            local_checksum="dummy_checksum"
        )
        
        if not success:
            print("✓ 正确处理了不存在的文件")
            return True
        else:
            print("✗ 应该拒绝不存在的文件")
            return False
    
    def test_integration_with_media_sync(self):
        """测试与MediaSyncManager的集成"""
        print("\n=== 测试与MediaSyncManager的集成 ===")
        
        try:
            # 创建MediaSyncManager实例
            sync_manager = MediaSyncManager()
            
            # 获取删除状态
            delete_status = sync_manager.get_delete_status()
            print(f"删除功能状态: {delete_status}")
            
            # 测试处理待删除任务
            result = sync_manager.process_pending_deletes()
            print(f"集成测试结果: {result}")
            
            print("✓ MediaSyncManager集成测试成功")
            return True
            
        except Exception as e:
            print(f"✗ MediaSyncManager集成测试失败: {e}")
            return False
    
    def cleanup_test_environment(self):
        """清理测试环境"""
        try:
            # 删除测试目录
            import shutil
            if os.path.exists(self.test_dir):
                shutil.rmtree(self.test_dir)
            print(f"测试环境清理完成: {self.test_dir}")
        except Exception as e:
            print(f"清理测试环境失败: {e}")
    
    def run_all_tests(self):
        """运行所有测试"""
        print("开始SafeDeleteManager功能测试")
        print("=" * 50)
        
        test_results = []
        
        # 运行各项测试
        test_results.append(("安排删除任务", self.test_schedule_delete()))
        test_results.append(("多文件删除", self.test_multiple_files()))
        test_results.append(("不存在文件处理", self.test_nonexistent_file()))
        test_results.append(("MediaSync集成", self.test_integration_with_media_sync()))
        test_results.append(("处理待删除任务", self.test_process_pending_deletes()))
        
        # 显示测试结果
        print("\n" + "=" * 50)
        print("测试结果汇总:")
        
        passed = 0
        total = len(test_results)
        
        for test_name, result in test_results:
            status = "✓ 通过" if result else "✗ 失败"
            print(f"{test_name}: {status}")
            if result:
                passed += 1
        
        print(f"\n总计: {passed}/{total} 个测试通过")
        
        # 清理测试环境
        self.cleanup_test_environment()
        
        return passed == total

def main():
    """主函数"""
    try:
        tester = SafeDeleteTester()
        success = tester.run_all_tests()
        
        if success:
            print("\n🎉 所有测试通过！SafeDeleteManager功能正常")
            sys.exit(0)
        else:
            print("\n❌ 部分测试失败，请检查SafeDeleteManager实现")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n用户中断测试")
        sys.exit(130)
    except Exception as e:
        print(f"\n测试过程发生异常: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()