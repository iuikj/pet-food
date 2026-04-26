# ~~CD（持续部署）指南~~

> **已废弃**：本文档对应旧的 Webhook / Cron CD 方案，仅保留作历史参考。
> 当前推荐方案请查看 [CD_GITHUB_ACTIONS.md](./CD_GITHUB_ACTIONS.md)。

自动化部署到腾讯云服务器 (81.71.128.32) 的完整方案。

---

## 方案选择

| 方案 | 触发方式 | 实时性 | 复杂度 | 推荐场景 |
|------|----------|--------|--------|----------|
| **方案 1: Webhook** | Git push 触发 | 秒级 | 中 | 生产环境，需要快速迭代 |
| **方案 2: 定时拉取** | Cron 定时检查 | 分钟级 | 低 | 测试环境，更新不频繁 |

---

## 方案 1: Webhook 自动部署（推荐）

### 架构流程

```
开发者 push 代码
    ↓
Git 仓库 (GitHub/GitLab/Gitee)
    ↓ webhook POST
服务器 webhook 接收服务 (端口 9000)
    ↓ 验证签名
执行部署脚本 deploy-webhook.sh
    ↓
1. git pull 拉取最新代码
2. 备份当前版本（用于回滚）
3. docker compose build 构建新镜像
4. docker compose up -d 滚动更新
5. 健康检查
6. 发送通知（可选）
```

### 1.1 安装 Webhook 接收服务

在服务器上安装轻量级 webhook 工具：

```bash
# 方式 1: 使用 webhook (Go 编写，推荐)
wget https://github.com/adnanh/webhook/releases/download/2.8.1/webhook-linux-amd64.tar.gz
tar -xzf webhook-linux-amd64.tar.gz
sudo mv webhook-linux-amd64/webhook /usr/local/bin/
sudo chmod +x /usr/local/bin/webhook

# 方式 2: 使用 Python Flask (如果服务器已有 Python)
# 见下方 webhook_server.py
```

### 1.2 创建 Webhook 配置

创建 `/opt/petfood-cd/hooks.json`：

```json
[
  {
    "id": "deploy-petfood",
    "execute-command": "/opt/petfood-cd/deploy-webhook.sh",
    "command-working-directory": "/opt/petfood",
    "response-message": "Deployment triggered",
    "trigger-rule": {
      "and": [
        {
          "match": {
            "type": "payload-hmac-sha256",
            "secret": "YOUR_WEBHOOK_SECRET_HERE",
            "parameter": {
                "source": "header",
                "name": "X-Hub-Signature-256"
            }
          }
        },
        {
          "match": {
            "type": "value",
            "value": "refs/heads/main",
            "parameter": {
              "source": "payload",
              "name": "ref"
            }
          }
        }
      ]
    }
  }
]
```

**安全说明**：
- `YOUR_WEBHOOK_SECRET_HERE` 替换为强密码（用于验证请求来源）
- `refs/heads/main` 改为你的分支名（如 `master`）

### 1.3 创建部署脚本

创建 `/opt/petfood-cd/deploy-webhook.sh`：

```bash
#!/bin/bash
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
```

赋予执行权限：

```bash
sudo chmod +x /opt/petfood-cd/deploy-webhook.sh
```

### 1.4 启动 Webhook 服务

```bash
# 创建 systemd 服务
sudo tee /etc/systemd/system/petfood-webhook.service > /dev/null <<EOF
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

[Install]
WantedBy=multi-user.target
EOF

# 启动服务
sudo systemctl daemon-reload
sudo systemctl enable petfood-webhook
sudo systemctl start petfood-webhook

# 查看状态
sudo systemctl status petfood-webhook
```

### 1.5 配置防火墙

```bash
# 开放 webhook 端口（仅允许 Git 服务器 IP）
sudo ufw allow from <GIT_SERVER_IP> to any port 9000 proto tcp

# 或者使用 Nginx 反向代理（推荐，可加 HTTPS）
# 在 nginx.conf 添加：
# location /webhook {
#     proxy_pass http://localhost:9000;
# }
```

### 1.6 配置 Git 仓库 Webhook

#### GitHub:
1. 进入仓库 Settings → Webhooks → Add webhook
2. Payload URL: `http://81.71.128.32:9000/hooks/deploy-petfood`
3. Content type: `application/json`
4. Secret: 填入 `hooks.json` 中的 `YOUR_WEBHOOK_SECRET_HERE`
5. 触发事件: 选择 `Just the push event`

#### GitLab:
1. 进入仓库 Settings → Webhooks
2. URL: `http://81.71.128.32:9000/hooks/deploy-petfood`
3. Secret Token: 填入密钥
4. Trigger: 勾选 `Push events`，分支填 `main`

#### Gitee:
1. 进入仓库 管理 → WebHooks
2. URL: `http://81.71.128.32:9000/hooks/deploy-petfood`
3. 密码: 填入密钥
4. 勾选 `Push`

---

## 方案 2: 定时拉取部署（简单）

### 2.1 创建部署脚本

创建 `/opt/petfood-cd/deploy-cron.sh`：

```bash
#!/bin/bash
set -e

PROJECT_DIR="/opt/petfood"
LOG_FILE="/var/log/petfood-deploy.log"
LOCK_FILE="/tmp/petfood-deploy.lock"

# 防止并发执行
if [ -f "$LOCK_FILE" ]; then
    echo "部署正在进行中，跳过" >> "$LOG_FILE"
    exit 0
fi

touch "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

cd "$PROJECT_DIR"

# 检查是否有更新
git fetch origin
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    echo "[$(date)] 无更新" >> "$LOG_FILE"
    exit 0
fi

# 有更新，执行部署（复用方案 1 的脚本逻辑）
echo "[$(date)] 检测到更新，开始部署..." >> "$LOG_FILE"
/opt/petfood-cd/deploy-webhook.sh >> "$LOG_FILE" 2>&1
```

### 2.2 配置 Cron

```bash
# 编辑 crontab
sudo crontab -e

# 添加（每 5 分钟检查一次）
*/5 * * * * /opt/petfood-cd/deploy-cron.sh

# 或每 10 分钟
*/10 * * * * /opt/petfood-cd/deploy-cron.sh
```

---

## 回滚机制

### 快速回滚到上一个版本

创建 `/opt/petfood-cd/rollback.sh`：

```bash
#!/bin/bash
set -e

PROJECT_DIR="/opt/petfood"
BACKUP_DIR="/opt/petfood-backups"
COMPOSE_FILE="$PROJECT_DIR/pet_food_backend/pet-food/deployment/docker-compose.prod.yml"
ENV_FILE="$PROJECT_DIR/pet_food_backend/pet-food/deployment/.env.prod"

echo "可用的备份版本："
ls -lt "$BACKUP_DIR"/*.commit | head -5

read -p "输入要回滚的备份名称（如 backup-20260424-143022）: " BACKUP_NAME

if [ ! -f "$BACKUP_DIR/$BACKUP_NAME.commit" ]; then
    echo "❌ 备份不存在"
    exit 1
fi

COMMIT=$(cat "$BACKUP_DIR/$BACKUP_NAME.commit")
echo "🔄 回滚到提交: $COMMIT"

cd "$PROJECT_DIR"
git reset --hard "$COMMIT"

cd "$PROJECT_DIR/pet_food_backend/pet-food"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --build --force-recreate

echo "✅ 回滚完成"
```

### 使用方式

```bash
sudo /opt/petfood-cd/rollback.sh
```

---

## 部署监控

### 查看部署日志

```bash
# 实时查看
tail -f /var/log/petfood-deploy.log

# 查看最近 50 行
tail -50 /var/log/petfood-deploy.log

# 查看今天的部署
grep "$(date +%Y-%m-%d)" /var/log/petfood-deploy.log
```

### 查看容器状态

```bash
cd /opt/petfood/pet_food_backend/pet-food
./deployment/deploy.sh ps
./deployment/deploy.sh logs api
```

---

## 初始化服务器

首次在服务器上设置 CD 环境：

```bash
# 1. 克隆代码
sudo mkdir -p /opt
cd /opt
sudo git clone <YOUR_REPO_URL> petfood
cd petfood

# 2. 配置环境变量
cd pet_food_backend/pet-food/deployment
sudo cp .env.prod.example .env.prod
sudo nano .env.prod  # 填写密钥

# 3. 创建 CD 目录
sudo mkdir -p /opt/petfood-cd
sudo mkdir -p /opt/petfood-backups

# 4. 复制脚本（从本地上传或直接创建）
# 将上述脚本保存到对应位置

# 5. 首次部署
cd /opt/petfood/pet_food_backend/pet-food
./deployment/deploy.sh up

# 6. 配置 webhook 或 cron（选择方案 1 或 2）
```

---

## 安全建议

1. **SSH 密钥认证**: 服务器禁用密码登录，只允许密钥
2. **Webhook 签名验证**: 必须配置 secret，防止恶意触发
3. **防火墙规则**: 只开放必要端口（80, 443, webhook 端口）
4. **日志轮转**: 配置 logrotate 防止日志文件过大
5. **备份策略**: 定期备份数据库和 MinIO 数据
6. **HTTPS**: 生产环境必须启用 SSL 证书

---

## 故障排查

### Webhook 未触发

```bash
# 检查服务状态
sudo systemctl status petfood-webhook

# 查看日志
sudo journalctl -u petfood-webhook -f

# 测试 webhook
curl -X POST http://localhost:9000/hooks/deploy-petfood \
     -H "Content-Type: application/json" \
     -d '{"ref":"refs/heads/main"}'
```

### 部署失败

```bash
# 查看部署日志
tail -100 /var/log/petfood-deploy.log

# 查看容器日志
cd /opt/petfood/pet_food_backend/pet-food
./deployment/deploy.sh logs

# 手动回滚
sudo /opt/petfood-cd/rollback.sh
```

### Git 权限问题

```bash
# 配置 Git 凭证（如果是私有仓库）
cd /opt/petfood
git config credential.helper store
git pull  # 输入一次用户名密码后会保存

# 或使用 SSH 密钥
ssh-keygen -t ed25519 -C "server@petfood"
cat ~/.ssh/id_ed25519.pub  # 添加到 Git 仓库的 Deploy Keys
```

---

## 下一步优化

1. **添加 CI**: 在部署前运行测试（pytest）
2. **蓝绿部署**: 使用两套环境，零停机切换
3. **金丝雀发布**: 先部署到部分用户，验证后全量
4. **监控告警**: 集成 Prometheus + Grafana
5. **自动化测试**: 部署后自动运行冒烟测试
