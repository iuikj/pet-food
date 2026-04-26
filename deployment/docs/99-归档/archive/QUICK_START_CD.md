# ~~Pet Food CD 快速部署指南~~

> **已废弃**：本文档对应旧的 Webhook / Cron 快速配置方案，仅保留作历史参考。
> 当前推荐方案请查看 [CD_GITHUB_ACTIONS.md](./CD_GITHUB_ACTIONS.md)。

本指南帮助你在 **5 分钟内** 在服务器上配置好 CD 环境。

---

## 前置条件

- 服务器：腾讯云 81.71.128.32（或其他 Linux 服务器）
- 已安装：Docker, Docker Compose, Git, curl
- 已有 SSH 访问权限

---

## 方案选择

**推荐方案 1（Webhook）**：代码 push 后秒级自动部署  
**备选方案 2（Cron）**：每 5-10 分钟自动检查更新

---

## 方案 1: Webhook 自动部署（5 步）

### 第 1 步：初始化服务器环境

SSH 登录服务器后执行：

```bash
# 克隆代码到 /opt/petfood
sudo mkdir -p /opt
cd /opt
sudo git clone <YOUR_REPO_URL> petfood

# 配置环境变量
cd petfood/pet_food_backend/pet-food/deployment
sudo cp .env.prod.example .env.prod
sudo nano .env.prod  # 填写必需的密钥（JWT_SECRET_KEY, POSTGRES_PASSWORD 等）

# 首次部署（验证配置正确）
./deploy.sh up
```

### 第 2 步：安装 Webhook 工具

```bash
# 下载 webhook 二进制
cd /tmp
wget https://github.com/adnanh/webhook/releases/download/2.8.1/webhook-linux-amd64.tar.gz
tar -xzf webhook-linux-amd64.tar.gz
sudo mv webhook-linux-amd64/webhook /usr/local/bin/
sudo chmod +x /usr/local/bin/webhook

# 验证安装
webhook -version
```

### 第 3 步：配置 CD 脚本

```bash
# 创建 CD 目录
sudo mkdir -p /opt/petfood-cd
sudo mkdir -p /opt/petfood-backups

# 复制脚本到 CD 目录
sudo cp /opt/petfood/pet_food_backend/pet-food/deployment/deploy-webhook.sh /opt/petfood-cd/
sudo cp /opt/petfood/pet_food_backend/pet-food/deployment/rollback.sh /opt/petfood-cd/
sudo cp /opt/petfood/pet_food_backend/pet-food/deployment/hooks.json /opt/petfood-cd/

# 赋予执行权限
sudo chmod +x /opt/petfood-cd/*.sh

# 配置 webhook 密钥
sudo nano /opt/petfood-cd/hooks.json
# 将 "CHANGE_ME_TO_YOUR_WEBHOOK_SECRET" 改为强密码（至少 32 位随机字符）
# 生成密钥：openssl rand -hex 32
```

### 第 4 步：启动 Webhook 服务

```bash
# 复制 systemd 服务文件
sudo cp /opt/petfood/pet_food_backend/pet-food/deployment/petfood-webhook.service /etc/systemd/system/

# 启动服务
sudo systemctl daemon-reload
sudo systemctl enable petfood-webhook
sudo systemctl start petfood-webhook

# 验证服务状态
sudo systemctl status petfood-webhook

# 查看日志
sudo journalctl -u petfood-webhook -f
```

### 第 5 步：配置 Git 仓库 Webhook

#### GitHub:
1. 进入仓库 **Settings** → **Webhooks** → **Add webhook**
2. **Payload URL**: `http://81.71.128.32:9000/hooks/deploy-petfood`
3. **Content type**: `application/json`
4. **Secret**: 填入第 3 步配置的密钥
5. **触发事件**: 选择 `Just the push event`
6. **Active**: 勾选
7. 点击 **Add webhook**

#### GitLab:
1. 进入仓库 **Settings** → **Webhooks**
2. **URL**: `http://81.71.128.32:9000/hooks/deploy-petfood`
3. **Secret Token**: 填入密钥
4. **Trigger**: 勾选 `Push events`，分支填 `main`
5. 点击 **Add webhook**

#### Gitee:
1. 进入仓库 **管理** → **WebHooks**
2. **URL**: `http://81.71.128.32:9000/hooks/deploy-petfood`
3. **密码**: 填入密钥
4. 勾选 **Push**
5. 点击 **添加**

### 测试部署

```bash
# 本地推送代码
git commit -m "test: trigger CD" --allow-empty
git push origin main

# 服务器查看部署日志
tail -f /var/log/petfood-deploy.log
```

---

## 方案 2: 定时拉取部署（3 步）

### 第 1 步：初始化（同方案 1 第 1 步）

### 第 2 步：配置脚本

```bash
sudo mkdir -p /opt/petfood-cd
sudo cp /opt/petfood/pet_food_backend/pet-food/deployment/deploy-webhook.sh /opt/petfood-cd/
sudo cp /opt/petfood/pet_food_backend/pet-food/deployment/deploy-cron.sh /opt/petfood-cd/
sudo cp /opt/petfood/pet_food_backend/pet-food/deployment/rollback.sh /opt/petfood-cd/
sudo chmod +x /opt/petfood-cd/*.sh
```

### 第 3 步：配置 Cron

```bash
# 编辑 root 的 crontab
sudo crontab -e

# 添加以下行（每 5 分钟检查一次）
*/5 * * * * /opt/petfood-cd/deploy-cron.sh

# 或每 10 分钟
*/10 * * * * /opt/petfood-cd/deploy-cron.sh

# 保存退出
```

### 测试

```bash
# 手动触发一次
sudo /opt/petfood-cd/deploy-cron.sh

# 查看日志
tail -f /var/log/petfood-deploy.log
```

---

## 常用操作

### 查看部署日志

```bash
# 实时查看
tail -f /var/log/petfood-deploy.log

# 查看最近 50 行
tail -50 /var/log/petfood-deploy.log

# 查看今天的部署
grep "$(date +%Y-%m-%d)" /var/log/petfood-deploy.log
```

### 手动回滚

```bash
sudo /opt/petfood-cd/rollback.sh
```

### 重启 Webhook 服务

```bash
sudo systemctl restart petfood-webhook
sudo systemctl status petfood-webhook
```

### 查看容器状态

```bash
cd /opt/petfood/pet_food_backend/pet-food
./deployment/deploy.sh ps
./deployment/deploy.sh logs api
```

---

## 安全加固（生产必做）

### 1. 配置防火墙

```bash
# 只允许 Git 服务器 IP 访问 webhook 端口
sudo ufw allow from <GIT_SERVER_IP> to any port 9000 proto tcp

# 或使用 Nginx 反向代理（推荐）
# 在 deployment/nginx/nginx.conf 添加：
# location /webhook {
#     proxy_pass http://localhost:9000;
# }
```

### 2. 配置 HTTPS（推荐）

```bash
# 使用 Let's Encrypt 免费证书
sudo apt install certbot
sudo certbot certonly --standalone -d your-domain.com

# 更新 .env.prod
VITE_API_BASE_URL=https://your-domain.com/api/v1
MINIO_PUBLIC_ENDPOINT=https://your-domain.com/minio-api

# 启用 nginx HTTPS（取消 nginx.conf 中 443 端口的注释）
```

### 3. 配置 Git 凭证（私有仓库）

```bash
# 方式 1: HTTPS + 凭证存储
cd /opt/petfood
git config credential.helper store
git pull  # 输入一次用户名密码后会保存

# 方式 2: SSH 密钥（推荐）
ssh-keygen -t ed25519 -C "server@petfood"
cat ~/.ssh/id_ed25519.pub  # 添加到 Git 仓库的 Deploy Keys

# 修改 remote URL 为 SSH
git remote set-url origin git@github.com:your-username/your-repo.git
```

### 4. 配置日志轮转

```bash
sudo tee /etc/logrotate.d/petfood > /dev/null <<EOF
/var/log/petfood-deploy.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
EOF
```

---

## 故障排查

### Webhook 未触发

```bash
# 1. 检查服务状态
sudo systemctl status petfood-webhook

# 2. 查看服务日志
sudo journalctl -u petfood-webhook -f

# 3. 测试 webhook 端点
curl -X POST http://localhost:9000/hooks/deploy-petfood \
     -H "Content-Type: application/json" \
     -d '{"ref":"refs/heads/main"}'

# 4. 检查防火墙
sudo ufw status
```

### 部署失败

```bash
# 1. 查看部署日志
tail -100 /var/log/petfood-deploy.log

# 2. 查看容器日志
cd /opt/petfood/pet_food_backend/pet-food
./deployment/deploy.sh logs

# 3. 检查磁盘空间
df -h

# 4. 检查 Docker 状态
docker ps -a
docker stats --no-stream
```

### Git 拉取失败

```bash
# 1. 检查网络
ping github.com

# 2. 检查 Git 凭证
cd /opt/petfood
git pull

# 3. 重置 Git 状态
git reset --hard origin/main
git clean -fd
```

---

## 通知集成（可选）

### 企业微信机器人

在 `deploy-webhook.sh` 的 `send_notification()` 函数中取消注释并填写：

```bash
send_notification() {
    curl -X POST "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY" \
         -H 'Content-Type: application/json' \
         -d "{\"msgtype\":\"text\",\"text\":{\"content\":\"$1\"}}"
}
```

### 钉钉机器人

```bash
send_notification() {
    curl -X POST "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN" \
         -H 'Content-Type: application/json' \
         -d "{\"msgtype\":\"text\",\"text\":{\"content\":\"$1\"}}"
}
```

---

## 完成！

现在你的 CD 流程已经配置完成：

✅ 代码 push → 自动部署  
✅ 部署失败 → 自动回滚  
✅ 健康检查 → 确保服务可用  
✅ 日志记录 → 可追溯问题  
✅ 手动回滚 → 快速恢复

**下一步**：查看 [CD_GUIDE.md](./CD_GUIDE.md) 了解更多高级功能。
