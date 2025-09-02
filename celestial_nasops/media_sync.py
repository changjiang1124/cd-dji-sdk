#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
媒体文件同步脚本 - 从边缘服务器同步到NAS

功能说明：
1. 监控本地媒体文件目录 (/data/temp/dji/media/)
2. 将媒体文件按日期结构同步到NAS (edge_sync@192.168.200.103:EdgeBackup/)
3. 验证文件完整性（校验和）
4. 同步成功后删除本地文件以释放空间
5. 支持重试机制和详细日志记录

作者: Celestial
日期: 2024-01-22
"""

import os
import sys
import json
import hashlib
import subprocess
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# 添加项目根目录到Python路径
sys.path.append('/home/celestial/dev/esdk-test/Edge-SDK')

# 导入安全删除管理器和存储管理器
from safe_delete_manager import SafeDeleteManager
from storage_manager import StorageManager

class MediaSyncManager:
    """媒体文件同步管理器"""
    
    def __init__(self, config_path: str = None):
        """初始化同步管理器
        
        Args:
            config_path: 配置文件路径，默认使用项目配置文件
        """
        self.config_path = config_path or '/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/unified_config.json'
        self.config = self._load_config()
        self.logger = self._setup_logging()
        
        # 从配置文件获取参数
        self.local_media_path = self.config['local_settings']['media_path']
        self.nas_host = self.config['nas_settings']['host']
        self.nas_username = self.config['nas_settings']['username']
        self.nas_base_path = self.config['nas_settings']['base_path']
        # 优先使用 SSH 别名（/home/celestial/.ssh/config 中配置的 Host）。若未配置则回退为 username@host
        self.nas_alias = self.config['nas_settings'].get('ssh_alias') or f"{self.nas_username}@{self.nas_host}"
        self.max_retry = self.config['sync_settings']['max_retry_attempts']
        self.enable_checksum = self.config['sync_settings']['enable_checksum']
        self.delete_after_sync = self.config['sync_settings']['delete_after_sync']
        
        # 初始化安全删除管理器（传入 nas_alias 以便远程校验也走免密）
        safe_delete_delay = self.config['sync_settings'].get('safe_delete_delay_minutes', 30)
        self.safe_delete_manager = SafeDeleteManager(
            nas_host=self.nas_host,
            nas_username=self.nas_username,
            nas_alias=self.nas_alias,
            delay_minutes=safe_delete_delay,
            enable_checksum=self.enable_checksum
        )
        
        # 初始化存储管理器
        self.storage_manager = StorageManager(config_file=self.config_path)
    
    def _load_config(self) -> Dict:
        """加载配置文件
        
        Returns:
            配置字典
        
        Raises:
            FileNotFoundError: 配置文件不存在
            json.JSONDecodeError: 配置文件格式错误
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError as e:
            print(f"加载配置文件失败: {e}")
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        except json.JSONDecodeError as e:
            print(f"配置文件格式错误: {e}")
            raise json.JSONDecodeError(f"配置文件格式错误: {self.config_path}", e.doc, e.pos)
        except Exception as e:
            print(f"加载配置文件失败: {e}")
            raise Exception(f"加载配置文件失败: {e}")
    
    def _setup_logging(self) -> logging.Logger:
        """设置日志记录
        
        Returns:
            配置好的日志记录器
        """
        log_config = self.config['logging']
        log_file = log_config['log_file']
        
        # 确保日志目录存在
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # 配置日志格式
        import logging.handlers
        handlers = []
        
        # 尝试创建文件日志处理器，如果失败则使用系统日志
        try:
            if os.getenv('DAEMON_MODE') == '1':
                # 守护进程模式：只使用系统日志
                syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
                syslog_handler.setFormatter(logging.Formatter('media-sync-daemon: %(levelname)s - %(message)s'))
                handlers.append(syslog_handler)
            else:
                # 普通模式：尝试使用文件和控制台日志
                handlers.extend([
                    logging.FileHandler(log_file, encoding='utf-8'),
                    logging.StreamHandler(sys.stdout)
                ])
        except (OSError, PermissionError) as e:
            # 如果无法创建文件日志，回退到系统日志
            print(f"Warning: Cannot create log file {log_file}: {e}")
            print("Falling back to system logging")
            syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
            syslog_handler.setFormatter(logging.Formatter('media-sync-daemon: %(levelname)s - %(message)s'))
            handlers = [syslog_handler]
        
        logging.basicConfig(
            level=getattr(logging, log_config['level']),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=handlers
        )
        
        return logging.getLogger(__name__)
    
    def get_file_checksum(self, file_path: str) -> str:
        """计算文件MD5校验和
        
        Args:
            file_path: 文件路径
            
        Returns:
            MD5校验和字符串
        """
        hash_md5 = hashlib.md5()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception as e:
            self.logger.error(f"计算文件校验和失败 {file_path}: {e}")
            return ""
    
    def parse_filename_date(self, filename: str) -> Optional[Tuple[str, str, str]]:
        """从文件名解析日期信息
        
        Args:
            filename: 文件名，格式如 20230815_100000.mp4
            
        Returns:
            (年, 月, 日) 元组，解析失败返回None
        """
        try:
            # 提取文件名中的日期部分（前8位数字）
            date_part = filename[:8]
            if len(date_part) == 8 and date_part.isdigit():
                year = date_part[:4]
                month = date_part[4:6]
                day = date_part[6:8]
                return (year, month, day)
        except Exception as e:
            self.logger.warning(f"解析文件名日期失败 {filename}: {e}")
        return None
    
    def get_remote_path(self, filename: str) -> str:
        """根据文件名生成远程存储路径
        
        Args:
            filename: 文件名
            
        Returns:
            远程存储路径
        """
        date_info = self.parse_filename_date(filename)
        if date_info and self.config['file_organization']['enable_date_structure']:
            year, month, day = date_info
            return f"{self.nas_base_path}/{year}/{month}/{day}/"
        else:
            # 如果无法解析日期，使用当前日期
            now = datetime.now()
            return f"{self.nas_base_path}/{now.year}/{now.month:02d}/{now.day:02d}/"
    
    def sync_file_to_nas(self, local_file_path: str) -> bool:
        """同步单个文件到NAS（原子性传输）
        
        Args:
            local_file_path: 本地文件路径
            
        Returns:
            同步是否成功
        """
        filename = os.path.basename(local_file_path)
        remote_dir = self.get_remote_path(filename)
        remote_host_path = f"{self.nas_alias}:{remote_dir}"
        
        # 生成临时文件名（添加.tmp后缀和时间戳）
        timestamp = int(time.time() * 1000)  # 毫秒时间戳
        temp_filename = f"{filename}.tmp.{timestamp}"
        remote_temp_path = f"{remote_dir}{temp_filename}"
        remote_final_path = f"{remote_dir}{filename}"
        
        self.logger.info(f"开始原子性同步文件: {filename} -> {remote_host_path}")
        
        # 计算本地文件校验和
        local_checksum = ""
        if self.enable_checksum:
            local_checksum = self.get_file_checksum(local_file_path)
            if not local_checksum:
                self.logger.error(f"无法计算本地文件校验和: {filename}")
                return False
        
        try:
            # 1. 创建远程目录
            if not self._create_remote_directory(remote_dir):
                return False
            
            # 2. 传输文件到临时位置
            if not self._transfer_file_to_temp(local_file_path, remote_temp_path):
                return False
            
            # 3. 验证传输完整性（如果启用校验和）
            if self.enable_checksum:
                if not self._verify_remote_checksum(remote_temp_path, local_checksum):
                    self.logger.error(f"临时文件校验失败: {temp_filename}")
                    self._cleanup_remote_temp_file(remote_temp_path)
                    return False
                self.logger.info(f"临时文件校验成功: {temp_filename}")
            
            # 4. 原子性重命名（临时文件 -> 最终文件）
            if not self._atomic_rename_remote_file(remote_temp_path, remote_final_path):
                self._cleanup_remote_temp_file(remote_temp_path)
                return False
            
            self.logger.info(f"文件原子性传输成功: {filename}")
            return True
            
        except Exception as e:
            self.logger.error(f"文件传输异常: {filename}, 错误: {e}")
            # 清理可能存在的临时文件
            self._cleanup_remote_temp_file(remote_temp_path)
            return False
    
    def _create_remote_directory(self, remote_dir: str) -> bool:
        """创建远程目录
        
        Args:
            remote_dir: 远程目录路径
            
        Returns:
            是否创建成功
        """
        mkdir_cmd = [
            'ssh', f"{self.nas_alias}",
            f'mkdir -p {remote_dir}'
        ]
        
        try:
            result = subprocess.run(
                mkdir_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return True
            else:
                self.logger.error(f"创建远程目录失败: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("创建远程目录超时")
            return False
        except Exception as e:
            self.logger.error(f"创建远程目录异常: {e}")
            return False
    
    def _transfer_file_to_temp(self, local_file_path: str, remote_temp_path: str) -> bool:
        """传输文件到远程临时位置
        
        Args:
            local_file_path: 本地文件路径
            remote_temp_path: 远程临时文件路径
            
        Returns:
            是否传输成功
        """
        # 使用SSH管道传输文件到临时位置（优先使用 ssh 别名以支持免密）
        transfer_cmd = f"cat '{local_file_path}' | ssh {self.nas_alias} 'cat > {remote_temp_path}'"
        
        try:
            result = subprocess.run(
                transfer_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                self.logger.debug(f"文件传输到临时位置成功: {os.path.basename(remote_temp_path)}")
                return True
            else:
                self.logger.error(f"文件传输到临时位置失败: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("文件传输到临时位置超时")
            return False
        except Exception as e:
            self.logger.error(f"文件传输到临时位置异常: {e}")
            return False
    
    def _atomic_rename_remote_file(self, remote_temp_path: str, remote_final_path: str) -> bool:
        """原子性重命名远程文件
        
        Args:
            remote_temp_path: 远程临时文件路径
            remote_final_path: 远程最终文件路径
            
        Returns:
            是否重命名成功
        """
        rename_cmd = [
            'ssh', f"{self.nas_alias}",
            f'mv {remote_temp_path} {remote_final_path}'
        ]
        
        try:
            result = subprocess.run(
                rename_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                self.logger.debug(f"文件原子性重命名成功: {os.path.basename(remote_final_path)}")
                return True
            else:
                self.logger.error(f"文件原子性重命名失败: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error("文件原子性重命名超时")
            return False
        except Exception as e:
            self.logger.error(f"文件原子性重命名异常: {e}")
            return False
    
    def _cleanup_remote_temp_file(self, remote_temp_path: str):
        """清理远程临时文件
        
        Args:
            remote_temp_path: 远程临时文件路径
        """
        cleanup_cmd = [
            'ssh', f"{self.nas_alias}",
            f'rm -f {remote_temp_path}'
        ]
        
        try:
            result = subprocess.run(
                cleanup_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                self.logger.debug(f"临时文件清理成功: {os.path.basename(remote_temp_path)}")
            else:
                self.logger.warning(f"临时文件清理失败: {result.stderr}")
                
        except Exception as e:
            self.logger.warning(f"临时文件清理异常: {e}")
    
    def _verify_remote_checksum(self, remote_file_path: str, expected_checksum: str) -> bool:
        """验证远程文件校验和
        
        Args:
            remote_file_path: 远程文件路径
            expected_checksum: 期望的校验和
            
        Returns:
            校验是否成功
        """
        try:
            # 通过SSH计算远程文件的MD5
            ssh_cmd = [
                'ssh',
                f"{self.nas_alias}",
                f"md5sum {remote_file_path}"
            ]
            
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                remote_checksum = result.stdout.split()[0]
                return remote_checksum == expected_checksum
            else:
                self.logger.error(f"远程校验和计算失败: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"远程校验和验证异常: {e}")
            return False
    
    def get_media_files(self) -> List[str]:
        """获取本地媒体文件列表
        
        Returns:
            媒体文件路径列表
        """
        media_files = []
        
        if not os.path.exists(self.local_media_path):
            self.logger.warning(f"媒体文件目录不存在: {self.local_media_path}")
            return media_files
        
        try:
            for filename in os.listdir(self.local_media_path):
                file_path = os.path.join(self.local_media_path, filename)
                if os.path.isfile(file_path):
                    media_files.append(file_path)
            
            self.logger.info(f"发现 {len(media_files)} 个媒体文件")
            return media_files
            
        except Exception as e:
            self.logger.error(f"读取媒体文件目录失败: {e}")
            return []
    
    def sync_all_files(self) -> Dict[str, int]:
        """同步所有媒体文件
        
        Returns:
            同步结果统计 {'success': 成功数量, 'failed': 失败数量}
        """
        media_files = self.get_media_files()
        
        if not media_files:
            self.logger.info("没有发现需要同步的媒体文件")
            return {'success': 0, 'failed': 0}
        
        success_count = 0
        failed_count = 0
        
        for file_path in media_files:
            filename = os.path.basename(file_path)
            
            # 重试机制
            sync_success = False
            for attempt in range(1, self.max_retry + 1):
                self.logger.info(f"同步文件 {filename} (尝试 {attempt}/{self.max_retry})")
                
                # 获取远程文件路径和本地文件校验和
                remote_dir = self.get_remote_path(filename)
                remote_file_path = f"{remote_dir}{filename}"
                local_checksum = None
                if self.enable_checksum:
                    local_checksum = self.get_file_checksum(file_path)
                
                if self.sync_file_to_nas(file_path):
                    sync_success = True
                    success_count += 1
                    
                    # 同步成功后安排延迟删除本地文件（如果配置启用）
                    if self.delete_after_sync:
                        if self.safe_delete_manager.schedule_delete(
                            local_file_path=file_path,
                            remote_file_path=remote_file_path,
                            local_checksum=local_checksum
                        ):
                            self.logger.info(f"已安排延迟删除: {filename}")
                        else:
                            self.logger.error(f"安排延迟删除失败: {filename}")
                    
                    break
                else:
                    if attempt < self.max_retry:
                        self.logger.warning(f"同步失败，等待重试: {filename}")
                        time.sleep(5)  # 等待5秒后重试
            
            if not sync_success:
                failed_count += 1
                self.logger.error(f"文件同步最终失败: {filename}")
        
        self.logger.info(f"同步完成 - 成功: {success_count}, 失败: {failed_count}")
        
        # 处理待删除任务
        if self.delete_after_sync:
            delete_success, delete_failed = self.safe_delete_manager.process_pending_deletes()
            if delete_success > 0 or delete_failed > 0:
                self.logger.info(f"删除任务处理完成 - 成功: {delete_success}, 失败: {delete_failed}")
        
        return {'success': success_count, 'failed': failed_count}
    
    def process_pending_deletes(self) -> Dict[str, int]:
        """处理待删除任务
        
        Returns:
            删除结果统计 {'success': 成功数量, 'failed': 失败数量}
        """
        if not self.delete_after_sync:
            self.logger.info("未启用同步后删除，跳过删除任务处理")
            return {'success': 0, 'failed': 0}
        
        success, failed = self.safe_delete_manager.process_pending_deletes()
        return {'success': success, 'failed': failed}
    
    def get_delete_status(self) -> Dict:
        """获取删除管理器状态
        
        Returns:
            删除管理器状态信息
        """
        if not self.delete_after_sync:
            return {'enabled': False}
        
        status = self.safe_delete_manager.get_status_summary()
        status['enabled'] = True
        return status
    
    def check_storage_space(self) -> Dict:
        """检查存储空间状态
        
        Returns:
            存储空间状态信息
        """
        try:
            return self.storage_manager.check_storage_space()
        except Exception as e:
            self.logger.error(f"检查存储空间失败: {e}")
            return {'error': str(e)}
    
    def cleanup_storage(self, force: bool = False) -> Dict:
        """清理存储空间
        
        Args:
            force: 是否强制清理，忽略阈值检查
            
        Returns:
            清理结果信息
        """
        try:
            return self.storage_manager.cleanup_storage(force=force)
        except Exception as e:
            self.logger.error(f"清理存储空间失败: {e}")
            return {'error': str(e)}
    
    def get_storage_status(self) -> Dict:
        """获取存储管理器状态
        
        Returns:
            存储管理器状态信息
        """
        try:
            return self.storage_manager.get_status_summary()
        except Exception as e:
            self.logger.error(f"获取存储状态失败: {e}")
            return {'error': str(e)}

def main():
    """主函数"""
    try:
        # 创建同步管理器实例
        sync_manager = MediaSyncManager()
        
        # 执行文件同步
        sync_manager.logger.info("=== 开始媒体文件同步 ===")
        result = sync_manager.sync_all_files()
        sync_manager.logger.info("=== 媒体文件同步完成 ===")
        
        # 返回适当的退出码
        if result['failed'] > 0:
            sys.exit(1)  # 有失败的文件
        else:
            sys.exit(0)  # 全部成功
            
    except KeyboardInterrupt:
        print("\n用户中断同步操作")
        sys.exit(130)
    except Exception as e:
        print(f"同步过程发生异常: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()