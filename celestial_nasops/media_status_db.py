#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@file media_status_db.py
@brief 媒体文件传输状态数据库操作类 (Python版本)
@author Celestial
@date 2025-01-22

功能说明：
1. 提供Python接口操作SQLite数据库
2. 查询待传输的媒体文件
3. 更新文件传输状态
4. 支持统计和维护功能
"""

import os
import sqlite3
import threading
import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from enum import Enum
from dataclasses import dataclass


class FileStatus(Enum):
    """文件状态枚举"""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class MediaFileInfo:
    """媒体文件信息数据类"""
    id: int
    file_path: str
    file_name: str
    file_size: int
    file_hash: str
    download_status: FileStatus
    download_start_time: str
    download_end_time: str
    download_retry_count: int
    transfer_status: FileStatus
    transfer_start_time: str
    transfer_end_time: str
    transfer_retry_count: int
    last_error_message: str
    created_at: str
    updated_at: str


class MediaStatusDB:
    """媒体文件传输状态数据库操作类"""
    
    def __init__(self, db_path: str = "/data/temp/dji/media_status.db"):
        """
        初始化数据库连接
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.connection = None
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        
    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()
        
    def connect(self) -> bool:
        """
        连接到数据库
        
        Returns:
            bool: 连接成功返回True
        """
        try:
            with self.lock:
                if self.connection is None:
                    # 确保数据库目录存在
                    db_dir = os.path.dirname(self.db_path)
                    if db_dir and not os.path.exists(db_dir):
                        os.makedirs(db_dir, exist_ok=True)
                        self.logger.info(f"创建数据库目录: {db_dir}")
                    
                    self.connection = sqlite3.connect(
                        self.db_path, 
                        check_same_thread=False,
                        timeout=30.0
                    )
                    self.connection.row_factory = sqlite3.Row
                    # 启用外键约束
                    self.connection.execute("PRAGMA foreign_keys = ON")
                    # 设置WAL模式
                    self.connection.execute("PRAGMA journal_mode = WAL")
                    self.connection.commit()
                    
                    # 初始化数据库表结构
                    self._initialize_tables()
                    
                self.logger.info(f"数据库连接成功: {self.db_path}")
                return True
                
        except sqlite3.Error as e:
            self.logger.error(f"数据库连接失败: {e}")
            return False
    
    def _initialize_tables(self):
        """
        初始化数据库表结构
        """
        try:
            cursor = self.connection.cursor()
            
            # 创建媒体文件传输状态表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS media_transfer_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL UNIQUE,
                    file_name TEXT NOT NULL,
                    file_size INTEGER DEFAULT 0,
                    file_hash TEXT DEFAULT '',
                    
                    download_status TEXT NOT NULL DEFAULT 'pending',
                    download_start_time DATETIME,
                    download_end_time DATETIME,
                    download_retry_count INTEGER DEFAULT 0,
                    
                    transfer_status TEXT NOT NULL DEFAULT 'pending',
                    transfer_start_time DATETIME,
                    transfer_end_time DATETIME,
                    transfer_retry_count INTEGER DEFAULT 0,
                    
                    last_error_message TEXT DEFAULT '',
                    
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_path ON media_transfer_status(file_path)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_download_status ON media_transfer_status(download_status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_transfer_status ON media_transfer_status(transfer_status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON media_transfer_status(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_updated_at ON media_transfer_status(updated_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_status_combo ON media_transfer_status(download_status, transfer_status)")
            
            # 创建触发器自动更新updated_at字段
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS update_media_transfer_status_updated_at
                    AFTER UPDATE ON media_transfer_status
                    FOR EACH ROW
                BEGIN
                    UPDATE media_transfer_status 
                    SET updated_at = CURRENT_TIMESTAMP 
                    WHERE id = NEW.id;
                END
            """)
            
            self.connection.commit()
            cursor.close()
            self.logger.info("数据库表结构初始化完成")
            
        except sqlite3.Error as e:
            self.logger.error(f"初始化数据库表失败: {e}")
            raise
            
    def close(self):
        """关闭数据库连接"""
        with self.lock:
            if self.connection:
                self.connection.close()
                self.connection = None
                self.logger.info("数据库连接已关闭")
                
    def get_ready_to_transfer_files(self) -> List[MediaFileInfo]:
        """
        获取准备传输的文件列表（下载完成但未传输的文件）
        
        Returns:
            List[MediaFileInfo]: 待传输文件列表
        """
        files = []
        
        try:
            with self.lock:
                if not self.connection:
                    self.logger.error("数据库未连接")
                    return files
                    
                cursor = self.connection.cursor()
                cursor.execute("""
                    SELECT id, file_path, file_name, file_size, file_hash,
                           download_status, download_start_time, download_end_time, download_retry_count,
                           transfer_status, transfer_start_time, transfer_end_time, transfer_retry_count,
                           last_error_message, created_at, updated_at
                    FROM media_transfer_status 
                    WHERE download_status = 'completed' AND transfer_status = 'pending'
                    ORDER BY created_at ASC
                """)
                
                rows = cursor.fetchall()
                for row in rows:
                    file_info = MediaFileInfo(
                        id=row['id'],
                        file_path=row['file_path'],
                        file_name=row['file_name'],
                        file_size=row['file_size'],
                        file_hash=row['file_hash'] or "",
                        download_status=FileStatus(row['download_status']),
                        download_start_time=row['download_start_time'] or "",
                        download_end_time=row['download_end_time'] or "",
                        download_retry_count=row['download_retry_count'],
                        transfer_status=FileStatus(row['transfer_status']),
                        transfer_start_time=row['transfer_start_time'] or "",
                        transfer_end_time=row['transfer_end_time'] or "",
                        transfer_retry_count=row['transfer_retry_count'],
                        last_error_message=row['last_error_message'] or "",
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    )
                    files.append(file_info)
                    
                cursor.close()
                self.logger.info(f"查询到 {len(files)} 个待传输文件")
                
        except sqlite3.Error as e:
            self.logger.error(f"查询待传输文件失败: {e}")
            
        return files
        
    def update_transfer_status(self, file_path: str, status: FileStatus, error_message: str = "") -> bool:
        """
        更新文件传输状态
        
        Args:
            file_path: 文件路径
            status: 新状态
            error_message: 错误信息（可选）
            
        Returns:
            bool: 更新成功返回True
        """
        try:
            with self.lock:
                if not self.connection:
                    self.logger.error("数据库未连接")
                    return False
                    
                cursor = self.connection.cursor()
                
                # 构建SQL语句
                sql = "UPDATE media_transfer_status SET transfer_status = ?, "
                params = [status.value]
                
                if status == FileStatus.DOWNLOADING:  # 传输开始
                    sql += "transfer_start_time = CURRENT_TIMESTAMP, "
                elif status == FileStatus.COMPLETED:  # 传输完成
                    sql += "transfer_end_time = CURRENT_TIMESTAMP, "
                elif status == FileStatus.FAILED:  # 传输失败
                    sql += "transfer_retry_count = transfer_retry_count + 1, "
                    
                sql += "last_error_message = ? WHERE file_path = ?"
                params.extend([error_message, file_path])
                
                cursor.execute(sql, params)
                self.connection.commit()
                
                if cursor.rowcount > 0:
                    self.logger.info(f"文件传输状态已更新: {file_path} -> {status.value}")
                    cursor.close()
                    return True
                else:
                    self.logger.warning(f"未找到文件记录: {file_path}")
                    cursor.close()
                    return False
                    
        except sqlite3.Error as e:
            self.logger.error(f"更新传输状态失败: {e}")
            return False
            
    def get_file_info(self, file_path: str) -> Optional[MediaFileInfo]:
        """
        获取指定文件的详细信息
        
        Args:
            file_path: 文件路径
            
        Returns:
            Optional[MediaFileInfo]: 文件信息，未找到返回None
        """
        try:
            with self.lock:
                if not self.connection:
                    self.logger.error("数据库未连接")
                    return None
                    
                cursor = self.connection.cursor()
                cursor.execute("""
                    SELECT id, file_path, file_name, file_size, file_hash,
                           download_status, download_start_time, download_end_time, download_retry_count,
                           transfer_status, transfer_start_time, transfer_end_time, transfer_retry_count,
                           last_error_message, created_at, updated_at
                    FROM media_transfer_status WHERE file_path = ?
                """, (file_path,))
                
                row = cursor.fetchone()
                cursor.close()
                
                if row:
                    return MediaFileInfo(
                        id=row['id'],
                        file_path=row['file_path'],
                        file_name=row['file_name'],
                        file_size=row['file_size'],
                        file_hash=row['file_hash'] or "",
                        download_status=FileStatus(row['download_status']),
                        download_start_time=row['download_start_time'] or "",
                        download_end_time=row['download_end_time'] or "",
                        download_retry_count=row['download_retry_count'],
                        transfer_status=FileStatus(row['transfer_status']),
                        transfer_start_time=row['transfer_start_time'] or "",
                        transfer_end_time=row['transfer_end_time'] or "",
                        transfer_retry_count=row['transfer_retry_count'],
                        last_error_message=row['last_error_message'] or "",
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    )
                else:
                    return None
                    
        except sqlite3.Error as e:
            self.logger.error(f"查询文件信息失败: {e}")
            return None
            
    def insert_file_record(self, file_path: str, file_name: str, file_size: int, 
                          file_hash: str = "", download_status: str = "pending", 
                          transfer_status: str = "pending") -> bool:
        """
        插入新的文件记录到数据库
        
        Args:
            file_path: 文件路径
            file_name: 文件名
            file_size: 文件大小（字节）
            file_hash: 文件哈希值（可选）
            download_status: 下载状态（默认pending）
            transfer_status: 传输状态（默认pending）
            
        Returns:
            bool: 插入成功返回True
        """
        try:
            with self.lock:
                if not self.connection:
                    self.logger.error("数据库未连接")
                    return False
                    
                # 检查文件是否已存在（直接在锁内执行，避免死锁）
                cursor = self.connection.cursor()
                cursor.execute(
                    "SELECT COUNT(*) FROM media_transfer_status WHERE file_path = ?", 
                    (file_path,)
                )
                count = cursor.fetchone()[0]
                if count > 0:
                    cursor.close()
                    self.logger.warning(f"文件记录已存在: {file_path}")
                    return False
                cursor.execute("""
                    INSERT INTO media_transfer_status (
                        file_path, file_name, file_size, file_hash,
                        download_status, download_start_time, download_end_time, download_retry_count,
                        transfer_status, transfer_start_time, transfer_end_time, transfer_retry_count,
                        last_error_message
                    ) VALUES (
                        ?, ?, ?, ?,
                        ?, 
                        CASE WHEN ? = 'completed' THEN CURRENT_TIMESTAMP ELSE NULL END,
                        CASE WHEN ? = 'completed' THEN CURRENT_TIMESTAMP ELSE NULL END,
                        0,
                        ?, NULL, NULL, 0,
                        ''
                    )
                """, (
                    file_path, file_name, file_size, file_hash,
                    download_status, download_status, download_status,
                    transfer_status
                ))
                
                self.connection.commit()
                cursor.close()
                
                self.logger.info(f"文件记录插入成功: {file_path} (下载状态: {download_status}, 传输状态: {transfer_status})")
                return True
                
        except sqlite3.Error as e:
            self.logger.error(f"插入文件记录失败: {e}")
            return False
            
    def file_exists(self, file_path: str) -> bool:
        """
        检查文件是否存在于数据库中
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 存在返回True
        """
        try:
            with self.lock:
                if not self.connection:
                    return False
                    
                cursor = self.connection.cursor()
                cursor.execute(
                    "SELECT COUNT(*) FROM media_transfer_status WHERE file_path = ?", 
                    (file_path,)
                )
                
                count = cursor.fetchone()[0]
                cursor.close()
                return count > 0
                
        except sqlite3.Error as e:
            self.logger.error(f"检查文件存在性失败: {e}")
            return False
            
    def get_statistics(self) -> Dict[str, int]:
        """
        获取数据库统计信息
        
        Returns:
            Dict[str, int]: 统计信息字典
        """
        stats = {
            'total_files': 0,
            'downloaded_files': 0,
            'transferred_files': 0,
            'failed_files': 0
        }
        
        try:
            with self.lock:
                if not self.connection:
                    return stats
                    
                cursor = self.connection.cursor()
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN download_status = 'completed' THEN 1 ELSE 0 END) as downloaded,
                        SUM(CASE WHEN transfer_status = 'completed' THEN 1 ELSE 0 END) as transferred,
                        SUM(CASE WHEN download_status = 'failed' OR transfer_status = 'failed' THEN 1 ELSE 0 END) as failed
                    FROM media_transfer_status
                    WHERE file_path != '__INIT_MARKER__'
                """)
                
                row = cursor.fetchone()
                if row:
                    stats['total_files'] = row[0] or 0
                    stats['downloaded_files'] = row[1] or 0
                    stats['transferred_files'] = row[2] or 0
                    stats['failed_files'] = row[3] or 0
                    
                cursor.close()
                
        except sqlite3.Error as e:
            self.logger.error(f"获取统计信息失败: {e}")
            
        return stats
        
    def cleanup_old_records(self, days_old: int = 30) -> int:
        """
        清理旧记录
        
        Args:
            days_old: 保留天数，超过此天数的记录将被删除
            
        Returns:
            int: 删除的记录数，失败返回-1
        """
        try:
            with self.lock:
                if not self.connection:
                    return -1
                    
                cursor = self.connection.cursor()
                cursor.execute("""
                    DELETE FROM media_transfer_status 
                    WHERE created_at < datetime('now', '-' || ? || ' days')
                    AND file_path != '__INIT_MARKER__'
                """, (days_old,))
                
                deleted_count = cursor.rowcount
                self.connection.commit()
                cursor.close()
                
                self.logger.info(f"清理了 {deleted_count} 条旧记录（超过 {days_old} 天）")
                return deleted_count
                
        except sqlite3.Error as e:
            self.logger.error(f"清理旧记录失败: {e}")
            return -1
            
    def get_failed_files(self, max_retry_count: int = 3) -> List[MediaFileInfo]:
        """
        获取传输失败的文件列表（重试次数未超过限制）
        
        Args:
            max_retry_count: 最大重试次数
            
        Returns:
            List[MediaFileInfo]: 失败文件列表
        """
        files = []
        
        try:
            with self.lock:
                if not self.connection:
                    return files
                    
                cursor = self.connection.cursor()
                cursor.execute("""
                    SELECT id, file_path, file_name, file_size, file_hash,
                           download_status, download_start_time, download_end_time, download_retry_count,
                           transfer_status, transfer_start_time, transfer_end_time, transfer_retry_count,
                           last_error_message, created_at, updated_at
                    FROM media_transfer_status 
                    WHERE transfer_status = 'failed' AND transfer_retry_count < ?
                    ORDER BY updated_at ASC
                """, (max_retry_count,))
                
                rows = cursor.fetchall()
                for row in rows:
                    file_info = MediaFileInfo(
                        id=row['id'],
                        file_path=row['file_path'],
                        file_name=row['file_name'],
                        file_size=row['file_size'],
                        file_hash=row['file_hash'] or "",
                        download_status=FileStatus(row['download_status']),
                        download_start_time=row['download_start_time'] or "",
                        download_end_time=row['download_end_time'] or "",
                        download_retry_count=row['download_retry_count'],
                        transfer_status=FileStatus(row['transfer_status']),
                        transfer_start_time=row['transfer_start_time'] or "",
                        transfer_end_time=row['transfer_end_time'] or "",
                        transfer_retry_count=row['transfer_retry_count'],
                        last_error_message=row['last_error_message'] or "",
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    )
                    files.append(file_info)
                    
                cursor.close()
                
        except sqlite3.Error as e:
            self.logger.error(f"查询失败文件失败: {e}")
            
        return files
    
    def get_files_by_status(self, status: str) -> List[Dict[str, any]]:
        """获取指定状态的文件列表
        
        Args:
            status: 文件状态
            
        Returns:
            List[Dict]: 文件信息列表
        """
        files = []
        
        # 规范化状态入参，支持大小写与别名映射
        normalized = (status.value if hasattr(status, 'value') else status or "").strip().lower()
        alias_map = {
            'transferred': 'completed',   # 测试中使用的状态名 -> 数据库状态
            'transferring': 'downloading', # 测试中使用的状态名 -> 数据库状态
            'pending': 'pending'          # 确保 PENDING -> pending 的映射
        }
        target_status = alias_map.get(normalized, normalized)
        
        try:
            with self.lock:
                if not self.connection:
                    return files
                    
                cursor = self.connection.cursor()
                cursor.execute("""
                    SELECT id, file_path, file_name, file_size, file_hash,
                           download_status, download_start_time, download_end_time, download_retry_count,
                           transfer_status, transfer_start_time, transfer_end_time, transfer_retry_count,
                           last_error_message, created_at, updated_at
                    FROM media_transfer_status 
                    WHERE transfer_status = ?
                    ORDER BY created_at ASC
                """, (target_status,))
                
                rows = cursor.fetchall()
                for row in rows:
                    file_dict = {
                        'id': row['id'],
                        'file_path': row['file_path'],
                        'filename': row['file_name'],
                        'file_size': row['file_size'],
                        'file_hash': row['file_hash'] or "",
                        'download_status': row['download_status'],
                        'transfer_status': row['transfer_status'],
                        'created_at': row['created_at'],
                        'updated_at': row['updated_at']
                    }
                    files.append(file_dict)
                    
                cursor.close()
                
        except sqlite3.Error as e:
            self.logger.error(f"查询状态文件失败: {e}")
            
        return files
    
    def get_all_files(self) -> List[Dict[str, any]]:
        """获取所有文件列表
        
        Returns:
            List[Dict]: 文件信息列表
        """
        files = []
        
        try:
            with self.lock:
                if not self.connection:
                    return files
                    
                cursor = self.connection.cursor()
                cursor.execute("""
                    SELECT id, file_path, file_name, file_size, file_hash,
                           download_status, download_start_time, download_end_time, download_retry_count,
                           transfer_status, transfer_start_time, transfer_end_time, transfer_retry_count,
                           last_error_message, created_at, updated_at
                    FROM media_transfer_status 
                    WHERE file_path != '__INIT_MARKER__'
                    ORDER BY created_at ASC
                """)
                
                rows = cursor.fetchall()
                for row in rows:
                    file_dict = {
                        'id': row['id'],
                        'file_path': row['file_path'],
                        'filename': row['file_name'],
                        'file_size': row['file_size'],
                        'file_hash': row['file_hash'] or "",
                        'download_status': row['download_status'],
                        'transfer_status': row['transfer_status'],
                        'created_at': row['created_at'],
                        'updated_at': row['updated_at']
                    }
                    files.append(file_dict)
                    
                cursor.close()
                
        except sqlite3.Error as e:
            self.logger.error(f"查询所有文件失败: {e}")
            
        return files


def main():
    """测试函数"""
    logging.basicConfig(level=logging.INFO)
    
    # 测试数据库操作
    with MediaStatusDB() as db:
        if db.connect():
            # 获取统计信息
            stats = db.get_statistics()
            print(f"数据库统计: {stats}")
            
            # 获取待传输文件
            files = db.get_ready_to_transfer_files()
            print(f"待传输文件数量: {len(files)}")
            
            for file_info in files[:5]:  # 只显示前5个
                print(f"  - {file_info.file_name} ({file_info.file_size} bytes)")


if __name__ == "__main__":
    main()