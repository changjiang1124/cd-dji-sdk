#!/usr/bin/env bash
# 一键部署并重启 dock-info-manager 守护进程
# 作用：重新编译 C++ 代码 -> 覆盖服务二进制 -> 安全重启 systemd 服务 -> 输出关键日志
# 使用：
#   ./deploy_dock_monitor.sh           # 正常部署并重启
#   ./deploy_dock_monitor.sh --no-build    # 跳过编译，仅覆盖并重启
#   ./deploy_dock_monitor.sh --no-restart  # 编译并覆盖，不重启服务（手动重启）
# 说明：需要具备 sudo 权限以执行 systemctl 操作

set -Eeuo pipefail

# -------------------- 配置区 --------------------
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$PROJECT_ROOT/build"
BIN_NAME="dock_info_manager"
BUILD_BIN="$BUILD_DIR/bin/$BIN_NAME"
TARGET_BIN="$PROJECT_ROOT/celestial_works/bin/$BIN_NAME"
SERVICE_NAME="dock-info-manager"
SYSTEMD_UNIT="/etc/systemd/system/${SERVICE_NAME}.service"
INSTALL_SCRIPT="$PROJECT_ROOT/celestial_works/config/install_dock_service.sh"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
COLOR_GREEN='\033[0;32m'
COLOR_YELLOW='\033[1;33m'
COLOR_RED='\033[0;31m'
COLOR_RESET='\033[0m'

# -------------------- 工具函数 --------------------
log()   { echo -e "${COLOR_GREEN}[INFO]${COLOR_RESET} $*"; }
warn()  { echo -e "${COLOR_YELLOW}[WARN]${COLOR_RESET} $*"; }
error() { echo -e "${COLOR_RED}[ERR ]${COLOR_RESET} $*" >&2; }
step()  { echo -e "\n${COLOR_GREEN}==>${COLOR_RESET} $*"; }

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || { error "未找到命令: $1"; exit 127; }
}

require_sudo() {
  if ! command -v sudo >/dev/null 2>&1; then
    error "未找到 sudo，请以 root 运行此脚本或安装 sudo"; exit 1
  fi
}

# -------------------- 参数解析 --------------------
DO_BUILD=1
DO_RESTART=1
for arg in "${@:-}"; do
  case "$arg" in
    --no-build) DO_BUILD=0 ;;
    --no-restart) DO_RESTART=0 ;;
    -h|--help)
      grep '^# ' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) warn "忽略未知参数: $arg" ;;
  esac
done

# -------------------- 预检查 --------------------
step "执行预检查"
need_cmd cmake
need_cmd make
need_cmd g++
need_cmd nproc

if [[ ! -f "$PROJECT_ROOT/CMakeLists.txt" ]]; then
  error "未找到 CMakeLists.txt，当前目录不是工程根目录: $PROJECT_ROOT"; exit 1
fi

mkdir -p "$BUILD_DIR" "$(dirname "$TARGET_BIN")"

# -------------------- 编译构建 --------------------
if [[ "$DO_BUILD" -eq 1 ]]; then
  step "配置并编译项目 (Release/C++17)"
  log "CMake 配置中..."
  cmake -S "$PROJECT_ROOT" -B "$BUILD_DIR" -DCMAKE_BUILD_TYPE=Release
  log "并行编译 dock_info_manager..."
  cmake --build "$BUILD_DIR" -j"$(nproc)" --target "$BIN_NAME"
else
  warn "按参数要求 --no-build: 跳过编译"
fi

# -------------------- 验证构建产物 --------------------
if [[ ! -f "$BUILD_BIN" ]]; then
  error "未找到构建产物: $BUILD_BIN"
  error "请先完成编译，或不要使用 --no-build 参数。"
  exit 2
fi

# -------------------- 服务安装检查 --------------------
if [[ ! -f "$SYSTEMD_UNIT" ]]; then
  warn "未检测到 systemd 单元文件: $SYSTEMD_UNIT"
  warn "将尝试安装服务 (需要 sudo)"
  require_sudo
  sudo bash "$INSTALL_SCRIPT"
fi

# -------------------- 停服务 -> 备份 -> 覆盖二进制 --------------------
step "停止服务并部署新二进制"
require_sudo
if systemctl is-active --quiet "$SERVICE_NAME"; then
  sudo systemctl stop "$SERVICE_NAME" || true
else
  warn "服务当前不在运行状态"
fi

if [[ -f "$TARGET_BIN" ]]; then
  local_bak="${TARGET_BIN}.${TIMESTAMP}.bak"
  cp -a "$TARGET_BIN" "$local_bak"
  log "已备份旧二进制: $local_bak"
fi

install -m 0755 "$BUILD_BIN" "$TARGET_BIN"
log "已部署新二进制 -> $TARGET_BIN"

# -------------------- 重启服务并校验 --------------------
if [[ "$DO_RESTART" -eq 1 ]]; then
  step "重启服务: $SERVICE_NAME"
  sudo systemctl daemon-reload
  sudo systemctl start "$SERVICE_NAME" || sudo systemctl restart "$SERVICE_NAME" || true
  sleep 1
  if systemctl is-active --quiet "$SERVICE_NAME"; then
    log "服务已运行。"
    echo
    log "最近 50 行日志："
    sudo journalctl -u "$SERVICE_NAME" -n 50 --no-pager || true
  else
    error "服务启动失败，尝试回滚二进制..."
    if ls "${TARGET_BIN}".*.bak >/dev/null 2>&1; then
      last_bak="$(ls -t "${TARGET_BIN}".*.bak | head -n1)"
      warn "回滚到: $last_bak"
      install -m 0755 "$last_bak" "$TARGET_BIN"
      sudo systemctl start "$SERVICE_NAME" || true
      if systemctl is-active --quiet "$SERVICE_NAME"; then
        log "回滚成功，服务已恢复到旧版本。"
      else
        error "回滚后服务仍未运行，请手动排查 (journalctl -u $SERVICE_NAME -e)"
        exit 3
      fi
    else
      error "未找到备份，无法回滚。"
      exit 3
    fi
  fi
else
  warn "按参数要求 --no-restart: 已部署新二进制，未重启服务。"
  echo "可手动执行: sudo systemctl restart $SERVICE_NAME"
fi

step "完成"
log "二进制: $TARGET_BIN"
log "服务:   $SERVICE_NAME"