#!/bin/bash
# DEPRECATED: legacy rollback helper for the webhook-based deployment path.
set -e

# ============================================================
# Pet Food 回滚脚本
# ============================================================

PROJECT_DIR="/opt/petfood"
BACKUP_DIR="/opt/petfood-backups"
COMPOSE_FILE="$PROJECT_DIR/pet_food_backend/pet-food/deployment/docker-compose.prod.yml"
ENV_FILE="$PROJECT_DIR/pet_food_backend/pet-food/deployment/.env.prod"

echo "=========================================="
echo "🔄 Pet Food 回滚工具"
echo "=========================================="
echo ""

# 检查备份目录
if [ ! -d "$BACKUP_DIR" ]; then
    echo "❌ 备份目录不存在: $BACKUP_DIR"
    exit 1
fi

# 列出可用备份
echo "📦 可用的备份版本（最近 10 个）："
echo ""
ls -lt "$BACKUP_DIR"/*.commit 2>/dev/null | head -10 | while read -r line; do
    file=$(echo "$line" | awk '{print $NF}')
    backup_name=$(basename "$file" .commit)
    commit=$(cat "$file")
    echo "  - $backup_name (提交: ${commit:0:8})"
done

echo ""
echo "=========================================="
read -p "输入要回滚的备份名称（如 backup-20260424-143022）: " BACKUP_NAME

if [ -z "$BACKUP_NAME" ]; then
    echo "❌ 未输入备份名称"
    exit 1
fi

if [ ! -f "$BACKUP_DIR/$BACKUP_NAME.commit" ]; then
    echo "❌ 备份不存在: $BACKUP_NAME"
    exit 1
fi

COMMIT=$(cat "$BACKUP_DIR/$BACKUP_NAME.commit")
echo ""
echo "🔄 准备回滚到:"
echo "   备份: $BACKUP_NAME"
echo "   提交: $COMMIT"
echo ""
read -p "确认回滚？(yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "❌ 已取消回滚"
    exit 0
fi

echo ""
echo "🔄 开始回滚..."

# 1. 回滚代码
echo "📥 回滚代码到 $COMMIT"
cd "$PROJECT_DIR" || exit 1
git reset --hard "$COMMIT"

# 2. 重新构建和部署
echo "🔨 重新构建镜像..."
cd "$PROJECT_DIR/pet_food_backend/pet-food" || exit 1
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build --no-cache

echo "🔄 重启服务..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --force-recreate

# 3. 等待服务就绪
echo "⏳ 等待服务启动..."
sleep 10

# 4. 健康检查
echo "🏥 健康检查..."
MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -f http://localhost/health > /dev/null 2>&1; then
        echo "✅ 健康检查通过"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "⏳ 等待服务就绪... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ 健康检查失败！请手动检查服务状态"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ 回滚完成！"
echo "   当前提交: $COMMIT"
echo "=========================================="
