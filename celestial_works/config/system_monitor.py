#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DJI Edge SDK 系统监控脚本
作者: Celestial
创建时间: 2025-01-22
描述: 持续监控系统状态，检测异常并发送警报

功能:
- 监控systemd服务状态
- 监控数据库连接和性能
- 监控磁盘空间和网络连接
- 监控日志文件增长
- 异常时发送邮件警报
- 生成监控报告
"""

import os
import sys
import time
import json
import sqlite3
import subprocess
import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root / 'celestial_nasops'))

try:
    from config_manager import ConfigManager
except ImportError:
    print("警告: 无法导入ConfigManager，将使用默认配置")
    ConfigManager = None

class SystemMonitor:
    """系统监控类"""
    
    def __init__(self, config_path: Optional[str] = None):
        """初始化监控器
        
        Args:
            config_path: 配置文件路径
        """
        self.project_root = project_root
        self.config_path = config_path or str(project_root / 'celestial_nasops' / 'unified_config.json')
        
        # 加载配置
        self.config = self._load_config()
        
        # 设置日志
        self._setup_logging()
        
        # 监控状态
        self.last_check_time = None
        self.alert_history = []
        self.service_status_history = []
        
        # 阈值配置
        self.thresholds = {
            'disk_usage_warning': 80,  # 磁盘使用率警告阈值
            'disk_usage_critical': 90,  # 磁盘使用率严重阈值
            'memory_usage_warning': 80,  # 内存使用率警告阈值
            'db_size_warning': 1000,  # 数据库大小警告阈值(MB)
            'log_size_warning': 500,  # 日志文件大小警告阈值(MB)
            'service_restart_threshold': 3,  # 服务重启次数阈值
        }
        
        self.logger.info("系统监控器初始化完成")
    
    def _load_config(self) -> Dict:
        """加载配置文件"""
        try:
            if ConfigManager and os.path.exists(self.config_path):
                config_manager = ConfigManager(self.config_path)
                return config_manager.get_all_config()
            else:
                # 使用默认配置
                return {
                    'monitoring': {
                        'check_interval': 300,  # 5分钟
                        'alert_email': 'admin@example.com',
                        'smtp_server': 'localhost',
                        'smtp_port': 587
                    }
                }
        except Exception as e:
            print(f"加载配置失败: {e}，使用默认配置")
            return {'monitoring': {'check_interval': 300}}
    
    def _setup_logging(self):
        """设置日志记录"""
        log_dir = self.project_root / 'celestial_works' / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / 'system_monitor.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger('SystemMonitor')
    
    def check_service_status(self) -> Dict:
        """检查systemd服务状态
        
        Returns:
            服务状态信息字典
        """
        service_name = 'dock-info-manager'
        status_info = {
            'service_name': service_name,
            'is_active': False,
            'is_enabled': False,
            'uptime': None,
            'memory_usage': None,
            'restart_count': 0,
            'last_restart': None,
            'status': 'unknown'
        }
        
        try:
            # 检查服务是否活跃
            result = subprocess.run(
                ['systemctl', 'is-active', service_name],
                capture_output=True, text=True, timeout=10
            )
            status_info['is_active'] = result.returncode == 0
            status_info['status'] = result.stdout.strip()
            
            # 检查服务是否启用
            result = subprocess.run(
                ['systemctl', 'is-enabled', service_name],
                capture_output=True, text=True, timeout=10
            )
            status_info['is_enabled'] = result.returncode == 0
            
            if status_info['is_active']:
                # 获取详细信息
                properties = ['ActiveEnterTimestamp', 'MemoryCurrent', 'NRestarts']
                for prop in properties:
                    result = subprocess.run(
                        ['systemctl', 'show', service_name, f'--property={prop}', '--value'],
                        capture_output=True, text=True, timeout=10
                    )
                    
                    if result.returncode == 0:
                        value = result.stdout.strip()
                        if prop == 'ActiveEnterTimestamp' and value:
                            status_info['uptime'] = value
                        elif prop == 'MemoryCurrent' and value.isdigit():
                            status_info['memory_usage'] = int(value) // (1024 * 1024)  # MB
                        elif prop == 'NRestarts' and value.isdigit():
                            status_info['restart_count'] = int(value)
            
            self.logger.info(f"服务状态检查完成: {service_name} - {status_info['status']}")
            
        except subprocess.TimeoutExpired:
            self.logger.error(f"检查服务状态超时: {service_name}")
            status_info['status'] = 'timeout'
        except Exception as e:
            self.logger.error(f"检查服务状态失败: {e}")
            status_info['status'] = 'error'
        
        return status_info
    
    def check_database_status(self) -> Dict:
        """检查数据库状态
        
        Returns:
            数据库状态信息字典
        """
        db_path = self.project_root / 'celestial_works' / 'media_status.db'
        status_info = {
            'db_path': str(db_path),
            'exists': False,
            'size_mb': 0,
            'is_accessible': False,
            'table_count': 0,
            'media_files_count': 0,
            'sync_status_count': 0,
            'last_modified': None
        }
        
        try:
            if db_path.exists():
                status_info['exists'] = True
                
                # 获取文件大小
                size_bytes = db_path.stat().st_size
                status_info['size_mb'] = size_bytes / (1024 * 1024)
                
                # 获取最后修改时间
                status_info['last_modified'] = datetime.fromtimestamp(
                    db_path.stat().st_mtime
                ).isoformat()
                
                # 测试数据库连接
                with sqlite3.connect(str(db_path), timeout=10) as conn:
                    cursor = conn.cursor()
                    
                    # 检查表数量
                    cursor.execute(
                        "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
                    )
                    status_info['table_count'] = cursor.fetchone()[0]
                    
                    # 检查媒体文件记录数
                    try:
                        cursor.execute("SELECT COUNT(*) FROM media_files")
                        status_info['media_files_count'] = cursor.fetchone()[0]
                    except sqlite3.OperationalError:
                        pass
                    
                    # 检查同步状态记录数
                    try:
                        cursor.execute("SELECT COUNT(*) FROM sync_status")
                        status_info['sync_status_count'] = cursor.fetchone()[0]
                    except sqlite3.OperationalError:
                        pass
                    
                    status_info['is_accessible'] = True
                
                self.logger.info(f"数据库状态检查完成: {status_info['size_mb']:.2f}MB")
            else:
                self.logger.warning(f"数据库文件不存在: {db_path}")
                
        except sqlite3.Error as e:
            self.logger.error(f"数据库连接失败: {e}")
        except Exception as e:
            self.logger.error(f"检查数据库状态失败: {e}")
        
        return status_info
    
    def check_disk_space(self) -> Dict:
        """检查磁盘空间
        
        Returns:
            磁盘空间信息字典
        """
        status_info = {
            'project_disk': {},
            'log_directory_size': 0,
            'db_directory_size': 0
        }
        
        try:
            # 检查项目目录所在磁盘
            result = subprocess.run(
                ['df', '-h', str(self.project_root)],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) >= 2:
                    fields = lines[1].split()
                    if len(fields) >= 6:
                        status_info['project_disk'] = {
                            'filesystem': fields[0],
                            'size': fields[1],
                            'used': fields[2],
                            'available': fields[3],
                            'use_percent': int(fields[4].rstrip('%')),
                            'mountpoint': fields[5]
                        }
            
            # 检查日志目录大小
            log_dir = self.project_root / 'celestial_works' / 'logs'
            if log_dir.exists():
                result = subprocess.run(
                    ['du', '-sm', str(log_dir)],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    status_info['log_directory_size'] = int(result.stdout.split()[0])
            
            # 检查数据库目录大小
            db_dir = self.project_root / 'celestial_works'
            if db_dir.exists():
                result = subprocess.run(
                    ['du', '-sm', str(db_dir)],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    status_info['db_directory_size'] = int(result.stdout.split()[0])
            
            self.logger.info(f"磁盘空间检查完成: {status_info['project_disk'].get('use_percent', 0)}%")
            
        except Exception as e:
            self.logger.error(f"检查磁盘空间失败: {e}")
        
        return status_info
    
    def check_network_connectivity(self) -> Dict:
        """检查网络连接
        
        Returns:
            网络连接状态信息字典
        """
        nas_host = '192.168.200.103'
        nas_user = 'edge_sync'
        
        status_info = {
            'nas_ping': False,
            'nas_ssh': False,
            'nas_host': nas_host,
            'ping_time': None,
            'network_interfaces': []
        }
        
        try:
            # 检查到NAS的ping连接
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '3', nas_host],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                status_info['nas_ping'] = True
                # 提取ping时间
                for line in result.stdout.split('\n'):
                    if 'time=' in line:
                        time_part = line.split('time=')[1].split()[0]
                        status_info['ping_time'] = float(time_part)
                        break
                
                # 检查SSH连接
                result = subprocess.run(
                    ['timeout', '10', 'ssh', '-o', 'ConnectTimeout=5', 
                     '-o', 'BatchMode=yes', f'{nas_user}@{nas_host}', 
                     'echo "SSH连接测试"'],
                    capture_output=True, text=True, timeout=15
                )
                
                status_info['nas_ssh'] = result.returncode == 0
            
            # 检查网络接口状态
            result = subprocess.run(
                ['ip', '-o', 'link', 'show'],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if ': lo:' not in line:  # 排除回环接口
                        parts = line.split(': ')
                        if len(parts) >= 2:
                            interface_name = parts[1].split('@')[0]
                            is_up = 'state UP' in line
                            status_info['network_interfaces'].append({
                                'name': interface_name,
                                'is_up': is_up
                            })
            
            self.logger.info(f"网络连接检查完成: NAS ping={status_info['nas_ping']}, SSH={status_info['nas_ssh']}")
            
        except Exception as e:
            self.logger.error(f"检查网络连接失败: {e}")
        
        return status_info
    
    def analyze_alerts(self, status_data: Dict) -> List[Dict]:
        """分析状态数据并生成警报
        
        Args:
            status_data: 系统状态数据
            
        Returns:
            警报列表
        """
        alerts = []
        
        # 检查服务状态
        service_status = status_data.get('service_status', {})
        if not service_status.get('is_active', False):
            alerts.append({
                'level': 'critical',
                'type': 'service',
                'message': f"服务 {service_status.get('service_name')} 未运行",
                'details': service_status
            })
        
        # 检查磁盘空间
        disk_status = status_data.get('disk_status', {})
        project_disk = disk_status.get('project_disk', {})
        use_percent = project_disk.get('use_percent', 0)
        
        if use_percent >= self.thresholds['disk_usage_critical']:
            alerts.append({
                'level': 'critical',
                'type': 'disk',
                'message': f"磁盘空间严重不足: {use_percent}%",
                'details': project_disk
            })
        elif use_percent >= self.thresholds['disk_usage_warning']:
            alerts.append({
                'level': 'warning',
                'type': 'disk',
                'message': f"磁盘空间不足: {use_percent}%",
                'details': project_disk
            })
        
        # 检查数据库状态
        db_status = status_data.get('database_status', {})
        if not db_status.get('is_accessible', False):
            alerts.append({
                'level': 'critical',
                'type': 'database',
                'message': "数据库无法访问",
                'details': db_status
            })
        
        # 检查网络连接
        network_status = status_data.get('network_status', {})
        if not network_status.get('nas_ping', False):
            alerts.append({
                'level': 'warning',
                'type': 'network',
                'message': f"无法连接到NAS: {network_status.get('nas_host')}",
                'details': network_status
            })
        
        return alerts
    
    def send_alert_email(self, alerts: List[Dict]):
        """发送警报邮件
        
        Args:
            alerts: 警报列表
        """
        if not alerts:
            return
        
        try:
            monitoring_config = self.config.get('monitoring', {})
            email_config = monitoring_config.get('email', {})
            
            if not email_config.get('enabled', False):
                self.logger.info("邮件警报未启用")
                return
            
            # 构建邮件内容
            subject = f"DJI Edge SDK 系统警报 - {len(alerts)}个问题"
            
            body_lines = [
                "DJI Edge SDK 系统监控检测到以下问题:",
                "",
                f"检查时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"主机名: {os.uname().nodename}",
                ""
            ]
            
            for i, alert in enumerate(alerts, 1):
                body_lines.extend([
                    f"{i}. [{alert['level'].upper()}] {alert['type'].upper()}",
                    f"   消息: {alert['message']}",
                    f"   详情: {json.dumps(alert['details'], indent=2, ensure_ascii=False)}",
                    ""
                ])
            
            body_lines.extend([
                "请及时检查系统状态并采取相应措施。",
                "",
                "详细日志请查看:",
                f"  {self.project_root}/celestial_works/logs/system_monitor.log"
            ])
            
            body = "\n".join(body_lines)
            
            # 发送邮件
            msg = MIMEMultipart()
            msg['From'] = email_config.get('from', 'system@localhost')
            msg['To'] = email_config.get('to', 'admin@localhost')
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            with smtplib.SMTP(email_config.get('smtp_server', 'localhost'), 
                            email_config.get('smtp_port', 587)) as server:
                if email_config.get('use_tls', False):
                    server.starttls()
                
                if email_config.get('username') and email_config.get('password'):
                    server.login(email_config['username'], email_config['password'])
                
                server.send_message(msg)
            
            self.logger.info(f"警报邮件已发送: {len(alerts)}个警报")
            
        except Exception as e:
            self.logger.error(f"发送警报邮件失败: {e}")
    
    def generate_status_report(self, status_data: Dict) -> str:
        """生成状态报告
        
        Args:
            status_data: 系统状态数据
            
        Returns:
            状态报告字符串
        """
        report_lines = [
            "=== DJI Edge SDK 系统状态报告 ===",
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"主机名: {os.uname().nodename}",
            ""
        ]
        
        # 服务状态
        service_status = status_data.get('service_status', {})
        report_lines.extend([
            "## 服务状态",
            f"服务名称: {service_status.get('service_name', 'N/A')}",
            f"运行状态: {'✓ 运行中' if service_status.get('is_active') else '✗ 未运行'}",
            f"启用状态: {'✓ 已启用' if service_status.get('is_enabled') else '✗ 未启用'}",
            f"内存使用: {service_status.get('memory_usage', 'N/A')}MB",
            f"重启次数: {service_status.get('restart_count', 'N/A')}",
            ""
        ])
        
        # 数据库状态
        db_status = status_data.get('database_status', {})
        report_lines.extend([
            "## 数据库状态",
            f"文件存在: {'✓ 是' if db_status.get('exists') else '✗ 否'}",
            f"可访问性: {'✓ 正常' if db_status.get('is_accessible') else '✗ 异常'}",
            f"文件大小: {db_status.get('size_mb', 0):.2f}MB",
            f"表数量: {db_status.get('table_count', 0)}",
            f"媒体文件记录: {db_status.get('media_files_count', 0)}",
            f"同步状态记录: {db_status.get('sync_status_count', 0)}",
            ""
        ])
        
        # 磁盘状态
        disk_status = status_data.get('disk_status', {})
        project_disk = disk_status.get('project_disk', {})
        report_lines.extend([
            "## 磁盘状态",
            f"使用率: {project_disk.get('use_percent', 0)}%",
            f"可用空间: {project_disk.get('available', 'N/A')}",
            f"日志目录大小: {disk_status.get('log_directory_size', 0)}MB",
            f"数据库目录大小: {disk_status.get('db_directory_size', 0)}MB",
            ""
        ])
        
        # 网络状态
        network_status = status_data.get('network_status', {})
        report_lines.extend([
            "## 网络状态",
            f"NAS连接: {'✓ 正常' if network_status.get('nas_ping') else '✗ 异常'}",
            f"SSH连接: {'✓ 正常' if network_status.get('nas_ssh') else '✗ 异常'}",
            f"Ping延迟: {network_status.get('ping_time', 'N/A')}ms",
            ""
        ])
        
        # 网络接口
        interfaces = network_status.get('network_interfaces', [])
        if interfaces:
            report_lines.append("## 网络接口")
            for interface in interfaces:
                status = '✓ UP' if interface.get('is_up') else '✗ DOWN'
                report_lines.append(f"{interface.get('name', 'N/A')}: {status}")
            report_lines.append("")
        
        return "\n".join(report_lines)
    
    def run_single_check(self) -> Dict:
        """执行单次系统检查
        
        Returns:
            系统状态数据字典
        """
        self.logger.info("开始系统状态检查")
        
        status_data = {
            'timestamp': datetime.now().isoformat(),
            'service_status': self.check_service_status(),
            'database_status': self.check_database_status(),
            'disk_status': self.check_disk_space(),
            'network_status': self.check_network_connectivity()
        }
        
        # 分析警报
        alerts = self.analyze_alerts(status_data)
        status_data['alerts'] = alerts
        
        # 发送警报邮件
        if alerts:
            self.send_alert_email(alerts)
        
        # 保存状态报告
        report = self.generate_status_report(status_data)
        report_file = self.project_root / 'celestial_works' / 'logs' / 'system_status_report.txt'
        
        try:
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            self.logger.info(f"状态报告已保存: {report_file}")
        except Exception as e:
            self.logger.error(f"保存状态报告失败: {e}")
        
        # 保存JSON格式的状态数据
        json_file = self.project_root / 'celestial_works' / 'logs' / 'system_status.json'
        try:
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, indent=2, ensure_ascii=False, default=str)
            self.logger.info(f"状态数据已保存: {json_file}")
        except Exception as e:
            self.logger.error(f"保存状态数据失败: {e}")
        
        self.last_check_time = datetime.now()
        self.logger.info(f"系统状态检查完成，发现 {len(alerts)} 个警报")
        
        return status_data
    
    def run_continuous_monitoring(self, interval: int = None):
        """运行持续监控
        
        Args:
            interval: 检查间隔（秒），默认从配置文件读取
        """
        if interval is None:
            interval = self.config.get('monitoring', {}).get('check_interval', 300)
        
        self.logger.info(f"开始持续监控，检查间隔: {interval}秒")
        
        try:
            while True:
                try:
                    self.run_single_check()
                except Exception as e:
                    self.logger.error(f"监控检查失败: {e}")
                
                self.logger.info(f"等待 {interval} 秒后进行下次检查")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            self.logger.info("监控已停止")
        except Exception as e:
            self.logger.error(f"监控程序异常退出: {e}")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='DJI Edge SDK 系统监控')
    parser.add_argument('--config', '-c', help='配置文件路径')
    parser.add_argument('--interval', '-i', type=int, default=300, help='监控间隔（秒）')
    parser.add_argument('--once', action='store_true', help='只执行一次检查')
    parser.add_argument('--daemon', '-d', action='store_true', help='以守护进程模式运行')
    
    args = parser.parse_args()
    
    # 创建监控器
    monitor = SystemMonitor(config_path=args.config)
    
    if args.once:
        # 执行单次检查
        status_data = monitor.run_single_check()
        
        # 打印摘要
        alerts = status_data.get('alerts', [])
        if alerts:
            print(f"\n发现 {len(alerts)} 个问题:")
            for alert in alerts:
                print(f"  [{alert['level'].upper()}] {alert['message']}")
        else:
            print("\n系统状态正常")
    else:
        # 持续监控
        if args.daemon:
            # TODO: 实现守护进程模式
            print("守护进程模式暂未实现，使用前台模式")
        
        monitor.run_continuous_monitoring(interval=args.interval)

if __name__ == '__main__':
    main()