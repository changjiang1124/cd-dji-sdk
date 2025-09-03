#!/bin/bash

# Media Finding Daemon 卸载脚本
# 用于卸载统一同步架构优化方案的核心daemon服务

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查是否以root权限运行
check_root() {
    if [[ $EUID -eq 0 ]]; then
        log_error "请不要以root权限运行此脚本"
        log_info "正确用法: ./uninstall_media_finding_daemon.sh"
        exit 1
    fi
}

# 停止服务
stop_service() {
    log_info "停止 Media Finding Daemon 服务..."
    
    if sudo systemctl is-active --quiet media_finding_daemon; then
        sudo systemctl stop media_finding_daemon
        log_success "服务已停止"
    else
        log_info "服务未运行"
    fi
}

# 禁用服务
disable_service() {
    log_info "禁用服务自启动..."
    
    if sudo systemctl is-enabled --quiet media_finding_daemon 2>/dev/null; then
        sudo systemctl disable media_finding_daemon
        log_success "服务自启动已禁用"
    else
        log_info "服务未启用自启动"
    fi
}

# 删除服务文件
remove_service_file() {
    log_info "删除systemd服务文件..."
    
    SERVICE_FILE="/etc/systemd/system/media_finding_daemon.service"
    
    if [[ -f "$SERVICE_FILE" ]]; then
        sudo rm -f "$SERVICE_FILE"
        sudo systemctl daemon-reload
        log_success "服务文件已删除"
    else
        log_info "服务文件不存在"
    fi
}

# 询问是否删除日志文件
ask_remove_logs() {
    echo
    read -p "是否删除日志文件? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "删除日志文件..."
        
        LOG_DIR="/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/logs"
        
        if [[ -d "$LOG_DIR" ]]; then
            rm -rf "$LOG_DIR/media_finding.log"*
            log_success "日志文件已删除"
        else
            log_info "日志目录不存在"
        fi
    else
        log_info "保留日志文件"
    fi
}

# 询问是否删除数据库文件
ask_remove_database() {
    echo
    read -p "是否删除数据库文件? (y/N): " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "删除数据库文件..."
        
        DB_FILE="/data/temp/dji/media_status.db"
        
        if [[ -f "$DB_FILE" ]]; then
            rm -f "$DB_FILE"*
            log_success "数据库文件已删除"
        else
            log_info "数据库文件不存在"
        fi
    else
        log_info "保留数据库文件"
    fi
}

# 显示卸载后信息
show_cleanup_info() {
    log_info "卸载完成！"
    echo
    log_info "以下文件和目录仍然保留:"
    echo "  - 程序文件: /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/media_finding_daemon.py"
    echo "  - 配置文件: /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/unified_config.json"
    echo "  - 安装脚本: /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/install_media_finding_daemon.sh"
    
    if [[ -d "/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/logs" ]]; then
        echo "  - 日志目录: /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/logs"
    fi
    
    if [[ -f "/data/temp/dji/media_status.db" ]]; then
        echo "  - 数据库文件: /data/temp/dji/media_status.db"
    fi
    
    echo
    log_info "如需完全清理，请手动删除上述文件和目录"
}

# 主函数
main() {
    log_info "开始卸载 Media Finding Daemon..."
    echo
    
    check_root
    stop_service
    disable_service
    remove_service_file
    ask_remove_logs
    ask_remove_database
    
    echo
    show_cleanup_info
    
    log_success "卸载完成！"
}

# 执行主函数
main "$@"