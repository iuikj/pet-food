#!/usr/bin/env bash
# API 容器入口：等待依赖服务 → 跑数据库迁移 → 启动 uvicorn
# 原则：幂等、失败即退、日志清晰

set -euo pipefail

log() { echo "[entrypoint $(date +%H:%M:%S)] $*"; }

# ─────────────────────────────────────────────────────────
# 1. 等待 PostgreSQL 就绪（最多 60s）
# ─────────────────────────────────────────────────────────
wait_for_postgres() {
    local host="${POSTGRES_HOST:-postgres}"
    local port="${POSTGRES_PORT:-5432}"
    local max_attempts=30

    log "等待 PostgreSQL ${host}:${port} ..."
    for i in $(seq 1 "$max_attempts"); do
        if python -c "
import socket, sys
s = socket.socket()
s.settimeout(2)
try:
    s.connect(('${host}', ${port}))
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
            log "PostgreSQL 就绪 (attempt $i)"
            return 0
        fi
        sleep 2
    done
    log "PostgreSQL 等待超时"
    return 1
}

# ─────────────────────────────────────────────────────────
# 2. 等待 Redis 就绪
# ─────────────────────────────────────────────────────────
wait_for_redis() {
    local host="${REDIS_HOST:-redis}"
    local port="${REDIS_PORT:-6379}"
    log "等待 Redis ${host}:${port} ..."
    for i in $(seq 1 15); do
        if python -c "
import socket, sys
s = socket.socket()
s.settimeout(2)
try:
    s.connect(('${host}', ${port}))
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
            log "Redis 就绪"
            return 0
        fi
        sleep 2
    done
    log "Redis 等待超时（非致命，继续）"
    return 0
}

# ─────────────────────────────────────────────────────────
# 3. 运行 Alembic 迁移（幂等）
# ─────────────────────────────────────────────────────────
run_migrations() {
    if [ "${SKIP_MIGRATIONS:-false}" = "true" ]; then
        log "SKIP_MIGRATIONS=true 跳过迁移"
        return 0
    fi

    log "执行 Alembic 数据库迁移..."
    cd /app
    if alembic upgrade head; then
        log "迁移完成"
        return 0
    fi

    # 迁移失败时的策略：
    #   - 默认退出（让 restart policy 拉起重试，避免 schema 不一致跑业务）
    #   - 设置 ALLOW_MIGRATION_FAILURE=true 可降级为 warning（仅调试用）
    if [ "${ALLOW_MIGRATION_FAILURE:-false}" = "true" ]; then
        log "迁移失败，但 ALLOW_MIGRATION_FAILURE=true，继续启动"
        return 0
    fi

    log "迁移失败 → 退出。请查看上方 alembic 报错，修复后重启容器。"
    log "如需先以缺陷状态启动调试，临时设置 ALLOW_MIGRATION_FAILURE=true"
    exit 1
}

# ─────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────
# 从 DATABASE_URL 解析 host（如已显式设置 POSTGRES_HOST 则优先）
if [ -z "${POSTGRES_HOST:-}" ] && [ -n "${DATABASE_URL:-}" ]; then
    # postgresql+asyncpg://user:pass@HOST:PORT/db
    host_port="${DATABASE_URL##*@}"       # user:pass@HOST:PORT/db -> HOST:PORT/db
    host_port="${host_port%%/*}"          # HOST:PORT
    export POSTGRES_HOST="${host_port%%:*}"
    export POSTGRES_PORT="${host_port##*:}"
fi

wait_for_postgres
wait_for_redis
run_migrations

log "启动应用: $*"
exec "$@"
