#!/bin/bash
# DEPRECATED: legacy one-shot setup for the webhook/tag deployment route.
# ============================================================
# Pet Food CD 一键配置脚本（针对腾讯云 81.71.128.32）
# 使用方式：在服务器上执行 bash setup-cd.sh
# ============================================================

set -e

echo "=========================================="
echo "🚀 Pet Food CD 自动配置脚本"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查是否为 root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ 请使用 root 权限运行此脚本${NC}"
    echo "   sudo bash setup-cd.sh"
    exit 1
fi

# 检查项目目录
PROJECT_DIR="/opt/petfood"
if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${RED}❌ 项目目录不存在: $PROJECT_DIR${NC}"
    echo "   请先部署项目到 /opt/petfood"
    exit 1
fi

echo -e "${GREEN}✓${NC} 项目目录检查通过"

# 步骤 1: 安装 webhook
echo ""
echo "步骤 1/5: 安装 Webhook 工具"
echo "----------------------------------------"

if command -v webhook &> /dev/null; then
    echo -e "${YELLOW}⚠${NC} Webhook 已安装，跳过"
else
    echo "正在下载 webhook..."
    cd /tmp
    wget -q https://github.com/adnanh/webhook/releases/download/2.8.1/webhook-linux-amd64.tar.gz
    tar -xzf webhook-linux-amd64.tar.gz
    mv webhook-linux-amd64/webhook /usr/local/bin/
    chmod +x /usr/local/bin/webhook
    rm -rf webhook-linux-amd64*
    echo -e "${GREEN}✓${NC} Webhook 安装完成"
fi

# 步骤 2: 创建目录
echo ""
echo "步骤 2/5: 创建 CD 目录"
echo "----------------------------------------"

mkdir -p /opt/petfood-cd
mkdir -p /opt/petfood-backups
echo -e "${GREEN}✓${NC} 目录创建完成"

# 步骤 3: 生成 webhook 密钥
echo ""
echo "步骤 3/5: 生成 Webhook 密钥"
echo "----------------------------------------"

WEBHOOK_SECRET=$(openssl rand -hex 32)
echo -e "${GREEN}✓${NC} 密钥已生成"
echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}⚠ 重要：请保存以下密钥，配置 GitHub Webhook 时需要${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  $WEBHOOK_SECRET"
echo ""
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
read -p "按回车键继续..."

# 步骤 4: 创建配置文件
echo ""
echo "步骤 4/5: 创建配置文件"
echo "----------------------------------------"

# 创建 hooks.json
cat > /opt/petfood-cd/hooks.json <<EOF
[
  {
    "id": "deploy-petfood-tag",
    "execute-command": "/opt/petfood-cd/deploy-tag.sh",
    "command-working-directory": "/opt/petfood",
    "response-message": "Tag deployment triggered",
    "pass-arguments-to-command": [
      {
        "source": "payload",
        "name": "ref"
      }
    ],
    "trigger-rule": {
      "and": [
        {
          "match": {
            "type": "payload-hmac-sha256",
            "secret": "$WEBHOOK_SECRET",
            "parameter": {
              "source": "header",
              "name": "X-Hub-Signature-256"
            }
          }
        },
        {
          "match": {
            "type": "regex",
            "regex": "^refs/tags/v[0-9]+\\\\.[0-9]+\\\\.[0-9]+$",
            "parameter": {
              "source": "payload",
              "name": "ref"
            }
          }
        }
      ]
    },
    "trigger-rule-mismatch-http-response-code": 400
  }
]
EOF

echo -e "${GREEN}✓${NC} hooks.json 创建完成"

# 创建部署脚本
cat > /opt/petfood-cd/deploy-tag.sh <<'EOFSCRIPT'
#!/bin/bash
set -e

PROJECT_DIR="/opt/petfood"
BACKUP_DIR="/opt/petfood-backups"
LOG_FILE="/var/log/petfood-deploy.log"
COMPOSE_FILE="$PROJECT_DIR/pet_food_backend/pet-food/deployment/docker-compose.prod.yml"
ENV_FILE="$PROJECT_DIR/pet_food_backend/pet-food/deployment/.env.prod"

# 从 webhook payload 提取标签名
TAG_REF="${1:-unknown}"
TAG_NAME=$(echo "$TAG_REF" | sed 's|refs/tags/||')

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error_exit() {
    log "❌ 错误: $1"
    exit 1
}

log "=========================================="
log "🚀 开始部署 Pet Food - 版本: $TAG_NAME"
log "=========================================="

cd "$PROJECT_DIR" || error_exit "项目目录不存在"

# 备份
BACKUP_NAME="backup-$(date +%Y%m%d-%H%M%S)-$TAG_NAME"
log "📦 备份当前版本: $BACKUP_NAME"
mkdir -p "$BACKUP_DIR"
git rev-parse HEAD > "$BACKUP_DIR/$BACKUP_NAME.commit" 2>/dev/null || true
echo "$TAG_NAME" > "$BACKUP_DIR/$BACKUP_NAME.tag"

# 拉取标签
log "📥 拉取标签 $TAG_NAME..."
git fetch --tags origin || error_exit "git fetch 失败"
BEFORE_COMMIT=$(git rev-parse HEAD)

# 切换标签
log "🔄 切换到标签 $TAG_NAME..."
git checkout "tags/$TAG_NAME" || error_exit "切换标签失败"
AFTER_COMMIT=$(git rev-parse HEAD)

if [ "$BEFORE_COMMIT" = "$AFTER_COMMIT" ]; then
    log "✅ 代码无变化，跳过部署"
    exit 0
fi

log "📝 版本更新: $BEFORE_COMMIT -> $AFTER_COMMIT"

# 检查环境文件
if [ ! -f "$ENV_FILE" ]; then
    error_exit ".env.prod 文件不存在"
fi

# 构建镜像
log "🔨 构建 Docker 镜像..."
cd "$PROJECT_DIR/pet_food_backend/pet-food" || error_exit "后端目录不存在"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build --no-cache || error_exit "构建失败"

# 更新服务
log "🔄 更新服务..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d || error_exit "启动失败"

# 等待启动
log "⏳ 等待服务启动..."
sleep 10

# 健康检查
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
    git checkout "$BEFORE_COMMIT"
    docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --force-recreate
    error_exit "健康检查超时，已回滚"
fi

# 清理
log "🧹 清理旧镜像..."
docker image prune -f || true

log "=========================================="
log "✅ 部署成功！"
log "   版本标签: $TAG_NAME"
log "   提交: $AFTER_COMMIT"
log "   时间: $(date '+%Y-%m-%d %H:%M:%S')"
log "=========================================="
EOFSCRIPT

chmod +x /opt/petfood-cd/deploy-tag.sh
echo -e "${GREEN}✓${NC} deploy-tag.sh 创建完成"

# 创建回滚脚本
cat > /opt/petfood-cd/rollback-tag.sh <<'EOFROLLBACK'
#!/bin/bash
set -e

echo "=========================================="
echo "🔄 Pet Food 版本回滚工具"
echo "=========================================="
echo ""

cd /opt/petfood

echo "📦 可用的版本标签（最近 10 个）："
git tag -l --sort=-version:refname | head -10

echo ""
read -p "输入要回滚的版本标签（如 v1.1.0）: " TAG_NAME

if [ -z "$TAG_NAME" ]; then
    echo "❌ 未输入版本标签"
    exit 1
fi

if ! git rev-parse "tags/$TAG_NAME" > /dev/null 2>&1; then
    echo "❌ 标签不存在: $TAG_NAME"
    exit 1
fi

echo ""
echo "🔄 准备回滚到版本: $TAG_NAME"
read -p "确认回滚？(yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "❌ 已取消回滚"
    exit 0
fi

/opt/petfood-cd/deploy-tag.sh "refs/tags/$TAG_NAME"
EOFROLLBACK

chmod +x /opt/petfood-cd/rollback-tag.sh
echo -e "${GREEN}✓${NC} rollback-tag.sh 创建完成"

# 步骤 5: 配置 systemd 服务
echo ""
echo "步骤 5/5: 配置 Webhook 服务"
echo "----------------------------------------"

cat > /etc/systemd/system/petfood-webhook.service <<EOF
[Unit]
Description=Pet Food Webhook Service
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/petfood-cd
ExecStart=/usr/local/bin/webhook -hooks /opt/petfood-cd/hooks.json -port 9000 -verbose
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable petfood-webhook
systemctl start petfood-webhook

echo -e "${GREEN}✓${NC} Webhook 服务已启动"

# 验证服务状态
sleep 2
if systemctl is-active --quiet petfood-webhook; then
    echo -e "${GREEN}✓${NC} 服务运行正常"
else
    echo -e "${RED}❌ 服务启动失败${NC}"
    systemctl status petfood-webhook
    exit 1
fi

# 完成
echo ""
echo "=========================================="
echo -e "${GREEN}✅ CD 配置完成！${NC}"
echo "=========================================="
echo ""
echo "📋 下一步操作："
echo ""
echo "1. 在 GitHub 仓库配置 Webhook："
echo "   - URL: http://81.71.128.32:9000/hooks/deploy-petfood-tag"
echo "   - Content type: application/json"
echo "   - Secret: (使用上面保存的密钥)"
echo "   - 事件: 只勾选 'Branch or tag creation'"
echo ""
echo "2. 测试部署："
echo "   git tag -a v1.0.1 -m 'Test deployment'"
echo "   git push origin v1.0.1"
echo ""
echo "3. 查看部署日志："
echo "   tail -f /var/log/petfood-deploy.log"
echo ""
echo "4. 查看 webhook 日志："
echo "   journalctl -u petfood-webhook -f"
echo ""
echo "5. 手动回滚："
echo "   /opt/petfood-cd/rollback-tag.sh"
echo ""
echo "=========================================="
echo ""
echo -e "${YELLOW}⚠ 重要提醒：${NC}"
echo "  - 请保存好 Webhook 密钥"
echo "  - 建议配置防火墙规则限制访问"
echo "  - 生产环境建议启用 HTTPS"
echo ""
echo "详细文档: /opt/petfood/pet_food_backend/pet-food/deployment/CD_TAG_BASED.md"
echo ""
