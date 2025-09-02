#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
DJI Edge SDK 数据库维护和查询工具
作者: Celestial
创建时间: 2025-01-22
描述: 提供数据库维护、查询、备份和恢复功能

功能:
- 数据库完整性检查和修复
- 数据库优化和清理
- 数据查询和统计
- 数据库备份和恢复
- 数据导出和导入
- 性能分析和监控
"""

import os
import sys
import sqlite3
import json
import shutil
import gzip
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from contextlib import contextmanager

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root / 'celestial_nasops'))

try:
    from config_manager import ConfigManager
except ImportError:
    print("警告: 无法导入ConfigManager，将使用默认配置")
    ConfigManager = None

class DatabaseMaintenance:
    """数据库维护类"""
    
    def __init__(self, db_path: Optional[str] = None, config_path: Optional[str] = None):
        """初始化数据库维护工具
        
        Args:
            db_path: 数据库文件路径
            config_path: 配置文件路径
        """
        self.project_root = project_root
        self.db_path = db_path or str(project_root / 'celestial_works' / 'media_status.db')
        self.config_path = config_path or str(project_root / 'celestial_nasops' / 'unified_config.json')
        
        # 备份目录
        self.backup_dir = project_root / 'celestial_works' / 'backups'
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # 设置日志
        self._setup_logging()
        
        # 加载配置
        self.config = self._load_config()
        
        self.logger.info(f"数据库维护工具初始化完成，数据库路径: {self.db_path}")
    
    def _load_config(self) -> Dict:
        """加载配置文件"""
        try:
            if ConfigManager and os.path.exists(self.config_path):
                config_manager = ConfigManager(self.config_path)
                return config_manager.config
            else:
                return {}
        except Exception as e:
            self.logger.warning(f"加载配置失败: {e}，使用默认配置")
            return {}
    
    def _setup_logging(self):
        """设置日志记录"""
        log_dir = self.project_root / 'celestial_works' / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / 'db_maintenance.log'
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger('DatabaseMaintenance')
    
    @contextmanager
    def get_connection(self, timeout: int = 30):
        """获取数据库连接的上下文管理器
        
        Args:
            timeout: 连接超时时间（秒）
            
        Yields:
            sqlite3.Connection: 数据库连接对象
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=timeout)
            conn.row_factory = sqlite3.Row  # 使结果可以按列名访问
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()
    
    def check_database_integrity(self) -> Dict:
        """检查数据库完整性
        
        Returns:
            完整性检查结果字典
        """
        self.logger.info("开始数据库完整性检查")
        
        result = {
            'integrity_check': False,
            'foreign_key_check': False,
            'quick_check': False,
            'errors': [],
            'warnings': []
        }
        
        if not os.path.exists(self.db_path):
            result['errors'].append(f"数据库文件不存在: {self.db_path}")
            return result
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 完整性检查
                cursor.execute("PRAGMA integrity_check")
                integrity_results = cursor.fetchall()
                
                if len(integrity_results) == 1 and integrity_results[0][0] == 'ok':
                    result['integrity_check'] = True
                    self.logger.info("数据库完整性检查通过")
                else:
                    result['errors'].extend([row[0] for row in integrity_results])
                    self.logger.error(f"数据库完整性检查失败: {integrity_results}")
                
                # 外键检查
                cursor.execute("PRAGMA foreign_key_check")
                fk_results = cursor.fetchall()
                
                if not fk_results:
                    result['foreign_key_check'] = True
                    self.logger.info("外键约束检查通过")
                else:
                    result['errors'].extend([f"外键约束错误: {row}" for row in fk_results])
                    self.logger.error(f"外键约束检查失败: {fk_results}")
                
                # 快速检查
                cursor.execute("PRAGMA quick_check")
                quick_results = cursor.fetchall()
                
                if len(quick_results) == 1 and quick_results[0][0] == 'ok':
                    result['quick_check'] = True
                    self.logger.info("数据库快速检查通过")
                else:
                    result['warnings'].extend([row[0] for row in quick_results])
                    self.logger.warning(f"数据库快速检查发现问题: {quick_results}")
                
        except Exception as e:
            result['errors'].append(f"检查过程中发生错误: {str(e)}")
            self.logger.error(f"数据库完整性检查失败: {e}")
        
        return result
    
    def optimize_database(self) -> Dict:
        """优化数据库
        
        Returns:
            优化结果字典
        """
        self.logger.info("开始数据库优化")
        
        result = {
            'vacuum_success': False,
            'analyze_success': False,
            'reindex_success': False,
            'size_before': 0,
            'size_after': 0,
            'space_saved': 0,
            'errors': []
        }
        
        if not os.path.exists(self.db_path):
            result['errors'].append(f"数据库文件不存在: {self.db_path}")
            return result
        
        try:
            # 记录优化前的大小
            result['size_before'] = os.path.getsize(self.db_path)
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # VACUUM - 重建数据库，回收空间
                try:
                    cursor.execute("VACUUM")
                    result['vacuum_success'] = True
                    self.logger.info("数据库VACUUM操作完成")
                except Exception as e:
                    result['errors'].append(f"VACUUM操作失败: {str(e)}")
                    self.logger.error(f"VACUUM操作失败: {e}")
                
                # ANALYZE - 更新查询优化器统计信息
                try:
                    cursor.execute("ANALYZE")
                    result['analyze_success'] = True
                    self.logger.info("数据库ANALYZE操作完成")
                except Exception as e:
                    result['errors'].append(f"ANALYZE操作失败: {str(e)}")
                    self.logger.error(f"ANALYZE操作失败: {e}")
                
                # REINDEX - 重建索引
                try:
                    cursor.execute("REINDEX")
                    result['reindex_success'] = True
                    self.logger.info("数据库REINDEX操作完成")
                except Exception as e:
                    result['errors'].append(f"REINDEX操作失败: {str(e)}")
                    self.logger.error(f"REINDEX操作失败: {e}")
            
            # 记录优化后的大小
            result['size_after'] = os.path.getsize(self.db_path)
            result['space_saved'] = result['size_before'] - result['size_after']
            
            self.logger.info(f"数据库优化完成，节省空间: {result['space_saved']} 字节")
            
        except Exception as e:
            result['errors'].append(f"优化过程中发生错误: {str(e)}")
            self.logger.error(f"数据库优化失败: {e}")
        
        return result
    
    def backup_database(self, backup_name: Optional[str] = None, compress: bool = True) -> Dict:
        """备份数据库
        
        Args:
            backup_name: 备份文件名，默认使用时间戳
            compress: 是否压缩备份文件
            
        Returns:
            备份结果字典
        """
        if backup_name is None:
            backup_name = f"media_status_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        
        if compress and not backup_name.endswith('.gz'):
            backup_name += '.gz'
        
        backup_path = self.backup_dir / backup_name
        
        self.logger.info(f"开始备份数据库到: {backup_path}")
        
        result = {
            'success': False,
            'backup_path': str(backup_path),
            'backup_size': 0,
            'original_size': 0,
            'compression_ratio': 0,
            'error': None
        }
        
        if not os.path.exists(self.db_path):
            result['error'] = f"数据库文件不存在: {self.db_path}"
            return result
        
        try:
            result['original_size'] = os.path.getsize(self.db_path)
            
            if compress:
                # 压缩备份
                with open(self.db_path, 'rb') as f_in:
                    with gzip.open(backup_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
            else:
                # 直接复制
                shutil.copy2(self.db_path, backup_path)
            
            result['backup_size'] = os.path.getsize(backup_path)
            
            if compress and result['original_size'] > 0:
                result['compression_ratio'] = (1 - result['backup_size'] / result['original_size']) * 100
            
            result['success'] = True
            self.logger.info(f"数据库备份完成: {backup_path}")
            
        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"数据库备份失败: {e}")
        
        return result
    
    def get_database_statistics(self) -> Dict:
        """获取数据库统计信息
        
        Returns:
            数据库统计信息字典
        """
        self.logger.info("获取数据库统计信息")
        
        stats = {
            'file_exists': False,
            'file_size': 0,
            'page_count': 0,
            'page_size': 0,
            'tables': {},
            'indexes': {},
            'total_records': 0,
            'last_modified': None,
            'schema_version': None
        }
        
        if not os.path.exists(self.db_path):
            return stats
        
        try:
            stats['file_exists'] = True
            stats['file_size'] = os.path.getsize(self.db_path)
            stats['last_modified'] = datetime.fromtimestamp(
                os.path.getmtime(self.db_path)
            ).isoformat()
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 获取页面信息
                cursor.execute("PRAGMA page_count")
                stats['page_count'] = cursor.fetchone()[0]
                
                cursor.execute("PRAGMA page_size")
                stats['page_size'] = cursor.fetchone()[0]
                
                # 获取模式版本
                cursor.execute("PRAGMA schema_version")
                stats['schema_version'] = cursor.fetchone()[0]
                
                # 获取表信息
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                )
                tables = cursor.fetchall()
                
                for table in tables:
                    table_name = table[0]
                    
                    # 获取表记录数
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    record_count = cursor.fetchone()[0]
                    stats['tables'][table_name] = {
                        'record_count': record_count
                    }
                    stats['total_records'] += record_count
                    
                    # 获取表结构信息
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = cursor.fetchall()
                    stats['tables'][table_name]['columns'] = [
                        {
                            'name': col[1],
                            'type': col[2],
                            'not_null': bool(col[3]),
                            'default_value': col[4],
                            'primary_key': bool(col[5])
                        }
                        for col in columns
                    ]
                
                # 获取索引信息
                cursor.execute(
                    "SELECT name, tbl_name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
                )
                indexes = cursor.fetchall()
                
                for index in indexes:
                    index_name, table_name = index
                    cursor.execute(f"PRAGMA index_info({index_name})")
                    index_info = cursor.fetchall()
                    
                    stats['indexes'][index_name] = {
                        'table': table_name,
                        'columns': [info[2] for info in index_info]
                    }
            
            self.logger.info(f"数据库统计信息获取完成，总记录数: {stats['total_records']}")
            
        except Exception as e:
            self.logger.error(f"获取数据库统计信息失败: {e}")
        
        return stats
    
    def query_media_files(self, limit: int = 100, offset: int = 0, 
                         status_filter: Optional[str] = None,
                         date_from: Optional[str] = None,
                         date_to: Optional[str] = None) -> Dict:
        """查询媒体文件记录
        
        Args:
            limit: 返回记录数限制
            offset: 偏移量
            status_filter: 状态过滤器
            date_from: 开始日期 (YYYY-MM-DD)
            date_to: 结束日期 (YYYY-MM-DD)
            
        Returns:
            查询结果字典
        """
        result = {
            'success': False,
            'records': [],
            'total_count': 0,
            'error': None
        }
        
        if not os.path.exists(self.db_path):
            result['error'] = f"数据库文件不存在: {self.db_path}"
            return result
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # 构建查询条件
                where_conditions = []
                params = []
                
                if status_filter:
                    where_conditions.append("status = ?")
                    params.append(status_filter)
                
                if date_from:
                    where_conditions.append("created_time >= ?")
                    params.append(date_from)
                
                if date_to:
                    where_conditions.append("created_time <= ?")
                    params.append(date_to + ' 23:59:59')
                
                where_clause = ""
                if where_conditions:
                    where_clause = "WHERE " + " AND ".join(where_conditions)
                
                # 获取总记录数
                count_query = f"SELECT COUNT(*) FROM media_files {where_clause}"
                cursor.execute(count_query, params)
                result['total_count'] = cursor.fetchone()[0]
                
                # 获取记录
                query = f"""
                    SELECT * FROM media_files 
                    {where_clause}
                    ORDER BY created_time DESC 
                    LIMIT ? OFFSET ?
                """
                
                cursor.execute(query, params + [limit, offset])
                rows = cursor.fetchall()
                
                result['records'] = [
                    dict(row) for row in rows
                ]
                
                result['success'] = True
                self.logger.info(f"查询媒体文件记录完成，返回 {len(result['records'])} 条记录")
                
        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"查询媒体文件记录失败: {e}")
        
        return result

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='DJI Edge SDK 数据库维护工具')
    parser.add_argument('--db-path', help='数据库文件路径')
    parser.add_argument('--config', help='配置文件路径')
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 完整性检查
    subparsers.add_parser('check', help='检查数据库完整性')
    
    # 优化数据库
    subparsers.add_parser('optimize', help='优化数据库')
    
    # 备份数据库
    backup_parser = subparsers.add_parser('backup', help='备份数据库')
    backup_parser.add_argument('--name', help='备份文件名')
    backup_parser.add_argument('--no-compress', action='store_true', help='不压缩备份文件')
    
    # 统计信息
    subparsers.add_parser('stats', help='显示数据库统计信息')
    
    # 查询数据
    query_parser = subparsers.add_parser('query', help='查询媒体文件')
    query_parser.add_argument('--limit', type=int, default=10, help='返回记录数限制')
    query_parser.add_argument('--offset', type=int, default=0, help='偏移量')
    query_parser.add_argument('--status', help='状态过滤器')
    query_parser.add_argument('--date-from', help='开始日期 (YYYY-MM-DD)')
    query_parser.add_argument('--date-to', help='结束日期 (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 创建维护工具实例
    db_tool = DatabaseMaintenance(db_path=args.db_path, config_path=args.config)
    
    # 执行相应命令
    if args.command == 'check':
        result = db_tool.check_database_integrity()
        print("\n=== 数据库完整性检查结果 ===")
        print(f"完整性检查: {'✓ 通过' if result['integrity_check'] else '✗ 失败'}")
        print(f"外键检查: {'✓ 通过' if result['foreign_key_check'] else '✗ 失败'}")
        print(f"快速检查: {'✓ 通过' if result['quick_check'] else '✗ 失败'}")
        
        if result['errors']:
            print("\n错误:")
            for error in result['errors']:
                print(f"  - {error}")
        
        if result['warnings']:
            print("\n警告:")
            for warning in result['warnings']:
                print(f"  - {warning}")
    
    elif args.command == 'optimize':
        result = db_tool.optimize_database()
        print("\n=== 数据库优化结果 ===")
        print(f"VACUUM: {'✓ 成功' if result['vacuum_success'] else '✗ 失败'}")
        print(f"ANALYZE: {'✓ 成功' if result['analyze_success'] else '✗ 失败'}")
        print(f"REINDEX: {'✓ 成功' if result['reindex_success'] else '✗ 失败'}")
        print(f"优化前大小: {result['size_before']} 字节")
        print(f"优化后大小: {result['size_after']} 字节")
        print(f"节省空间: {result['space_saved']} 字节")
        
        if result['errors']:
            print("\n错误:")
            for error in result['errors']:
                print(f"  - {error}")
    
    elif args.command == 'backup':
        result = db_tool.backup_database(
            backup_name=args.name,
            compress=not args.no_compress
        )
        print("\n=== 数据库备份结果 ===")
        print(f"备份状态: {'✓ 成功' if result['success'] else '✗ 失败'}")
        print(f"备份文件: {result['backup_path']}")
        print(f"原始大小: {result['original_size']} 字节")
        print(f"备份大小: {result['backup_size']} 字节")
        if result['compression_ratio'] > 0:
            print(f"压缩率: {result['compression_ratio']:.1f}%")
        
        if result['error']:
            print(f"错误: {result['error']}")
    
    elif args.command == 'stats':
        stats = db_tool.get_database_statistics()
        print("\n=== 数据库统计信息 ===")
        print(f"文件存在: {'✓ 是' if stats['file_exists'] else '✗ 否'}")
        print(f"文件大小: {stats['file_size']} 字节")
        print(f"页面数量: {stats['page_count']}")
        print(f"页面大小: {stats['page_size']} 字节")
        print(f"总记录数: {stats['total_records']}")
        print(f"最后修改: {stats['last_modified']}")
        
        if stats['tables']:
            print("\n表信息:")
            for table_name, table_info in stats['tables'].items():
                print(f"  {table_name}: {table_info['record_count']} 条记录")
        
        if stats['indexes']:
            print("\n索引信息:")
            for index_name, index_info in stats['indexes'].items():
                print(f"  {index_name}: {index_info['table']} ({', '.join(index_info['columns'])})")
    
    elif args.command == 'query':
        result = db_tool.query_media_files(
            limit=args.limit,
            offset=args.offset,
            status_filter=args.status,
            date_from=args.date_from,
            date_to=args.date_to
        )
        
        if result['success']:
            print(f"\n=== 查询结果 (总计: {result['total_count']} 条) ===")
            for i, record in enumerate(result['records'], 1):
                print(f"\n{i}. 文件: {record.get('file_path', 'N/A')}")
                print(f"   状态: {record.get('status', 'N/A')}")
                print(f"   创建时间: {record.get('created_time', 'N/A')}")
                print(f"   大小: {record.get('file_size', 'N/A')} 字节")
        else:
            print(f"查询失败: {result['error']}")

if __name__ == '__main__':
    main()