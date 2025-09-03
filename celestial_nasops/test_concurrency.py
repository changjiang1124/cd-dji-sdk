#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
并发同步控制测试脚本
测试多进程同步的安全性和锁机制的有效性
"""

import os
import sys
import time
import multiprocessing
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sync_lock_manager import SyncLockManager
from media_sync import MediaSyncManager
from config_manager import ConfigManager

class ConcurrencyTester:
    """并发测试器"""
    
    def __init__(self):
        self.test_dir = None
        self.lock_manager = None
        self.results = []
        
    def setup_test_environment(self):
        """设置测试环境"""
        # 创建临时测试目录
        self.test_dir = tempfile.mkdtemp(prefix='concurrency_test_')
        print(f"测试目录: {self.test_dir}")
        
        # 创建锁管理器
        lock_dir = os.path.join(self.test_dir, 'locks')
        os.makedirs(lock_dir, exist_ok=True)
        self.lock_manager = SyncLockManager(lock_dir=lock_dir, lock_timeout=60)
        
        # 创建测试媒体目录
        media_dir = os.path.join(self.test_dir, 'media')
        os.makedirs(media_dir, exist_ok=True)
        
        # 创建测试文件
        for i in range(3):
            test_file = os.path.join(media_dir, f'test_video_{i}.mp4')
            with open(test_file, 'wb') as f:
                f.write(b'test video content ' * 100)  # 创建一些测试内容
        
        return media_dir
    
    def cleanup_test_environment(self):
        """清理测试环境"""
        if self.test_dir and os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
            print(f"测试环境已清理: {self.test_dir}")
    
    def simulate_sync_process(self, process_id: int, media_dir: str, duration: int = 5):
        """模拟同步进程
        
        Args:
            process_id: 进程ID
            media_dir: 媒体目录
            duration: 模拟工作时长（秒）
        
        Returns:
            进程执行结果
        """
        try:
            start_time = time.time()
            
            # 每个进程创建自己的锁管理器实例，但使用相同的锁目录
            lock_dir = os.path.join(os.path.dirname(media_dir), 'locks')
            lock_manager = SyncLockManager(lock_dir=lock_dir, lock_timeout=60)
            
            # 尝试获取同步锁
            with lock_manager.sync_lock(timeout=30) as lock_acquired:
                if not lock_acquired:
                    return {
                        'process_id': process_id,
                        'status': 'failed',
                        'reason': 'failed_to_acquire_lock',
                        'start_time': start_time,
                        'end_time': time.time(),
                        'duration': time.time() - start_time
                    }
                
                # 模拟同步工作
                work_start = time.time()
                print(f"进程 {process_id}: 开始同步工作 ({datetime.now().strftime('%H:%M:%S')})")
                
                # 模拟文件处理
                files = [f for f in os.listdir(media_dir) if f.endswith('.mp4')]
                for i, filename in enumerate(files):
                    time.sleep(duration / len(files))  # 模拟处理时间
                    print(f"进程 {process_id}: 处理文件 {filename} ({i+1}/{len(files)})")
                
                work_end = time.time()
                print(f"进程 {process_id}: 同步工作完成 ({datetime.now().strftime('%H:%M:%S')})")
                
                return {
                    'process_id': process_id,
                    'status': 'success',
                    'reason': 'completed_successfully',
                    'start_time': start_time,
                    'work_start': work_start,
                    'work_end': work_end,
                    'end_time': time.time(),
                    'duration': time.time() - start_time,
                    'work_duration': work_end - work_start,
                    'files_processed': len(files)
                }
                
        except Exception as e:
            return {
                'process_id': process_id,
                'status': 'error',
                'reason': str(e),
                'start_time': start_time,
                'end_time': time.time(),
                'duration': time.time() - start_time
            }
    
    def test_concurrent_sync(self, num_processes: int = 3, work_duration: int = 3):
        """测试并发同步
        
        Args:
            num_processes: 并发进程数
            work_duration: 每个进程的工作时长
        """
        print(f"\n=== 测试并发同步控制 ({num_processes} 个进程) ===")
        
        media_dir = self.setup_test_environment()
        
        try:
            # 创建进程池
            with multiprocessing.Pool(processes=num_processes) as pool:
                # 启动多个同步进程
                print(f"启动 {num_processes} 个并发同步进程...")
                
                # 使用异步方式启动进程
                async_results = []
                for i in range(num_processes):
                    result = pool.apply_async(
                        self.simulate_sync_process,
                        args=(i + 1, media_dir, work_duration)
                    )
                    async_results.append(result)
                    time.sleep(0.1)  # 稍微错开启动时间
                
                # 等待所有进程完成
                results = []
                for async_result in async_results:
                    try:
                        result = async_result.get(timeout=60)  # 最多等待60秒
                        results.append(result)
                    except multiprocessing.TimeoutError:
                        results.append({
                            'process_id': 'unknown',
                            'status': 'timeout',
                            'reason': 'process_timeout'
                        })
            
            # 分析结果
            self.analyze_concurrency_results(results)
            
        finally:
            self.cleanup_test_environment()
    
    def analyze_concurrency_results(self, results):
        """分析并发测试结果
        
        Args:
            results: 进程执行结果列表
        """
        print("\n=== 并发测试结果分析 ===")
        
        successful_processes = [r for r in results if r['status'] == 'success']
        failed_processes = [r for r in results if r['status'] == 'failed']
        error_processes = [r for r in results if r['status'] == 'error']
        timeout_processes = [r for r in results if r['status'] == 'timeout']
        
        print(f"总进程数: {len(results)}")
        print(f"成功完成: {len(successful_processes)}")
        print(f"获取锁失败: {len(failed_processes)}")
        print(f"执行错误: {len(error_processes)}")
        print(f"超时: {len(timeout_processes)}")
        
        # 详细结果
        print("\n详细结果:")
        for result in results:
            process_id = result['process_id']
            status = result['status']
            reason = result.get('reason', 'unknown')
            duration = result.get('duration', 0)
            
            if status == 'success':
                work_duration = result.get('work_duration', 0)
                files_processed = result.get('files_processed', 0)
                print(f"  进程 {process_id}: ✓ 成功 (总时长: {duration:.2f}s, 工作时长: {work_duration:.2f}s, 处理文件: {files_processed})")
            elif status == 'failed':
                print(f"  进程 {process_id}: ✗ 失败 - {reason} (时长: {duration:.2f}s)")
            elif status == 'error':
                print(f"  进程 {process_id}: ⚠ 错误 - {reason} (时长: {duration:.2f}s)")
            else:
                print(f"  进程 {process_id}: ? {status} - {reason}")
        
        # 验证并发控制
        print("\n=== 并发控制验证 ===")
        
        if len(successful_processes) == 1:
            print("✓ 并发控制正常：只有一个进程成功获取锁并完成同步")
        elif len(successful_processes) == 0:
            print("⚠ 警告：没有进程成功完成同步")
        else:
            print(f"✗ 并发控制失败：{len(successful_processes)} 个进程同时获取了锁")
        
        if len(failed_processes) > 0:
            print(f"✓ 锁机制正常：{len(failed_processes)} 个进程因无法获取锁而跳过")
        
        # 时间重叠检查
        if len(successful_processes) > 1:
            print("\n检查时间重叠:")
            for i, proc1 in enumerate(successful_processes):
                for proc2 in successful_processes[i+1:]:
                    if self.check_time_overlap(proc1, proc2):
                        print(f"✗ 发现时间重叠：进程 {proc1['process_id']} 和进程 {proc2['process_id']}")
                    else:
                        print(f"✓ 无时间重叠：进程 {proc1['process_id']} 和进程 {proc2['process_id']}")
        
        # 总结
        print("\n=== 测试总结 ===")
        if len(successful_processes) == 1 and len(failed_processes) > 0:
            print("🎉 并发控制测试通过！")
            print("   - 只有一个进程成功获取锁")
            print("   - 其他进程正确地被阻止")
            print("   - 锁机制工作正常")
        else:
            print("❌ 并发控制测试失败！")
            print("   - 可能存在锁机制问题")
            print("   - 需要检查同步锁实现")
    
    def check_time_overlap(self, proc1, proc2):
        """检查两个进程的工作时间是否重叠
        
        Args:
            proc1: 进程1结果
            proc2: 进程2结果
            
        Returns:
            是否存在时间重叠
        """
        start1 = proc1.get('work_start', proc1.get('start_time', 0))
        end1 = proc1.get('work_end', proc1.get('end_time', 0))
        start2 = proc2.get('work_start', proc2.get('start_time', 0))
        end2 = proc2.get('work_end', proc2.get('end_time', 0))
        
        # 检查时间区间是否重叠
        return not (end1 <= start2 or end2 <= start1)

def main():
    """主函数"""
    print("=== 并发同步控制测试 ===")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tester = ConcurrencyTester()
    
    try:
        # 测试不同的并发场景
        test_scenarios = [
            {'processes': 2, 'duration': 2, 'name': '轻量并发测试'},
            {'processes': 3, 'duration': 3, 'name': '中等并发测试'},
            {'processes': 5, 'duration': 2, 'name': '高并发测试'}
        ]
        
        for scenario in test_scenarios:
            print(f"\n{'='*50}")
            print(f"场景: {scenario['name']}")
            print(f"进程数: {scenario['processes']}, 工作时长: {scenario['duration']}秒")
            print(f"{'='*50}")
            
            tester.test_concurrent_sync(
                num_processes=scenario['processes'],
                work_duration=scenario['duration']
            )
            
            # 场景间稍作休息
            time.sleep(1)
        
        print(f"\n=== 所有并发测试完成 ===")
        print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    except KeyboardInterrupt:
        print("\n测试被用户中断")
    except Exception as e:
        print(f"\n测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("脚本开始执行...")
    # 设置多进程启动方法
    try:
        multiprocessing.set_start_method('spawn', force=True)
        print("多进程方法设置完成")
    except RuntimeError:
        print("多进程方法已设置，跳过")
    
    print("调用main函数...")
    main()