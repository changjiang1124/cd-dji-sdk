#!/bin/bash

# DJI Edge SDK 绑定状态监控脚本
# 用于监控 sample_media_file_list 程序的绑定状态

LOG_FILE="/home/celestial/dev/esdk-test/Edge-SDK/media_list.log"
STATUS_FILE="/tmp/dji_binding_status"
BINDING_LOG="/home/celestial/dev/esdk-test/Edge-SDK/dji_binding.log"
PID_FILE="/tmp/monitor_binding.pid"
KEY_DIR="/home/celestial/dev/esdk-test/keystore"
PRIVATE_KEY="$KEY_DIR/private.der"
PUBLIC_KEY="$KEY_DIR/public.der"

# 检查是否已经在运行
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "监控脚本已经在运行 (PID: $OLD_PID)"
        exit 1
    fi
fi

# 保存当前进程ID
echo $$ > "$PID_FILE"

# 清理函数
cleanup() {
    echo "$(date): 监控脚本停止" >> "$BINDING_LOG"
    rm -f "$PID_FILE"
    exit 0
}

# 设置信号处理
trap cleanup SIGTERM SIGINT

echo "$(date): DJI 绑定状态监控脚本启动" >> "$BINDING_LOG"
echo "监控日志文件: $LOG_FILE"
echo "状态文件: $STATUS_FILE"
echo "绑定日志: $BINDING_LOG"
echo "密钥目录: $KEY_DIR"
echo "私钥文件: $PRIVATE_KEY"
echo "公钥文件: $PUBLIC_KEY"
echo "按 Ctrl+C 停止监控"
echo ""

# 检查密钥文件是否存在
if [ ! -f "$PRIVATE_KEY" ] || [ ! -f "$PUBLIC_KEY" ]; then
    echo "❌ 错误: 密钥文件不存在！"
    echo "请确保以下文件存在:"
    echo "  - $PRIVATE_KEY"
    echo "  - $PUBLIC_KEY"
    exit 1
fi

echo "✅ 密钥文件检查通过"
echo ""

# 初始化状态
echo "UNKNOWN" > "$STATUS_FILE"

while true; do
    if [ ! -f "$LOG_FILE" ]; then
        echo "WAITING_FOR_LOG" > "$STATUS_FILE"
        echo "$(date): 等待日志文件创建..."
        sleep 5
        continue
    fi
    
    # 检查密钥文件访问时间（表示正在使用）
    KEY_ACCESSED=false
    if [ -f "$PRIVATE_KEY" ] && [ -f "$PUBLIC_KEY" ]; then
        # 检查最近5分钟内是否访问过密钥文件
        if [ $(find "$PRIVATE_KEY" -amin -5 2>/dev/null | wc -l) -gt 0 ] || 
           [ $(find "$PUBLIC_KEY" -amin -5 2>/dev/null | wc -l) -gt 0 ]; then
            KEY_ACCESSED=true
        fi
    fi
    
    # 检查是否在等待绑定
    if tail -n 50 "$LOG_FILE" | grep -q "Updating session key"; then
        CURRENT_STATUS=$(cat "$STATUS_FILE" 2>/dev/null || echo "")
        if [ "$CURRENT_STATUS" != "WAITING_FOR_BINDING" ]; then
            echo "WAITING_FOR_BINDING" > "$STATUS_FILE"
            echo "$(date): 等待 DJI Pilot 绑定..." | tee -a "$BINDING_LOG"
        fi
    # 检查绑定是否成功（结合日志和密钥访问）
    elif tail -n 50 "$LOG_FILE" | grep -qE "session key.*success|Device connected|Media file list|Heartbeat.*success" || [ "$KEY_ACCESSED" = true ]; then
        CURRENT_STATUS=$(cat "$STATUS_FILE" 2>/dev/null || echo "")
        if [ "$CURRENT_STATUS" != "BINDING_SUCCESS" ]; then
            echo "BINDING_SUCCESS" > "$STATUS_FILE"
            if [ "$KEY_ACCESSED" = true ]; then
                echo "$(date): ✅ DJI Dock 绑定成功！（检测到密钥文件访问）" | tee -a "$BINDING_LOG"
            else
                echo "$(date): ✅ DJI Dock 绑定成功！" | tee -a "$BINDING_LOG"
            fi
            
            # 发送系统通知（如果支持）
            if command -v notify-send > /dev/null 2>&1; then
                notify-send "DJI Edge SDK" "设备绑定成功！"
            fi
        fi
    # 检查是否有错误
    elif tail -n 20 "$LOG_FILE" | grep -qE "Error|Failed|Exception"; then
        CURRENT_STATUS=$(cat "$STATUS_FILE" 2>/dev/null || echo "")
        if [ "$CURRENT_STATUS" != "ERROR" ]; then
            echo "ERROR" > "$STATUS_FILE"
            echo "$(date): ❌ 检测到错误状态" | tee -a "$BINDING_LOG"
        fi
    fi
    
    # 显示当前状态
    CURRENT_STATUS=$(cat "$STATUS_FILE" 2>/dev/null || echo "UNKNOWN")
    case "$CURRENT_STATUS" in
        "WAITING_FOR_BINDING")
            printf "\r状态: 🔄 等待绑定... $(date '+%H:%M:%S')"
            ;;
        "BINDING_SUCCESS")
            printf "\r状态: ✅ 绑定成功   $(date '+%H:%M:%S')"
            ;;
        "ERROR")
            printf "\r状态: ❌ 错误状态   $(date '+%H:%M:%S')"
            ;;
        *)
            printf "\r状态: ❓ 未知状态   $(date '+%H:%M:%S')"
            ;;
    esac
    
    sleep 3
done