#!/bin/bash
# DEPRECATED: legacy webhook deployment script. Use deployment/deploy-ghcr.sh instead.
set -e

# ============================================================
# Pet Food 自动部署脚本 (Webhook 触发)
# ============================================================

PROJECT_DIR="/opt/petfood"
BACKUP_DIR="/opt/petfood-backups"
LOG_FILE="/var/log/petfood-deploy.log"
COMPOSE_FILE="$PROJECT_DIR/pet_food_backend/pet-food/deployment/docker-compose.prod.yml"
ENV_FILE="$PROJECT_DIR/pet_food_backend/pet-food/deployment/.env.prod"

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 错误处理
error_exit() {
    log "❌ 错误: $1"
    exit 1
}

# 发送通知（可选，需配置）
send_notification() {
    # 示例：发送到企业微信机器人
    # curl -X POST "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY" \
    #      -H 'Content-Type: application/json' \
    #      -d "{\"msgtype\":\"text\",\"text\":{\"content\":\"$1\"}}"

    # 或发送到钉钉
    # curl -X POST "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN" \
    #      -H 'Content-Type: application/json' \
    #      -d "{\"msgtype\":\"text\",\"text\":{\"content\":\"$1\"}}"

    log "📢 通知: $1"
}

log "=========================================="
log "🚀 开始部署 Pet Food"
log "=========================================="

# 1. 进入项目目录
cd "$PROJECT_DIR" || error_exit "项目目录不存在"

# 2. 备份当前版本（用于回滚）
BACKUP_NAME="backup-$(date +%Y%m%d-%H%M%S)"
log "📦 备份当前版本到 $BACKUP_DIR/$BACKUP_NAME"
mkdir -p "$BACKUP_DIR"
git rev-parse HEAD > "$BACKUP_DIR/$BACKUP_NAME.commit" || true

# 3. 拉取最新代码
log "📥 拉取最新代码..."
git fetch origin || error_exit "git fetch 失败"
BEFORE_COMMIT=$(git rev-parse HEAD)
git reset --hard origin/main || error_exit "git reset 失败"
AFTER_COMMIT=$(git rev-parse HEAD)

if [ "$BEFORE_COMMIT" = "$AFTER_COMMIT" ]; then
    log "✅ 代码无变化，跳过部署"
    exit 0
fi

log "📝 代码更新: $BEFORE_COMMIT -> $AFTER_COMMIT"

# 4. 检查环境变量文件
if [ ! -f "$ENV_FILE" ]; then
    error_exit ".env.prod 文件不存在"
fi

# 5. 构建新镜像
log "🔨 构建 Docker 镜像..."
cd "$PROJECT_DIR/pet_food_backend/pet-food" || error_exit "后端目录不存在"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build --no-cache || error_exit "构建失败"

# 6. 滚动更新服务
log "🔄 更新服务..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d || error_exit "启动失败"

# 7. 等待服务就绪
log "⏳ 等待服务启动..."
sleep 10

# 8. 健康检查
log "🏥 健康检查..."
MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -f http://localhost/health > /dev/null 2>&1; then
        log "✅ 健康检查通过"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    log "⏳ 等待服务就绪... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    log "❌ 健康检查失败，开始回滚..."
    git reset --hard "$BEFORE_COMMIT"
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --force-recreate
    send_notification "❌ Pet Food 部署失败，已回滚到 $BEFORE_COMMIT"
    error_exit "健康检查超时"
fi

# 9. 清理旧镜像
log "🧹 清理旧镜像..."
docker image prune -f || true

# 10. 完成
log "=========================================="
log "✅ 部署成功！"
log "   提交: $AFTER_COMMIT"
log "   时间: $(date '+%Y-%m-%d %H:%M:%S')"
log "=========================================="

send_notification "✅ Pet Food 部署成功！提交: ${AFTER_COMMIT:0:8}"
