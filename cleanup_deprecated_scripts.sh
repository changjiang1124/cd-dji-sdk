#!/bin/bash

# 废弃脚本清理工具
# 生成时间: 2025-01-25
# 目的: 安全删除已废弃的脚本文件和服务配置

set -e  # 遇到错误立即退出

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

# 检查是否在正确的目录
check_directory() {
    if [[ ! -f "devnote.md" ]] || [[ ! -d "celestial_nasops" ]]; then
        log_error "请在 Edge-SDK 项目根目录下运行此脚本"
        exit 1
    fi
}

# 备份当前状态
create_backup() {
    log_info "创建备份..."
    
    # 检查git状态
    if git status --porcelain | grep -q .; then
        log_warning "检测到未提交的更改，建议先提交当前状态"
        read -p "是否继续? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "操作已取消"
            exit 0
        fi
    fi
    
    # 创建备份分支
    BACKUP_BRANCH="backup-before-cleanup-$(date +%Y%m%d-%H%M%S)"
    git checkout -b "$BACKUP_BRANCH"
    git add -A
    git commit -m "备份: 清理废弃脚本前的状态" || true
    git checkout -
    
    log_success "已创建备份分支: $BACKUP_BRANCH"
}

# 阶段1: 删除无依赖的文件
phase1_safe_deletion() {
    log_info "=== 阶段1: 删除无依赖的废弃文件 ==="
    
    # 删除废弃的服务配置文件
    if [[ -f "celestial_nasops/media_sync_daemon.service" ]]; then
        rm -f "celestial_nasops/media_sync_daemon.service"
        log_success "删除 celestial_nasops/media_sync_daemon.service"
    else
        log_info "celestial_nasops/media_sync_daemon.service 不存在，跳过"
    fi
    
    # 删除废弃的安装脚本
    if [[ -f "celestial_nasops/install_daemon.sh" ]]; then
        rm -f "celestial_nasops/install_daemon.sh"
        log_success "删除 celestial_nasops/install_daemon.sh"
    else
        log_info "celestial_nasops/install_daemon.sh 不存在，跳过"
    fi
    
    if [[ -f "celestial_nasops/uninstall_daemon.sh" ]]; then
        rm -f "celestial_nasops/uninstall_daemon.sh"
        log_success "删除 celestial_nasops/uninstall_daemon.sh"
    else
        log_info "celestial_nasops/uninstall_daemon.sh 不存在，跳过"
    fi
    
    log_success "阶段1 完成"
}

# 阶段2: 删除废弃的测试文件
phase2_test_files() {
    log_info "=== 阶段2: 删除废弃的测试文件 ==="
    
    local test_files=(
        "celestial_nasops/test_sync.py"
        "celestial_nasops/test_concurrency.py"
        "celestial_nasops/test_storage_manager.py"
        "celestial_nasops/test_safe_delete.py"
    )
    
    for file in "${test_files[@]}"; do
        if [[ -f "$file" ]]; then
            rm -f "$file"
            log_success "删除 $file"
        else
            log_info "$file 不存在，跳过"
        fi
    done
    
    log_success "阶段2 完成"
}

# 阶段3: 删除核心废弃组件
phase3_core_components() {
    log_info "=== 阶段3: 删除核心废弃组件 ==="
    
    # 检查依赖关系
    log_info "检查依赖关系..."
    
    local has_dependencies=false
    
    # 检查 sync_scheduler.py 的依赖
    if grep -r "import.*sync_scheduler\|from.*sync_scheduler" . --exclude-dir=.git --exclude-dir=.venv 2>/dev/null; then
        log_warning "发现 sync_scheduler.py 仍有依赖关系"
        has_dependencies=true
    fi
    
    # 检查 media_sync.py 的依赖
    if grep -r "import.*media_sync\|from.*media_sync" . --exclude-dir=.git --exclude-dir=.venv 2>/dev/null; then
        log_warning "发现 media_sync.py 仍有依赖关系"
        has_dependencies=true
    fi
    
    if [[ "$has_dependencies" == "true" ]]; then
        log_warning "检测到依赖关系，建议先处理依赖后再删除核心组件"
        read -p "是否强制删除? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "跳过核心组件删除"
            return 0
        fi
    fi
    
    # 删除核心废弃文件
    if [[ -f "celestial_nasops/sync_scheduler.py" ]]; then
        rm -f "celestial_nasops/sync_scheduler.py"
        log_success "删除 celestial_nasops/sync_scheduler.py"
    else
        log_info "celestial_nasops/sync_scheduler.py 不存在，跳过"
    fi
    
    if [[ -f "celestial_nasops/media_sync.py" ]]; then
        rm -f "celestial_nasops/media_sync.py"
        log_success "删除 celestial_nasops/media_sync.py"
    else
        log_info "celestial_nasops/media_sync.py 不存在，跳过"
    fi
    
    log_success "阶段3 完成"
}

# 清理系统服务文件
cleanup_system_services() {
    log_info "=== 清理系统服务文件 ==="
    
    if [[ -f "/etc/systemd/system/media-sync-daemon.service" ]]; then
        log_info "发现系统中的废弃服务文件，需要root权限删除"
        if sudo rm -f "/etc/systemd/system/media-sync-daemon.service"; then
            sudo systemctl daemon-reload
            log_success "删除系统服务文件并重新加载systemd"
        else
            log_error "删除系统服务文件失败"
        fi
    else
        log_info "系统中无废弃服务文件"
    fi
}

# 验证清理结果
verify_cleanup() {
    log_info "=== 验证清理结果 ==="
    
    # 检查服务状态
    log_info "检查当前活跃的相关服务..."
    systemctl list-units --type=service --state=active | grep -E '(media|dock)' || log_info "无相关活跃服务或仅有正常服务"
    
    # 检查是否还有废弃文件
    log_info "检查是否还有废弃文件..."
    local remaining_files=$(find . -name "sync_scheduler.py" -o -name "media_sync.py" -o -name "install_daemon.sh" -o -name "uninstall_daemon.sh" -o -name "media_sync_daemon.service" 2>/dev/null | grep -v ".git" || true)
    
    if [[ -n "$remaining_files" ]]; then
        log_warning "发现剩余的废弃文件:"
        echo "$remaining_files"
    else
        log_success "所有废弃文件已清理完成"
    fi
    
    # 检查当前架构服务状态
    log_info "检查当前架构服务状态..."
    if systemctl is-active --quiet dock-info-manager; then
        log_success "dock-info-manager.service 运行正常"
    else
        log_warning "dock-info-manager.service 未运行"
    fi
    
    if systemctl is-active --quiet media_finding_daemon; then
        log_success "media_finding_daemon.service 运行正常"
    else
        log_warning "media_finding_daemon.service 未运行"
    fi
}

# 显示使用帮助
show_help() {
    echo "废弃脚本清理工具"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --phase1    只执行阶段1 (删除无依赖文件)"
    echo "  --phase2    只执行阶段2 (删除测试文件)"
    echo "  --phase3    只执行阶段3 (删除核心组件)"
    echo "  --system    只清理系统服务文件"
    echo "  --verify    只验证清理结果"
    echo "  --all       执行所有阶段 (默认)"
    echo "  --help      显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 --phase1          # 只删除无依赖的文件"
    echo "  $0 --all             # 执行完整清理"
    echo "  $0 --verify          # 验证清理结果"
}

# 主函数
main() {
    log_info "废弃脚本清理工具启动"
    
    check_directory
    
    case "${1:-all}" in
        --phase1)
            create_backup
            phase1_safe_deletion
            ;;
        --phase2)
            create_backup
            phase2_test_files
            ;;
        --phase3)
            create_backup
            phase3_core_components
            ;;
        --system)
            cleanup_system_services
            ;;
        --verify)
            verify_cleanup
            ;;
        --all)
            create_backup
            phase1_safe_deletion
            phase2_test_files
            phase3_core_components
            cleanup_system_services
            verify_cleanup
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            log_error "未知选项: $1"
            show_help
            exit 1
            ;;
    esac
    
    log_success "清理操作完成"
    log_info "如需回滚，请使用: git checkout <backup_branch>"
}

# 执行主函数
main "$@"