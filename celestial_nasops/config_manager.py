#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一配置管理器

功能：
1. 统一管理所有配置文件
2. 提供配置项的类型安全访问
3. 支持配置验证和默认值
4. 支持配置热重载

作者: Celestial
日期: 2025-01-02
"""

import os
import json
import logging
from typing import Dict, Any, Optional, Union
from pathlib import Path

class ConfigManager:
    """统一配置管理器"""
    
    _instance = None
    _config_cache = None
    
    def __new__(cls, config_file: str = None):
        """单例模式实现"""
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self, config_file: str = None):
        """初始化配置管理器
        
        Args:
            config_file: 配置文件路径，默认使用unified_config.json
        """
        if hasattr(self, '_initialized'):
            return
            
        self._initialized = True
        self.logger = logging.getLogger('ConfigManager')
        
        # 确定配置文件路径
        if config_file is None:
            config_file = os.path.join(
                os.path.dirname(__file__), 
                'unified_config.json'
            )
        
        self.config_file = config_file
        self._load_config()
    
    def _load_config(self) -> None:
        """加载配置文件"""
        try:
            if not os.path.exists(self.config_file):
                self.logger.warning(f"配置文件不存在: {self.config_file}，使用默认配置")
                self._config_cache = self._get_default_config()
                return
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self._config_cache = json.load(f)
            
            self.logger.info(f"配置文件加载成功: {self.config_file}")
            
        except json.JSONDecodeError as e:
            self.logger.error(f"配置文件格式错误: {e}")
            self._config_cache = self._get_default_config()
        except Exception as e:
            self.logger.error(f"加载配置文件失败: {e}")
            self._config_cache = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置
        
        Returns:
            默认配置字典
        """
        return {
            "nas_settings": {
                "host": "192.168.200.103",
                "username": "edge_sync",
                "ssh_alias": "nas-edge",
                "base_path": "/volume1/homes/edge_sync/drone_media",
                "backup_path": "EdgeBackup"
            },
            "local_settings": {
                "media_path": "/data/temp/dji/media/",
                "temp_path": "/tmp/media",
                "log_path": "/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/logs"
            },
            "sync_settings": {
                "interval_minutes": 10,
                "max_retry_attempts": 3,
                "retry_delay_seconds": 5,
                "enable_checksum": True,
                "delete_after_sync": True,
                "safe_delete_delay_minutes": 30
            },
            "logging": {
                "level": "INFO",
                "log_file": "/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/logs/media_sync.log",
                "max_file_size_mb": 10,
                "backup_count": 5
            }
        }
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """获取配置项
        
        Args:
            key_path: 配置项路径，使用点号分隔，如 'nas_settings.host'
            default: 默认值
            
        Returns:
            配置项值
        """
        if self._config_cache is None:
            self._load_config()
        
        keys = key_path.split('.')
        value = self._config_cache
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            self.logger.warning(f"配置项不存在: {key_path}，使用默认值: {default}")
            return default
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """获取配置段
        
        Args:
            section: 配置段名称
            
        Returns:
            配置段字典
        """
        return self.get(section, {})
    
    def set(self, key_path: str, value: Any) -> None:
        """设置配置项
        
        Args:
            key_path: 配置项路径
            value: 配置项值
        """
        if self._config_cache is None:
            self._load_config()
        
        keys = key_path.split('.')
        config = self._config_cache
        
        # 导航到目标位置
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        # 设置值
        config[keys[-1]] = value
        self.logger.info(f"配置项已更新: {key_path} = {value}")
    
    def save(self) -> bool:
        """保存配置到文件
        
        Returns:
            是否保存成功
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config_cache, f, indent=2, ensure_ascii=False)
            
            self.logger.info(f"配置已保存到: {self.config_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存配置失败: {e}")
            return False
    
    def reload(self) -> None:
        """重新加载配置文件"""
        self.logger.info("重新加载配置文件")
        self._config_cache = None
        self._load_config()
    
    def validate_config(self) -> bool:
        """验证配置文件完整性
        
        Returns:
            配置是否有效
        """
        required_sections = [
            'nas_settings',
            'local_settings', 
            'sync_settings',
            'logging'
        ]
        
        for section in required_sections:
            if not self.get_section(section):
                self.logger.error(f"缺少必需的配置段: {section}")
                return False
        
        # 验证关键配置项
        nas_host = self.get('nas_settings.host')
        if not nas_host:
            self.logger.error("NAS主机地址未配置")
            return False
        
        local_media_path = self.get('local_settings.media_path')
        if not local_media_path:
            self.logger.error("本地媒体路径未配置")
            return False
        
        self.logger.info("配置验证通过")
        return True
    
    def get_nas_config(self) -> Dict[str, Any]:
        """获取NAS配置
        
        Returns:
            NAS配置字典
        """
        return self.get_section('nas_settings')
    
    def get_sync_config(self) -> Dict[str, Any]:
        """获取同步配置
        
        Returns:
            同步配置字典
        """
        return self.get_section('sync_settings')
    
    def get_storage_config(self) -> Dict[str, Any]:
        """获取存储管理配置
        
        Returns:
            存储管理配置字典
        """
        return self.get_section('storage_management')
    
    def get_logging_config(self) -> Dict[str, Any]:
        """获取日志配置
        
        Returns:
            日志配置字典
        """
        return self.get_section('logging')
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"ConfigManager(config_file={self.config_file})"
    
    def __repr__(self) -> str:
        """对象表示"""
        return self.__str__()


# 全局配置管理器实例
config_manager = ConfigManager()


def get_config() -> ConfigManager:
    """获取全局配置管理器实例
    
    Returns:
        配置管理器实例
    """
    return config_manager


if __name__ == '__main__':
    # 测试配置管理器
    logging.basicConfig(level=logging.INFO)
    
    config = ConfigManager()
    
    # 测试配置验证
    if config.validate_config():
        print("✓ 配置验证通过")
    else:
        print("✗ 配置验证失败")
    
    # 测试配置访问
    print(f"NAS主机: {config.get('nas_settings.host')}")
    print(f"同步间隔: {config.get('sync_settings.interval_minutes')}分钟")
    print(f"日志级别: {config.get('logging.level')}")
    
    # 测试配置段访问
    nas_config = config.get_nas_config()
    print(f"NAS配置: {nas_config}")