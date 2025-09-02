#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NAS端目录结构管理器

功能说明：
1. 在NAS端创建按年/月/日组织的目录结构
2. 管理媒体文件的存储路径
3. 提供目录清理和维护功能
4. 支持目录结构验证和修复

目录结构示例：
/EdgeBackup/
├── 2024/
│   ├── 01/
│   │   ├── 15/
│   │   │   ├── 20240115_100000.mp4
│   │   │   └── 20240115_100001.jpg
│   │   └── 16/
│   └── 02/
└── 2023/

作者: Celestial
日期: 01/09/2025
"""

import os
import sys
import json
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple

class NASStructureManager:
    """NAS目录结构管理器"""
    
    def __init__(self, config_file: str = None):
        """初始化NAS结构管理器
        
        Args:
            config_file: 配置文件路径
        """
        self.config = self._load_config(config_file)
        self.logger = self._setup_logging()
        
        # NAS连接信息
        self.nas_host = self.config['nas_server']['host'] if 'nas_server' in self.config else self.config['nas_settings']['host']
        self.nas_username = self.config['nas_server']['username'] if 'nas_server' in self.config else self.config['nas_settings']['username']
        self.nas_base_path = self.config['nas_server']['remote_path'] if 'nas_server' in self.config else self.config['nas_settings']['base_path']
        # 新增：SSH 别名，来自 unified_config.json 的 nas_settings.ssh_alias
        self.nas_alias = (self.config.get('nas_settings', {}) or {}).get('ssh_alias', 'nas-edge')
        
        # 日期格式配置
        # 兼容旧字段 file_organization 与新字段 file_organization/enable_date_structure
        if 'file_organization' in self.config:
            self.date_format = self.config['file_organization'].get('date_format') or self.config['file_organization'].get('date_format', "%Y/%m/%d")
            self.use_date_structure = self.config['file_organization'].get('use_date_structure') or self.config['file_organization'].get('enable_date_structure', True)
        else:
            self.date_format = "%Y/%m/%d"
            self.use_date_structure = True
    
    def _load_config(self, config_file: str = None) -> dict:
        """加载配置文件
        
        Args:
            config_file: 配置文件路径
            
        Returns:
            配置字典
        """
        if config_file is None:
            config_file = '/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/unified_config.json'
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            # 返回默认配置
            return {
                "nas_server": {
                    "host": "192.168.200.103",
                    "username": "edge_sync",
                    "remote_path": "/EdgeBackup"
                },
                "file_organization": {
                    "use_date_structure": True,
                    "date_format": "%Y/%m/%d"
                },
                "logging": {
                    "level": "INFO"
                }
            }
    
    def _setup_logging(self) -> logging.Logger:
        """设置日志记录
        
        Returns:
            配置好的日志记录器
        """
        import logging.handlers
        
        # 检查是否在守护进程模式下运行
        if os.getenv('DAEMON_MODE') == '1':
            # 守护进程模式：只使用系统日志
            logging.basicConfig(
                level=getattr(logging, self.config['logging']['level']),
                format='nas-structure-manager: %(levelname)s - %(message)s',
                handlers=[
                    logging.handlers.SysLogHandler(address='/dev/log')
                ]
            )
        else:
            # 普通模式：尝试使用文件和控制台日志
            try:
                log_dir = '/home/celestial/dev/esdk-test/Edge-SDK/celestial_works/logs'
                os.makedirs(log_dir, exist_ok=True)
                
                log_file = os.path.join(log_dir, 'nas_structure_manager.log')
                
                logging.basicConfig(
                    level=getattr(logging, self.config['logging']['level']),
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
                    level=getattr(logging, self.config['logging']['level']),
                    format='nas-structure-manager: %(levelname)s - %(message)s',
                    handlers=[
                        logging.handlers.SysLogHandler(address='/dev/log')
                    ]
                )
        
        return logging.getLogger('NASStructureManager')
    
    def _execute_remote_command(self, command: str) -> Tuple[bool, str, str]:
        """在NAS上执行远程命令
        
        Args:
            command: 要执行的命令
            
        Returns:
            (成功标志, 标准输出, 错误输出)
        """
        ssh_target = self.nas_alias if getattr(self, 'nas_alias', None) else f'{self.nas_username}@{self.nas_host}'
        ssh_command = [
            'ssh',
            ssh_target,
            command
        ]
        
        try:
            result = subprocess.run(
                ssh_command,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            success = result.returncode == 0
            return success, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            return False, '', '命令执行超时'
        except Exception as e:
            return False, '', str(e)
    
    def get_date_path(self, file_date: datetime = None) -> str:
        """获取基于日期的路径
        
        Args:
            file_date: 文件日期，默认为当前日期
            
        Returns:
            日期路径字符串
        """
        if file_date is None:
            file_date = datetime.now()
        
        if self.use_date_structure:
            return file_date.strftime(self.date_format)
        else:
            return ''
    
    def get_full_remote_path(self, file_date: datetime = None) -> str:
        """获取完整的远程路径
        
        Args:
            file_date: 文件日期
            
        Returns:
            完整的远程路径
        """
        date_path = self.get_date_path(file_date)
        
        if date_path:
            return f"{self.nas_base_path}/{date_path}"
        else:
            return self.nas_base_path
    
    def create_date_directory(self, file_date: datetime = None) -> bool:
        """在NAS上创建日期目录
        
        Args:
            file_date: 文件日期
            
        Returns:
            创建成功标志
        """
        remote_path = self.get_full_remote_path(file_date)
        
        # 创建目录命令
        command = f"mkdir -p '{remote_path}'"
        
        success, stdout, stderr = self._execute_remote_command(command)
        
        if success:
            self.logger.info(f"成功创建目录: {remote_path}")
        else:
            self.logger.error(f"创建目录失败: {remote_path}, 错误: {stderr}")
        
        return success
    
    def verify_directory_exists(self, file_date: datetime = None) -> bool:
        """验证目录是否存在
        
        Args:
            file_date: 文件日期
            
        Returns:
            目录存在标志
        """
        remote_path = self.get_full_remote_path(file_date)
        
        # 检查目录是否存在
        command = f"test -d '{remote_path}' && echo 'exists' || echo 'not_exists'"
        
        success, stdout, stderr = self._execute_remote_command(command)
        
        if success and 'exists' in stdout:
            return True
        else:
            return False
    
    def ensure_directory_exists(self, file_date: datetime = None) -> bool:
        """确保目录存在，不存在则创建
        
        Args:
            file_date: 文件日期
            
        Returns:
            目录可用标志
        """
        if self.verify_directory_exists(file_date):
            return True
        else:
            return self.create_date_directory(file_date)
    
    def list_directory_structure(self, start_date: datetime = None, end_date: datetime = None) -> List[Dict]:
        """列出目录结构
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            目录结构列表
        """
        if start_date is None:
            start_date = datetime.now() - timedelta(days=30)  # 默认最近30天
        if end_date is None:
            end_date = datetime.now()
        
        directories = []
        
        # 遍历日期范围
        current_date = start_date
        while current_date <= end_date:
            remote_path = self.get_full_remote_path(current_date)
            
            if self.verify_directory_exists(current_date):
                # 获取目录信息
                command = f"ls -la '{remote_path}' 2>/dev/null | wc -l"
                success, stdout, stderr = self._execute_remote_command(command)
                
                file_count = 0
                if success and stdout.strip().isdigit():
                    file_count = max(0, int(stdout.strip()) - 3)  # 减去 ., .., 和标题行
                
                directories.append({
                    'date': current_date.strftime('%Y-%m-%d'),
                    'path': remote_path,
                    'exists': True,
                    'file_count': file_count
                })
            else:
                directories.append({
                    'date': current_date.strftime('%Y-%m-%d'),
                    'path': remote_path,
                    'exists': False,
                    'file_count': 0
                })
            
            current_date += timedelta(days=1)
        
        return directories
    
    def get_directory_size(self, file_date: datetime = None) -> Optional[int]:
        """获取目录大小
        
        Args:
            file_date: 文件日期
            
        Returns:
            目录大小（字节），失败返回None
        """
        remote_path = self.get_full_remote_path(file_date)
        
        # 获取目录大小
        command = f"du -sb '{remote_path}' 2>/dev/null | cut -f1"
        
        success, stdout, stderr = self._execute_remote_command(command)
        
        if success and stdout.strip().isdigit():
            return int(stdout.strip())
        else:
            return None
    
    def cleanup_empty_directories(self, older_than_days: int = 7) -> int:
        """清理空目录
        
        Args:
            older_than_days: 清理多少天前的空目录
            
        Returns:
            清理的目录数量
        """
        cutoff_date = datetime.now() - timedelta(days=older_than_days)
        
        # 查找空目录的命令
        command = f"find '{self.nas_base_path}' -type d -empty -mtime +{older_than_days} 2>/dev/null"
        
        success, stdout, stderr = self._execute_remote_command(command)
        
        if not success:
            self.logger.error(f"查找空目录失败: {stderr}")
            return 0
        
        empty_dirs = [line.strip() for line in stdout.split('\n') if line.strip()]
        
        cleaned_count = 0
        for empty_dir in empty_dirs:
            # 删除空目录
            delete_command = f"rmdir '{empty_dir}' 2>/dev/null"
            delete_success, _, delete_stderr = self._execute_remote_command(delete_command)
            
            if delete_success:
                self.logger.info(f"已删除空目录: {empty_dir}")
                cleaned_count += 1
            else:
                self.logger.warning(f"删除空目录失败: {empty_dir}, 错误: {delete_stderr}")
        
        return cleaned_count
    
    def validate_structure(self) -> Dict[str, any]:
        """验证NAS目录结构
        
        Returns:
            验证结果字典
        """
        validation_result = {
            'base_path_exists': False,
            'base_path_writable': False,
            'total_size': 0,
            'directory_count': 0,
            'file_count': 0,
            'errors': []
        }
        
        try:
            # 检查基础路径是否存在
            command = f"test -d '{self.nas_base_path}' && echo 'exists' || echo 'not_exists'"
            success, stdout, stderr = self._execute_remote_command(command)
            
            if success and 'exists' in stdout:
                validation_result['base_path_exists'] = True
            else:
                validation_result['errors'].append(f"基础路径不存在: {self.nas_base_path}")
                return validation_result
            
            # 检查写入权限
            test_file = f"{self.nas_base_path}/.write_test_{int(datetime.now().timestamp())}"
            command = f"touch '{test_file}' && rm '{test_file}' && echo 'writable' || echo 'not_writable'"
            success, stdout, stderr = self._execute_remote_command(command)
            
            if success and 'writable' in stdout:
                validation_result['base_path_writable'] = True
            else:
                validation_result['errors'].append(f"基础路径不可写: {self.nas_base_path}")
            
            # 获取总大小
            size = self.get_directory_size()
            if size is not None:
                validation_result['total_size'] = size
            
            # 统计目录和文件数量
            command = f"find '{self.nas_base_path}' -type d 2>/dev/null | wc -l"
            success, stdout, stderr = self._execute_remote_command(command)
            if success and stdout.strip().isdigit():
                validation_result['directory_count'] = int(stdout.strip())
            
            command = f"find '{self.nas_base_path}' -type f 2>/dev/null | wc -l"
            success, stdout, stderr = self._execute_remote_command(command)
            if success and stdout.strip().isdigit():
                validation_result['file_count'] = int(stdout.strip())
            
        except Exception as e:
            validation_result['errors'].append(f"验证过程异常: {str(e)}")
        
        return validation_result
    
    def generate_structure_report(self) -> str:
        """生成目录结构报告
        
        Returns:
            结构报告字符串
        """
        report_lines = []
        report_lines.append("=== NAS目录结构报告 ===")
        report_lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"NAS服务器: {self.nas_host}")
        report_lines.append(f"基础路径: {self.nas_base_path}")
        report_lines.append("")
        
        # 验证结果
        validation = self.validate_structure()
        report_lines.append("=== 结构验证 ===")
        report_lines.append(f"基础路径存在: {'是' if validation['base_path_exists'] else '否'}")
        report_lines.append(f"基础路径可写: {'是' if validation['base_path_writable'] else '否'}")
        report_lines.append(f"总大小: {validation['total_size'] / (1024**3):.2f} GB")
        report_lines.append(f"目录数量: {validation['directory_count']}")
        report_lines.append(f"文件数量: {validation['file_count']}")
        
        if validation['errors']:
            report_lines.append("")
            report_lines.append("=== 错误信息 ===")
            for error in validation['errors']:
                report_lines.append(f"- {error}")
        
        # 最近目录结构
        report_lines.append("")
        report_lines.append("=== 最近7天目录结构 ===")
        
        directories = self.list_directory_structure(
            start_date=datetime.now() - timedelta(days=7),
            end_date=datetime.now()
        )
        
        for dir_info in directories:
            status = "存在" if dir_info['exists'] else "不存在"
            report_lines.append(
                f"{dir_info['date']}: {status}, 文件数: {dir_info['file_count']}"
            )
        
        return "\n".join(report_lines)

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='NAS目录结构管理器')
    parser.add_argument('--create', metavar='DATE', help='创建指定日期的目录 (YYYY-MM-DD)')
    parser.add_argument('--verify', metavar='DATE', help='验证指定日期的目录 (YYYY-MM-DD)')
    parser.add_argument('--list', action='store_true', help='列出目录结构')
    parser.add_argument('--cleanup', type=int, metavar='DAYS', help='清理N天前的空目录')
    parser.add_argument('--validate', action='store_true', help='验证整体结构')
    parser.add_argument('--report', action='store_true', help='生成结构报告')
    parser.add_argument('--config', metavar='FILE', help='配置文件路径')
    
    args = parser.parse_args()
    
    # 创建管理器实例
    manager = NASStructureManager(config_file=args.config)
    
    if args.create:
        try:
            date = datetime.strptime(args.create, '%Y-%m-%d')
            success = manager.create_date_directory(date)
            print(f"创建目录: {'成功' if success else '失败'}")
        except ValueError:
            print("日期格式错误，请使用 YYYY-MM-DD 格式")
    
    elif args.verify:
        try:
            date = datetime.strptime(args.verify, '%Y-%m-%d')
            exists = manager.verify_directory_exists(date)
            print(f"目录存在: {'是' if exists else '否'}")
        except ValueError:
            print("日期格式错误，请使用 YYYY-MM-DD 格式")
    
    elif args.list:
        directories = manager.list_directory_structure()
        print("\n=== 目录结构列表 ===")
        for dir_info in directories:
            status = "✓" if dir_info['exists'] else "✗"
            print(f"{status} {dir_info['date']}: {dir_info['file_count']} 文件")
    
    elif args.cleanup is not None:
        cleaned = manager.cleanup_empty_directories(args.cleanup)
        print(f"已清理 {cleaned} 个空目录")
    
    elif args.validate:
        validation = manager.validate_structure()
        print("\n=== 结构验证结果 ===")
        print(f"基础路径存在: {'是' if validation['base_path_exists'] else '否'}")
        print(f"基础路径可写: {'是' if validation['base_path_writable'] else '否'}")
        print(f"总大小: {validation['total_size'] / (1024**3):.2f} GB")
        print(f"目录数量: {validation['directory_count']}")
        print(f"文件数量: {validation['file_count']}")
        
        if validation['errors']:
            print("\n错误:")
            for error in validation['errors']:
                print(f"- {error}")
    
    elif args.report:
        report = manager.generate_structure_report()
        print(report)
        
        # 保存报告到文件
        report_file = f"/home/celestial/dev/esdk-test/Edge-SDK/celestial_works/logs/nas_structure_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n报告已保存到: {report_file}")
    
    else:
        parser.print_help()

if __name__ == '__main__':
    main()