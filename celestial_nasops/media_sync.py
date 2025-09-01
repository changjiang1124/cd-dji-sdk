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

class MediaSyncManager:
    """媒体文件同步管理器"""
    
    def __init__(self, config_path: str = None):
        """初始化同步管理器
        
        Args:
            config_path: 配置文件路径，默认使用项目配置文件
        """
        self.config_path = config_path or '/home/celestial/dev/esdk-test/Edge-SDK/media_sync_config.json'
        self.config = self._load_config()
        self.logger = self._setup_logging()
        
        # 从配置文件获取参数
        self.local_media_path = self.config['local_storage']['media_path']
        self.nas_host = self.config['nas_server']['host']
        self.nas_username = self.config['nas_server']['username']
        self.nas_base_path = self.config['nas_server']['remote_path']
        self.max_retry = self.config['sync_settings']['max_retries']
        self.enable_checksum = self.config['sync_settings']['verify_checksum']
        self.delete_after_sync = self.config['sync_settings']['delete_after_sync']
        
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
        logging.basicConfig(
            level=getattr(logging, log_config['level']),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
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
        """同步单个文件到NAS
        
        Args:
            local_file_path: 本地文件路径
            
        Returns:
            同步是否成功
        """
        filename = os.path.basename(local_file_path)
        remote_dir = self.get_remote_path(filename)
        remote_host_path = f"{self.nas_username}@{self.nas_host}:{remote_dir}"
        
        self.logger.info(f"开始同步文件: {filename} -> {remote_host_path}")
        
        # 计算本地文件校验和
        local_checksum = ""
        if self.enable_checksum:
            local_checksum = self.get_file_checksum(local_file_path)
            if not local_checksum:
                self.logger.error(f"无法计算本地文件校验和: {filename}")
                return False
        
        # 由于NAS系统限制rsync和scp，使用SSH管道传输文件
        remote_file_path = f"{remote_dir}{filename}"
        
        # 先创建远程目录
        mkdir_cmd = [
            'ssh', f"{self.nas_username}@{self.nas_host}",
            f'mkdir -p {remote_dir}'
        ]
        
        try:
            # 创建远程目录
            mkdir_result = subprocess.run(
                mkdir_cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if mkdir_result.returncode != 0:
                self.logger.error(f"创建远程目录失败: {mkdir_result.stderr}")
                return False
            
            # 使用SSH管道传输文件
            transfer_cmd = f"cat '{local_file_path}' | ssh {self.nas_username}@{self.nas_host} 'cat > {remote_file_path}'"
            
            # 执行文件传输命令
            result = subprocess.run(
                transfer_cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            if result.returncode == 0:
                self.logger.info(f"文件传输成功: {filename}")
                
                # 验证远程文件校验和（如果启用）
                if self.enable_checksum:
                    if self._verify_remote_checksum(remote_file_path, local_checksum):
                        self.logger.info(f"文件校验成功: {filename}")
                        return True
                    else:
                        self.logger.error(f"文件校验失败: {filename}")
                        return False
                else:
                    return True
            else:
                self.logger.error(f"文件传输失败: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            self.logger.error(f"文件传输超时: {filename}")
            return False
        except Exception as e:
            self.logger.error(f"文件传输异常: {filename}, 错误: {e}")
            return False
    
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
                f"{self.nas_username}@{self.nas_host}",
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
                
                if self.sync_file_to_nas(file_path):
                    sync_success = True
                    success_count += 1
                    
                    # 同步成功后删除本地文件（如果配置启用）
                    if self.delete_after_sync:
                        try:
                            os.remove(file_path)
                            self.logger.info(f"本地文件已删除: {filename}")
                        except Exception as e:
                            self.logger.error(f"删除本地文件失败: {filename}, 错误: {e}")
                    
                    break
                else:
                    if attempt < self.max_retry:
                        self.logger.warning(f"同步失败，等待重试: {filename}")
                        time.sleep(5)  # 等待5秒后重试
            
            if not sync_success:
                failed_count += 1
                self.logger.error(f"文件同步最终失败: {filename}")
        
        self.logger.info(f"同步完成 - 成功: {success_count}, 失败: {failed_count}")
        return {'success': success_count, 'failed': failed_count}

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