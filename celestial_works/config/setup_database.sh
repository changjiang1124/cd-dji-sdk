#!/bin/bash

# DJI Edge SDK 媒体文件状态数据库初始化脚本
# 作者: Celestial
# 创建时间: 2025-01-22
# 描述: 自动创建和初始化SQLite数据库

set -e  # 遇到错误立即退出

# 配置变量
DB_PATH="/data/temp/dji/media_status.db"
SQL_SCRIPT="/home/celestial/dev/esdk-test/Edge-SDK/celestial_works/config/init_media_status_db.sql"
LOG_FILE="/home/celestial/dev/esdk-test/Edge-SDK/celestial_works/logs/database_setup.log"

# 创建日志函数
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 检查必要的目录和文件
check_prerequisites() {
    log_message "检查前置条件..."
    
    # 检查SQLite3是否安装
    if ! command -v sqlite3 &> /dev/null; then
        log_message "错误: sqlite3 未安装，请先安装: sudo apt-get install sqlite3"
        exit 1
    fi
    
    # 检查SQL脚本文件是否存在
    if [ ! -f "$SQL_SCRIPT" ]; then
        log_message "错误: SQL初始化脚本不存在: $SQL_SCRIPT"
        exit 1
    fi
    
    # 创建数据库目录
    DB_DIR=$(dirname "$DB_PATH")
    if [ ! -d "$DB_DIR" ]; then
        log_message "创建数据库目录: $DB_DIR"
        sudo mkdir -p "$DB_DIR"
        sudo chown celestial:celestial "$DB_DIR"
    fi
    
    # 创建日志目录
    LOG_DIR=$(dirname "$LOG_FILE")
    if [ ! -d "$LOG_DIR" ]; then
        log_message "创建日志目录: $LOG_DIR"
        mkdir -p "$LOG_DIR"
    fi
    
    log_message "前置条件检查完成"
}

# 备份现有数据库
backup_existing_db() {
    if [ -f "$DB_PATH" ]; then
        BACKUP_PATH="${DB_PATH}.backup.$(date +%Y%m%d_%H%M%S)"
        log_message "备份现有数据库到: $BACKUP_PATH"
        cp "$DB_PATH" "$BACKUP_PATH"
    fi
}

# 初始化数据库
init_database() {
    log_message "开始初始化数据库: $DB_PATH"
    
    # 执行SQL初始化脚本
    if sqlite3 "$DB_PATH" < "$SQL_SCRIPT"; then
        log_message "数据库初始化成功"
    else
        log_message "错误: 数据库初始化失败"
        exit 1
    fi
    
    # 设置数据库文件权限
    chmod 664 "$DB_PATH"
    chown celestial:celestial "$DB_PATH"
    
    log_message "数据库权限设置完成"
}

# 验证数据库
verify_database() {
    log_message "验证数据库结构..."
    
    # 检查表是否存在
    TABLE_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='media_transfer_status';")
    if [ "$TABLE_COUNT" -eq 1 ]; then
        log_message "✓ 表 media_transfer_status 创建成功"
    else
        log_message "✗ 表 media_transfer_status 创建失败"
        exit 1
    fi
    
    # 检查索引
    INDEX_COUNT=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND tbl_name='media_transfer_status';")
    log_message "✓ 创建了 $INDEX_COUNT 个索引"
    
    # 检查初始化标记
    INIT_MARKER=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM media_transfer_status WHERE file_path='__INIT_MARKER__';")
    if [ "$INIT_MARKER" -eq 1 ]; then
        log_message "✓ 数据库初始化标记存在"
    else
        log_message "✗ 数据库初始化标记缺失"
        exit 1
    fi
    
    log_message "数据库验证完成"
}

# 显示数据库信息
show_database_info() {
    log_message "数据库信息:"
    log_message "  路径: $DB_PATH"
    log_message "  大小: $(du -h "$DB_PATH" | cut -f1)"
    log_message "  权限: $(ls -l "$DB_PATH" | awk '{print $1, $3, $4}')"
    
    # 显示表结构
    log_message "表结构:"
    sqlite3 "$DB_PATH" ".schema media_transfer_status" | while read line; do
        log_message "  $line"
    done
}

# 主函数
main() {
    log_message "=== DJI Edge SDK 媒体文件状态数据库初始化开始 ==="
    
    check_prerequisites
    backup_existing_db
    init_database
    verify_database
    show_database_info
    
    log_message "=== 数据库初始化完成 ==="
    log_message "数据库路径: $DB_PATH"
    log_message "可以使用以下命令连接数据库:"
    log_message "  sqlite3 $DB_PATH"
}

# 执行主函数
main "$@"