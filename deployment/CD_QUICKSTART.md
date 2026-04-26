# GitHub Actions CD 快速开始

> 5 步完成自动化部署配置

**预计时间：** 15 分钟  
**难度：** ⭐⭐☆☆☆

---

## 📋 前置条件

- ✅ 有一台 Linux 服务器（已安装 Docker 和 Docker Compose）
- ✅ 有 GitHub 仓库的 Admin 权限
- ✅ 本地已安装 Git 和 SSH 客户端

---

## 🚀 5 步配置

### 步骤 1：生成 SSH 密钥

```bash
# 生成密钥
ssh-keygen -t ed25519 -C "github-actions" -f ~/.ssh/github_actions_deploy

# 查看公钥
cat ~/.ssh/github_actions_deploy.pub
```

**复制公钥内容**，然后添加到服务器：

```bash
# SSH 登录服务器
ssh root@你的服务器IP

# 添加公钥
echo "刚才复制的公钥" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

---

### 步骤 2：配置 GitHub Secrets

1. 访问：`https://github.com/你的用户名/pet-food/settings/environments`
2. 创建 Environment：`pet-food`
3. 添加 8 个 Secrets：

| Secret 名称 | 值 |
|------------|---|
| `SERVER_HOST` | 服务器 IP（如 `81.71.128.32`） |
| `SERVER_USER` | SSH 用户名（通常是 `root`） |
| `SERVER_PORT` | SSH 端口（通常是 `22`） |
| `SERVER_SSH_KEY` | `~/.ssh/github_actions_deploy` 文件的**完整内容** |
| `SERVER_APP_DIR` | `/opt/petfood/pet_food_backend/pet-food` |
| `GHCR_USERNAME` | 你的 GitHub 用户名 |
| `GHCR_TOKEN` | GitHub Token（见下方） |
| `ENV_PROD_FILE` | 服务器上 `.env.prod` 的完整内容（见步骤 4） |

**创建 GitHub Token：**

1. 访问：`https://github.com/settings/tokens/new`
2. 勾选：`write:packages` 和 `read:packages`
3. 生成并复制 Token

---

### 步骤 3：准备服务器

```bash
# SSH 登录服务器
ssh root@你的服务器IP

# 创建目录
mkdir -p /opt/petfood/pet_food_backend/pet-food/deployment/nginx

# 配置 Docker 镜像加速
sudo tee /etc/docker/daemon.json > /dev/null <<EOF
{
  "registry-mirrors": [
    "https://docker.1ms.run",
    "https://ghcr.1ms.run"
  ]
}
EOF

# 重启 Docker
sudo systemctl restart docker
```

---

### 步骤 4：创建 .env.prod 文件

在服务器上创建配置文件：

```bash
# 创建文件
nano /opt/petfood/pet_food_backend/pet-food/deployment/.env.prod
```

**粘贴以下内容并修改：**

```bash
# 运行参数
API_WORKERS=2
LOG_LEVEL=info

# 密钥（必须修改为随机字符串）
JWT_SECRET_KEY=请替换为随机32字节字符串
SECRET_KEY=请替换为随机32字节字符串

# 数据库密码（必须修改）
POSTGRES_PASSWORD=请设置强密码

# Redis 密码（必须修改）
REDIS_PASSWORD=请设置强密码

# MinIO 配置（必须修改）
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=请设置强密码
MINIO_BUCKET=petfood-bucket
MINIO_PUBLIC_ENDPOINT=http://你的服务器IP:9000
MINIO_CONSOLE_PUBLIC_URL=http://你的服务器IP:9001

# CORS 配置
CORS_ORIGINS=["http://localhost","http://localhost:80","capacitor://localhost","https://localhost"]
ALLOWED_HOSTS=["*"]

# 前端配置
VITE_API_BASE_URL=http://localhost/api/v1
VITE_ENABLE_SSE=true
VITE_RECONNECT_DELAY=3000

# LLM API（必须配置）
DASHSCOPE_API_KEY=你的DashScope_API_Key
DASHSCOPE_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
TAVILIY_API_KEY=你的Tavily_API_Key

# 可选 API
ZAI_API_KEY=
DEEPSEEK_API_KEY=
SILICONFLOW_API_KEY=
MOONSHOT_API_KEY=

# 邮件配置（可选）
SMTP_HOST=smtp.qq.com
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
```

**生成随机密钥：**

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**保存后，复制完整内容到 GitHub Secret `ENV_PROD_FILE`**

---

### 步骤 5：测试部署

```bash
# 在本地执行
git tag -a v0.0.1-test -m "Test CD"
git push origin v0.0.1-test

# 查看部署进度
# 访问：https://github.com/你的用户名/pet-food/actions
```

**等待 15-20 分钟，部署完成后验证：**

```bash
# 测试健康检查
curl http://你的服务器IP/health

# 预期输出：
# {"code":0,"message":"ok","data":{"status":"healthy","version":"1.0.0"}}
```

---

## ✅ 完成！

现在你可以通过推送 Git 标签来自动部署：

```bash
# 发布新版本
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0
```

---

## 🔧 常见问题

### Q1: 部署失败怎么办？

**A:** 查看 GitHub Actions 日志和服务器日志：

```bash
# 服务器日志
ssh root@你的服务器IP
tail -100 /opt/petfood/pet_food_backend/pet-food/deployment/.cd-state/deploy-ghcr.log
docker logs pet-food-api --tail 100
```

### Q2: 如何回滚版本？

**A:** 在服务器上执行：

```bash
cd /opt/petfood/pet_food_backend/pet-food
./deployment/rollback-ghcr.sh v0.9.0
```

### Q3: 如何更新环境变量？

**A:** 修改服务器上的 `.env.prod` 并重启容器：

```bash
nano /opt/petfood/pet_food_backend/pet-food/deployment/.env.prod
docker restart pet-food-api
```

**同时更新 GitHub Secret `ENV_PROD_FILE`**

---

## 📚 更多文档

- [CD_COMPLETE_GUIDE.md](./CD_COMPLETE_GUIDE.md) - 完整指南
- [README.md](./README.md) - Docker 部署基础
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) - 故障排查

---

**遇到问题？** 查看 [CD_COMPLETE_GUIDE.md](./CD_COMPLETE_GUIDE.md) 的故障排查章节。
