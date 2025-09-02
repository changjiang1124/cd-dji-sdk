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
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# 项目根目录（根据实际路径调整）。这里不依赖导入项目模块，仅读取配置与调用系统 ssh。
PROJECT_ROOT = "/home/celestial/dev/esdk-test/Edge-SDK"
DEFAULT_CONFIG = f"{PROJECT_ROOT}/celestial_nasops/unified_config.json"


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


def write_local_file(local_dir: str, filename: str, size_bytes: int = 1024) -> str:
    """在本地媒体目录写入测试文件

    参数：
        local_dir: 本地媒体目录（来自配置 local_settings.media_path）
        filename: 生成的文件名
        size_bytes: 文件大小（字节），默认 1KB
    返回：
        文件的绝对路径
    """
    ensure_dir(local_dir)
    path = os.path.join(local_dir, filename)
    data = ("smoke test for media sync\n" * ((size_bytes // 24) + 1)).encode("utf-8")
    with open(path, "wb") as f:
        f.write(data[:size_bytes])
    return path


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


def parse_args() -> argparse.Namespace:
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
        default=None,
        help=(
            "最大等待分钟数（默认：使用配置 sync_settings.interval_minutes + 2）。"
            "应不小于守护进程调度周期。"
        ),
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=30,
        help="轮询间隔（秒），默认 30",
    )
    parser.add_argument(
        "--size-bytes",
        type=int,
        default=1024,
        help="测试文件大小（字节），默认 1024",
    )
    parser.add_argument(
        "--prefix",
        default="smoketest",
        help="测试文件名前缀，默认 smoketest",
    )
    parser.add_argument(
        "--ext",
        default=".txt",
        help="测试文件扩展名（例如 .txt/.bin），默认 .txt",
    )
    parser.add_argument(
        "--no-remote-check",
        action="store_true",
        help="仅检查本地文件被删除（不检查远端存在）",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_config(args.config)

    local_dir = cfg["local_settings"]["media_path"].rstrip("/")
    ssh_target = resolve_ssh_target(cfg)

    # 计算等待上限（分钟）
    if args.wait_minutes is None:
        wait_minutes = int(cfg["sync_settings"].get("interval_minutes", 10)) + 2
    else:
        wait_minutes = args.wait_minutes

    filename = generate_test_filename(prefix=args.prefix, ext=args.ext)
    local_path = write_local_file(local_dir, filename, size_bytes=args.size_bytes)
    remote_path = expected_remote_path(cfg, filename)

    print("==== Smoke Test (media-sync-daemon) ====")
    print(f"Local media dir: {local_dir}")
    print(f"Local file     : {local_path}")
    print(f"SSH target     : {ssh_target}")
    if not args.no_remote_check:
        print(f"Expected remote: {remote_path}")
    print(f"Wait minutes   : {wait_minutes} (poll every {args.poll_interval}s)\n")

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
            print("\nSUCCESS: Daemon appears to be working as expected.")
            return 0

        time.sleep(args.poll_interval)

    print("\nTIMEOUT: Did not observe expected transfer within the allotted time.")
    print("Hints:")
    print("- 确认 systemd 服务已运行：sudo systemctl status media-sync-daemon (仅提示，不在本脚本中执行)")
    print("- 查看日志：journalctl -u media-sync-daemon --since '30 min ago' -n 200")
    print("- 也可手动触发一次：python celestial_nasops/sync_scheduler.py --once")
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nAborted by user.")
        sys.exit(130)