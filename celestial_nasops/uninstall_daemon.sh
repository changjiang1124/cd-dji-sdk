#!/bin/bash
# DJI媒体文件同步守护进程卸载脚本

set -e

SERVICE_NAME="media-sync-daemon"
SYSTEM_SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "=== DJI媒体文件同步守护进程卸载脚本 ==="
echo

# 检查是否以root权限运行
if [[ $EUID -ne 0 ]]; then
   echo "错误: 此脚本需要root权限运行"
   echo "请使用: sudo $0"
   exit 1
fi

# 检查服务是否存在
if [[ ! -f "$SYSTEM_SERVICE_FILE" ]]; then
    echo "警告: 服务文件不存在: $SYSTEM_SERVICE_FILE"
    echo "服务可能已经被卸载"
    exit 0
fi

# 停止服务
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "停止服务..."
    systemctl stop "$SERVICE_NAME"
else
    echo "服务未在运行"
fi

# 禁用服务
if systemctl is-enabled --quiet "$SERVICE_NAME"; then
    echo "禁用服务..."
    systemctl disable "$SERVICE_NAME"
else
    echo "服务未启用"
fi

# 删除服务文件
echo "删除服务文件..."
rm -f "$SYSTEM_SERVICE_FILE"

# 重新加载systemd配置
echo "重新加载systemd配置..."
systemctl daemon-reload

# 重置失败状态（如果有）
systemctl reset-failed "$SERVICE_NAME" 2>/dev/null || true

echo
echo "=== 卸载完成 ==="
echo "服务 $SERVICE_NAME 已成功卸载"
echo
echo "注意: 以下文件和目录未被删除，如需要请手动清理:"
echo "  - 日志目录: /home/celestial/dev/esdk-test/Edge-SDK/celestial_works/logs/"
echo "  - 媒体目录: /data/temp/dji/media/"
echo "  - 项目代码: /home/celestial/dev/esdk-test/Edge-SDK/celestial_nasops/"
echo