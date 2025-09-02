#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NAS存储管理器

功能：
1. 监控NAS存储空间使用情况
2. 自动清理旧文件以释放空间
3. 提供存储空间预警机制
4. 支持按文件类型和时间进行清理策略

作者: Celestial
日期: 2024-01-22
"""

import os
import sys
import json
import time
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

@dataclass
class StorageInfo:
    """存储空间信息"""
    total_space: int  # 总空间（字节）
    used_space: int   # 已用空间（字节）
    free_space: int   # 可用空间（字节）
    usage_percent: float  # 使用率（百分比）
    timestamp: str    # 检查时间戳

@dataclass
class CleanupRule:
    """清理规则"""
    path_pattern: str     # 路径模式
    file_extension: str   # 文件扩展名
    max_age_days: int     # 最大保留天数
    priority: int         # 清理优先级（数字越小优先级越高）
    enabled: bool = True  # 是否启用

class StorageManager:
    """NAS存储管理器"""
    
    def __init__(self, config_file: str = "config.json"):
        """初始化存储管理器
        
        Args:
            config_file: 配置文件路径
        """
        # 首先设置日志
        self.logger = logging.getLogger('StorageManager')
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        self.config_file = config_file
        self.config = self._load_config()
        
        # NAS连接配置
        nas_settings = self.config.get('nas_settings', {})
        self.nas_host = nas_settings.get('host', '192.168.200.103')
        self.nas_user = nas_settings.get('username', 'edge_sync')
        # 使用 unified_config.json 中的 ssh_alias；若未配置则回退为 username@host
        self.nas_alias = nas_settings.get('ssh_alias') or f"{self.nas_user}@{self.nas_host}"
        self.nas_base_path = nas_settings.get('base_path', '/volume1/drone_media')
        
        # 存储管理配置
        storage_config = self.config.get('storage_management', {})
        self.warning_threshold = storage_config.get('warning_threshold_percent', 80)
        self.critical_threshold = storage_config.get('critical_threshold_percent', 90)
        self.cleanup_target_percent = storage_config.get('cleanup_target_percent', 70)
        self.check_interval_minutes = storage_config.get('check_interval_minutes', 60)
        
        # 清理规则
        self.cleanup_rules = self._load_cleanup_rules()
        
        # 状态文件
        self.status_file = storage_config.get('status_file', 'storage_status.json')
        
        self.logger.info(f"StorageManager初始化完成 - NAS: {self.nas_host}")
    
    def _load_config(self) -> Dict:
        """加载配置文件
        
        Returns:
            配置字典
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                self.logger.warning(f"配置文件不存在: {self.config_file}，使用默认配置")
                return self._get_default_config()
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """获取默认配置
        
        Returns:
            默认配置字典
        """
        return {
            "nas": {
                "host": "192.168.200.103",
                "username": "edge_sync",
                "base_path": "/volume1/drone_media"
            },
            "storage_management": {
                "warning_threshold_percent": 80,
                "critical_threshold_percent": 90,
                "cleanup_target_percent": 70,
                "check_interval_minutes": 60,
                "status_file": "storage_status.json"
            }
        }
    
    def _load_cleanup_rules(self) -> List[CleanupRule]:
        """加载清理规则
        
        Returns:
            清理规则列表
        """
        rules_config = self.config.get('storage_management', {}).get('cleanup_rules', [])
        
        # 如果配置中没有规则，使用默认规则
        if not rules_config:
            rules_config = self._get_default_cleanup_rules()
        
        rules = []
        for rule_data in rules_config:
            try:
                rule = CleanupRule(**rule_data)
                rules.append(rule)
            except Exception as e:
                self.logger.error(f"加载清理规则失败: {e}")
        
        # 按优先级排序
        rules.sort(key=lambda x: x.priority)
        
        self.logger.info(f"加载了 {len(rules)} 个清理规则")
        return rules
    
    def _get_default_cleanup_rules(self) -> List[Dict]:
        """获取默认清理规则
        
        Returns:
            默认清理规则列表
        """
        return [
            {
                "path_pattern": "*/logs/*",
                "file_extension": ".log",
                "max_age_days": 7,
                "priority": 1,
                "enabled": True
            },
            {
                "path_pattern": "*/temp/*",
                "file_extension": "*",
                "max_age_days": 1,
                "priority": 2,
                "enabled": True
            },
            {
                "path_pattern": "*/media/*",
                "file_extension": ".jpg",
                "max_age_days": 30,
                "priority": 3,
                "enabled": True
            },
            {
                "path_pattern": "*/media/*",
                "file_extension": ".mp4",
                "max_age_days": 60,
                "priority": 4,
                "enabled": True
            }
        ]
    
    def get_storage_info(self) -> Optional[StorageInfo]:
        """获取NAS存储空间信息
        
        Returns:
            存储空间信息，失败时返回None
        """
        try:
            # 使用SSH执行df命令获取存储空间信息
            cmd = f"ssh {self.nas_alias} 'df -B1 {self.nas_base_path}'"
            
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                self.logger.error(f"获取存储信息失败: {result.stderr}")
                return None
            
            # 解析df命令输出
            lines = result.stdout.strip().split('\n')
            if len(lines) < 2:
                self.logger.error("df命令输出格式异常")
                return None
            
            # 解析第二行数据（第一行是标题）
            data_line = lines[1].split()
            if len(data_line) < 4:
                self.logger.error("df命令数据格式异常")
                return None
            
            total_space = int(data_line[1])  # 总空间
            used_space = int(data_line[2])   # 已用空间
            free_space = int(data_line[3])   # 可用空间
            
            usage_percent = (used_space / total_space) * 100 if total_space > 0 else 0
            
            storage_info = StorageInfo(
                total_space=total_space,
                used_space=used_space,
                free_space=free_space,
                usage_percent=usage_percent,
                timestamp=datetime.now().isoformat()
            )
            
            self.logger.debug(f"存储信息: 总计{self._format_size(total_space)}, "
                            f"已用{self._format_size(used_space)}, "
                            f"可用{self._format_size(free_space)}, "
                            f"使用率{usage_percent:.1f}%")
            
            return storage_info
            
        except subprocess.TimeoutExpired:
            self.logger.error("获取存储信息超时")
            return None
        except Exception as e:
            self.logger.error(f"获取存储信息异常: {e}")
            return None
    
    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小
        
        Args:
            size_bytes: 字节数
            
        Returns:
            格式化后的大小字符串
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f}{unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f}PB"
    
    def check_storage_status(self) -> Dict:
        """检查存储状态
        
        Returns:
            存储状态字典
        """
        storage_info = self.get_storage_info()
        
        if not storage_info:
            return {
                "status": "error",
                "message": "无法获取存储信息",
                "timestamp": datetime.now().isoformat()
            }
        
        # 判断存储状态
        if storage_info.usage_percent >= self.critical_threshold:
            status = "critical"
            message = f"存储空间严重不足！使用率{storage_info.usage_percent:.1f}%"
        elif storage_info.usage_percent >= self.warning_threshold:
            status = "warning"
            message = f"存储空间不足，使用率{storage_info.usage_percent:.1f}%"
        else:
            status = "normal"
            message = f"存储空间正常，使用率{storage_info.usage_percent:.1f}%"
        
        status_data = {
            "status": status,
            "message": message,
            "storage_info": asdict(storage_info),
            "thresholds": {
                "warning": self.warning_threshold,
                "critical": self.critical_threshold,
                "cleanup_target": self.cleanup_target_percent
            },
            "timestamp": datetime.now().isoformat()
        }
        
        # 保存状态到文件
        self._save_status(status_data)
        
        return status_data
    
    def _save_status(self, status_data: Dict):
        """保存状态到文件
        
        Args:
            status_data: 状态数据
        """
        try:
            with open(self.status_file, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"保存状态文件失败: {e}")
    
    def find_files_to_cleanup(self, rule: CleanupRule) -> List[str]:
        """根据规则查找需要清理的文件
        
        Args:
            rule: 清理规则
            
        Returns:
            需要清理的文件路径列表
        """
        try:
            # 计算截止日期
            cutoff_date = datetime.now() - timedelta(days=rule.max_age_days)
            cutoff_timestamp = int(cutoff_date.timestamp())
            
            # 构建查找命令
            search_path = os.path.join(self.nas_base_path, rule.path_pattern.lstrip('*/'))
            
            if rule.file_extension == "*":
                find_cmd = f"find {search_path} -type f -not -newermt @{cutoff_timestamp}"
            else:
                find_cmd = f"find {search_path} -type f -name '*{rule.file_extension}' -not -newermt @{cutoff_timestamp}"
            
            # 通过SSH执行查找命令
            cmd = f"ssh {self.nas_alias} '{find_cmd}'"
            
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                self.logger.error(f"查找文件失败: {result.stderr}")
                return []
            
            # 解析结果
            files = [line.strip() for line in result.stdout.strip().split('\n') if line.strip()]
            
            self.logger.info(f"规则 '{rule.path_pattern}' 找到 {len(files)} 个待清理文件")
            return files
            
        except subprocess.TimeoutExpired:
            self.logger.error(f"查找文件超时: {rule.path_pattern}")
            return []
        except Exception as e:
            self.logger.error(f"查找文件异常: {e}")
            return []
    
    def cleanup_files(self, file_paths: List[str]) -> Tuple[int, int]:
        """清理指定的文件
        
        Args:
            file_paths: 要清理的文件路径列表
            
        Returns:
            (成功删除数量, 失败数量)
        """
        if not file_paths:
            return 0, 0
        
        success_count = 0
        failed_count = 0
        
        # 批量删除文件
        try:
            # 将文件路径写入临时文件
            files_list = '\n'.join(file_paths)
            
            # 使用SSH执行批量删除
            cmd = f"ssh {self.nas_alias} 'xargs rm -f'"
            
            result = subprocess.run(
                cmd,
                input=files_list,
                shell=True,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                success_count = len(file_paths)
                self.logger.info(f"成功删除 {success_count} 个文件")
            else:
                failed_count = len(file_paths)
                self.logger.error(f"批量删除失败: {result.stderr}")
            
        except subprocess.TimeoutExpired:
            failed_count = len(file_paths)
            self.logger.error("批量删除超时")
        except Exception as e:
            failed_count = len(file_paths)
            self.logger.error(f"批量删除异常: {e}")
        
        return success_count, failed_count
    
    def auto_cleanup(self) -> Dict:
        """自动清理存储空间
        
        Returns:
            清理结果字典
        """
        self.logger.info("开始自动清理存储空间")
        
        # 检查当前存储状态
        status = self.check_storage_status()
        
        if status["status"] == "error":
            return {
                "success": False,
                "message": "无法获取存储状态",
                "details": status
            }
        
        storage_info = StorageInfo(**status["storage_info"])
        
        # 如果存储空间充足，不需要清理
        if storage_info.usage_percent < self.warning_threshold:
            return {
                "success": True,
                "message": f"存储空间充足({storage_info.usage_percent:.1f}%)，无需清理",
                "details": {
                    "current_usage": storage_info.usage_percent,
                    "threshold": self.warning_threshold
                }
            }
        
        # 执行清理
        cleanup_results = []
        total_deleted = 0
        total_failed = 0
        
        for rule in self.cleanup_rules:
            if not rule.enabled:
                continue
            
            self.logger.info(f"执行清理规则: {rule.path_pattern} ({rule.file_extension})")
            
            # 查找需要清理的文件
            files_to_cleanup = self.find_files_to_cleanup(rule)
            
            if files_to_cleanup:
                # 执行清理
                success_count, failed_count = self.cleanup_files(files_to_cleanup)
                
                cleanup_results.append({
                    "rule": asdict(rule),
                    "files_found": len(files_to_cleanup),
                    "files_deleted": success_count,
                    "files_failed": failed_count
                })
                
                total_deleted += success_count
                total_failed += failed_count
                
                # 检查是否达到目标使用率
                current_status = self.check_storage_status()
                if current_status["status"] != "error":
                    current_usage = current_status["storage_info"]["usage_percent"]
                    if current_usage <= self.cleanup_target_percent:
                        self.logger.info(f"已达到目标使用率 {self.cleanup_target_percent}%，停止清理")
                        break
        
        # 获取最终状态
        final_status = self.check_storage_status()
        
        return {
            "success": True,
            "message": f"清理完成，删除 {total_deleted} 个文件，失败 {total_failed} 个",
            "details": {
                "total_deleted": total_deleted,
                "total_failed": total_failed,
                "cleanup_results": cleanup_results,
                "initial_usage": storage_info.usage_percent,
                "final_usage": final_status.get("storage_info", {}).get("usage_percent", 0),
                "target_usage": self.cleanup_target_percent
            }
        }
    
    def check_storage_space(self) -> Dict:
        """检查存储空间状态
        
        Returns:
            存储空间检查结果
        """
        return self.check_storage_status()
    
    def cleanup_storage(self, force: bool = False) -> Dict:
        """清理存储空间
        
        Args:
            force: 是否强制清理
            
        Returns:
            清理结果
        """
        if force:
            self.logger.info("强制执行存储清理")
            return self.auto_cleanup()
        else:
            # 检查是否需要清理
            status = self.check_storage_status()
            if status["status"] == "error":
                return {
                    "success": False,
                    "message": "无法获取存储状态",
                    "details": status
                }
            
            storage_info = StorageInfo(**status["storage_info"])
            
            if storage_info.usage_percent >= self.warning_threshold:
                self.logger.info(f"存储使用率 {storage_info.usage_percent:.1f}% 超过警告阈值，开始清理")
                return self.auto_cleanup()
            else:
                return {
                    "success": True,
                    "message": f"存储空间充足({storage_info.usage_percent:.1f}%)，无需清理",
                    "details": {
                        "current_usage": storage_info.usage_percent,
                        "threshold": self.warning_threshold
                    }
                }
    
    def get_status_summary(self) -> Dict:
        """获取存储管理器状态摘要
        
        Returns:
            状态摘要字典
        """
        try:
            # 读取最新状态
            if os.path.exists(self.status_file):
                with open(self.status_file, 'r', encoding='utf-8') as f:
                    latest_status = json.load(f)
            else:
                latest_status = self.check_storage_status()
            
            return {
                "storage_manager_enabled": True,
                "nas_host": self.nas_host,
                "nas_path": self.nas_base_path,
                "latest_status": latest_status,
                "thresholds": {
                    "warning_percent": self.warning_threshold,
                    "critical_percent": self.critical_threshold,
                    "cleanup_target_percent": self.cleanup_target_percent
                },
                "cleanup_rules_count": len([r for r in self.cleanup_rules if r.enabled]),
                "check_interval_minutes": self.check_interval_minutes
            }
            
        except Exception as e:
            self.logger.error(f"获取状态摘要失败: {e}")
            return {
                "storage_manager_enabled": False,
                "error": str(e)
            }

def main():
    """主函数 - 用于测试"""
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # 创建存储管理器
        storage_manager = StorageManager()
        
        print("=== NAS存储管理器测试 ===")
        
        # 获取存储信息
        print("\n1. 获取存储信息:")
        storage_info = storage_manager.get_storage_info()
        if storage_info:
            print(f"总空间: {storage_manager._format_size(storage_info.total_space)}")
            print(f"已用空间: {storage_manager._format_size(storage_info.used_space)}")
            print(f"可用空间: {storage_manager._format_size(storage_info.free_space)}")
            print(f"使用率: {storage_info.usage_percent:.1f}%")
        else:
            print("获取存储信息失败")
        
        # 检查存储状态
        print("\n2. 检查存储状态:")
        status = storage_manager.check_storage_status()
        print(f"状态: {status['status']}")
        print(f"消息: {status['message']}")
        
        # 获取状态摘要
        print("\n3. 状态摘要:")
        summary = storage_manager.get_status_summary()
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        
        print("\n测试完成！")
        
    except KeyboardInterrupt:
        print("\n用户中断测试")
    except Exception as e:
        print(f"\n测试过程发生异常: {e}")

if __name__ == "__main__":
    main()