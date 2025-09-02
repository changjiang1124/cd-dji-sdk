#!/bin/bash
# DJI Dock Info Manager服务安装脚本
# 基于celestial_nasops/install_daemon.sh的模式创建

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="dock-info-manager"
SERVICE_FILE="${SCRIPT_DIR}/dock-info-manager.service"
SYSTEM_SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
BINARY_PATH="/home/celestial/dev/esdk-test/Edge-SDK/celestial_works/bin/dock_info_manager"

echo "=== DJI Dock Info Manager服务安装脚本 ==="
echo

# 检查是否以root权限运行
if [[ $EUID -ne 0 ]]; then
   echo "错误: 此脚本需要root权限运行"
   echo "请使用: sudo $0"
   exit 1
fi

# 检查服务文件是否存在
if [[ ! -f "$SERVICE_FILE" ]]; then
    echo "错误: 服务文件不存在: $SERVICE_FILE"
    exit 1
fi

# 检查二进制文件是否存在
if [[ ! -f "$BINARY_PATH" ]]; then
    echo "警告: 二进制文件不存在: $BINARY_PATH"
    echo "请先编译dock_info_manager程序"
    echo "继续安装服务配置..."
fi

# 检查配置文件
CONFIG_FILE="/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/unified_config.json"
if [[ ! -f "$CONFIG_FILE" ]]; then
    echo "错误: 配置文件不存在: $CONFIG_FILE"
    exit 1
fi

# 创建必要的目录
echo "创建必要的目录..."
mkdir -p /home/celestial/dev/esdk-test/Edge-SDK/celestial_works/logs
mkdir -p /home/celestial/dev/esdk-test/Edge-SDK/celestial_works/bin
mkdir -p /opt/dji/Edge-SDK/celestial_works
chown -R celestial:celestial /home/celestial/dev/esdk-test/Edge-SDK/celestial_works
chown -R celestial:celestial /opt/dji/Edge-SDK/celestial_works

# 停止现有服务（如果存在）
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "停止现有服务..."
    systemctl stop "$SERVICE_NAME"
fi

# 复制服务文件
echo "安装systemd服务文件..."
cp "$SERVICE_FILE" "$SYSTEM_SERVICE_FILE"

# 重新加载systemd配置
echo "重新加载systemd配置..."
systemctl daemon-reload

# 启用服务
echo "启用服务..."
systemctl enable "$SERVICE_NAME"

# 如果二进制文件存在，启动服务
if [[ -f "$BINARY_PATH" ]]; then
    echo "启动服务..."
    systemctl start "$SERVICE_NAME"
    
    # 检查服务状态
    echo
    echo "=== 服务状态 ==="
    systemctl status "$SERVICE_NAME" --no-pager -l
else
    echo "跳过启动服务（二进制文件不存在）"
fi

echo
echo "=== 安装完成 ==="
echo "服务名称: $SERVICE_NAME"
echo "服务文件: $SYSTEM_SERVICE_FILE"
echo "二进制文件: $BINARY_PATH"
echo "配置文件: $CONFIG_FILE"
echo
echo "常用命令:"
echo "  查看状态: sudo systemctl status $SERVICE_NAME"
echo "  查看日志: sudo journalctl -u $SERVICE_NAME -f"
echo "  停止服务: sudo systemctl stop $SERVICE_NAME"
echo "  启动服务: sudo systemctl start $SERVICE_NAME"
echo "  重启服务: sudo systemctl restart $SERVICE_NAME"
echo "  禁用服务: sudo systemctl disable $SERVICE_NAME"
echo
echo "日志文件位置: /home/celestial/dev/esdk-test/Edge-SDK/celestial_works/logs/"
echo
echo "注意: 如果二进制文件不存在，请先编译dock_info_manager程序后再启动服务"
echo