#!/usr/bin/env python3
"""
Media Finding Daemon - 统一同步架构优化方案核心组件

功能：
1. 监控媒体文件目录，发现新文件
2. 独占管理数据库操作，避免并发冲突
3. 线性传输模式，按优先级处理文件
4. 详细日志记录，便于问题追踪
5. 配置化文件过滤策略

作者: Edge-SDK Team
版本: 1.0.0
"""

import os
import sys
import time
import hashlib
import logging
import sqlite3
import json
import fnmatch
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Set
from logging.handlers import RotatingFileHandler
from enum import Enum

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config_manager import ConfigManager
from media_status_db import MediaStatusDB

class FileStatus(Enum):
    """文件传输状态枚举"""
    PENDING = "PENDING"
    TRANSFERRING = "TRANSFERRING"
    TRANSFERRED = "TRANSFERRED"
    FAILED = "FAILED"

class MediaFindingDaemon:
    """媒体文件发现和传输管理守护进程"""
    
    def __init__(self, config_path: str = None):
        """初始化守护进程
        
        Args:
            config_path: 配置文件路径，默认使用unified_config.json
        """
        self.config_path = config_path or "/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/unified_config.json"
        self.config_manager = ConfigManager(self.config_path)
        
        # 初始化配置
        self._load_config()
        
        # 初始化日志
        self.logger = self._setup_logging()
        
        # 初始化数据库
        self.db = MediaStatusDB(self.db_path)
        self.db.connect()
        
        # 运行状态
        self.running = False
        
        self.logger.info("MediaFindingDaemon 初始化完成")
        self.logger.info(f"监控目录: {self.media_directory}")
        self.logger.info(f"数据库路径: {self.db_path}")
        self.logger.info(f"文件过滤策略: {self.filter_strategy}")
    
    def _load_config(self):
        """加载配置文件"""
        # 基础配置
        self.media_directory = self.config_manager.get('local_settings.media_directory', '/home/celestial/dev/esdk-test/Edge-SDK/celestial_works/media')
        self.db_path = self.config_manager.get('database.path', '/home/celestial/dev/esdk-test/Edge-SDK/celestial_works/media_status.db')
        
        # 日志配置
        self.log_file_path = self.config_manager.get('logging.media_finding_log', '/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/logs/media_finding.log')
        self.log_level = self.config_manager.get('logging.level', 'INFO')
        
        # 文件过滤配置
        self._load_filter_config()
        
        # 传输配置
        self.scan_interval = self.config_manager.get('transfer.scan_interval', 30)  # 扫描间隔（秒）
        self.batch_size = self.config_manager.get('transfer.batch_size', 10)  # 批处理大小
        
        # NAS配置
        self.nas_host = self.config_manager.get('nas.host', '192.168.1.100')
        self.nas_username = self.config_manager.get('nas.username', 'admin')
        self.nas_password = self.config_manager.get('nas.password', '')
        self.nas_destination = self.config_manager.get('nas.destination_path', '/volume1/EdgeData')
    
    def _load_filter_config(self):
        """加载文件过滤配置"""
        self.filter_strategy = self.config_manager.get('file_sync.filter_strategy', 'extended')
        self.custom_extensions = set(self.config_manager.get('file_sync.custom_extensions', []))
        self.exclude_patterns = self.config_manager.get('file_sync.exclude_patterns', [
            '.*', '.tmp_*', '*.tmp', '.DS_Store', 'Thumbs.db', 'desktop.ini'
        ])
        
        # 预定义的扩展名集合
        self.media_extensions = {
            '.mp4', '.mov', '.jpg', '.jpeg', '.png', '.dng'
        }
        
        self.extended_extensions = {
            # 视频文件
            '.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v',
            # 图片文件
            '.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', '.webp',
            # RAW格式
            '.dng', '.raw', '.cr2', '.nef', '.arw', '.orf', '.rw2',
            # 文档文件
            '.txt', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            # 数据文件
            '.csv', '.json', '.xml', '.log', '.las', '.laz',
            # 压缩文件
            '.zip', '.rar', '.7z', '.tar', '.gz',
            # 其他常见格式
            '.kml', '.kmz', '.gpx', '.shp'
        }
    
    def _setup_logging(self) -> logging.Logger:
        """设置详细的日志记录系统"""
        # 确保日志目录存在
        log_dir = os.path.dirname(self.log_file_path)
        os.makedirs(log_dir, exist_ok=True)
        
        # 创建logger
        logger = logging.getLogger('media_finding')
        logger.setLevel(getattr(logging, self.log_level.upper()))
        
        # 清除已有的处理器
        logger.handlers.clear()
        
        # 创建文件处理器，支持日志轮转
        file_handler = RotatingFileHandler(
            self.log_file_path,
            maxBytes=50*1024*1024,  # 50MB
            backupCount=5
        )
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        
        # 设置详细的日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def _should_process_file(self, filename: str) -> bool:
        """根据配置的策略判断是否应该处理该文件"""
        # 检查排除模式
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(filename, pattern) or filename.startswith(pattern.rstrip('*')):
                return False
        
        # 根据策略决定是否处理
        if self.filter_strategy == 'all_files':
            return True
        
        file_ext = os.path.splitext(filename)[1].lower()
        
        if self.filter_strategy == 'media_only':
            return file_ext in self.media_extensions
        
        elif self.filter_strategy == 'extended':
            # 如果文件没有扩展名，也允许同步（如某些数据文件）
            return not file_ext or file_ext in self.extended_extensions
        
        elif self.filter_strategy == 'custom':
            return not file_ext or file_ext in self.custom_extensions
        
        # 默认使用扩展策略
        return not file_ext or file_ext in self.extended_extensions
    
    def _scan_media_directory(self) -> List[str]:
        """扫描媒体目录发现新文件"""
        new_files = []
        
        if not os.path.exists(self.media_directory):
            self.logger.warning(f"媒体目录不存在: {self.media_directory}")
            return new_files
        
        try:
            for root, dirs, files in os.walk(self.media_directory):
                for filename in files:
                    if self._should_process_file(filename):
                        file_path = os.path.join(root, filename)
                        new_files.append(file_path)
        
        except Exception as e:
            self.logger.error(f"扫描目录失败: {str(e)}")
        
        return new_files
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """计算文件哈希值，针对大文件优化
        
        对于大文件（>100MB），使用采样哈希策略：
        - 文件头部 1MB + 文件中部 1MB + 文件尾部 1MB
        - 文件大小和修改时间
        """
        try:
            file_size = os.path.getsize(file_path)
            
            # 小文件直接计算完整哈希
            if file_size < 100 * 1024 * 1024:  # 100MB
                return self._calculate_full_hash(file_path)
            
            # 大文件使用采样哈希
            return self._calculate_sampled_hash(file_path, file_size)
        
        except Exception as e:
            self.logger.error(f"计算文件哈希失败: {file_path}, 错误: {str(e)}")
            return ""
    
    def _calculate_full_hash(self, file_path: str) -> str:
        """计算完整文件哈希"""
        hasher = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        
        return hasher.hexdigest()
    
    def _calculate_sampled_hash(self, file_path: str, file_size: int) -> str:
        """大文件采样哈希计算 - 30GB文件约耗时1-2秒"""
        hasher = hashlib.sha256()
        sample_size = 1024 * 1024  # 1MB
        
        with open(file_path, 'rb') as f:
            # 文件头部 1MB
            hasher.update(f.read(sample_size))
            
            # 文件中部 1MB
            if file_size > 2 * sample_size:
                f.seek(file_size // 2 - sample_size // 2)
                hasher.update(f.read(sample_size))
            
            # 文件尾部 1MB
            if file_size > sample_size:
                f.seek(-sample_size, 2)
                hasher.update(f.read(sample_size))
        
        # 添加文件元信息
        stat = os.stat(file_path)
        hasher.update(str(file_size).encode())
        hasher.update(str(int(stat.st_mtime)).encode())
        
        return hasher.hexdigest()
    
    def discover_and_register_files(self):
        """发现新文件并注册到数据库"""
        start_time = time.time()
        
        # 1. 扫描文件夹发现新文件
        self.logger.info("开始扫描媒体文件目录")
        new_files = self._scan_media_directory()
        self.logger.info(f"扫描完成，发现 {len(new_files)} 个文件")
        
        if not new_files:
            self.logger.info("没有发现新文件")
            return
        
        processed_count = 0
        skipped_count = 0
        registered_count = 0
        
        for file_path in new_files:
            try:
                processed_count += 1
                filename = os.path.basename(file_path)
                file_size = os.path.getsize(file_path)
                
                self.logger.info(f"处理文件 [{processed_count}/{len(new_files)}]: {filename} ({file_size} bytes)")
                
                # 2. 计算文件哈希（用于去重）
                hash_start = time.time()
                file_hash = self._calculate_file_hash(file_path)
                hash_duration = time.time() - hash_start
                
                if not file_hash:
                    self.logger.error(f"无法计算文件哈希，跳过: {filename}")
                    continue
                
                self.logger.info(f"文件哈希计算完成: {filename}, 哈希: {file_hash[:16]}..., 耗时: {hash_duration:.2f}秒")
                
                # 3. 检查数据库中是否已存在（通过文件路径）
                if self.db.file_exists(file_path):
                    skipped_count += 1
                    self.logger.info(f"文件已存在数据库，跳过: {filename}")
                    continue
                
                # 4. 文件不存在，添加新记录并标记为 pending
                success = self.db.insert_file_record(
                    file_path=file_path,
                    file_name=filename,
                    file_size=file_size,
                    file_hash=file_hash,
                    download_status="completed",
                    transfer_status="pending"
                )
                
                if success:
                    registered_count += 1
                    self.logger.info(f"新文件已注册到数据库: {filename}, 状态: PENDING")
                else:
                    self.logger.error(f"文件注册失败: {filename}")

                
            except Exception as e:
                self.logger.error(f"处理文件失败: {filename}, 错误: {str(e)}")
        
        total_duration = time.time() - start_time
        self.logger.info(f"文件发现和注册完成 - 总计: {processed_count}, 新注册: {registered_count}, 跳过: {skipped_count}, 总耗时: {total_duration:.2f}秒")
    
    def process_pending_files(self):
        """处理数据库中 pending 状态的文件"""
        start_time = time.time()
        
        # 1. 查询所有待传输的文件
        self.logger.info("开始查询待传输文件")
        pending_files = self.db.get_ready_to_transfer_files()
        self.logger.info(f"查询到 {len(pending_files)} 个待传输文件")
        
        if not pending_files:
            self.logger.info("没有待传输文件，跳过处理")
            return
        
        # 按文件大小排序：小文件优先
        pending_files.sort(key=lambda x: x.file_size)
        
        success_count = 0
        failed_count = 0
        
        for index, file_info in enumerate(pending_files[:self.batch_size], 1):
            filename = file_info.file_name
            file_path = file_info.file_path
            file_size = file_info.file_size
            
            try:
                self.logger.info(f"开始处理文件 [{index}/{min(len(pending_files), self.batch_size)}]: {filename} (大小: {file_size} bytes)")
                
                # 2. 开始传输前，更新状态为传输中
                from media_status_db import FileStatus as DBFileStatus
                self.db.update_transfer_status(file_path, DBFileStatus.DOWNLOADING)
                self.logger.info(f"文件状态已更新为 DOWNLOADING: {filename}")
                
                # 3. 执行文件传输
                transfer_start_time = time.time()
                success = self._transfer_file_to_nas(file_path)
                transfer_duration = time.time() - transfer_start_time
                
                # 4. 根据传输结果更新状态
                if success:
                    success_count += 1
                    transfer_speed = file_size / transfer_duration if transfer_duration > 0 else 0
                    self.db.update_transfer_status(file_path, DBFileStatus.COMPLETED)
                    self.logger.info(f"文件传输成功: {filename}, 耗时: {transfer_duration:.2f}秒, 速度: {transfer_speed/1024/1024:.2f} MB/s")
                else:
                    failed_count += 1
                    self.db.update_transfer_status(file_path, DBFileStatus.FAILED, "传输失败")
                    self.logger.error(f"文件传输失败: {filename}, 耗时: {transfer_duration:.2f}秒")
                    
            except Exception as e:
                failed_count += 1
                error_msg = str(e)
                from media_status_db import FileStatus as DBFileStatus
                self.db.update_transfer_status(file_path, DBFileStatus.FAILED, error_msg)
                self.logger.error(f"文件处理异常: {filename}, 错误: {error_msg}")
        
        total_duration = time.time() - start_time
        self.logger.info(f"待传输文件处理完成 - 成功: {success_count}, 失败: {failed_count}, 总耗时: {total_duration:.2f}秒")
    
    def _transfer_file_to_nas(self, file_path: str) -> bool:
        """传输文件到NAS
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 传输是否成功
        """
        try:
            filename = os.path.basename(file_path)
            
            # 检查源文件是否存在
            if not os.path.exists(file_path):
                self.logger.error(f"源文件不存在: {file_path}")
                return False
            
            # 构建目标路径
            # 这里简化实现，实际应该使用rsync或scp等工具
            # 目前先模拟传输过程
            self.logger.info(f"模拟传输文件到NAS: {filename}")
            
            # 模拟传输延迟
            file_size = os.path.getsize(file_path)
            # 模拟传输速度：10MB/s
            simulated_duration = max(0.1, file_size / (10 * 1024 * 1024))
            time.sleep(min(simulated_duration, 2.0))  # 最多等待2秒
            
            # TODO: 实际实现应该调用rsync或其他传输工具
            # 例如: rsync -avz source_path user@nas_host:destination_path
            
            return True
            
        except Exception as e:
            self.logger.error(f"传输文件异常: {str(e)}")
            return False
    
    def run_cycle(self):
        """执行一次完整的处理周期"""
        cycle_start = time.time()
        self.logger.info("开始新的处理周期")
        
        try:
            # 阶段A: 文件发现和注册
            self.discover_and_register_files()
            
            # 阶段B: 处理待传输文件
            self.process_pending_files()
            
        except Exception as e:
            self.logger.error(f"处理周期异常: {str(e)}")
        
        cycle_duration = time.time() - cycle_start
        self.logger.info(f"处理周期完成，耗时: {cycle_duration:.2f}秒")
    
    def start(self):
        """启动守护进程"""
        self.logger.info("MediaFindingDaemon 启动")
        self.running = True
        
        try:
            while self.running:
                self.run_cycle()
                
                # 等待下一个扫描周期
                self.logger.info(f"等待 {self.scan_interval} 秒后进行下一次扫描")
                time.sleep(self.scan_interval)
                
        except KeyboardInterrupt:
            self.logger.info("收到中断信号，正在停止...")
        except Exception as e:
            self.logger.error(f"守护进程异常: {str(e)}")
        finally:
            self.stop()
    
    def stop(self):
        """停止守护进程"""
        self.logger.info("MediaFindingDaemon 停止")
        self.running = False
        
        # 关闭数据库连接
        if hasattr(self, 'db'):
            self.db.close()

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Media Finding Daemon - 统一同步架构优化方案')
    parser.add_argument('--config', '-c', help='配置文件路径')
    parser.add_argument('--once', action='store_true', help='只运行一次，不循环')
    
    args = parser.parse_args()
    
    # 创建守护进程实例
    daemon = MediaFindingDaemon(config_path=args.config)
    
    if args.once:
        # 只运行一次
        daemon.run_cycle()
    else:
        # 持续运行
        daemon.start()

if __name__ == '__main__':
    main()