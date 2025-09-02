#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
同步锁管理器 - 防止多个同步进程并发执行

功能说明：
1. 基于文件锁实现进程级别的互斥控制
2. 支持锁超时机制，防止死锁
3. 自动清理过期锁文件
4. 提供锁状态查询和强制释放功能

作者: Celestial
日期: 2024-01-22
"""

import os
import time
import fcntl
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
from contextlib import contextmanager

class SyncLockManager:
    """同步锁管理器"""
    
    def __init__(self, lock_dir: str = None, lock_timeout: int = 3600):
        """初始化锁管理器
        
        Args:
            lock_dir: 锁文件存储目录，默认使用项目logs目录
            lock_timeout: 锁超时时间（秒），默认1小时
        """
        self.lock_dir = lock_dir or '/home/celestial/dev/esdk-test/Edge-SDK/celestial_works/logs'
        self.lock_timeout = lock_timeout
        self.lock_file_path = os.path.join(self.lock_dir, 'media_sync.lock')
        self.lock_info_path = os.path.join(self.lock_dir, 'media_sync.lock.info')
        
        # 确保锁目录存在
        os.makedirs(self.lock_dir, exist_ok=True)
        
        # 设置日志
        self.logger = logging.getLogger('SyncLockManager')
        
        # 当前持有的锁文件句柄
        self._lock_file = None
        self._lock_acquired = False
        self._lock_thread = threading.current_thread().ident
    
    def _write_lock_info(self, info: Dict[str, Any]):
        """写入锁信息文件
        
        Args:
            info: 锁信息字典
        """
        try:
            import json
            with open(self.lock_info_path, 'w', encoding='utf-8') as f:
                json.dump(info, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            self.logger.warning(f"写入锁信息失败: {e}")
    
    def _read_lock_info(self) -> Optional[Dict[str, Any]]:
        """读取锁信息文件
        
        Returns:
            锁信息字典，读取失败返回None
        """
        try:
            import json
            if os.path.exists(self.lock_info_path):
                with open(self.lock_info_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.warning(f"读取锁信息失败: {e}")
        return None
    
    def _is_lock_expired(self) -> bool:
        """检查锁是否已过期
        
        Returns:
            锁是否已过期
        """
        lock_info = self._read_lock_info()
        if not lock_info:
            return True
        
        try:
            lock_time = datetime.fromisoformat(lock_info['acquired_at'])
            return datetime.now() - lock_time > timedelta(seconds=self.lock_timeout)
        except Exception:
            return True
    
    def _cleanup_expired_lock(self):
        """清理过期的锁文件"""
        if self._is_lock_expired():
            try:
                if os.path.exists(self.lock_file_path):
                    os.remove(self.lock_file_path)
                if os.path.exists(self.lock_info_path):
                    os.remove(self.lock_info_path)
                self.logger.info("已清理过期锁文件")
            except Exception as e:
                self.logger.warning(f"清理过期锁文件失败: {e}")
    
    def acquire_lock(self, timeout: int = 0) -> bool:
        """获取同步锁
        
        Args:
            timeout: 等待超时时间（秒），0表示不等待
            
        Returns:
            是否成功获取锁
        """
        if self._lock_acquired:
            self.logger.warning("锁已被当前进程持有")
            return True
        
        # 清理过期锁
        self._cleanup_expired_lock()
        
        start_time = time.time()
        
        while True:
            try:
                # 尝试创建并锁定文件
                self._lock_file = open(self.lock_file_path, 'w')
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                
                # 写入锁信息
                lock_info = {
                    'pid': os.getpid(),
                    'thread_id': threading.current_thread().ident,
                    'acquired_at': datetime.now().isoformat(),
                    'timeout': self.lock_timeout,
                    'process_name': 'media_sync_scheduler'
                }
                
                self._write_lock_info(lock_info)
                
                # 在锁文件中写入基本信息
                self._lock_file.write(f"PID: {os.getpid()}\n")
                self._lock_file.write(f"Time: {datetime.now()}\n")
                self._lock_file.flush()
                
                self._lock_acquired = True
                self._lock_thread = threading.current_thread().ident
                
                self.logger.info(f"成功获取同步锁 (PID: {os.getpid()})")
                return True
                
            except (IOError, OSError) as e:
                # 锁被其他进程持有
                if timeout == 0:
                    self.logger.info("同步锁被其他进程持有，无法获取")
                    return False
                
                # 检查是否超时
                if time.time() - start_time >= timeout:
                    self.logger.warning(f"等待锁超时 ({timeout}秒)")
                    return False
                
                # 等待一段时间后重试
                time.sleep(1)
            
            except Exception as e:
                self.logger.error(f"获取锁时发生异常: {e}")
                return False
    
    def release_lock(self):
        """释放同步锁"""
        if not self._lock_acquired:
            self.logger.warning("当前进程未持有锁")
            return
        
        if threading.current_thread().ident != self._lock_thread:
            self.logger.warning("只能由获取锁的线程释放锁")
            return
        
        try:
            if self._lock_file:
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
                self._lock_file.close()
                self._lock_file = None
            
            # 删除锁文件
            if os.path.exists(self.lock_file_path):
                os.remove(self.lock_file_path)
            if os.path.exists(self.lock_info_path):
                os.remove(self.lock_info_path)
            
            self._lock_acquired = False
            self._lock_thread = None
            
            self.logger.info("同步锁已释放")
            
        except Exception as e:
            self.logger.error(f"释放锁时发生异常: {e}")
    
    def is_locked(self) -> bool:
        """检查是否有锁存在
        
        Returns:
            是否存在有效锁
        """
        if not os.path.exists(self.lock_file_path):
            return False
        
        # 检查锁是否过期
        if self._is_lock_expired():
            self._cleanup_expired_lock()
            return False
        
        return True
    
    def get_lock_info(self) -> Optional[Dict[str, Any]]:
        """获取当前锁信息
        
        Returns:
            锁信息字典，无锁时返回None
        """
        if not self.is_locked():
            return None
        
        return self._read_lock_info()
    
    def force_release_lock(self) -> bool:
        """强制释放锁（谨慎使用）
        
        Returns:
            是否成功释放
        """
        try:
            if os.path.exists(self.lock_file_path):
                os.remove(self.lock_file_path)
            if os.path.exists(self.lock_info_path):
                os.remove(self.lock_info_path)
            
            self.logger.warning("已强制释放同步锁")
            return True
            
        except Exception as e:
            self.logger.error(f"强制释放锁失败: {e}")
            return False
    
    @contextmanager
    def sync_lock(self, timeout: int = 0):
        """同步锁上下文管理器
        
        Args:
            timeout: 等待锁的超时时间（秒）
            
        Yields:
            是否成功获取锁
            
        Example:
            with lock_manager.sync_lock(timeout=30) as acquired:
                if acquired:
                    # 执行需要同步的操作
                    pass
                else:
                    # 处理获取锁失败的情况
                    pass
        """
        acquired = self.acquire_lock(timeout=timeout)
        try:
            yield acquired
        finally:
            if acquired:
                self.release_lock()

# 全局锁管理器实例
_global_lock_manager = None

def get_global_lock_manager() -> SyncLockManager:
    """获取全局锁管理器实例
    
    Returns:
        全局锁管理器实例
    """
    global _global_lock_manager
    if _global_lock_manager is None:
        _global_lock_manager = SyncLockManager()
    return _global_lock_manager

def main():
    """测试函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='同步锁管理器测试工具')
    parser.add_argument('--status', action='store_true', help='查看锁状态')
    parser.add_argument('--force-release', action='store_true', help='强制释放锁')
    parser.add_argument('--test-lock', action='store_true', help='测试锁机制')
    
    args = parser.parse_args()
    
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    lock_manager = SyncLockManager()
    
    if args.status:
        # 查看锁状态
        if lock_manager.is_locked():
            info = lock_manager.get_lock_info()
            print("锁状态: 已锁定")
            if info:
                print(f"PID: {info.get('pid')}")
                print(f"获取时间: {info.get('acquired_at')}")
                print(f"超时时间: {info.get('timeout')}秒")
        else:
            print("锁状态: 未锁定")
    
    elif args.force_release:
        # 强制释放锁
        if lock_manager.force_release_lock():
            print("锁已强制释放")
        else:
            print("强制释放锁失败")
    
    elif args.test_lock:
        # 测试锁机制
        print("测试锁机制...")
        
        with lock_manager.sync_lock(timeout=5) as acquired:
            if acquired:
                print("成功获取锁，模拟工作5秒...")
                time.sleep(5)
                print("工作完成")
            else:
                print("获取锁失败")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()