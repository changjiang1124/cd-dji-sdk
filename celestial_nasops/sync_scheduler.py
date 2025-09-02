#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
媒体文件同步调度器 - 定期执行同步任务

功能说明：
1. 每10分钟自动执行一次媒体文件同步
2. 支持手动启动/停止调度
3. 记录调度执行日志
4. 支持系统服务模式运行

作者: Celestial
日期: 2024-01-22
"""

import os
import sys
import time
import signal
import logging
import threading
from datetime import datetime
from pathlib import Path

# 添加项目路径
sys.path.append('/home/celestial/dev/esdk-test/Edge-SDK')
sys.path.append('/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops')

from media_sync import MediaSyncManager
from sync_lock_manager import SyncLockManager

class SyncScheduler:
    """同步调度器"""
    
    def __init__(self, interval_minutes: int = 10):
        """初始化调度器
        
        Args:
            interval_minutes: 同步间隔（分钟）
        """
        self.interval_minutes = interval_minutes
        self.interval_seconds = interval_minutes * 60
        self.running = False
        self.scheduler_thread = None
        
        # 设置日志
        self.logger = self._setup_logging()
        
        # 创建同步管理器
        self.sync_manager = MediaSyncManager()
        
        # 创建锁管理器
        self.lock_manager = SyncLockManager()
        
        # 注册信号处理器
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _setup_logging(self) -> logging.Logger:
        """设置调度器日志
        
        Returns:
            配置好的日志记录器
        """
        import logging.handlers
        
        # 检查是否在守护进程模式下运行
        if os.getenv('DAEMON_MODE') == '1':
            # 守护进程模式：只使用系统日志
            logging.basicConfig(
                level=logging.INFO,
                format='sync-scheduler: %(levelname)s - %(message)s',
                handlers=[
                    logging.handlers.SysLogHandler(address='/dev/log')
                ]
            )
        else:
            # 普通模式：尝试使用文件和控制台日志
            try:
                log_dir = '/home/celestial/dev/esdk-test/Edge-SDK/celestial_works/logs'
                os.makedirs(log_dir, exist_ok=True)
                
                log_file = os.path.join(log_dir, 'sync_scheduler.log')
                
                # 配置日志格式
                logging.basicConfig(
                    level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler(log_file, encoding='utf-8'),
                        logging.StreamHandler(sys.stdout)
                    ]
                )
            except (OSError, PermissionError) as e:
                # 如果无法创建文件日志，回退到系统日志
                print(f"Warning: Cannot create log file: {e}")
                logging.basicConfig(
                    level=logging.INFO,
                    format='sync-scheduler: %(levelname)s - %(message)s',
                    handlers=[
                        logging.handlers.SysLogHandler(address='/dev/log')
                    ]
                )
        
        return logging.getLogger('SyncScheduler')
    
    def _signal_handler(self, signum, frame):
        """信号处理器
        
        Args:
            signum: 信号编号
            frame: 当前栈帧
        """
        self.logger.info(f"收到信号 {signum}，正在停止调度器...")
        self.stop()
    
    def _run_sync_task(self):
        """执行单次同步任务"""
        # 使用锁机制防止并发执行
        with self.lock_manager.sync_lock(timeout=30) as acquired:
            if not acquired:
                self.logger.warning("无法获取同步锁，可能有其他同步进程正在运行，跳过本次同步")
                return
            
            try:
                self.logger.info("=== 开始执行定时同步任务 ===")
                start_time = datetime.now()
                
                # 执行同步
                result = self.sync_manager.sync_all_files()
                
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                self.logger.info(
                    f"同步任务完成 - 耗时: {duration:.2f}秒, "
                    f"成功: {result['success']}, 失败: {result['failed']}"
                )
                
            except Exception as e:
                self.logger.error(f"同步任务执行异常: {e}")
    
    def _scheduler_loop(self):
        """调度器主循环"""
        self.logger.info(f"调度器启动，同步间隔: {self.interval_minutes} 分钟")
        
        # 启动时立即执行一次同步
        self._run_sync_task()
        
        while self.running:
            try:
                # 等待指定间隔时间
                for _ in range(self.interval_seconds):
                    if not self.running:
                        break
                    time.sleep(1)
                
                if self.running:
                    self._run_sync_task()
                    
                    # 处理待删除任务（每次同步后都处理一次）
                    try:
                        delete_result = self.sync_manager.process_pending_deletes()
                        if delete_result['success'] > 0 or delete_result['failed'] > 0:
                            self.logger.info(
                                f"删除任务处理完成 - 成功: {delete_result['success']}, "
                                f"失败: {delete_result['failed']}"
                            )
                    except Exception as e:
                        self.logger.error(f"处理待删除任务异常: {e}")
                    
                    # 检查存储空间并自动清理（每次同步后都检查一次）
                    try:
                        storage_info = self.sync_manager.check_storage_space()
                        if 'error' not in storage_info:
                            used_percent = storage_info.get('used_percent', 0)
                            if storage_info.get('needs_cleanup', False):
                                self.logger.warning(f"存储空间使用率达到 {used_percent:.1f}%，开始自动清理")
                                cleanup_result = self.sync_manager.cleanup_storage()
                                if 'error' not in cleanup_result:
                                    self.logger.info(
                                        f"自动清理完成 - 删除文件: {cleanup_result.get('files_deleted', 0)}, "
                                        f"释放空间: {cleanup_result.get('space_freed_gb', 0):.2f} GB"
                                    )
                                else:
                                    self.logger.error(f"自动清理失败: {cleanup_result['error']}")
                        else:
                            self.logger.error(f"检查存储空间失败: {storage_info['error']}")
                    except Exception as e:
                        self.logger.error(f"存储空间检查异常: {e}")
                    
            except Exception as e:
                self.logger.error(f"调度器循环异常: {e}")
                time.sleep(60)  # 异常时等待1分钟后继续
        
        self.logger.info("调度器已停止")
    
    def start(self):
        """启动调度器"""
        if self.running:
            self.logger.warning("调度器已在运行中")
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        
        self.logger.info("调度器已启动")
    
    def stop(self):
        """停止调度器"""
        if not self.running:
            self.logger.warning("调度器未在运行")
            return
        
        self.running = False
        
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=10)
        
        self.logger.info("调度器已停止")
    
    def is_running(self) -> bool:
        """检查调度器是否在运行
        
        Returns:
            调度器运行状态
        """
        return self.running
    
    def run_once(self):
        """手动执行一次同步任务"""
        self.logger.info("手动执行同步任务")
        self._run_sync_task()
    
    def get_sync_status(self) -> dict:
        """获取同步状态信息
        
        Returns:
            同步状态字典
        """
        lock_info = self.lock_manager.get_lock_info()
        
        # 获取删除管理器状态
        delete_status = {}
        try:
            delete_status = self.sync_manager.get_delete_status()
        except Exception as e:
            delete_status = {'error': f'获取删除状态失败: {e}'}
        
        # 获取存储状态
        storage_status = {}
        try:
            storage_status = self.sync_manager.get_storage_status()
        except Exception as e:
            storage_status = {'error': f'获取存储状态失败: {e}'}
        
        return {
            'scheduler_running': self.running,
            'sync_locked': self.lock_manager.is_locked(),
            'lock_info': lock_info,
            'delete_status': delete_status,
            'storage_status': storage_status,
            'interval_minutes': self.interval_minutes
        }
    
    def force_unlock(self) -> bool:
        """强制释放同步锁（谨慎使用）
        
        Returns:
            是否成功释放锁
        """
        self.logger.warning("强制释放同步锁")
        return self.lock_manager.force_release_lock()

def create_systemd_service():
    """创建systemd服务文件"""
    service_content = f"""[Unit]
Description=DJI Media Sync Scheduler
After=network.target

[Service]
Type=simple
User=celestial
WorkingDirectory=/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops
ExecStart=/home/celestial/dev/esdk-test/Edge-SDK/.venv/bin/python /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/sync_scheduler.py --daemon
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    
    service_file = '/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/media_sync_daemon.service'
    
    with open(service_file, 'w', encoding='utf-8') as f:
        f.write(service_content)
    
    print(f"Systemd服务文件已创建: {service_file}")
    print("要安装服务，请运行:")
    print(f"sudo cp {service_file} /etc/systemd/system/media-sync-daemon.service")
    print("sudo systemctl daemon-reload")
    print("sudo systemctl enable media-sync-daemon")
    print("sudo systemctl start media-sync-daemon")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='DJI媒体文件同步调度器')
    parser.add_argument('--daemon', action='store_true', help='以守护进程模式运行')
    parser.add_argument('--once', action='store_true', help='只执行一次同步')
    parser.add_argument('--interval', type=int, default=10, help='同步间隔（分钟），默认10分钟')
    parser.add_argument('--create-service', action='store_true', help='创建systemd服务文件')
    parser.add_argument('--status', action='store_true', help='查看同步状态')
    parser.add_argument('--force-unlock', action='store_true', help='强制释放同步锁')
    
    args = parser.parse_args()
    
    if args.create_service:
        create_systemd_service()
        return
    
    # 创建调度器实例
    scheduler = SyncScheduler(interval_minutes=args.interval)
    
    if args.status:
        # 查看同步状态
        status = scheduler.get_sync_status()
        print("\n=== 同步状态 ===")
        print(f"调度器运行状态: {'运行中' if status['scheduler_running'] else '已停止'}")
        print(f"同步锁状态: {'已锁定' if status['sync_locked'] else '未锁定'}")
        print(f"同步间隔: {status['interval_minutes']} 分钟")
        
        if status['lock_info']:
            print("\n=== 锁信息 ===")
            print(f"进程ID: {status['lock_info'].get('pid')}")
            print(f"获取时间: {status['lock_info'].get('acquired_at')}")
            print(f"超时时间: {status['lock_info'].get('timeout')} 秒")
        
        # 显示删除管理器状态
        delete_status = status.get('delete_status', {})
        if delete_status.get('enabled', False):
            print("\n=== 延迟删除状态 ===")
            print(f"待删除任务: {delete_status.get('total_pending', 0)}")
            print(f"可执行删除: {delete_status.get('ready_for_deletion', 0)}")
            print(f"等待中: {delete_status.get('waiting', 0)}")
            print(f"延迟时间: {delete_status.get('delay_minutes', 0)}分钟")
            print(f"校验和验证: {'启用' if delete_status.get('enable_checksum', False) else '禁用'}")
        elif 'error' in delete_status:
            print(f"\n删除状态获取失败: {delete_status['error']}")
        else:
            print("\n延迟删除功能: 未启用")
        return
    
    if args.force_unlock:
        # 强制释放锁
        if scheduler.force_unlock():
            print("同步锁已强制释放")
        else:
            print("强制释放锁失败")
        return
    
    if args.once:
        # 只执行一次同步
        scheduler.run_once()
    elif args.daemon:
        # 守护进程模式
        scheduler.start()
        try:
            while scheduler.is_running():
                time.sleep(1)
        except KeyboardInterrupt:
            scheduler.stop()
    else:
        # 交互模式
        scheduler.start()
        
        print("\n=== DJI媒体文件同步调度器 ===")
        print(f"同步间隔: {args.interval} 分钟")
        print("命令:")
        print("  'q' 或 'quit' - 退出")
        print("  's' 或 'sync' - 手动执行同步")
        print("  'status' - 显示状态")
        print("  'unlock' - 强制释放锁")
        print("  'process-deletes' - 处理待删除任务")
        print("  'check-storage' - 检查存储空间")
        print("  'cleanup-storage' - 清理存储空间")
        print("")
        
        try:
            while True:
                cmd = input("请输入命令: ").strip().lower()
                
                if cmd in ['q', 'quit', 'exit']:
                    break
                elif cmd in ['s', 'sync']:
                    scheduler.run_once()
                elif cmd == 'status':
                    status = scheduler.get_sync_status()
                    print(f"调度器状态: {'运行中' if status['scheduler_running'] else '已停止'}")
                    print(f"同步锁状态: {'已锁定' if status['sync_locked'] else '未锁定'}")
                    if status['lock_info']:
                        print(f"锁进程ID: {status['lock_info'].get('pid')}")
                    
                    # 显示删除管理器状态
                    delete_status = status.get('delete_status', {})
                    if delete_status.get('enabled', False):
                        print(f"\n=== 延迟删除状态 ===")
                        print(f"待删除任务: {delete_status.get('total_pending', 0)}")
                        print(f"可执行删除: {delete_status.get('ready_for_deletion', 0)}")
                        print(f"等待中: {delete_status.get('waiting', 0)}")
                        print(f"延迟时间: {delete_status.get('delay_minutes', 0)}分钟")
                        print(f"校验和验证: {'启用' if delete_status.get('enable_checksum', False) else '禁用'}")
                    elif 'error' in delete_status:
                        print(f"\n删除状态获取失败: {delete_status['error']}")
                    else:
                        print("\n延迟删除功能: 未启用")
                    
                    # 显示存储管理器状态
                    storage_status = status.get('storage_status', {})
                    if 'error' not in storage_status:
                        print(f"\n=== 存储空间状态 ===")
                        print(f"监控状态: {'运行中' if storage_status.get('monitoring_active', False) else '已停止'}")
                        print(f"上次检查: {storage_status.get('last_check_time', '未知')}")
                        print(f"检查间隔: {storage_status.get('check_interval_minutes', 0)}分钟")
                        
                        space_info = storage_status.get('current_space_info', {})
                        if space_info:
                            used_percent = space_info.get('used_percent', 0)
                            print(f"磁盘使用率: {used_percent:.1f}%")
                            print(f"可用空间: {space_info.get('available_gb', 0):.1f} GB")
                            print(f"总空间: {space_info.get('total_gb', 0):.1f} GB")
                            
                            # 显示警告状态
                            warning_threshold = storage_status.get('warning_threshold_percent', 80)
                            critical_threshold = storage_status.get('critical_threshold_percent', 90)
                            if used_percent >= critical_threshold:
                                print("⚠️  存储空间严重不足！")
                            elif used_percent >= warning_threshold:
                                print("⚠️  存储空间不足")
                    elif 'error' in storage_status:
                        print(f"\n存储状态获取失败: {storage_status['error']}")
                elif cmd == 'unlock':
                    if scheduler.force_unlock():
                        print("同步锁已强制释放")
                    else:
                        print("强制释放锁失败")
                elif cmd == 'process-deletes':
                    print("正在处理待删除任务...")
                    try:
                        result = scheduler.sync_manager.process_pending_deletes()
                        print(f"删除任务处理完成 - 成功: {result['success']}, 失败: {result['failed']}")
                    except Exception as e:
                        print(f"处理删除任务失败: {e}")
                elif cmd == 'check-storage':
                    print("正在检查存储空间...")
                    try:
                        result = scheduler.sync_manager.check_storage_space()
                        if 'error' not in result:
                            used_percent = result.get('used_percent', 0)
                            print(f"磁盘使用率: {used_percent:.1f}%")
                            print(f"可用空间: {result.get('available_gb', 0):.1f} GB")
                            print(f"总空间: {result.get('total_gb', 0):.1f} GB")
                            
                            if result.get('needs_cleanup', False):
                                print("⚠️  建议进行存储清理")
                        else:
                            print(f"检查存储空间失败: {result['error']}")
                    except Exception as e:
                        print(f"检查存储空间失败: {e}")
                elif cmd == 'cleanup-storage':
                    print("正在清理存储空间...")
                    try:
                        result = scheduler.sync_manager.cleanup_storage()
                        if 'error' not in result:
                            print(f"清理完成 - 删除文件: {result.get('files_deleted', 0)}")
                            print(f"释放空间: {result.get('space_freed_gb', 0):.2f} GB")
                        else:
                            print(f"清理存储空间失败: {result['error']}")
                    except Exception as e:
                        print(f"清理存储空间失败: {e}")
                else:
                    print("未知命令，请重新输入")
                    
        except KeyboardInterrupt:
            print("\n用户中断")
        finally:
            scheduler.stop()

if __name__ == "__main__":
    main()