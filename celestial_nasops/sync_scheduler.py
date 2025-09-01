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
        
        # 注册信号处理器
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _setup_logging(self) -> logging.Logger:
        """设置调度器日志
        
        Returns:
            配置好的日志记录器
        """
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
    
    service_file = '/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/dji-media-sync.service'
    
    with open(service_file, 'w', encoding='utf-8') as f:
        f.write(service_content)
    
    print(f"Systemd服务文件已创建: {service_file}")
    print("要安装服务，请运行:")
    print(f"sudo cp {service_file} /etc/systemd/system/")
    print("sudo systemctl daemon-reload")
    print("sudo systemctl enable dji-media-sync")
    print("sudo systemctl start dji-media-sync")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='DJI媒体文件同步调度器')
    parser.add_argument('--daemon', action='store_true', help='以守护进程模式运行')
    parser.add_argument('--once', action='store_true', help='只执行一次同步')
    parser.add_argument('--interval', type=int, default=10, help='同步间隔（分钟），默认10分钟')
    parser.add_argument('--create-service', action='store_true', help='创建systemd服务文件')
    
    args = parser.parse_args()
    
    if args.create_service:
        create_systemd_service()
        return
    
    # 创建调度器实例
    scheduler = SyncScheduler(interval_minutes=args.interval)
    
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
        print("")
        
        try:
            while True:
                cmd = input("请输入命令: ").strip().lower()
                
                if cmd in ['q', 'quit', 'exit']:
                    break
                elif cmd in ['s', 'sync']:
                    scheduler.run_once()
                elif cmd == 'status':
                    status = "运行中" if scheduler.is_running() else "已停止"
                    print(f"调度器状态: {status}")
                else:
                    print("未知命令，请重新输入")
                    
        except KeyboardInterrupt:
            print("\n用户中断")
        finally:
            scheduler.stop()

if __name__ == "__main__":
    main()