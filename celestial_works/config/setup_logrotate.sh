#!/bin/bash

# DJI Edge SDK 日志轮转设置脚本
# 作者: Celestial
# 创建时间: 2025-01-22
# 描述: 安装和配置logrotate规则

set -e  # 遇到错误立即退出

# 配置变量
PROJECT_ROOT="/home/celestial/dev/esdk-test/Edge-SDK"
LOGROTATE_CONF="$PROJECT_ROOT/celestial_works/config/logrotate.conf"
SYSTEM_LOGROTATE_DIR="/etc/logrotate.d"
LOGROTATE_NAME="dji-edge-sdk"
LOG_FILE="$PROJECT_ROOT/celestial_works/logs/setup_logrotate.log"

# 创建日志函数
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 检查权限
check_permissions() {
    log_message "检查系统权限..."
    
    if [ "$EUID" -ne 0 ]; then
        log_message "错误: 需要root权限来安装logrotate配置"
        log_message "请使用: sudo $0"
        exit 1
    fi
    
    log_message "权限检查通过"
}

# 检查前置条件
check_prerequisites() {
    log_message "检查前置条件..."
    
    # 检查logrotate是否安装
    if ! command -v logrotate &> /dev/null; then
        log_message "错误: logrotate 未安装，请先安装: sudo apt-get install logrotate"
        exit 1
    fi
    
    # 检查配置文件是否存在
    if [ ! -f "$LOGROTATE_CONF" ]; then
        log_message "错误: logrotate配置文件不存在: $LOGROTATE_CONF"
        exit 1
    fi
    
    # 检查系统logrotate目录
    if [ ! -d "$SYSTEM_LOGROTATE_DIR" ]; then
        log_message "错误: 系统logrotate目录不存在: $SYSTEM_LOGROTATE_DIR"
        exit 1
    fi
    
    log_message "前置条件检查完成"
}

# 创建必要的日志目录
create_log_directories() {
    log_message "创建日志目录..."
    
    # 创建celestial_works日志目录
    WORKS_LOG_DIR="$PROJECT_ROOT/celestial_works/logs"
    if [ ! -d "$WORKS_LOG_DIR" ]; then
        mkdir -p "$WORKS_LOG_DIR"
        chown celestial:celestial "$WORKS_LOG_DIR"
        chmod 755 "$WORKS_LOG_DIR"
        log_message "创建目录: $WORKS_LOG_DIR"
    fi
    
    # 创建celestial_nasops日志目录
    NASOPS_LOG_DIR="$PROJECT_ROOT/celestial_nasops/logs"
    if [ ! -d "$NASOPS_LOG_DIR" ]; then
        mkdir -p "$NASOPS_LOG_DIR"
        chown celestial:celestial "$NASOPS_LOG_DIR"
        chmod 755 "$NASOPS_LOG_DIR"
        log_message "创建目录: $NASOPS_LOG_DIR"
    fi
    
    log_message "日志目录创建完成"
}

# 安装logrotate配置
install_logrotate_config() {
    log_message "安装logrotate配置..."
    
    TARGET_FILE="$SYSTEM_LOGROTATE_DIR/$LOGROTATE_NAME"
    
    # 备份现有配置（如果存在）
    if [ -f "$TARGET_FILE" ]; then
        BACKUP_FILE="${TARGET_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
        cp "$TARGET_FILE" "$BACKUP_FILE"
        log_message "备份现有配置到: $BACKUP_FILE"
    fi
    
    # 复制配置文件
    cp "$LOGROTATE_CONF" "$TARGET_FILE"
    chown root:root "$TARGET_FILE"
    chmod 644 "$TARGET_FILE"
    
    log_message "logrotate配置已安装到: $TARGET_FILE"
}

# 测试logrotate配置
test_logrotate_config() {
    log_message "测试logrotate配置..."
    
    TARGET_FILE="$SYSTEM_LOGROTATE_DIR/$LOGROTATE_NAME"
    
    # 测试配置语法
    if logrotate -d "$TARGET_FILE" > /dev/null 2>&1; then
        log_message "✓ logrotate配置语法正确"
    else
        log_message "✗ logrotate配置语法错误"
        log_message "详细错误信息:"
        logrotate -d "$TARGET_FILE" 2>&1 | tee -a "$LOG_FILE"
        exit 1
    fi
    
    log_message "配置测试完成"
}

# 显示安装信息
show_installation_info() {
    log_message "安装信息:"
    log_message "  配置文件: $SYSTEM_LOGROTATE_DIR/$LOGROTATE_NAME"
    log_message "  日志目录: $PROJECT_ROOT/celestial_works/logs"
    log_message "  日志目录: $PROJECT_ROOT/celestial_nasops/logs"
    log_message "  "
    log_message "手动测试命令:"
    log_message "  sudo logrotate -d $SYSTEM_LOGROTATE_DIR/$LOGROTATE_NAME"
    log_message "  sudo logrotate -f $SYSTEM_LOGROTATE_DIR/$LOGROTATE_NAME"
}

# 主函数
main() {
    log_message "=== DJI Edge SDK 日志轮转设置开始 ==="
    
    check_permissions
    check_prerequisites
    create_log_directories
    install_logrotate_config
    test_logrotate_config
    show_installation_info
    
    log_message "=== 日志轮转设置完成 ==="
}

# 执行主函数
main "$@"