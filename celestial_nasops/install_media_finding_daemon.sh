#!/bin/bash

# Media Finding Daemon 安装脚本
# 用于安装和配置统一同步架构优化方案的核心daemon服务

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
        log_info "正确用法: ./install_media_finding_daemon.sh"
        exit 1
    fi
}

# 检查依赖
check_dependencies() {
    log_info "检查系统依赖..."
    
    # 检查Python3
    if ! command -v python3 &> /dev/null; then
        log_error "Python3 未安装，请先安装Python3"
        exit 1
    fi
    
    # 检查systemctl
    if ! command -v systemctl &> /dev/null; then
        log_error "systemctl 未找到，此系统可能不支持systemd"
        exit 1
    fi
    
    log_success "依赖检查完成"
}

# 创建必要的目录
create_directories() {
    log_info "创建必要的目录..."
    
    # 日志目录
    mkdir -p /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/logs
    
    # 媒体目录
    mkdir -p /home/celestial/dev/esdk-test/Edge-SDK/celestial_works/media
    
    # 数据库目录
    mkdir -p /data/temp/dji
    
    log_success "目录创建完成"
}

# 设置文件权限
set_permissions() {
    log_info "设置文件权限..."
    
    # 设置daemon脚本可执行权限
    chmod +x /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/media_finding_daemon.py
    
    # 设置目录权限
    chmod 755 /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/logs
    chmod 755 /home/celestial/dev/esdk-test/Edge-SDK/celestial_works/media
    
    log_success "权限设置完成"
}

# 安装systemd服务
install_service() {
    log_info "安装systemd服务..."
    
    # 复制服务文件到系统目录
    sudo cp /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/media_finding_daemon.service /etc/systemd/system/
    
    # 重新加载systemd配置
    sudo systemctl daemon-reload
    
    # 启用服务（开机自启）
    sudo systemctl enable media_finding_daemon.service
    
    log_success "systemd服务安装完成"
}

# 验证配置文件
validate_config() {
    log_info "验证配置文件..."
    
    CONFIG_FILE="/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/unified_config.json"
    
    if [[ ! -f "$CONFIG_FILE" ]]; then
        log_error "配置文件不存在: $CONFIG_FILE"
        exit 1
    fi
    
    # 检查JSON格式
    if ! python3 -m json.tool "$CONFIG_FILE" > /dev/null 2>&1; then
        log_error "配置文件JSON格式错误: $CONFIG_FILE"
        exit 1
    fi
    
    log_success "配置文件验证通过"
}

# 测试daemon启动
test_daemon() {
    log_info "测试daemon启动..."
    
    # 运行一次性测试
    if python3 /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/media_finding_daemon.py --once; then
        log_success "daemon测试启动成功"
    else
        log_warning "daemon测试启动失败，请检查日志"
    fi
}

# 显示服务管理命令
show_usage() {
    log_info "Media Finding Daemon 安装完成！"
    echo
    log_info "服务管理命令:"
    echo "  启动服务: sudo systemctl start media_finding_daemon"
    echo "  停止服务: sudo systemctl stop media_finding_daemon"
    echo "  重启服务: sudo systemctl restart media_finding_daemon"
    echo "  查看状态: sudo systemctl status media_finding_daemon"
    echo "  查看日志: sudo journalctl -u media_finding_daemon -f"
    echo "  禁用自启: sudo systemctl disable media_finding_daemon"
    echo
    log_info "配置文件位置:"
    echo "  /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/unified_config.json"
    echo
    log_info "日志文件位置:"
    echo "  /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/logs/media_finding.log"
    echo
}

# 主函数
main() {
    log_info "开始安装 Media Finding Daemon..."
    echo
    
    check_root
    check_dependencies
    create_directories
    set_permissions
    validate_config
    install_service
    test_daemon
    
    echo
    show_usage
    
    log_success "安装完成！"
}

# 执行主函数
main "$@"