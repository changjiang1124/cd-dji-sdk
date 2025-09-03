#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
烟雾测试脚本：验证媒体同步守护进程是否按期将本地文件传输至 NAS

用途：
- 在本地媒体目录放置一个小文件；
- 等待一段时间（应大于配置中的 sync_settings.interval_minutes）;
- 轮询检查 NAS 端是否出现对应文件（并可选检查本地文件是否被删除，取决于 delete_after_sync 配置）。

设计原则：
- 读取统一配置文件 celestial_nasops/unified_config.json，避免硬编码；
- 优先使用 ssh 别名 nas_settings.ssh_alias（如 nas-edge），若未配置则回退为 username@host；
- 生成带日期前缀的文件名，以匹配按日期组织的远端目录结构（YYYY/MM/DD）。

运行示例：
  python celestial_nasops/tools/smoke_transfer_check.py \
    --wait-minutes 12 \
    --poll-interval 30

可选：无需等待周期，可先手动触发一次同步（不依赖守护进程）：
  python celestial_nasops/sync_scheduler.py --once

注意：
- 本脚本不调用 systemctl，仅通过 SSH 检查远端文件是否存在；
- 需要提前配置好 ~/.ssh/config 中的 Host 别名（如 nas-edge）和免密登录；
- 代码注释使用中文，便于团队理解与维护。
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
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List, Tuple

# 项目根目录（根据实际路径调整）
PROJECT_ROOT = "/home/celestial/dev/esdk-test/Edge-SDK"
DEFAULT_CONFIG = f"{PROJECT_ROOT}/celestial_nasops/unified_config.json"

# 添加项目路径以导入数据库模块
sys.path.insert(0, PROJECT_ROOT)
from celestial_nasops.media_status_db import MediaStatusDB


def load_config(path: str) -> Dict:
    """加载统一配置文件

    参数：
        path: 配置文件路径
    返回：
        dict 配置字典
    异常：
        FileNotFoundError / json.JSONDecodeError
    """
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_ssh_target(cfg: Dict) -> str:
    """解析 SSH 目标（优先使用 ssh_alias，其次 username@host）"""
    nas = cfg.get("nas_settings", {})
    alias = nas.get("ssh_alias")
    if alias:
        return alias
    username = nas.get("username")
    host = nas.get("host")
    if not username or not host:
        raise ValueError("unified_config.json 缺少 nas_settings.username 或 host 配置")
    return f"{username}@{host}"


def ensure_dir(path: str) -> None:
    """确保目录存在"""
    os.makedirs(path, exist_ok=True)


def generate_test_filename(prefix: str = "smoketest", ext: str = ".txt") -> str:
    """生成包含日期的测试文件名，便于远端按日期目录归档

    格式：YYYYMMDD_HHMMSS_<prefix>_<pid>.<ext>
    """
    now = datetime.now()
    ts = now.strftime("%Y%m%d_%H%M%S")
    return f"{ts}_{prefix}_{os.getpid()}{ext}"


def expected_remote_path(cfg: Dict, filename: str) -> str:
    """根据文件名和配置计算远端文件的绝对存储路径

    远端结构： base_path/YYYY/MM/DD/filename
    """
    nas = cfg["nas_settings"]
    base = nas["base_path"].rstrip("/")
    # 从文件名取前 8 位日期
    date_part = filename[:8]
    try:
        dt = datetime.strptime(date_part, "%Y%m%d")
    except ValueError:
        # 如果文件名不含日期（不太可能，因为我们生成了日期前缀），则使用当前日期
        dt = datetime.now()
    return f"{base}/{dt.year:04d}/{dt.month:02d}/{dt.day:02d}/{filename}"


def calculate_file_hash(file_path: str) -> str:
    """计算文件的SHA256哈希值
    
    参数：
        file_path: 文件路径
    返回：
        文件的SHA256哈希值（十六进制字符串）
    """
    hash_sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()
    except Exception as e:
        print(f"计算文件哈希失败: {e}")
        return ""


def write_local_file(local_dir: str, filename: str, size_bytes: int = 1024) -> tuple[str, int]:
    """在本地媒体目录写入测试文件

    参数：
        local_dir: 本地媒体目录（来自配置 local_settings.media_path）
        filename: 生成的文件名
        size_bytes: 文件大小（字节），默认 1KB
    返回：
        (文件的绝对路径, 实际文件大小)
    """
    ensure_dir(local_dir)
    path = os.path.join(local_dir, filename)
    data = ("smoke test for media sync\n" * ((size_bytes // 24) + 1)).encode("utf-8")
    actual_data = data[:size_bytes]
    with open(path, "wb") as f:
        f.write(actual_data)
    return path, len(actual_data)


def local_file_exists(path: str) -> bool:
    """检查本地文件是否存在"""
    return Path(path).exists()


def remote_file_exists(ssh_target: str, remote_path: str, timeout: int = 15) -> bool:
    """通过 SSH 检查远端文件是否存在

    做法：执行 `ssh <target> test -f <remote_path>`，返回码为 0 则存在。

    参数：
        ssh_target: SSH 目标（别名或 user@host）
        remote_path: 远端文件绝对路径
        timeout: 单次 SSH 超时时间（秒）
    返回：
        True 存在，False 不存在或出错
    """
    try:
        res = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                ssh_target,
                "test",
                "-f",
                remote_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=timeout,
            check=False,
        )
        return res.returncode == 0
    except Exception:
        return False


def check_disk_space(path: str) -> Tuple[bool, Dict[str, any]]:
    """检查磁盘空间
    
    参数：
        path: 要检查的路径
    返回：
        (是否正常, 磁盘信息字典)
    """
    try:
        stat = shutil.disk_usage(path)
        total_gb = stat.total / (1024**3)
        used_gb = (stat.total - stat.free) / (1024**3)
        free_gb = stat.free / (1024**3)
        usage_percent = (used_gb / total_gb) * 100
        
        info = {
            "total_gb": round(total_gb, 2),
            "used_gb": round(used_gb, 2),
            "free_gb": round(free_gb, 2),
            "usage_percent": round(usage_percent, 2)
        }
        
        # 磁盘使用率超过90%认为异常
        is_healthy = usage_percent < 90
        return is_healthy, info
    except Exception as e:
        return False, {"error": str(e)}


def check_network_connectivity(host: str, port: int = 22, timeout: int = 10) -> Tuple[bool, str]:
    """检查网络连接
    
    参数：
        host: 目标主机
        port: 目标端口
        timeout: 超时时间（秒）
    返回：
        (是否连通, 状态信息)
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            return True, f"连接到 {host}:{port} 成功"
        else:
            return False, f"无法连接到 {host}:{port}"
    except Exception as e:
        return False, f"网络检查失败: {e}"


def check_ssh_connection(ssh_target: str, timeout: int = 15) -> Tuple[bool, str]:
    """检查SSH连接
    
    参数：
        ssh_target: SSH目标（别名或user@host）
        timeout: 超时时间（秒）
    返回：
        (是否连通, 状态信息)
    """
    try:
        res = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", ssh_target, "echo", "test"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            text=True
        )
        
        if res.returncode == 0 and res.stdout.strip() == "test":
            return True, f"SSH连接到 {ssh_target} 成功"
        else:
            return False, f"SSH连接失败: {res.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return False, f"SSH连接超时 ({timeout}秒)"
    except Exception as e:
        return False, f"SSH检查失败: {e}"


def check_daemon_status(service_name: str = "media-sync-daemon") -> Tuple[bool, str]:
    """检查守护进程状态
    
    参数：
        service_name: 服务名称
    返回：
        (是否运行, 状态信息)
    """
    try:
        res = subprocess.run(
            ["systemctl", "is-active", service_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if res.returncode == 0 and res.stdout.strip() == "active":
            return True, f"服务 {service_name} 正在运行"
        else:
            return False, f"服务 {service_name} 未运行或异常"
    except Exception as e:
        return False, f"无法检查服务状态: {e}"


def check_daemon_logs(service_name: str = "media-sync-daemon", minutes: int = 10) -> List[str]:
    """检查守护进程最近的错误日志
    
    参数：
        service_name: 服务名称
        minutes: 检查最近多少分钟的日志
    返回：
        错误日志列表
    """
    try:
        res = subprocess.run(
            [
                "journalctl", 
                "-u", service_name, 
                "--since", f"{minutes} min ago",
                "--no-pager",
                "-q"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=30
        )
        
        if res.returncode != 0:
            return [f"无法获取日志: {res.stderr.strip()}"]
        
        # 过滤错误和警告日志
        error_lines = []
        for line in res.stdout.split('\n'):
            line = line.strip()
            if line and any(keyword in line.lower() for keyword in ['error', 'failed', 'exception', 'critical']):
                error_lines.append(line)
        
        return error_lines
    except subprocess.TimeoutExpired:
        return ["获取日志超时"]
    except Exception as e:
        return [f"检查日志失败: {e}"]


def check_daemon_prerequisites() -> Tuple[bool, List[str]]:
    """检查守护进程运行的前置条件
    
    返回：
        (是否满足条件, 问题列表)
    """
    issues = []
    
    # 1. 检查守护进程状态
    daemon_running, daemon_msg = check_daemon_status("media-sync-daemon")
    if not daemon_running:
        issues.append(f"守护进程未运行: {daemon_msg}")
    
    # 2. 检查守护进程服务文件
    service_file = "/etc/systemd/system/media-sync-daemon.service"
    if not os.path.exists(service_file):
        issues.append(f"守护进程服务文件不存在: {service_file}")
    
    # 3. 检查守护进程日志是否有错误
    recent_errors = check_daemon_logs("media-sync-daemon", minutes=10)
    if recent_errors:
        issues.append(f"守护进程最近有错误日志: {len(recent_errors)} 条")
        # 只显示最近的3条错误，避免输出过长
        for error in recent_errors[:3]:
            issues.append(f"  - {error}")
        if len(recent_errors) > 3:
            issues.append(f"  - ... 还有 {len(recent_errors) - 3} 条错误")
    
    # 4. 检查配置文件是否存在
    config_file = f"{PROJECT_ROOT}/celestial_nasops/unified_config.json"
    if not os.path.exists(config_file):
        issues.append(f"配置文件不存在: {config_file}")
    
    return len(issues) == 0, issues


def provide_daemon_guidance(issues: List[str]) -> None:
    """提供守护进程问题的解决指导"""
    print("\n🔧 守护进程问题解决指导:")
    
    for issue in issues:
        print(f"  ❌ {issue}")
    
    print("\n建议的解决步骤:")
    print("  1. 检查服务状态: sudo systemctl status media-sync-daemon")
    print("  2. 查看服务日志: journalctl -u media-sync-daemon --since '10 min ago'")
    print("  3. 重启服务: sudo systemctl restart media-sync-daemon")
    print("  4. 如果服务未安装，运行: cd celestial_nasops && sudo ./install_daemon.sh")
    print("  5. 检查配置文件: cat celestial_nasops/unified_config.json")


def interactive_daemon_check(args) -> bool:
    """交互式守护进程检查
    
    参数：
        args: 命令行参数对象
    返回：
        是否继续执行测试
    """
    print("正在检查守护进程状态...")
    
    prerequisites_ok, issues = check_daemon_prerequisites()
    
    if prerequisites_ok:
        print("✅ 守护进程状态正常，可以继续执行烟雾测试")
        return True
    
    print("\n⚠️  发现守护进程问题:")
    provide_daemon_guidance(issues)
    
    # 检查是否有 --force 参数
    if hasattr(args, 'force') and args.force:
        print("\n--force 参数已指定，强制继续执行测试")
        return True
    
    # 交互式询问
    while True:
        try:
            choice = input("\n是否继续执行测试? (y/n/r) [y=继续, n=退出, r=重新检查]: ").lower().strip()
            if choice in ['y', 'yes', '']:
                return True
            elif choice in ['n', 'no']:
                return False
            elif choice in ['r', 'recheck']:
                return interactive_daemon_check(args)  # 递归重新检查
            else:
                print("请输入 y, n 或 r")
        except (EOFError, KeyboardInterrupt):
            print("\n用户中断操作")
            return False


def check_database_health(db_path: str) -> Tuple[bool, Dict[str, any]]:
    """检查数据库健康状态
    
    参数：
        db_path: 数据库文件路径
    返回：
        (是否健康, 数据库信息)
    """
    try:
        if not os.path.exists(db_path):
            return False, {"error": "数据库文件不存在"}
        
        # 检查文件大小
        file_size = os.path.getsize(db_path)
        
        # 尝试连接数据库
        from celestial_nasops.media_status_db import MediaStatusDB
        db = MediaStatusDB(db_path)
        
        # 获取统计信息
        stats = db.get_statistics()
        db.close()
        
        info = {
            "file_size_bytes": file_size,
            "file_size_mb": round(file_size / (1024*1024), 2),
            "statistics": stats
        }
        
        return True, info
    except Exception as e:
        return False, {"error": str(e)}


def run_system_diagnostics(cfg: Dict) -> Dict[str, any]:
    """运行系统诊断检查
    
    参数：
        cfg: 配置字典
    返回：
        诊断结果字典
    """
    diagnostics = cfg.get("diagnostics", {})
    results = {
        "timestamp": datetime.now().isoformat(),
        "checks": {},
        "overall_health": True
    }
    
    # 磁盘空间检查
    if diagnostics.get("check_disk_space", True):
        local_path = cfg["local_settings"]["media_path"]
        is_healthy, disk_info = check_disk_space(local_path)
        results["checks"]["disk_space"] = {
            "healthy": is_healthy,
            "info": disk_info
        }
        if not is_healthy:
            results["overall_health"] = False
    
    # 网络连接检查
    if diagnostics.get("check_network_connectivity", True):
        nas_host = cfg["nas_settings"]["host"]
        is_connected, conn_info = check_network_connectivity(nas_host)
        results["checks"]["network_connectivity"] = {
            "healthy": is_connected,
            "info": conn_info
        }
        if not is_connected:
            results["overall_health"] = False
    
    # SSH连接检查
    if diagnostics.get("check_ssh_connection", True):
        ssh_target = resolve_ssh_target(cfg)
        is_connected, ssh_info = check_ssh_connection(ssh_target)
        results["checks"]["ssh_connection"] = {
            "healthy": is_connected,
            "info": ssh_info
        }
        if not is_connected:
            results["overall_health"] = False
    
    # 守护进程状态检查
    if diagnostics.get("check_daemon_status", True):
        is_running, daemon_info = check_daemon_status()
        results["checks"]["daemon_status"] = {
            "healthy": is_running,
            "info": daemon_info
        }
        if not is_running:
            results["overall_health"] = False
    
    # 数据库健康检查
    if diagnostics.get("check_database_health", True):
        db_path = cfg.get("database", {}).get("path")
        if not db_path:
            results["checks"]["database_health"] = {
                "healthy": False,
                "info": {"error": "配置文件中未指定数据库路径 (database.path)"}
            }
            results["overall_health"] = False
        elif not os.path.isabs(db_path):
            # 相对路径转换为基于项目根目录的绝对路径
            db_path = os.path.join(PROJECT_ROOT, "celestial_nasops", db_path)
            is_healthy, db_info = check_database_health(db_path)
            results["checks"]["database_health"] = {
                "healthy": is_healthy,
                "info": {**db_info, "resolved_path": db_path}
            }
            if not is_healthy:
                results["overall_health"] = False
        else:
            is_healthy, db_info = check_database_health(db_path)
            results["checks"]["database_health"] = {
                "healthy": is_healthy,
                "info": db_info
            }
            if not is_healthy:
                results["overall_health"] = False
    
    return results


def print_diagnostic_report(results: Dict[str, any]) -> None:
    """打印诊断报告
    
    参数：
        results: 诊断结果字典
    """
    print("\n==== 系统诊断报告 ====")
    print(f"检查时间: {results['timestamp']}")
    print(f"整体健康状态: {'✓ 正常' if results['overall_health'] else '✗ 异常'}\n")
    
    for check_name, check_result in results["checks"].items():
        status = "✓ 正常" if check_result["healthy"] else "✗ 异常"
        print(f"{check_name}: {status}")
        
        if isinstance(check_result["info"], dict):
            for key, value in check_result["info"].items():
                print(f"  {key}: {value}")
        else:
            print(f"  {check_result['info']}")
        print()


def save_diagnostic_report(results: Dict[str, any], cfg: Dict) -> Optional[str]:
    """保存诊断报告到文件
    
    参数：
        results: 诊断结果字典
        cfg: 配置字典
    返回:
        保存的文件路径，失败时返回None
    """
    try:
        diagnostics = cfg.get("diagnostics", {})
        if not diagnostics.get("save_reports", True):
            return None
        
        reports_dir = diagnostics.get("reports_path", "/tmp")
        os.makedirs(reports_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = os.path.join(reports_dir, f"diagnostic_report_{timestamp}.json")
        
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        return report_file
    except Exception as e:
        print(f"保存诊断报告失败: {e}")
        return None


def parse_args(cfg: Dict = None) -> argparse.Namespace:
    """解析命令行参数，使用配置文件中的默认值"""
    # 从配置文件获取默认值
    smoke_cfg = cfg.get("smoke_test", {}) if cfg else {}
    
    parser = argparse.ArgumentParser(
        description="烟雾测试：验证 media-sync-daemon 是否按期将文件传输至 NAS",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help="统一配置文件路径（默认：%(default)s）",
    )
    parser.add_argument(
        "--wait-minutes",
        type=int,
        default=smoke_cfg.get("default_wait_minutes"),
        help=(
            "最大等待分钟数（默认：使用配置 smoke_test.default_wait_minutes 或 sync_settings.interval_minutes + 2）。"
            "应不小于守护进程调度周期。"
        ),
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=smoke_cfg.get("poll_interval_seconds", 30),
        help=f"轮询间隔（秒），默认 {smoke_cfg.get('poll_interval_seconds', 30)}",
    )
    parser.add_argument(
        "--size-bytes",
        type=int,
        default=smoke_cfg.get("default_file_size_bytes", 1024),
        help=f"测试文件大小（字节），默认 {smoke_cfg.get('default_file_size_bytes', 1024)}",
    )
    parser.add_argument(
        "--prefix",
        default=smoke_cfg.get("test_file_prefix", "smoketest"),
        help=f"测试文件名前缀，默认 {smoke_cfg.get('test_file_prefix', 'smoketest')}",
    )
    parser.add_argument(
        "--ext",
        default=smoke_cfg.get("test_file_extension", ".txt"),
        help=f"测试文件扩展名（例如 .txt/.bin），默认 {smoke_cfg.get('test_file_extension', '.txt')}",
    )
    parser.add_argument(
        "--no-remote-check",
        action="store_true",
        help="仅检查本地文件被删除（不检查远端存在）",
    )
    parser.add_argument(
        "--diagnostics-only",
        action="store_true",
        help="仅运行系统诊断检查，不执行烟雾测试",
    )
    parser.add_argument(
        "--skip-diagnostics",
        action="store_true",
        help="跳过系统诊断检查，直接执行烟雾测试",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制执行测试，即使守护进程检查或系统诊断发现问题",
    )
    return parser.parse_args()


def main() -> int:
    # 先加载配置文件以获取默认值
    temp_args = parse_args(None)  # 临时解析以获取config路径
    cfg = load_config(temp_args.config)
    
    # 使用配置重新解析参数
    args = parse_args(cfg)

    local_dir = cfg["local_settings"]["media_path"].rstrip("/")
    ssh_target = resolve_ssh_target(cfg)

    # 计算等待上限（分钟）
    if args.wait_minutes is None:
        wait_minutes = int(cfg["sync_settings"].get("interval_minutes", 10)) + 2
    else:
        wait_minutes = args.wait_minutes

    print("==== Smoke Test (media-sync-daemon) ====")
    print("-" * 50)
    
    # 阶段1: 守护进程预检查
    if not args.skip_diagnostics:
        print("\n=== 阶段1: 守护进程预检查 ===")
        daemon_check_result = interactive_daemon_check(args)
        
        if not daemon_check_result and not args.force:
            print("\n✗ 守护进程预检查失败，测试终止")
            print("提示: 使用 --force 参数可强制执行测试")
            return 1
        elif not daemon_check_result and args.force:
            print("\n⚠️  守护进程预检查失败，但使用 --force 参数继续执行")

    filename = generate_test_filename(prefix=args.prefix, ext=args.ext)
    local_path, actual_size = write_local_file(local_dir, filename, size_bytes=args.size_bytes)
    remote_path = expected_remote_path(cfg, filename)
    
    print(f"\n=== 阶段2: 测试文件准备 ===")
    print(f"Local media dir: {local_dir}")
    print(f"Local file     : {local_path}")
    print(f"SSH target     : {ssh_target}")
    if not args.no_remote_check:
        print(f"Expected remote: {remote_path}")
    print(f"Wait minutes   : {wait_minutes} (poll every {args.poll_interval}s)")
    
    # 初始化数据库连接
    db = None
    try:
        db_path = cfg.get("database", {}).get("path")
        if not db_path:
            print("警告: 配置文件中未指定数据库路径 (database.path)，跳过数据库操作")
        elif not os.path.isabs(db_path):
            # 相对路径转换为基于项目根目录的绝对路径
            db_path = os.path.join(PROJECT_ROOT, "celestial_nasops", db_path)
            print(f"使用相对路径数据库: {db_path}")
            db = MediaStatusDB(db_path)
        else:
            db = MediaStatusDB(db_path)
        
        if db:
            # 显式连接数据库，避免未连接导致插入失败
            if not db.connect():
                print(f"数据库连接失败: {db_path}")
                db = None
            else:
                # 计算文件哈希值
                file_hash = calculate_file_hash(local_path)
                
                # 插入文件记录到数据库（将下载状态标记为completed，以便守护进程拾取）
                if file_hash:
                    success = db.insert_file_record(
                        file_path=local_path,
                        file_name=filename,
                        file_size=actual_size,
                        file_hash=file_hash,
                        download_status='completed',
                        transfer_status='pending'
                    )
                    if success:
                        print(f"✓ 已将测试文件记录插入数据库并标记为下载完成: {filename}")
                    else:
                        print(f"警告: 无法将测试文件记录插入数据库: {filename}")
                else:
                    print("警告: 无法计算文件哈希值，跳过数据库插入")
            
    except Exception as e:
        print(f"数据库初始化失败: {e}")
        print("继续执行烟雾测试，但不记录数据库信息")

    # 运行系统诊断检查
    if not args.skip_diagnostics:
        print("\n=== 阶段3: 系统诊断检查 ===")
        diagnostic_results = run_system_diagnostics(cfg)
        print_diagnostic_report(diagnostic_results)
        
        # 保存诊断报告
        report_file = save_diagnostic_report(diagnostic_results, cfg)
        if report_file:
            print(f"诊断报告已保存到: {report_file}")
        
        # 如果仅运行诊断，则退出
        if args.diagnostics_only:
            if db:
                try:
                    db.close()
                except Exception as e:
                    print(f"关闭数据库连接时出错: {e}")
            return 0 if diagnostic_results["overall_health"] else 1
        
        # 检查诊断结果
        if not diagnostic_results["overall_health"] and not args.force:
            print("\n✗ 系统诊断发现问题，测试终止")
            print("提示: 使用 --force 参数可强制执行测试")
            if db:
                try:
                    db.close()
                except Exception as e:
                    print(f"关闭数据库连接时出错: {e}")
            return 1
        elif not diagnostic_results["overall_health"] and args.force:
            print("\n⚠️  系统诊断发现问题，但使用 --force 参数继续执行")

    print("\n=== 阶段4: 守护进程监控与验证 ===")

    # 轮询等待：优先检查远端出现；如果配置 delete_after_sync 为 True，则本地文件应被删除
    deadline = time.time() + wait_minutes * 60
    last_local_exist: Optional[bool] = None

    while time.time() < deadline:
        # 检查本地文件状态
        local_exist = local_file_exists(local_path)
        if last_local_exist is None or local_exist != last_local_exist:
            print(time.strftime("[%H:%M:%S]"), "Local exists:", local_exist)
            last_local_exist = local_exist

        # 检查远端文件
        remote_ok = True if args.no_remote_check else remote_file_exists(ssh_target, remote_path)
        if not args.no_remote_check:
            print(time.strftime("[%H:%M:%S]"), "Remote exists:", remote_ok)

        # 判定成功条件：
        # - 若需要远端检查：remote_ok 为 True；
        # - 若 delete_after_sync=True：则 local_exist 应为 False（表示已清理本地）。
        success = False
        if args.no_remote_check:
            # 仅基于本地删除来判断（较弱判据）
            if not local_exist:
                success = True
        else:
            success = remote_ok
            # 如配置要求删除本地，则同时要求本地不存在以更严格判定
            if success and cfg["sync_settings"].get("delete_after_sync", True):
                success = not local_exist

        if success:
            print("\n✓ 烟雾测试成功！")
            print("  - 文件已成功传输到远程")
            print("  - 本地文件已被清理")
            # 清理数据库连接
            if db:
                try:
                    db.close()
                except Exception as e:
                    print(f"关闭数据库连接时出错: {e}")
            return 0

        time.sleep(args.poll_interval)

    print(f"\n✗ 烟雾测试超时（{wait_minutes}分钟）")
    print("最终状态:")
    if not args.no_remote_check:
        remote_exists = remote_file_exists(ssh_target, remote_path)
        print(f"  - 远程文件: {'存在' if remote_exists else '不存在'}")
    local_exists = local_file_exists(local_path)
    print(f"  - 本地文件: {'存在' if local_exists else '已删除'}")
    print("\nHints:")
    print("- 确认 systemd 服务已运行：sudo systemctl status media-sync-daemon")
    print("- 查看日志：journalctl -u media-sync-daemon --since '30 min ago' -n 200")
    print("- 也可手动触发一次：python celestial_nasops/sync_scheduler.py --once")
    
    # 清理数据库连接
    if db:
        try:
            db.close()
        except Exception as e:
            print(f"关闭数据库连接时出错: {e}")
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nAborted by user.")
        sys.exit(130)