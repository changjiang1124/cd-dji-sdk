#!/bin/bash
# DJI媒体文件同步守护进程安装脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="media-sync-daemon"
SERVICE_FILE="${SCRIPT_DIR}/media_sync_daemon.service"
SYSTEM_SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "=== DJI媒体文件同步守护进程安装脚本 ==="
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

# 检查Python虚拟环境
VENV_PYTHON="/home/celestial/dev/esdk-test/Edge-SDK/.venv/bin/python"
if [[ ! -f "$VENV_PYTHON" ]]; then
    echo "错误: Python虚拟环境不存在: $VENV_PYTHON"
    echo "请先激活虚拟环境并安装依赖"
    exit 1
fi

# 检查同步脚本
SYNC_SCRIPT="/home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/sync_scheduler.py"
if [[ ! -f "$SYNC_SCRIPT" ]]; then
    echo "错误: 同步脚本不存在: $SYNC_SCRIPT"
    exit 1
fi

# 创建必要的目录
echo "创建必要的目录..."
mkdir -p /data/temp/dji/media
mkdir -p /home/celestial/dev/esdk-test/Edge-SDK/celestial_works/logs
chown -R celestial:celestial /home/celestial/dev/esdk-test/Edge-SDK/celestial_works/logs

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

# 启动服务
echo "启动服务..."
systemctl start "$SERVICE_NAME"

# 检查服务状态
echo
echo "=== 服务状态 ==="
systemctl status "$SERVICE_NAME" --no-pager -l

echo
echo "=== 安装完成 ==="
echo "服务名称: $SERVICE_NAME"
echo "服务文件: $SYSTEM_SERVICE_FILE"
echo
echo "常用命令:"
echo "  查看状态: sudo systemctl status $SERVICE_NAME"
echo "  查看日志: sudo journalctl -u $SERVICE_NAME -f"
echo "  停止服务: sudo systemctl stop $SERVICE_NAME"
echo "  启动服务: sudo systemctl start $SERVICE_NAME"
echo "  重启服务: sudo systemctl restart $SERVICE_NAME"
echo "  禁用服务: sudo systemctl disable $SERVICE_NAME"
echo
echo "日志文件位置: /home/celestial/dev/esdk-test/Edge-SDK/celestial_works/logs/sync_scheduler.log"
echo