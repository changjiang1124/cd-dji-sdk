#!/bin/bash

# DJI Edge SDK 系统健康检查脚本
# 作者: Celestial
# 创建时间: 2025-01-22
# 描述: 监控系统各组件状态，包括服务、数据库、日志和网络连接

set -e

# 配置变量
PROJECT_ROOT="/home/celestial/dev/esdk-test/Edge-SDK"
LOG_FILE="$PROJECT_ROOT/celestial_works/logs/health_check.log"
DB_PATH="$PROJECT_ROOT/celestial_works/media_status.db"
NAS_HOST="192.168.200.103"
NAS_USER="edge_sync"
SERVICE_NAME="dock-info-manager"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
    log_message "SUCCESS: $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
    log_message "WARNING: $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
    log_message "ERROR: $1"
}

log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
    log_message "INFO: $1"
}

# 检查systemd服务状态
check_service_status() {
    log_info "检查systemd服务状态..."
    
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log_success "$SERVICE_NAME 服务正在运行"
        
        # 获取服务详细信息
        local uptime=$(systemctl show "$SERVICE_NAME" --property=ActiveEnterTimestamp --value)
        local memory=$(systemctl show "$SERVICE_NAME" --property=MemoryCurrent --value)
        
        log_info "服务启动时间: $uptime"
        if [ "$memory" != "[not set]" ] && [ -n "$memory" ]; then
            local memory_mb=$((memory / 1024 / 1024))
            log_info "内存使用: ${memory_mb}MB"
        fi
    else
        log_error "$SERVICE_NAME 服务未运行"
        
        # 尝试获取服务失败原因
        local status=$(systemctl is-failed "$SERVICE_NAME" 2>/dev/null || echo "unknown")
        log_error "服务状态: $status"
        
        # 显示最近的日志
        log_info "最近的服务日志:"
        journalctl -u "$SERVICE_NAME" --no-pager -n 5 | while read line; do
            log_info "  $line"
        done
    fi
}

# 检查数据库状态
check_database_status() {
    log_info "检查SQLite数据库状态..."
    
    if [ -f "$DB_PATH" ]; then
        log_success "数据库文件存在: $DB_PATH"
        
        # 检查数据库文件大小
        local db_size=$(stat -c%s "$DB_PATH")
        local db_size_mb=$((db_size / 1024 / 1024))
        log_info "数据库大小: ${db_size_mb}MB"
        
        # 检查数据库连接
        if sqlite3 "$DB_PATH" "SELECT 1;" >/dev/null 2>&1; then
            log_success "数据库连接正常"
            
            # 获取表统计信息
            local media_count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM media_files;" 2>/dev/null || echo "0")
            local sync_count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM sync_status;" 2>/dev/null || echo "0")
            
            log_info "媒体文件记录数: $media_count"
            log_info "同步状态记录数: $sync_count"
        else
            log_error "数据库连接失败"
        fi
    else
        log_error "数据库文件不存在: $DB_PATH"
    fi
}

# 检查日志文件状态
check_log_status() {
    log_info "检查日志文件状态..."
    
    local log_dir="$PROJECT_ROOT/celestial_works/logs"
    
    if [ -d "$log_dir" ]; then
        log_success "日志目录存在: $log_dir"
        
        # 检查日志文件
        local log_files=("dock_init_info.txt" "media_list.log" "database_setup.log")
        
        for log_file in "${log_files[@]}"; do
            local full_path="$log_dir/$log_file"
            if [ -f "$full_path" ]; then
                local file_size=$(stat -c%s "$full_path")
                local file_size_kb=$((file_size / 1024))
                log_success "$log_file 存在 (${file_size_kb}KB)"
                
                # 检查最近修改时间
                local mod_time=$(stat -c %Y "$full_path")
                local current_time=$(date +%s)
                local age=$((current_time - mod_time))
                
                if [ $age -lt 3600 ]; then  # 1小时内
                    log_info "  最近更新: $((age / 60))分钟前"
                elif [ $age -lt 86400 ]; then  # 24小时内
                    log_info "  最近更新: $((age / 3600))小时前"
                else
                    log_warning "  最近更新: $((age / 86400))天前"
                fi
            else
                log_warning "$log_file 不存在"
            fi
        done
    else
        log_error "日志目录不存在: $log_dir"
    fi
}

# 检查网络连接
check_network_status() {
    log_info "检查网络连接状态..."
    
    # 检查到NAS的连接
    if ping -c 1 -W 3 "$NAS_HOST" >/dev/null 2>&1; then
        log_success "NAS网络连接正常 ($NAS_HOST)"
        
        # 检查SSH连接
        if timeout 10 ssh -o ConnectTimeout=5 -o BatchMode=yes "$NAS_USER@$NAS_HOST" "echo 'SSH连接测试'" >/dev/null 2>&1; then
            log_success "NAS SSH连接正常"
        else
            log_error "NAS SSH连接失败"
        fi
    else
        log_error "NAS网络连接失败 ($NAS_HOST)"
    fi
    
    # 检查本地网络接口
    local interfaces=$(ip -o link show | awk -F': ' '{print $2}' | grep -v lo)
    log_info "网络接口状态:"
    
    for interface in $interfaces; do
        local status=$(ip link show "$interface" | grep -o 'state [A-Z]*' | cut -d' ' -f2)
        if [ "$status" = "UP" ]; then
            log_success "  $interface: $status"
        else
            log_warning "  $interface: $status"
        fi
    done
}

# 检查磁盘空间
check_disk_space() {
    log_info "检查磁盘空间状态..."
    
    # 检查项目目录所在磁盘
    local disk_usage=$(df -h "$PROJECT_ROOT" | tail -1)
    local used_percent=$(echo "$disk_usage" | awk '{print $5}' | sed 's/%//')
    local available=$(echo "$disk_usage" | awk '{print $4}')
    
    log_info "项目目录磁盘使用率: ${used_percent}% (可用: $available)"
    
    if [ "$used_percent" -lt 80 ]; then
        log_success "磁盘空间充足"
    elif [ "$used_percent" -lt 90 ]; then
        log_warning "磁盘空间紧张 (${used_percent}%)"
    else
        log_error "磁盘空间严重不足 (${used_percent}%)"
    fi
    
    # 检查日志目录大小
    local log_size=$(du -sh "$PROJECT_ROOT/celestial_works/logs" 2>/dev/null | cut -f1 || echo "0")
    log_info "日志目录大小: $log_size"
}

# 检查Python环境
check_python_environment() {
    log_info "检查Python环境状态..."
    
    # 检查虚拟环境
    local venv_path="$PROJECT_ROOT/.venv"
    if [ -d "$venv_path" ]; then
        log_success "Python虚拟环境存在"
        
        # 激活虚拟环境并检查包
        source "$venv_path/bin/activate"
        
        local python_version=$(python --version 2>&1)
        log_info "Python版本: $python_version"
        
        # 检查关键包
        local packages=("sqlite3" "paramiko" "schedule")
        for package in "${packages[@]}"; do
            if python -c "import $package" 2>/dev/null; then
                log_success "  $package 包可用"
            else
                log_error "  $package 包缺失"
            fi
        done
        
        deactivate
    else
        log_error "Python虚拟环境不存在: $venv_path"
    fi
}

# 生成健康报告摘要
generate_summary() {
    log_info "生成健康检查摘要..."
    
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local summary_file="$PROJECT_ROOT/celestial_works/logs/health_summary.txt"
    
    {
        echo "=== DJI Edge SDK 健康检查报告 ==="
        echo "检查时间: $timestamp"
        echo "检查主机: $(hostname)"
        echo ""
        echo "详细日志: $LOG_FILE"
        echo "数据库路径: $DB_PATH"
        echo "NAS地址: $NAS_HOST"
        echo ""
        echo "如需查看完整日志，请运行:"
        echo "  tail -f $LOG_FILE"
        echo ""
        echo "如需手动测试各组件，请运行:"
        echo "  systemctl status $SERVICE_NAME"
        echo "  sqlite3 $DB_PATH '.tables'"
        echo "  ssh $NAS_USER@$NAS_HOST"
    } > "$summary_file"
    
    log_success "健康检查摘要已保存到: $summary_file"
}

# 主函数
main() {
    echo "=== DJI Edge SDK 系统健康检查 ==="
    echo "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
    
    log_message "=== 健康检查开始 ==="
    
    # 创建日志目录
    mkdir -p "$(dirname "$LOG_FILE")"
    
    # 执行各项检查
    check_service_status
    echo ""
    
    check_database_status
    echo ""
    
    check_log_status
    echo ""
    
    check_network_status
    echo ""
    
    check_disk_space
    echo ""
    
    check_python_environment
    echo ""
    
    generate_summary
    
    log_message "=== 健康检查完成 ==="
    echo ""
    echo "健康检查完成！详细日志请查看: $LOG_FILE"
}

# 如果直接运行此脚本
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi