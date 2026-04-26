# ~~基于版本标签的 CD 部署指南~~

> **已废弃**：本文档基于 `webhook` 触发标签部署，仅保留作历史参考。
> 当前推荐方案请查看 [CD_GITHUB_ACTIONS.md](./CD_GITHUB_ACTIONS.md)。

针对腾讯云 81.71.128.32 服务器的定制化 CD 方案。

---

## 🎯 部署策略

**触发条件**：仅在推送版本标签时触发部署（如 `v1.0.0`, `v1.2.0`）  
**优势**：
- ✅ 避免每次 commit 都部署，减少不必要的部署
- ✅ 版本管理清晰，便于回滚
- ✅ 生产环境更稳定，只部署经过验证的版本

---

## 📋 快速配置（5 步）

### 第 1 步：SSH 登录服务器，配置 CD 环境

```bash
# SSH 登录
ssh root@81.71.128.32

# 创建 CD 目录
sudo mkdir -p /opt/petfood-cd
sudo mkdir -p /opt/petfood-backups

# 确认项目路径（假设已部署在 /opt/petfood）
cd /opt/petfood
pwd  # 应该显示 /opt/petfood
```

### 第 2 步：安装 Webhook 工具

```bash
# 下载 webhook
cd /tmp
wget https://github.com/adnanh/webhook/releases/download/2.8.1/webhook-linux-amd64.tar.gz
tar -xzf webhook-linux-amd64.tar.gz
sudo mv webhook-linux-amd64/webhook /usr/local/bin/
sudo chmod +x /usr/local/bin/webhook

# 验证安装
webhook -version
```

### 第 3 步：创建部署脚本

创建 `/opt/petfood-cd/deploy-tag.sh`：

```bash
sudo tee /opt/petfood-cd/deploy-tag.sh > /dev/null <<'EOF'
#!/bin/bash
set -e

# ============================================================
# Pet Food 版本标签部署脚本
# ============================================================

PROJECT_DIR="/opt/petfood"
BACKUP_DIR="/opt/petfood-backups"
LOG_FILE="/var/log/petfood-deploy.log"
COMPOSE_FILE="$PROJECT_DIR/pet_food_backend/pet-food/deployment/docker-compose.prod.yml"
ENV_FILE="$PROJECT_DIR/pet_food_backend/pet-food/deployment/.env.prod"

# 从环境变量获取标签名
TAG_NAME="${1:-unknown}"

# 日志函数
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

# 1. 进入项目目录
cd "$PROJECT_DIR" || error_exit "项目目录不存在"

# 2. 备份当前版本
BACKUP_NAME="backup-$(date +%Y%m%d-%H%M%S)-$TAG_NAME"
log "📦 备份当前版本到 $BACKUP_DIR/$BACKUP_NAME"
mkdir -p "$BACKUP_DIR"
git rev-parse HEAD > "$BACKUP_DIR/$BACKUP_NAME.commit" || true
echo "$TAG_NAME" > "$BACKUP_DIR/$BACKUP_NAME.tag"

# 3. 拉取最新代码
log "📥 拉取标签 $TAG_NAME..."
git fetch --tags origin || error_exit "git fetch 失败"
BEFORE_COMMIT=$(git rev-parse HEAD)

# 4. 切换到指定标签
log "🔄 切换到标签 $TAG_NAME..."
git checkout "tags/$TAG_NAME" || error_exit "切换标签失败"
AFTER_COMMIT=$(git rev-parse HEAD)

if [ "$BEFORE_COMMIT" = "$AFTER_COMMIT" ]; then
    log "✅ 代码无变化，跳过部署"
    exit 0
fi

log "📝 版本更新: $BEFORE_COMMIT -> $AFTER_COMMIT (标签: $TAG_NAME)"

# 5. 检查环境变量文件
if [ ! -f "$ENV_FILE" ]; then
    error_exit ".env.prod 文件不存在"
fi

# 6. 构建新镜像
log "🔨 构建 Docker 镜像..."
cd "$PROJECT_DIR/pet_food_backend/pet-food" || error_exit "后端目录不存在"
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build --no-cache || error_exit "构建失败"

# 7. 滚动更新服务
log "🔄 更新服务..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d || error_exit "启动失败"

# 8. 等待服务就绪
log "⏳ 等待服务启动..."
sleep 10

# 9. 健康检查
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

# 10. 清理旧镜像
log "🧹 清理旧镜像..."
docker image prune -f || true

# 11. 完成
log "=========================================="
log "✅ 部署成功！"
log "   版本标签: $TAG_NAME"
log "   提交: $AFTER_COMMIT"
log "   时间: $(date '+%Y-%m-%d %H:%M:%S')"
log "=========================================="

# 可选：发送通知（企业微信/钉钉）
# curl -X POST "YOUR_WEBHOOK_URL" \
#      -H 'Content-Type: application/json' \
#      -d "{\"msgtype\":\"text\",\"text\":{\"content\":\"✅ Pet Food $TAG_NAME 部署成功！\"}}"
EOF

# 赋予执行权限
sudo chmod +x /opt/petfood-cd/deploy-tag.sh
```

### 第 4 步：配置 Webhook

创建 `/opt/petfood-cd/hooks.json`：

```bash
# 生成 webhook 密钥
WEBHOOK_SECRET=$(openssl rand -hex 32)
echo "你的 Webhook 密钥（请保存）: $WEBHOOK_SECRET"

# 创建配置文件
sudo tee /opt/petfood-cd/hooks.json > /dev/null <<EOF
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
    "pass-environment-to-command": [
      {
        "envname": "TAG_NAME",
        "source": "string",
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
            "regex": "^refs/tags/v[0-9]+\\.[0-9]+\\.[0-9]+$",
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
```

**重要**：记下生成的 `WEBHOOK_SECRET`，后面配置 GitHub 时需要用到。

### 第 5 步：启动 Webhook 服务

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
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# 启动服务
sudo systemctl daemon-reload
sudo systemctl enable petfood-webhook
sudo systemctl start petfood-webhook

# 验证服务状态
sudo systemctl status petfood-webhook
```

### 第 6 步：配置防火墙（可选但推荐）

```bash
# 方式 1: 只允许 GitHub IP 访问（推荐）
# GitHub Webhook IP 段：https://api.github.com/meta
sudo ufw allow from 140.82.112.0/20 to any port 9000 proto tcp
sudo ufw allow from 143.55.64.0/20 to any port 9000 proto tcp
sudo ufw allow from 192.30.252.0/22 to any port 9000 proto tcp

# 方式 2: 使用 Nginx 反向代理（更安全，支持 HTTPS）
# 见下方 Nginx 配置
```

---

## 🔧 GitHub 仓库配置

### 1. 添加 Webhook

1. 进入你的 GitHub 仓库
2. 点击 **Settings** → **Webhooks** → **Add webhook**
3. 填写配置：
   - **Payload URL**: `http://81.71.128.32:9000/hooks/deploy-petfood-tag`
   - **Content type**: `application/json`
   - **Secret**: 填入第 4 步生成的 `WEBHOOK_SECRET`
   - **Which events**: 选择 **Let me select individual events**
     - ✅ 只勾选 **Branch or tag creation**
     - ❌ 取消勾选其他所有事件
   - **Active**: ✅ 勾选
4. 点击 **Add webhook**

### 2. 验证 Webhook

GitHub 会自动发送一个 ping 请求，查看是否返回绿色的 ✓。

---

## 🚀 使用方式

### 发布新版本

```bash
# 1. 在本地开发完成后，打标签
git tag -a v1.2.0 -m "Release version 1.2.0"

# 2. 推送标签到 GitHub
git push origin v1.2.0

# 3. 自动触发部署！
# 服务器会自动：
#   - 拉取 v1.2.0 标签
#   - 构建新镜像
#   - 滚动更新服务
#   - 健康检查
#   - 失败自动回滚
```

### 查看部署日志

```bash
# SSH 登录服务器
ssh root@81.71.128.32

# 实时查看部署日志
tail -f /var/log/petfood-deploy.log

# 查看最近的部署
tail -50 /var/log/petfood-deploy.log

# 查看 webhook 服务日志
sudo journalctl -u petfood-webhook -f
```

---

## 🔄 回滚操作

### 快速回滚到上一个版本

```bash
# SSH 登录服务器
ssh root@81.71.128.32

# 查看可用的备份版本
ls -lt /opt/petfood-backups/*.tag | head -10

# 回滚到指定版本（例如 v1.1.0）
cd /opt/petfood
git checkout tags/v1.1.0
cd pet_food_backend/pet-food
./deployment/deploy.sh restart
```

### 使用回滚脚本

```bash
# 创建回滚脚本
sudo tee /opt/petfood-cd/rollback-tag.sh > /dev/null <<'EOF'
#!/bin/bash
set -e

echo "=========================================="
echo "🔄 Pet Food 版本回滚工具"
echo "=========================================="
echo ""

# 列出最近的标签
echo "📦 可用的版本标签（最近 10 个）："
cd /opt/petfood
git tag -l --sort=-version:refname | head -10

echo ""
read -p "输入要回滚的版本标签（如 v1.1.0）: " TAG_NAME

if [ -z "$TAG_NAME" ]; then
    echo "❌ 未输入版本标签"
    exit 1
fi

# 验证标签存在
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

# 执行回滚
/opt/petfood-cd/deploy-tag.sh "$TAG_NAME"
EOF

sudo chmod +x /opt/petfood-cd/rollback-tag.sh

# 使用方式
sudo /opt/petfood-cd/rollback-tag.sh
```

---

## 🔒 安全加固（生产必做）

### 1. 使用 Nginx 反向代理（推荐）

在 `/opt/petfood/pet_food_backend/pet-food/deployment/nginx/nginx.conf` 添加：

```nginx
# 在 http 块内添加
upstream webhook {
    server localhost:9000;
}

# 在 server 块内添加
location /webhook {
    # 只允许 GitHub IP
    allow 140.82.112.0/20;
    allow 143.55.64.0/20;
    allow 192.30.252.0/22;
    deny all;

    proxy_pass http://webhook/hooks/deploy-petfood-tag;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

然后 GitHub Webhook URL 改为：`http://81.71.128.32/webhook`

### 2. 配置 HTTPS（强烈推荐）

```bash
# 安装 certbot
sudo apt install certbot

# 申请证书（假设你有域名 petfood.example.com）
sudo certbot certonly --standalone -d petfood.example.com

# 更新 .env.prod
sudo nano /opt/petfood/pet_food_backend/pet-food/deployment/.env.prod
# 修改：
# VITE_API_BASE_URL=https://petfood.example.com/api/v1
# MINIO_PUBLIC_ENDPOINT=https://petfood.example.com/minio-api

# 重新构建前端
cd /opt/petfood/pet_food_backend/pet-food
./deployment/deploy.sh restart
```

### 3. 配置日志轮转

```bash
sudo tee /etc/logrotate.d/petfood > /dev/null <<EOF
/var/log/petfood-deploy.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0644 root root
}
EOF
```

---

## 📊 监控和通知

### 企业微信通知

在 `deploy-tag.sh` 末尾取消注释并配置：

```bash
# 企业微信机器人
WEBHOOK_URL="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"
curl -X POST "$WEBHOOK_URL" \
     -H 'Content-Type: application/json' \
     -d "{\"msgtype\":\"text\",\"text\":{\"content\":\"✅ Pet Food $TAG_NAME 部署成功！\\n提交: ${AFTER_COMMIT:0:8}\\n时间: $(date '+%Y-%m-%d %H:%M:%S')\"}}"
```

### 钉钉通知

```bash
# 钉钉机器人
WEBHOOK_URL="https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN"
curl -X POST "$WEBHOOK_URL" \
     -H 'Content-Type: application/json' \
     -d "{\"msgtype\":\"text\",\"text\":{\"content\":\"✅ Pet Food $TAG_NAME 部署成功！\"}}"
```

---

## 🧪 测试部署

### 1. 本地测试标签推送

```bash
# 创建测试标签
git tag -a v1.0.1 -m "Test deployment"
git push origin v1.0.1

# 观察服务器日志
ssh root@81.71.128.32 "tail -f /var/log/petfood-deploy.log"
```

### 2. 手动触发测试

```bash
# 在服务器上手动执行
sudo /opt/petfood-cd/deploy-tag.sh v1.0.1
```

---

## ❓ 故障排查

### Webhook 未触发

```bash
# 1. 检查服务状态
sudo systemctl status petfood-webhook

# 2. 查看服务日志
sudo journalctl -u petfood-webhook -f

# 3. 检查 GitHub Webhook 日志
# 在 GitHub 仓库 Settings → Webhooks → 点击你的 webhook → Recent Deliveries

# 4. 测试端口连通性
curl http://81.71.128.32:9000/hooks/deploy-petfood-tag
```

### 部署失败

```bash
# 查看部署日志
tail -100 /var/log/petfood-deploy.log

# 查看容器状态
cd /opt/petfood/pet_food_backend/pet-food
./deployment/deploy.sh ps
./deployment/deploy.sh logs api
```

### 标签正则不匹配

当前配置只匹配 `v1.0.0` 格式（语义化版本）。如果你使用其他格式：

```bash
# 修改 hooks.json 中的正则
sudo nano /opt/petfood-cd/hooks.json

# 示例：匹配 v1.0, v1.2 等
"regex": "^refs/tags/v[0-9]+\\.[0-9]+$"

# 示例：匹配所有 v 开头的标签
"regex": "^refs/tags/v.*$"

# 重启服务
sudo systemctl restart petfood-webhook
```

---

## ✅ 完成检查清单

- [ ] Webhook 工具已安装
- [ ] 部署脚本已创建并赋予执行权限
- [ ] Webhook 配置文件已创建，密钥已保存
- [ ] Webhook 服务已启动并设置开机自启
- [ ] GitHub Webhook 已配置，ping 测试通过
- [ ] 防火墙规则已配置（可选）
- [ ] 推送测试标签，部署成功
- [ ] 日志轮转已配置
- [ ] 通知已配置（可选）

---

## 📚 相关文档

- [完整 CD 指南](./CD_GUIDE.md) - 包含 Cron 方案和更多高级功能
- [部署手册](./README.md) - Docker 部署基础
- [故障排查](./TROUBLESHOOTING.md) - 常见问题解决方案

---

## 🎉 完成！

现在你的 CD 流程已配置完成：

✅ 只在推送版本标签时触发部署  
✅ 自动构建、更新、健康检查  
✅ 失败自动回滚  
✅ 完整的部署日志  
✅ 支持手动回滚到任意版本

**下次发布新版本时，只需：**
```bash
git tag -a v1.2.0 -m "Release 1.2.0"
git push origin v1.2.0
```

就会自动部署到云服务器！🚀
