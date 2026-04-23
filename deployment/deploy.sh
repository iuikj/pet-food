#!/usr/bin/env bash
# ============================================================
# 宠物饮食助手 - 本机/生产一键部署脚本
# ------------------------------------------------------------
# 用法:
#   ./deployment/deploy.sh up         # 构建并启动
#   ./deployment/deploy.sh down       # 停止但保留数据卷
#   ./deployment/deploy.sh clean      # 停止并删除数据卷（危险）
#   ./deployment/deploy.sh logs [svc] # 跟踪日志（默认全部）
#   ./deployment/deploy.sh restart    # 重启所有服务
#   ./deployment/deploy.sh ps         # 查看容器状态
#   ./deployment/deploy.sh migrate    # 手动跑数据库迁移
# ============================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.prod.yml"
ENV_FILE="$SCRIPT_DIR/.env.prod"

# ────── 颜色输出 ──────
if [ -t 1 ]; then
    RED=$'\033[31m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; BLUE=$'\033[34m'; RESET=$'\033[0m'
else
    RED=''; GREEN=''; YELLOW=''; BLUE=''; RESET=''
fi
info()  { echo "${BLUE}[INFO]${RESET}  $*"; }
ok()    { echo "${GREEN}[OK]${RESET}    $*"; }
warn()  { echo "${YELLOW}[WARN]${RESET}  $*"; }
error() { echo "${RED}[ERR]${RESET}   $*" >&2; }

# ────── 前置检查 ──────
preflight() {
    command -v docker >/dev/null 2>&1 || { error "未安装 docker"; exit 1; }
    docker compose version >/dev/null 2>&1 || { error "docker compose v2 未安装"; exit 1; }

    if [ ! -f "$ENV_FILE" ]; then
        error "缺少环境变量文件: $ENV_FILE"
        warn "请执行: cp $SCRIPT_DIR/.env.prod.example $ENV_FILE 并填写"
        exit 1
    fi

    # 提醒未替换的 CHANGE_ME
    if grep -q "CHANGE_ME" "$ENV_FILE"; then
        error ".env.prod 中仍有 CHANGE_ME 占位，请先替换成真实密钥！"
        grep -n "CHANGE_ME" "$ENV_FILE" | head -5
        exit 1
    fi
}

compose() {
    docker compose --project-directory "$PROJECT_DIR" \
                   -f "$COMPOSE_FILE" \
                   --env-file "$ENV_FILE" "$@"
}

# ────── 子命令 ──────
cmd_up() {
    preflight
    info "构建镜像（首次需要几分钟）..."
    compose build --pull

    info "启动所有服务..."
    compose up -d

    info "等待服务就绪..."
    sleep 5
    compose ps

    echo
    ok "部署完成。访问入口："
    echo "    前端应用     : http://localhost"
    echo "    API 文档     : http://localhost/docs"
    echo "    健康检查     : http://localhost/health"
    echo "    MinIO 控制台 : http://localhost:9001"
    echo "    PostgreSQL   : 内网仅 (docker compose exec postgres psql -U petfood)"
    echo
    echo "查看日志: $0 logs"
}

cmd_down() {
    info "停止所有服务（保留数据卷）..."
    compose down
    ok "已停止"
}

cmd_clean() {
    warn "⚠️ 此操作会删除所有数据（PostgreSQL / Redis / MinIO 的持久化卷）！"
    read -r -p "输入 YES 确认: " confirm
    [ "$confirm" = "YES" ] || { info "已取消"; exit 0; }
    compose down -v
    ok "清理完成"
}

cmd_logs() {
    if [ -n "${1:-}" ]; then
        compose logs -f --tail=200 "$1"
    else
        compose logs -f --tail=100
    fi
}

cmd_restart() {
    compose restart
    compose ps
}

cmd_ps() {
    compose ps
    echo
    info "资源占用："
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" \
        $(compose ps -q) 2>/dev/null || true
}

cmd_migrate() {
    info "执行 Alembic 迁移..."
    compose exec api alembic upgrade head
    ok "迁移完成"
}

cmd_shell() {
    local svc="${1:-api}"
    compose exec "$svc" sh
}

# ────── 入口 ──────
action="${1:-}"
shift || true
case "$action" in
    up)       cmd_up "$@" ;;
    down)     cmd_down "$@" ;;
    clean)    cmd_clean "$@" ;;
    logs)     cmd_logs "$@" ;;
    restart)  cmd_restart "$@" ;;
    ps|status) cmd_ps "$@" ;;
    migrate)  cmd_migrate "$@" ;;
    shell)    cmd_shell "$@" ;;
    *)
        cat <<EOF
用法: $0 <command>
  up        构建并启动所有服务
  down      停止服务（保留数据）
  clean     停止并删除所有数据卷
  logs [svc] 跟踪日志
  restart   重启所有服务
  ps        查看容器状态和资源占用
  migrate   手动运行数据库迁移
  shell [svc] 进入容器（默认 api）
EOF
        exit 1
        ;;
esac
