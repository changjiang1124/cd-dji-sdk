#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全删除管理器 - 实现延迟删除机制

功能说明：
1. 替换立即删除为延迟删除，提高数据安全性
2. 在删除前验证远程文件完整性
3. 支持删除任务的持久化存储
4. 提供删除任务的管理和监控功能
5. 支持批量处理和错误恢复

作者: Celestial
日期: 2024-01-22
"""

import os
import json
import time
import hashlib
import subprocess
import logging
import logging.handlers
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict

@dataclass
class DeleteTask:
    """删除任务数据类"""
    local_file_path: str          # 本地文件路径
    remote_file_path: str         # 远程文件路径
    local_checksum: str           # 本地文件校验和
    scheduled_time: float         # 计划删除时间（时间戳）
    retry_count: int = 0          # 重试次数
    max_retries: int = 3          # 最大重试次数
    created_time: float = None    # 创建时间
    
    def __post_init__(self):
        if self.created_time is None:
            self.created_time = time.time()
    
    def is_ready_for_deletion(self) -> bool:
        """检查是否可以执行删除"""
        return time.time() >= self.scheduled_time
    
    def should_retry(self) -> bool:
        """检查是否应该重试"""
        return self.retry_count < self.max_retries
    
    def increment_retry(self):
        """增加重试次数"""
        self.retry_count += 1

class SafeDeleteManager:
    """安全删除管理器
    
    实现延迟删除机制，确保文件在远程验证成功后才删除本地副本
    """
    
    def __init__(self, 
                 nas_host: str = "192.168.200.103",
                 nas_username: str = "edge_sync",
                 delay_minutes: int = 30,
                 pending_file: str = None,
                 enable_checksum: bool = True,
                 nas_alias: str = "nas-edge"):
        """初始化安全删除管理器
        
        Args:
            nas_host: NAS主机地址
            nas_username: NAS用户名
            delay_minutes: 延迟删除时间（分钟）
            pending_file: 待删除任务文件路径
            enable_checksum: 是否启用校验和验证
            nas_alias: SSH 别名（优先使用，来自 /home/celestial/.ssh/config 的 Host 配置）
        """
        self.nas_host = nas_host
        self.nas_username = nas_username
        self.delay_minutes = delay_minutes
        self.enable_checksum = enable_checksum
        self.nas_alias = nas_alias
        
        # 设置待删除任务文件路径
        if pending_file is None:
            self.pending_file = "/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/pending_deletes.json"
        else:
            self.pending_file = pending_file
        
        # 设置日志
        self.logger = self._setup_logger()
        
        # 加载待删除任务
        self.pending_deletes: List[DeleteTask] = self._load_pending_deletes()
        
        self.logger.info(f"SafeDeleteManager初始化完成，延迟删除时间: {delay_minutes}分钟，SSH目标优先使用别名: {self.nas_alias}")
    
    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger('SafeDeleteManager')
        logger.setLevel(logging.INFO)
        
        # 避免重复添加处理器
        if not logger.handlers:
            # 已在模块级导入 logging.handlers，避免在函数内导入引发作用域问题
            
            # 检查是否在守护进程模式下运行
            if os.getenv('DAEMON_MODE') == '1':
                # 守护进程模式：只使用系统日志
                syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
                syslog_handler.setLevel(logging.DEBUG)
                syslog_handler.setFormatter(logging.Formatter('safe-delete-manager: %(levelname)s - %(message)s'))
                logger.addHandler(syslog_handler)
            else:
                # 普通模式：尝试使用文件和控制台日志
                try:
                    # 文件处理器
                    log_file = "/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/logs/safe_delete.log"
                    os.makedirs(os.path.dirname(log_file), exist_ok=True)
                    
                    file_handler = logging.FileHandler(log_file)
                    file_handler.setLevel(logging.DEBUG)
                    
                    # 控制台处理器
                    console_handler = logging.StreamHandler()
                    console_handler.setLevel(logging.INFO)
                except (OSError, PermissionError) as e:
                    # 如果无法创建文件日志，回退到系统日志
                    print(f"Warning: Cannot create log file: {e}")
                    syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
                    syslog_handler.setLevel(logging.DEBUG)
                    syslog_handler.setFormatter(logging.Formatter('safe-delete-manager: %(levelname)s - %(message)s'))
                    logger.addHandler(syslog_handler)
                    return logger
                
                # 格式化器
                formatter = logging.Formatter(
                    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
                )
                file_handler.setFormatter(formatter)
                console_handler.setFormatter(formatter)
                
                logger.addHandler(file_handler)
            logger.addHandler(console_handler)
        
        return logger
    
    def schedule_delete(self, 
                       local_file_path: str, 
                       remote_file_path: str, 
                       local_checksum: str = None) -> bool:
        """安排文件延迟删除
        
        Args:
            local_file_path: 本地文件路径
            remote_file_path: 远程文件路径
            local_checksum: 本地文件校验和（可选）
            
        Returns:
            是否成功安排删除任务
        """
        try:
            # 检查本地文件是否存在
            if not os.path.exists(local_file_path):
                self.logger.warning(f"本地文件不存在，跳过删除安排: {local_file_path}")
                return False
            
            # 计算校验和（如果未提供）
            if local_checksum is None and self.enable_checksum:
                local_checksum = self._calculate_file_checksum(local_file_path)
                if not local_checksum:
                    self.logger.error(f"无法计算文件校验和: {local_file_path}")
                    return False
            
            # 计算延迟删除时间
            scheduled_time = time.time() + (self.delay_minutes * 60)
            
            # 创建删除任务
            delete_task = DeleteTask(
                local_file_path=local_file_path,
                remote_file_path=remote_file_path,
                local_checksum=local_checksum or "",
                scheduled_time=scheduled_time
            )
            
            # 添加到待删除列表
            self.pending_deletes.append(delete_task)
            
            # 保存到文件
            if self._save_pending_deletes():
                scheduled_datetime = datetime.fromtimestamp(scheduled_time)
                self.logger.info(
                    f"已安排延迟删除: {os.path.basename(local_file_path)} "
                    f"(计划时间: {scheduled_datetime.strftime('%Y-%m-%d %H:%M:%S')})"
                )
                return True
            else:
                # 保存失败，从列表中移除
                self.pending_deletes.remove(delete_task)
                return False
                
        except Exception as e:
            self.logger.error(f"安排删除任务失败: {local_file_path}, 错误: {e}")
            return False
    
    def process_pending_deletes(self) -> Tuple[int, int]:
        """处理待删除任务
        
        Returns:
            (成功删除数量, 失败删除数量)
        """
        if not self.pending_deletes:
            self.logger.debug("没有待处理的删除任务")
            return 0, 0
        
        success_count = 0
        failed_count = 0
        completed_tasks = []
        
        self.logger.info(f"开始处理 {len(self.pending_deletes)} 个待删除任务")
        
        for task in self.pending_deletes[:]:
            try:
                # 检查是否到达删除时间
                if not task.is_ready_for_deletion():
                    continue
                
                # 执行删除验证和删除
                if self._verify_and_delete(task):
                    success_count += 1
                    completed_tasks.append(task)
                    self.logger.info(f"成功删除文件: {os.path.basename(task.local_file_path)}")
                else:
                    # 删除失败，检查是否需要重试
                    if task.should_retry():
                        task.increment_retry()
                        # 延长重试时间（指数退避）
                        retry_delay = min(60 * (2 ** task.retry_count), 3600)  # 最大1小时
                        task.scheduled_time = time.time() + retry_delay
                        self.logger.warning(
                            f"删除失败，安排重试 ({task.retry_count}/{task.max_retries}): "
                            f"{os.path.basename(task.local_file_path)}"
                        )
                    else:
                        # 超过最大重试次数，标记为失败
                        failed_count += 1
                        completed_tasks.append(task)
                        self.logger.error(
                            f"删除失败，超过最大重试次数: {os.path.basename(task.local_file_path)}"
                        )
                        
            except Exception as e:
                self.logger.error(f"处理删除任务异常: {task.local_file_path}, 错误: {e}")
                failed_count += 1
                completed_tasks.append(task)
        
        # 移除已完成的任务
        for task in completed_tasks:
            if task in self.pending_deletes:
                self.pending_deletes.remove(task)
        
        # 保存更新后的待删除列表
        if completed_tasks:
            self._save_pending_deletes()
        
        if success_count > 0 or failed_count > 0:
            self.logger.info(f"删除任务处理完成 - 成功: {success_count}, 失败: {failed_count}")
        
        return success_count, failed_count
    
    def _verify_and_delete(self, task: DeleteTask) -> bool:
        """验证远程文件并删除本地文件
        
        Args:
            task: 删除任务
            
        Returns:
            是否成功删除
        """
        try:
            # 检查本地文件是否仍然存在
            if not os.path.exists(task.local_file_path):
                self.logger.info(f"本地文件已不存在: {task.local_file_path}")
                return True
            
            # 验证远程文件存在性
            if not self._verify_remote_file_exists(task.remote_file_path):
                self.logger.error(f"远程文件不存在，跳过删除: {task.remote_file_path}")
                return False
            
            # 验证远程文件完整性（如果启用校验和）
            if self.enable_checksum and task.local_checksum:
                if not self._verify_remote_checksum(task.remote_file_path, task.local_checksum):
                    self.logger.error(f"远程文件校验和不匹配，跳过删除: {task.remote_file_path}")
                    return False
            
            # 删除本地文件
            os.remove(task.local_file_path)
            self.logger.debug(f"本地文件删除成功: {task.local_file_path}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"验证和删除失败: {task.local_file_path}, 错误: {e}")
            return False
    
    def _verify_remote_file_exists(self, remote_file_path: str) -> bool:
        """验证远程文件是否存在
        
        Args:
            remote_file_path: 远程文件路径
            
        Returns:
            远程文件是否存在
        """
        ssh_target = self.nas_alias if self.nas_alias else f"{self.nas_username}@{self.nas_host}"
        check_cmd = [
            'ssh', ssh_target,
            f'test -f {remote_file_path}'
        ]
        
        try:
            result = subprocess.run(
                check_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            self.logger.error("验证远程文件存在性超时")
            return False
        except Exception as e:
            self.logger.error(f"验证远程文件存在性异常: {e}")
            return False
    
    def _verify_remote_checksum(self, remote_file_path: str, expected_checksum: str) -> bool:
        """验证远程文件校验和
        
        Args:
            remote_file_path: 远程文件路径
            expected_checksum: 期望的校验和
            
        Returns:
            校验和是否匹配
        """
        ssh_target = self.nas_alias if self.nas_alias else f"{self.nas_username}@{self.nas_host}"
        checksum_cmd = [
            'ssh', ssh_target,
            f'md5sum {remote_file_path}'
        ]
        
        try:
            result = subprocess.run(
                checksum_cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                # 解析md5sum输出
                remote_checksum = result.stdout.strip().split()[0]
                return remote_checksum.lower() == expected_checksum.lower()
            else:
                self.logger.error(f"计算远程文件校验和失败: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("计算远程文件校验和超时")
            return False
        except Exception as e:
            self.logger.error(f"计算远程文件校验和异常: {e}")
            return False
    
    def _calculate_file_checksum(self, file_path: str) -> Optional[str]:
        """计算文件MD5校验和
        
        Args:
            file_path: 文件路径
            
        Returns:
            文件的MD5校验和，失败时返回None
        """
        try:
            hash_md5 = hashlib.md5()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            self.logger.error(f"计算文件校验和失败: {file_path}, 错误: {e}")
            return None
    
    def _load_pending_deletes(self) -> List[DeleteTask]:
        """从文件加载待删除任务列表
        
        Returns:
            待删除任务列表
        """
        try:
            if os.path.exists(self.pending_file):
                with open(self.pending_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                tasks = []
                for item in data:
                    task = DeleteTask(**item)
                    tasks.append(task)
                
                self.logger.info(f"加载了 {len(tasks)} 个待删除任务")
                return tasks
            else:
                self.logger.info("待删除任务文件不存在，创建新的任务列表")
                return []
                
        except Exception as e:
            self.logger.error(f"加载待删除任务失败: {e}")
            return []
    
    def _save_pending_deletes(self) -> bool:
        """保存待删除任务列表到文件
        
        Returns:
            是否保存成功
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.pending_file), exist_ok=True)
            
            # 转换为字典列表
            data = [asdict(task) for task in self.pending_deletes]
            
            # 保存到文件
            with open(self.pending_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            self.logger.debug(f"保存了 {len(self.pending_deletes)} 个待删除任务")
            return True
            
        except Exception as e:
            self.logger.error(f"保存待删除任务失败: {e}")
            return False
    
    def get_pending_count(self) -> int:
        """获取待删除任务数量
        
        Returns:
            待删除任务数量
        """
        return len(self.pending_deletes)
    
    def get_ready_count(self) -> int:
        """获取可执行删除的任务数量
        
        Returns:
            可执行删除的任务数量
        """
        return sum(1 for task in self.pending_deletes if task.is_ready_for_deletion())
    
    def clear_completed_tasks(self) -> int:
        """清理已完成的任务（本地文件已不存在）
        
        Returns:
            清理的任务数量
        """
        initial_count = len(self.pending_deletes)
        
        # 过滤出本地文件仍存在的任务
        self.pending_deletes = [
            task for task in self.pending_deletes 
            if os.path.exists(task.local_file_path)
        ]
        
        cleared_count = initial_count - len(self.pending_deletes)
        
        if cleared_count > 0:
            self._save_pending_deletes()
            self.logger.info(f"清理了 {cleared_count} 个已完成的删除任务")
        
        return cleared_count
    
    def get_status_summary(self) -> Dict:
        """获取删除管理器状态摘要
        
        Returns:
            状态摘要字典
        """
        ready_count = self.get_ready_count()
        pending_count = len(self.pending_deletes)
        
        return {
            'total_pending': pending_count,
            'ready_for_deletion': ready_count,
            'waiting': pending_count - ready_count,
            'delay_minutes': self.delay_minutes,
            'enable_checksum': self.enable_checksum,
            'pending_file': self.pending_file
        }

def main():
    """主函数 - 用于测试"""
    # 创建安全删除管理器
    delete_manager = SafeDeleteManager(delay_minutes=1)  # 测试用1分钟延迟
    
    # 显示状态
    status = delete_manager.get_status_summary()
    print(f"SafeDeleteManager状态: {status}")
    
    # 处理待删除任务
    success, failed = delete_manager.process_pending_deletes()
    print(f"处理结果 - 成功: {success}, 失败: {failed}")

if __name__ == "__main__":
    main()