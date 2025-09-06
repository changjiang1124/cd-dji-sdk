#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
空间管理服务（NAS 侧）

职责：
- 周期性检查 NAS 存储使用率（通过 SSH 使用 df）
- 达到阈值时按规则在 NAS 上执行安全批量清理（由 StorageManager 执行）
- 将状态与结果写入日志与状态文件，必要时邮件通知

使用方法：
- 单次检查：
  python3 celestial_nasops/space_manager.py --run-once
- 循环运行（按配置 storage_management.check_interval_minutes）：
  python3 celestial_nasops/space_manager.py --loop
- 指定间隔（分钟）：
  python3 celestial_nasops/space_manager.py --loop --interval 30
- 强制清理（忽略当前使用率，直接按规则执行清理）：
  python3 celestial_nasops/space_manager.py --run-once --force-cleanup

说明：
- 日志文件默认写入 local_settings.log_path/space_manager.log
- 日志轮转请在项目根目录 logrotate.user.conf 中添加条目，并执行 ./sync_logrotate.sh

作者: Celestial
日期: 2025-09-06
"""

import os
import sys
import time
import json
import logging
import argparse
from datetime import datetime
from typing import Optional, Dict

# 本地模块
from config_manager import ConfigManager
from storage_manager import StorageManager

# 邮件通知器（可能为 None，需判空处理）
try:
    from email_notifier import email_notifier
except Exception:
    email_notifier = None


def setup_logger(cfg: ConfigManager) -> logging.Logger:
    """初始化日志
    
    优先使用 unified_config.json 中的 logging.format/level 和 local_settings.log_path。
    日志文件固定命名为 space_manager.log。
    """
    logger = logging.getLogger("SpaceManager")
    logger.setLevel(getattr(logging, str(cfg.get('logging.level', 'INFO')).upper(), logging.INFO))

    # 日志目录与文件
    log_dir = cfg.get('local_settings.log_path', os.path.join(os.path.dirname(__file__), 'logs'))
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'space_manager.log')

    # 日志格式
    log_format = cfg.get('logging.format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    formatter = logging.Formatter(log_format)

    # 文件 Handler
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logger.level)
    fh.setFormatter(formatter)

    # 控制台 Handler（便于命令行运行时观察）
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logger.level)
    ch.setFormatter(formatter)

    # 避免重复添加 handler
    if not logger.handlers:
        logger.addHandler(fh)
        logger.addHandler(ch)

    logger.propagate = False
    logger.info("SpaceManager 日志初始化完成: %s", log_file)
    return logger


class SpaceManagerService:
    """空间管理服务封装
    
    封装一次性检查与循环运行逻辑，复用 StorageManager 的能力。
    """
    def __init__(self, cfg: Optional[ConfigManager] = None, logger: Optional[logging.Logger] = None):
        self.cfg = cfg or ConfigManager()
        self.logger = logger or setup_logger(self.cfg)
        # StorageManager 仅接受配置文件路径，传入 unified_config.json 的绝对路径
        config_path = os.path.join(os.path.dirname(__file__), 'unified_config.json')
        self.storage = StorageManager(config_file=config_path)

        sm_cfg = self.cfg.get_storage_config() or {}
        self.enable_auto_cleanup = bool(sm_cfg.get('enable_auto_cleanup', True))
        self.check_interval_minutes = int(sm_cfg.get('check_interval_minutes', 60))

    def _notify(self, level: str, subject: str, message: str, details: Optional[str] = None) -> None:
        """发送通知（如果已配置邮件）"""
        if email_notifier is None:
            self.logger.debug("EmailNotifier 未初始化，跳过邮件通知: %s - %s", subject, message)
            return
        try:
            if level == 'success':
                email_notifier.send_success(subject, message, details)
            elif level == 'warning':
                email_notifier.send_warning(subject, message, details)
            elif level == 'error':
                email_notifier.send_error(subject, message, details)
            else:
                email_notifier.send_info(subject, message, details)
        except Exception as e:
            self.logger.error("发送邮件通知失败: %s", e)

    def run_once(self, force_cleanup: bool = False) -> Dict:
        """执行一次检查/清理
        
        返回：结果字典，含状态与摘要。
        """
        self.logger.info("开始一次存储空间检查：force_cleanup=%s", force_cleanup)

        try:
            if force_cleanup:
                result = self.storage.cleanup_storage(force=True)
                msg = f"强制清理完成: 删除{result.get('details', {}).get('total_deleted', 0)}个，失败{result.get('details', {}).get('total_failed', 0)}个"
                self.logger.info(msg)
                # 强制清理后，不根据使用率发通知，仅记录结果
                return {"success": True, "message": msg, "result": result}

            # 读取当前状态
            status = self.storage.check_storage_status()
            st = status.get('status', 'error')
            usage = status.get('storage_info', {}).get('usage_percent')
            self.logger.info("当前存储状态: %s，使用率: %s%%", st, f"{usage:.1f}" if isinstance(usage, (int, float)) else "未知")

            if st == 'error':
                self._notify('error', 'NAS 存储状态检查失败', status.get('message', '未知错误'), json.dumps(status, ensure_ascii=False))
                return {"success": False, "message": "状态检查失败", "status": status}

            # 根据状态决定是否清理
            if st in ('warning', 'critical'):
                if self.enable_auto_cleanup:
                    self.logger.info("达到阈值，开始自动清理（目标使用率 %s%%）", self.storage.cleanup_target_percent)
                    result = self.storage.auto_cleanup()
                    if result.get('success'):
                        details = json.dumps(result.get('details', {}), ensure_ascii=False, indent=2)
                        level = 'warning' if st == 'warning' else 'error'
                        subj = 'NAS 存储空间自动清理完成'
                        msg = f"初始使用率 {result['details'].get('initial_usage', '未知')}%，清理后 {result['details'].get('final_usage', '未知')}%，目标 {result['details'].get('target_usage', '未知')}%"
                        self._notify(level, subj, msg, details)
                        return {"success": True, "message": msg, "result": result}
                    else:
                        self._notify('error', 'NAS 自动清理失败', result.get('message', '清理失败'), json.dumps(result, ensure_ascii=False))
                        return {"success": False, "message": "自动清理失败", "result": result}
                else:
                    self.logger.warning("达到阈值但已关闭自动清理，建议人工执行清理")
                    self._notify('warning', 'NAS 存储空间接近/超过阈值', status.get('message', ''), json.dumps(status, ensure_ascii=False))
                    return {"success": True, "message": "达到阈值，已通知但未清理", "status": status}

            # 正常状态
            self.logger.info("存储空间正常，无需清理")
            return {"success": True, "message": "存储空间正常，无需清理", "status": status}

        except Exception as e:
            self.logger.exception("运行一次检查时发生异常: %s", e)
            self._notify('error', 'SpaceManager 异常', '执行 run_once 发生异常', str(e))
            return {"success": False, "message": str(e)}

    def run_loop(self, interval_minutes: Optional[int] = None) -> None:
        """按固定间隔循环运行"""
        interval = int(interval_minutes or self.check_interval_minutes)
        self.logger.info("进入循环运行模式，间隔 %s 分钟", interval)
        try:
            while True:
                self.run_once(force_cleanup=False)
                time.sleep(interval * 60)
        except KeyboardInterrupt:
            self.logger.info("收到中断信号，退出循环运行模式")
        except Exception as e:
            self.logger.exception("循环运行异常: %s", e)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='NAS 空间管理服务')
    parser.add_argument('--run-once', action='store_true', help='执行一次检查后退出')
    parser.add_argument('--loop', action='store_true', help='按间隔循环运行')
    parser.add_argument('--interval', type=int, default=None, help='循环运行的间隔（分钟）')
    parser.add_argument('--force-cleanup', action='store_true', help='强制执行清理（忽略阈值）')
    return parser.parse_args()


def main():
    # 加载配置并初始化服务
    cfg = ConfigManager()
    logger = setup_logger(cfg)
    svc = SpaceManagerService(cfg, logger)

    args = parse_args()

    if args.run_once:
        svc.run_once(force_cleanup=args.force_cleanup)
    elif args.loop:
        svc.run_loop(interval_minutes=args.interval)
    else:
        # 默认单次运行
        svc.run_once(force_cleanup=args.force_cleanup)


if __name__ == '__main__':
    main()