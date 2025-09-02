#!/bin/bash

# DJI Edge SDK 监控系统部署脚本
# 作者: Celestial
# 创建时间: 2025-01-22
# 描述: 部署系统监控服务和健康检查脚本

set -e  # 遇到错误立即退出

# 配置变量
PROJECT_ROOT="/home/celestial/dev/esdk-test/Edge-SDK"
CONFIG_DIR="$PROJECT_ROOT/celestial_works/config"
LOG_DIR="$PROJECT_ROOT/celestial_works/logs"
SERVICE_NAME="system-monitor"
SERVICE_FILE="$CONFIG_DIR/system-monitor.service"
HEALTH_CHECK_SCRIPT="$CONFIG_DIR/health_check.sh"
MONITOR_SCRIPT="$CONFIG_DIR/system_monitor.py"
LOG_FILE="$LOG_DIR/deploy_monitoring.log"

# 日志函数
log_message() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

# 检查权限
check_permissions() {
    log_message "INFO" "检查用户权限..."
    
    if [[ $EUID -ne 0 ]]; then
        log_message "ERROR" "此脚本需要root权限才能安装systemd服务"
        log_message "INFO" "请使用: sudo $0"
        exit 1
    fi
    
    log_message "INFO" "权限检查通过"
}

# 检查前置条件
check_prerequisites() {
    log_message "INFO" "检查前置条件..."
    
    # 检查Python虚拟环境
    if [[ ! -f "$PROJECT_ROOT/.venv/bin/python" ]]; then
        log_message "ERROR" "Python虚拟环境不存在: $PROJECT_ROOT/.venv"
        exit 1
    fi
    
    # 检查监控脚本
    if [[ ! -f "$MONITOR_SCRIPT" ]]; then
        log_message "ERROR" "监控脚本不存在: $MONITOR_SCRIPT"
        exit 1
    fi
    
    # 检查健康检查脚本
    if [[ ! -f "$HEALTH_CHECK_SCRIPT" ]]; then
        log_message "ERROR" "健康检查脚本不存在: $HEALTH_CHECK_SCRIPT"
        exit 1
    fi
    
    # 检查服务文件
    if [[ ! -f "$SERVICE_FILE" ]]; then
        log_message "ERROR" "服务文件不存在: $SERVICE_FILE"
        exit 1
    fi
    
    log_message "INFO" "前置条件检查通过"
}

# 创建必要的目录
create_directories() {
    log_message "INFO" "创建必要的目录..."
    
    # 创建日志目录
    mkdir -p "$LOG_DIR"
    chown celestial:celestial "$LOG_DIR"
    chmod 755 "$LOG_DIR"
    
    log_message "INFO" "目录创建完成"
}

# 安装systemd服务
install_service() {
    log_message "INFO" "安装systemd服务..."
    
    # 停止现有服务（如果存在）
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log_message "INFO" "停止现有服务: $SERVICE_NAME"
        systemctl stop "$SERVICE_NAME"
    fi
    
    # 复制服务文件
    cp "$SERVICE_FILE" "/etc/systemd/system/$SERVICE_NAME.service"
    log_message "INFO" "服务文件已复制到: /etc/systemd/system/$SERVICE_NAME.service"
    
    # 重新加载systemd配置
    systemctl daemon-reload
    log_message "INFO" "systemd配置已重新加载"
    
    # 启用服务
    systemctl enable "$SERVICE_NAME"
    log_message "INFO" "服务已启用: $SERVICE_NAME"
    
    log_message "INFO" "systemd服务安装完成"
}

# 测试服务配置
test_service() {
    log_message "INFO" "测试服务配置..."
    
    # 验证服务文件语法
    if ! systemd-analyze verify "/etc/systemd/system/$SERVICE_NAME.service"; then
        log_message "ERROR" "服务文件语法错误"
        exit 1
    fi
    
    log_message "INFO" "服务配置测试通过"
}

# 启动服务
start_service() {
    log_message "INFO" "启动监控服务..."
    
    # 启动服务
    systemctl start "$SERVICE_NAME"
    
    # 等待服务启动
    sleep 3
    
    # 检查服务状态
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log_message "INFO" "服务启动成功: $SERVICE_NAME"
        
        # 显示服务状态
        systemctl status "$SERVICE_NAME" --no-pager -l
    else
        log_message "ERROR" "服务启动失败: $SERVICE_NAME"
        log_message "INFO" "查看服务日志: journalctl -u $SERVICE_NAME -f"
        exit 1
    fi
}

# 设置定时任务
setup_cron_jobs() {
    log_message "INFO" "设置定时任务..."
    
    # 创建cron任务文件
    cat > "/tmp/dji-edge-sdk-cron" << EOF
# DJI Edge SDK 监控任务
# 每小时执行一次健康检查
0 * * * * /bin/bash $HEALTH_CHECK_SCRIPT > $LOG_DIR/health_check_cron.log 2>&1

# 每天凌晨2点执行系统维护
0 2 * * * /bin/bash $CONFIG_DIR/maintenance.sh > $LOG_DIR/maintenance_cron.log 2>&1

# 每周日凌晨3点清理旧日志
0 3 * * 0 /usr/sbin/logrotate -f /etc/logrotate.d/dji-edge-sdk
EOF

    # 安装cron任务
    crontab -u celestial "/tmp/dji-edge-sdk-cron"
    rm "/tmp/dji-edge-sdk-cron"
    
    log_message "INFO" "定时任务设置完成"
}

# 创建维护脚本
create_maintenance_script() {
    log_message "INFO" "创建维护脚本..."
    
    cat > "$CONFIG_DIR/maintenance.sh" << 'EOF'
#!/bin/bash

# DJI Edge SDK 系统维护脚本
# 执行日常维护任务

PROJECT_ROOT="/home/celestial/dev/esdk-test/Edge-SDK"
LOG_DIR="$PROJECT_ROOT/celestial_works/logs"
DB_FILE="$PROJECT_ROOT/celestial_works/media_status.db"

# 日志函数
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log_message "开始系统维护任务"

# 清理旧的临时文件
log_message "清理临时文件..."
find /tmp -name "dji-*" -mtime +7 -delete 2>/dev/null || true

# 压缩旧日志文件
log_message "压缩旧日志文件..."
find "$LOG_DIR" -name "*.log" -mtime +7 -exec gzip {} \; 2>/dev/null || true

# 数据库维护
if [[ -f "$DB_FILE" ]]; then
    log_message "执行数据库维护..."
    
    # 数据库完整性检查
    sqlite3 "$DB_FILE" "PRAGMA integrity_check;" > /dev/null 2>&1 || {
        log_message "警告: 数据库完整性检查失败"
    }
    
    # 数据库优化
    sqlite3 "$DB_FILE" "VACUUM;" 2>/dev/null || {
        log_message "警告: 数据库优化失败"
    }
    
    # 更新统计信息
    sqlite3 "$DB_FILE" "ANALYZE;" 2>/dev/null || {
        log_message "警告: 数据库统计信息更新失败"
    }
fi

# 检查磁盘空间
log_message "检查磁盘空间..."
df -h "$PROJECT_ROOT" | tail -1 | awk '{print "磁盘使用率: " $5}'

# 检查服务状态
log_message "检查服务状态..."
for service in dock-info-manager system-monitor; do
    if systemctl is-active --quiet "$service"; then
        log_message "服务 $service: 运行中"
    else
        log_message "警告: 服务 $service 未运行"
    fi
done

log_message "系统维护任务完成"
EOF

    chmod +x "$CONFIG_DIR/maintenance.sh"
    chown celestial:celestial "$CONFIG_DIR/maintenance.sh"
    
    log_message "INFO" "维护脚本创建完成: $CONFIG_DIR/maintenance.sh"
}

# 显示部署信息
show_deployment_info() {
    log_message "INFO" "部署完成！"
    
    echo ""
    echo "=== DJI Edge SDK 监控系统部署信息 ==="
    echo "部署时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "项目目录: $PROJECT_ROOT"
    echo "配置目录: $CONFIG_DIR"
    echo "日志目录: $LOG_DIR"
    echo ""
    echo "=== 服务管理命令 ==="
    echo "查看服务状态: sudo systemctl status $SERVICE_NAME"
    echo "启动服务: sudo systemctl start $SERVICE_NAME"
    echo "停止服务: sudo systemctl stop $SERVICE_NAME"
    echo "重启服务: sudo systemctl restart $SERVICE_NAME"
    echo "查看服务日志: sudo journalctl -u $SERVICE_NAME -f"
    echo ""
    echo "=== 监控工具 ==="
    echo "执行健康检查: $HEALTH_CHECK_SCRIPT"
    echo "执行单次监控: $MONITOR_SCRIPT --once"
    echo "查看系统状态: cat $LOG_DIR/system_status_report.txt"
    echo ""
    echo "=== 日志文件 ==="
    echo "部署日志: $LOG_FILE"
    echo "监控日志: $LOG_DIR/system_monitor.log"
    echo "健康检查日志: $LOG_DIR/health_check.log"
    echo ""
}

# 主函数
main() {
    log_message "INFO" "开始部署DJI Edge SDK监控系统"
    
    # 创建日志目录
    mkdir -p "$LOG_DIR"
    
    # 执行部署步骤
    check_permissions
    check_prerequisites
    create_directories
    install_service
    test_service
    start_service
    setup_cron_jobs
    create_maintenance_script
    
    # 显示部署信息
    show_deployment_info
    
    log_message "INFO" "监控系统部署完成"
}

# 错误处理
trap 'log_message "ERROR" "部署过程中发生错误，退出码: $?"' ERR

# 执行主函数
main "$@"