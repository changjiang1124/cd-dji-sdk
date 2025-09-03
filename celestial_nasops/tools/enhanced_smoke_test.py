#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版烟雾测试脚本：验证媒体同步守护进程的完整功能

主要增强功能：
- 模块化架构设计
- 实时数据库状态监控
- 性能指标监控
- 详细的JSON测试报告
- 多种测试场景支持
- 智能文件生成
- 异常处理和恢复

作者: Enhanced Smoke Test System
版本: 2.0
日期: 2025-01-13
"""

import argparse
import json
import os
import sys
import time
import subprocess
import hashlib
import shutil
import socket
import threading
import psutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, List, Tuple, Any
from dataclasses import dataclass, asdict
from enum import Enum

# 项目根目录
PROJECT_ROOT = "/home/celestial/dev/esdk-test/Edge-SDK"
DEFAULT_CONFIG = f"{PROJECT_ROOT}/celestial_nasops/unified_config.json"

# 添加项目路径以导入数据库模块
sys.path.insert(0, PROJECT_ROOT)
from celestial_nasops.media_status_db import MediaStatusDB


class TestStatus(Enum):
    """测试状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ERROR = "error"


class FileType(Enum):
    """测试文件类型枚举"""
    TEXT = "text"
    BINARY = "binary"
    IMAGE = "image"
    VIDEO = "video"
    LARGE = "large"


@dataclass
class TestFile:
    """测试文件信息"""
    name: str
    path: str
    size: int
    hash: str
    file_type: FileType
    created_at: datetime
    expected_remote_path: str


@dataclass
class PerformanceMetrics:
    """性能指标"""
    transfer_start_time: Optional[datetime] = None
    transfer_end_time: Optional[datetime] = None
    transfer_duration: Optional[float] = None
    transfer_speed_mbps: Optional[float] = None
    cpu_usage_percent: Optional[float] = None
    memory_usage_mb: Optional[float] = None
    disk_io_read_mb: Optional[float] = None
    disk_io_write_mb: Optional[float] = None
    network_sent_mb: Optional[float] = None
    network_recv_mb: Optional[float] = None


@dataclass
class TestResult:
    """测试结果"""
    test_id: str
    status: TestStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[float] = None
    test_file: Optional[TestFile] = None
    performance: Optional[PerformanceMetrics] = None
    error_message: Optional[str] = None
    diagnostics: Optional[Dict[str, Any]] = None
    database_records: Optional[List[Dict[str, Any]]] = None


class FileManager:
    """文件管理器 - 负责测试文件的创建、管理和清理"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.local_media_path = config["local_settings"]["media_path"]
        self.temp_path = config["local_settings"].get("temp_path", "/tmp")
        
    def generate_test_filename(self, prefix: str = "enhanced_smoke", 
                             file_type: FileType = FileType.TEXT) -> str:
        """生成智能测试文件名"""
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        type_suffix = file_type.value
        pid = os.getpid()
        
        extensions = {
            FileType.TEXT: ".txt",
            FileType.BINARY: ".bin",
            FileType.IMAGE: ".jpg",
            FileType.VIDEO: ".mp4",
            FileType.LARGE: ".dat"
        }
        
        ext = extensions.get(file_type, ".txt")
        return f"{timestamp}_{prefix}_{type_suffix}_{pid}{ext}"
    
    def create_test_file(self, filename: str, size_bytes: int, 
                        file_type: FileType = FileType.TEXT) -> TestFile:
        """创建测试文件"""
        local_path = os.path.join(self.local_media_path, filename)
        os.makedirs(self.local_media_path, exist_ok=True)
        
        # 根据文件类型生成不同内容
        if file_type == FileType.TEXT:
            content = self._generate_text_content(size_bytes)
        elif file_type == FileType.BINARY:
            content = self._generate_binary_content(size_bytes)
        elif file_type == FileType.IMAGE:
            content = self._generate_image_content(size_bytes)
        elif file_type == FileType.VIDEO:
            content = self._generate_video_content(size_bytes)
        else:
            content = self._generate_random_content(size_bytes)
        
        with open(local_path, "wb") as f:
            f.write(content)
        
        # 计算文件哈希
        file_hash = self._calculate_file_hash(local_path)
        actual_size = os.path.getsize(local_path)
        
        # 计算预期远程路径
        expected_remote_path = self._calculate_expected_remote_path(filename)
        
        return TestFile(
            name=filename,
            path=local_path,
            size=actual_size,
            hash=file_hash,
            file_type=file_type,
            created_at=datetime.now(),
            expected_remote_path=expected_remote_path
        )
    
    def _generate_text_content(self, size_bytes: int) -> bytes:
        """生成文本内容"""
        base_text = "Enhanced Smoke Test for Media Sync Daemon\n"
        base_text += f"Generated at: {datetime.now().isoformat()}\n"
        base_text += f"Test ID: {os.getpid()}\n"
        base_text += "Content: " + "A" * 50 + "\n"
        
        content = base_text
        while len(content.encode('utf-8')) < size_bytes:
            content += base_text
        
        return content.encode('utf-8')[:size_bytes]
    
    def _generate_binary_content(self, size_bytes: int) -> bytes:
        """生成二进制内容"""
        import random
        return bytes([random.randint(0, 255) for _ in range(size_bytes)])
    
    def _generate_image_content(self, size_bytes: int) -> bytes:
        """生成模拟图像内容（简单的二进制数据）"""
        # 简单的JPEG文件头
        jpeg_header = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00'
        jpeg_footer = b'\xff\xd9'
        
        remaining = size_bytes - len(jpeg_header) - len(jpeg_footer)
        if remaining > 0:
            middle_content = self._generate_binary_content(remaining)
            return jpeg_header + middle_content + jpeg_footer
        else:
            return jpeg_header[:size_bytes]
    
    def _generate_video_content(self, size_bytes: int) -> bytes:
        """生成模拟视频内容"""
        # 简单的MP4文件头
        mp4_header = b'\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom'
        
        remaining = size_bytes - len(mp4_header)
        if remaining > 0:
            middle_content = self._generate_binary_content(remaining)
            return mp4_header + middle_content
        else:
            return mp4_header[:size_bytes]
    
    def _generate_random_content(self, size_bytes: int) -> bytes:
        """生成随机内容"""
        return self._generate_binary_content(size_bytes)
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """计算文件SHA256哈希值"""
        hash_sha256 = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception:
            return ""
    
    def _calculate_expected_remote_path(self, filename: str) -> str:
        """计算预期的远程文件路径"""
        nas_settings = self.config["nas_settings"]
        base_path = nas_settings["base_path"].rstrip("/")
        
        # 从文件名提取日期
        date_part = filename[:8]
        try:
            dt = datetime.strptime(date_part, "%Y%m%d")
        except ValueError:
            dt = datetime.now()
        
        return f"{base_path}/{dt.year:04d}/{dt.month:02d}/{dt.day:02d}/{filename}"
    
    def file_exists(self, file_path: str) -> bool:
        """检查文件是否存在"""
        return Path(file_path).exists()
    
    def remote_file_exists(self, ssh_target: str, remote_path: str, timeout: int = 15) -> bool:
        """检查远程文件是否存在"""
        try:
            result = subprocess.run(
                ["ssh", "-o", "BatchMode=yes", ssh_target, "test", "-f", remote_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout,
                check=False
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def cleanup_test_file(self, file_path: str) -> bool:
        """清理测试文件"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            return True
        except Exception:
            return False


class DatabaseMonitor:
    """数据库监控器 - 负责监控数据库状态变化"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db_path = self._resolve_db_path()
        self.db = None
        self.monitoring = False
        self.status_changes = []
        
    def _resolve_db_path(self) -> Optional[str]:
        """解析数据库路径"""
        db_config = self.config.get("database", {})
        db_path = db_config.get("path")
        
        if not db_path:
            return None
            
        if not os.path.isabs(db_path):
            return os.path.join(PROJECT_ROOT, "celestial_nasops", db_path)
        
        return db_path
    
    def connect(self) -> bool:
        """连接数据库"""
        if not self.db_path:
            return False
            
        try:
            self.db = MediaStatusDB(self.db_path)
            return self.db.connect()
        except Exception:
            return False
    
    def disconnect(self):
        """断开数据库连接"""
        if self.db:
            try:
                self.db.close()
            except Exception:
                pass
            self.db = None
    
    def insert_test_record(self, test_file: TestFile) -> bool:
        """插入测试记录"""
        if not self.db:
            return False
            
        try:
            return self.db.insert_file_record(
                file_path=test_file.path,
                file_name=test_file.name,
                file_size=test_file.size,
                file_hash=test_file.hash,
                download_status='completed',
                transfer_status='pending'
            )
        except Exception:
            return False
    
    def get_file_status(self, file_path: str) -> Optional[Dict[str, Any]]:
        """获取文件状态"""
        if not self.db:
            return None
            
        try:
            # 使用get_file_info方法获取文件信息
            file_info = self.db.get_file_info(file_path)
            if file_info:
                return {
                    'id': file_info.id,
                    'file_path': file_info.file_path,
                    'file_name': file_info.file_name,
                    'download_status': file_info.download_status.value,
                    'transfer_status': file_info.transfer_status.value,
                    'created_at': file_info.created_at,
                    'updated_at': file_info.updated_at
                }
            return None
        except Exception:
            return None
    
    def start_monitoring(self, file_path: str, callback=None):
        """开始监控文件状态变化"""
        self.monitoring = True
        self.status_changes = []
        
        def monitor_loop():
            last_status = None
            while self.monitoring:
                current_status = self.get_file_status(file_path)
                if current_status and current_status != last_status:
                    change_record = {
                        "timestamp": datetime.now().isoformat(),
                        "status": current_status
                    }
                    self.status_changes.append(change_record)
                    
                    if callback:
                        callback(change_record)
                    
                    last_status = current_status
                
                time.sleep(1)  # 每秒检查一次
        
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
    
    def get_status_changes(self) -> List[Dict[str, Any]]:
        """获取状态变化记录"""
        return self.status_changes.copy()
    
    def wait_for_status_change(self, file_path: str, expected_status: str, 
                              timeout_seconds: int = 300) -> bool:
        """等待特定状态变化"""
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            status = self.get_file_status(file_path)
            if status and status.get('transfer_status') == expected_status:
                return True
            time.sleep(2)
        
        return False


class PerformanceMonitor:
    """性能监控器 - 负责监控系统性能指标"""
    
    def __init__(self):
        self.monitoring = False
        self.metrics = PerformanceMetrics()
        self.initial_stats = None
        
    def start_monitoring(self):
        """开始性能监控"""
        self.monitoring = True
        self.metrics = PerformanceMetrics()
        self.metrics.transfer_start_time = datetime.now()
        
        # 记录初始系统状态
        self.initial_stats = {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory': psutil.virtual_memory(),
            'disk_io': psutil.disk_io_counters(),
            'network_io': psutil.net_io_counters()
        }
    
    def stop_monitoring(self, file_size_bytes: int = 0):
        """停止性能监控并计算指标"""
        if not self.monitoring:
            return
            
        self.monitoring = False
        self.metrics.transfer_end_time = datetime.now()
        
        if self.metrics.transfer_start_time:
            duration = (self.metrics.transfer_end_time - self.metrics.transfer_start_time).total_seconds()
            self.metrics.transfer_duration = duration
            
            if duration > 0 and file_size_bytes > 0:
                speed_bps = file_size_bytes / duration
                self.metrics.transfer_speed_mbps = speed_bps / (1024 * 1024)
        
        # 获取最终系统状态
        try:
            final_stats = {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory': psutil.virtual_memory(),
                'disk_io': psutil.disk_io_counters(),
                'network_io': psutil.net_io_counters()
            }
            
            # 计算差值
            if self.initial_stats:
                self.metrics.cpu_usage_percent = final_stats['cpu_percent']
                self.metrics.memory_usage_mb = final_stats['memory'].used / (1024 * 1024)
                
                if self.initial_stats['disk_io'] and final_stats['disk_io']:
                    disk_read_diff = final_stats['disk_io'].read_bytes - self.initial_stats['disk_io'].read_bytes
                    disk_write_diff = final_stats['disk_io'].write_bytes - self.initial_stats['disk_io'].write_bytes
                    self.metrics.disk_io_read_mb = disk_read_diff / (1024 * 1024)
                    self.metrics.disk_io_write_mb = disk_write_diff / (1024 * 1024)
                
                if self.initial_stats['network_io'] and final_stats['network_io']:
                    net_sent_diff = final_stats['network_io'].bytes_sent - self.initial_stats['network_io'].bytes_sent
                    net_recv_diff = final_stats['network_io'].bytes_recv - self.initial_stats['network_io'].bytes_recv
                    self.metrics.network_sent_mb = net_sent_diff / (1024 * 1024)
                    self.metrics.network_recv_mb = net_recv_diff / (1024 * 1024)
                    
        except Exception as e:
            print(f"性能监控数据收集失败: {e}")
    
    def get_metrics(self) -> PerformanceMetrics:
        """获取性能指标"""
        return self.metrics


class SystemDiagnostics:
    """系统诊断器 - 负责系统健康检查"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    def run_full_diagnostics(self) -> Dict[str, Any]:
        """运行完整系统诊断"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "overall_health": True
        }
        
        # 磁盘空间检查
        disk_health, disk_info = self._check_disk_space()
        results["checks"]["disk_space"] = {
            "healthy": disk_health,
            "info": disk_info
        }
        if not disk_health:
            results["overall_health"] = False
        
        # 网络连接检查
        network_health, network_info = self._check_network_connectivity()
        results["checks"]["network_connectivity"] = {
            "healthy": network_health,
            "info": network_info
        }
        if not network_health:
            results["overall_health"] = False
        
        # SSH连接检查
        ssh_health, ssh_info = self._check_ssh_connection()
        results["checks"]["ssh_connection"] = {
            "healthy": ssh_health,
            "info": ssh_info
        }
        if not ssh_health:
            results["overall_health"] = False
        
        # 守护进程状态检查
        daemon_health, daemon_info = self._check_daemon_status()
        results["checks"]["daemon_status"] = {
            "healthy": daemon_health,
            "info": daemon_info
        }
        if not daemon_health:
            results["overall_health"] = False
        
        # 数据库健康检查
        db_health, db_info = self._check_database_health()
        results["checks"]["database_health"] = {
            "healthy": db_health,
            "info": db_info
        }
        if not db_health:
            results["overall_health"] = False
        
        return results
    
    def _check_disk_space(self) -> Tuple[bool, Dict[str, Any]]:
        """检查磁盘空间"""
        try:
            path = self.config["local_settings"]["media_path"]
            stat = shutil.disk_usage(path)
            total_gb = stat.total / (1024**3)
            used_gb = (stat.total - stat.free) / (1024**3)
            free_gb = stat.free / (1024**3)
            usage_percent = (used_gb / total_gb) * 100
            
            info = {
                "path": path,
                "total_gb": round(total_gb, 2),
                "used_gb": round(used_gb, 2),
                "free_gb": round(free_gb, 2),
                "usage_percent": round(usage_percent, 2)
            }
            
            return usage_percent < 90, info
        except Exception as e:
            return False, {"error": str(e)}
    
    def _check_network_connectivity(self) -> Tuple[bool, str]:
        """检查网络连接"""
        try:
            host = self.config["nas_settings"]["host"]
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            result = sock.connect_ex((host, 22))
            sock.close()
            
            if result == 0:
                return True, f"连接到 {host}:22 成功"
            else:
                return False, f"无法连接到 {host}:22"
        except Exception as e:
            return False, f"网络检查失败: {e}"
    
    def _check_ssh_connection(self) -> Tuple[bool, str]:
        """检查SSH连接"""
        try:
            ssh_target = self._resolve_ssh_target()
            result = subprocess.run(
                ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", 
                 ssh_target, "echo", "test"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=15,
                text=True
            )
            
            if result.returncode == 0 and result.stdout.strip() == "test":
                return True, f"SSH连接到 {ssh_target} 成功"
            else:
                return False, f"SSH连接失败: {result.stderr.strip()}"
        except Exception as e:
            return False, f"SSH检查失败: {e}"
    
    def _check_daemon_status(self) -> Tuple[bool, str]:
        """检查守护进程状态"""
        try:
            result = subprocess.run(
                ["systemctl", "is-active", "media_finding_daemon"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            if result.returncode == 0 and result.stdout.strip() == "active":
                return True, "守护进程正在运行"
            else:
                return False, "守护进程未运行或异常"
        except Exception as e:
            return False, f"无法检查守护进程状态: {e}"
    
    def _check_database_health(self) -> Tuple[bool, Dict[str, Any]]:
        """检查数据库健康状态"""
        try:
            db_config = self.config.get("database", {})
            db_path = db_config.get("path")
            
            if not db_path:
                return False, {"error": "配置文件中未指定数据库路径"}
            
            if not os.path.isabs(db_path):
                db_path = os.path.join(PROJECT_ROOT, "celestial_nasops", db_path)
            
            if not os.path.exists(db_path):
                return False, {"error": "数据库文件不存在"}
            
            file_size = os.path.getsize(db_path)
            
            # 尝试连接数据库
            db = MediaStatusDB(db_path)
            if not db.connect():
                return False, {"error": "无法连接数据库"}
            
            stats = db.get_statistics()
            db.close()
            
            info = {
                "path": db_path,
                "file_size_bytes": file_size,
                "file_size_mb": round(file_size / (1024*1024), 2),
                "statistics": stats
            }
            
            return True, info
        except Exception as e:
            return False, {"error": str(e)}
    
    def _resolve_ssh_target(self) -> str:
        """解析SSH目标"""
        nas = self.config.get("nas_settings", {})
        alias = nas.get("ssh_alias")
        if alias:
            return alias
        username = nas.get("username")
        host = nas.get("host")
        if not username or not host:
            raise ValueError("配置文件缺少SSH连接信息")
        return f"{username}@{host}"


class TestReportGenerator:
    """测试报告生成器 - 负责生成详细的JSON测试报告"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.reports_dir = config.get("smoke_test", {}).get("reports_path", "/tmp/smoke_test_reports")
        os.makedirs(self.reports_dir, exist_ok=True)
    
    def generate_report(self, test_result: TestResult) -> str:
        """生成测试报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_filename = f"enhanced_smoke_test_report_{timestamp}.json"
        report_path = os.path.join(self.reports_dir, report_filename)
        
        # 转换为可序列化的字典
        report_data = {
            "test_metadata": {
                "test_id": test_result.test_id,
                "test_version": "2.0",
                "generated_at": datetime.now().isoformat(),
                "config_file": DEFAULT_CONFIG
            },
            "test_result": self._serialize_test_result(test_result),
            "system_info": self._collect_system_info(),
            "configuration": self._sanitize_config()
        }
        
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False, default=str)
        
        return report_path
    
    def _serialize_test_result(self, result: TestResult) -> Dict[str, Any]:
        """序列化测试结果"""
        data = asdict(result)
        
        # 处理枚举类型
        if data.get('status'):
            data['status'] = data['status'].value if hasattr(data['status'], 'value') else str(data['status'])
        
        # 处理测试文件信息
        if data.get('test_file') and data['test_file'].get('file_type'):
            data['test_file']['file_type'] = data['test_file']['file_type'].value if hasattr(data['test_file']['file_type'], 'value') else str(data['test_file']['file_type'])
        
        return data
    
    def _collect_system_info(self) -> Dict[str, Any]:
        """收集系统信息"""
        try:
            return {
                "hostname": socket.gethostname(),
                "platform": sys.platform,
                "python_version": sys.version,
                "cpu_count": psutil.cpu_count(),
                "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
                "disk_usage": {
                    path: {
                        "total_gb": round(shutil.disk_usage(path).total / (1024**3), 2),
                        "free_gb": round(shutil.disk_usage(path).free / (1024**3), 2)
                    } for path in ["/", "/tmp"] if os.path.exists(path)
                }
            }
        except Exception as e:
            return {"error": f"无法收集系统信息: {e}"}
    
    def _sanitize_config(self) -> Dict[str, Any]:
        """清理配置信息（移除敏感数据）"""
        sanitized = self.config.copy()
        
        # 移除敏感信息
        if "nas_settings" in sanitized:
            nas = sanitized["nas_settings"]
            if "password" in nas:
                nas["password"] = "***REDACTED***"
        
        return sanitized


class TestManager:
    """测试管理器 - 核心测试协调器"""
    
    def __init__(self, config_path: str = DEFAULT_CONFIG):
        self.config = self._load_config(config_path)
        self.file_manager = FileManager(self.config)
        self.db_monitor = DatabaseMonitor(self.config)
        self.perf_monitor = PerformanceMonitor()
        self.diagnostics = SystemDiagnostics(self.config)
        self.report_generator = TestReportGenerator(self.config)
        
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """加载配置文件"""
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def run_basic_functionality_test(self, **kwargs) -> TestResult:
        """运行基本功能测试"""
        test_id = f"basic_test_{int(time.time())}"
        result = TestResult(
            test_id=test_id,
            status=TestStatus.RUNNING,
            start_time=datetime.now()
        )
        
        try:
            # 获取测试参数
            file_size = kwargs.get('file_size', 1024)
            file_type = kwargs.get('file_type', FileType.TEXT)
            wait_minutes = kwargs.get('wait_minutes', 15)
            
            print(f"\n=== 开始基本功能测试 (ID: {test_id}) ===")
            
            # 1. 系统诊断
            if not kwargs.get('skip_diagnostics', False):
                print("运行系统诊断...")
                diagnostics = self.diagnostics.run_full_diagnostics()
                result.diagnostics = diagnostics
                
                if not diagnostics["overall_health"] and not kwargs.get('force', False):
                    result.status = TestStatus.FAILED
                    result.error_message = "系统诊断发现问题"
                    return result
            
            # 2. 连接数据库
            if not self.db_monitor.connect():
                print("警告: 无法连接数据库，继续执行测试")
            
            # 3. 创建测试文件
            print("创建测试文件...")
            filename = self.file_manager.generate_test_filename(file_type=file_type)
            test_file = self.file_manager.create_test_file(filename, file_size, file_type)
            result.test_file = test_file
            
            print(f"测试文件已创建: {test_file.name} ({test_file.size} bytes)")
            
            # 4. 插入数据库记录
            if self.db_monitor.db:
                if self.db_monitor.insert_test_record(test_file):
                    print("测试文件记录已插入数据库")
                else:
                    print("警告: 无法插入数据库记录")
            
            # 5. 开始监控
            print("开始性能监控...")
            self.perf_monitor.start_monitoring()
            
            if self.db_monitor.db:
                self.db_monitor.start_monitoring(test_file.path, self._on_status_change)
            
            # 6. 等待传输完成
            print(f"等待文件传输完成 (最多 {wait_minutes} 分钟)...")
            success = self._wait_for_transfer_completion(test_file, wait_minutes)
            
            # 7. 停止监控
            self.perf_monitor.stop_monitoring(test_file.size)
            self.db_monitor.stop_monitoring()
            
            result.performance = self.perf_monitor.get_metrics()
            result.database_records = self.db_monitor.get_status_changes()
            
            if success:
                result.status = TestStatus.SUCCESS
                print("✓ 测试成功完成")
            else:
                result.status = TestStatus.TIMEOUT
                result.error_message = "传输超时"
                print("✗ 测试超时")
            
        except Exception as e:
            result.status = TestStatus.ERROR
            result.error_message = str(e)
            print(f"✗ 测试出错: {e}")
        
        finally:
            result.end_time = datetime.now()
            if result.start_time and result.end_time:
                result.duration = (result.end_time - result.start_time).total_seconds()
            
            # 清理资源
            self.db_monitor.disconnect()
            
            # 生成报告
            report_path = self.report_generator.generate_report(result)
            print(f"测试报告已生成: {report_path}")
        
        return result
    
    def _wait_for_transfer_completion(self, test_file: TestFile, wait_minutes: int) -> bool:
        """等待传输完成"""
        ssh_target = self._resolve_ssh_target()
        deadline = time.time() + wait_minutes * 60
        
        while time.time() < deadline:
            # 检查远程文件是否存在
            remote_exists = self.file_manager.remote_file_exists(
                ssh_target, test_file.expected_remote_path
            )
            
            # 检查本地文件是否被删除（如果配置了删除）
            local_exists = self.file_manager.file_exists(test_file.path)
            delete_after_sync = self.config["sync_settings"].get("delete_after_sync", True)
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 远程: {remote_exists}, 本地: {local_exists}")
            
            # 判断成功条件
            if remote_exists:
                if not delete_after_sync or not local_exists:
                    return True
            
            time.sleep(10)  # 每10秒检查一次
        
        return False
    
    def _resolve_ssh_target(self) -> str:
        """解析SSH目标"""
        nas = self.config.get("nas_settings", {})
        alias = nas.get("ssh_alias")
        if alias:
            return alias
        username = nas.get("username")
        host = nas.get("host")
        if not username or not host:
            raise ValueError("配置文件缺少SSH连接信息")
        return f"{username}@{host}"
    
    def _on_status_change(self, change_record: Dict[str, Any]):
        """数据库状态变化回调"""
        print(f"[DB] 状态变化: {change_record}")


def parse_enhanced_args() -> argparse.Namespace:
    """解析增强版命令行参数"""
    parser = argparse.ArgumentParser(
        description="增强版烟雾测试：验证 media-sync-daemon 完整功能"
    )
    
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help="配置文件路径"
    )
    
    parser.add_argument(
        "--test-type",
        choices=["basic", "performance", "stress", "exception"],
        default="basic",
        help="测试类型"
    )
    
    parser.add_argument(
        "--file-type",
        choices=["text", "binary", "image", "video", "large"],
        default="text",
        help="测试文件类型"
    )
    
    parser.add_argument(
        "--file-size",
        type=int,
        default=1024,
        help="测试文件大小（字节）"
    )
    
    parser.add_argument(
        "--wait-minutes",
        type=int,
        default=15,
        help="最大等待时间（分钟）"
    )
    
    parser.add_argument(
        "--skip-diagnostics",
        action="store_true",
        help="跳过系统诊断"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制执行测试"
    )
    
    return parser.parse_args()


def main() -> int:
    """主函数"""
    args = parse_enhanced_args()
    
    try:
        # 创建测试管理器
        test_manager = TestManager(args.config)
        
        # 转换文件类型
        file_type_map = {
            "text": FileType.TEXT,
            "binary": FileType.BINARY,
            "image": FileType.IMAGE,
            "video": FileType.VIDEO,
            "large": FileType.LARGE
        }
        
        file_type = file_type_map.get(args.file_type, FileType.TEXT)
        
        # 运行测试
        if args.test_type == "basic":
            result = test_manager.run_basic_functionality_test(
                file_type=file_type,
                file_size=args.file_size,
                wait_minutes=args.wait_minutes,
                skip_diagnostics=args.skip_diagnostics,
                force=args.force
            )
        else:
            print(f"测试类型 '{args.test_type}' 暂未实现")
            return 1
        
        # 返回结果
        if result.status == TestStatus.SUCCESS:
            return 0
        elif result.status == TestStatus.TIMEOUT:
            return 2
        else:
            return 1
            
    except KeyboardInterrupt:
        print("\n用户中断测试")
        return 130
    except Exception as e:
        print(f"测试执行失败: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())