# 部署指南

> Docker 部署和生产环境配置指南

---

## 目录

1. [部署方式](#部署方式)
2. [环境准备](#环境准备)
3. [Docker 部署](#docker-部署)
4. [Nginx 配置](#nginx-配置)
5. [生产环境配置](#生产环境配置)
6. [故障排查](#故障排查)

---

## 部署方式

### 开发环境

使用 Docker Compose 快速启动所有服务：

```bash
docker-compose -f deployment/docker-compose.dev.yml up -d
```

访问地址：
- FastAPI: http://localhost:8000
- API 文档: http://localhost:8000/docs
- pgAdmin: http://localhost:5050

### 生产环境

推荐使用 Docker Compose 一键部署：

```bash
# 配置环境变量
cp .env.example .env.production
# 编辑 .env.production 文件，修改生产环境配置

# 构建并启动
docker-compose -f deployment/docker-compose.prod.yml up -d --build

# 查看日志
docker-compose -f deployment/docker-compose.prod.yml logs -f api
```

---

## 环境准备

### 系统要求

| 资源 | 最低要求 | 推荐配置 |
|------|---------|----------|
| CPU | 2 核 | 4 核 |
| 内存 | 4GB | 8GB |
| 磁盘 | 20GB | 50GB SSD |
| 网络 | 10 Mbps | 100 Mbps |

### 软件依赖

- **Docker**: 20.10+
- **Docker Compose**: 2.0+
- **Nginx**: 1.18+（生产环境）

---

## Docker 部署

### 开发环境

```bash
# 1. 克隆代码仓库
git clone <repository-url>
cd pet-food

# 2. 复制环境变量模板
cp .env.example .env
# 编辑 .env 文件

# 3. 启动服务
docker-compose -f deployment/docker-compose.dev.yml up -d

# 4. 查看服务状态
docker-compose -f deployment/docker-compose.dev.yml ps

# 5. 查看日志
docker-compose -f deployment/docker-compose.dev.yml logs -f api
```

### 生产环境

#### 1. 环境变量配置

创建生产环境的环境变量文件：

```bash
# 创建 .env.production
cat > .env.production << 'EOF'
# ============ JWT 配置 ============
JWT_SECRET_KEY=$(openssl rand -hex 32)
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# ============ 数据库配置 ============
POSTGRES_PASSWORD=$(openssl rand -hex 16)
DATABASE_URL=postgresql+asyncpg://petfood:${POSTGRES_PASSWORD}@postgres:5432/petfood
DATABASE_ECHO=false

# ============ Redis 配置 ============
REDIS_PASSWORD=$(openssl rand -hex 16)
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0

# ============ CORS 配置 ============
CORS_ORIGINS=["https://yourdomain.com","https://www.yourdomain.com"]
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOW_METHODS=["GET","POST","PUT","DELETE","OPTIONS"]
CORS_ALLOW_HEADERS=["*"]

# ============ 安全配置 ============
SECRET_KEY=$(openssl rand -hex 32)
ALLOWED_HOSTS=["yourdomain.com","www.yourdomain.com"]
MAX_REQUEST_SIZE=10485760

# ============ LLM API 配置 ============
# 填写实际的 API 密钥
DASHSCOPE_API_KEY=your-api-key
DEEPSEEK_API_KEY=your-api-key
ZAI_API_KEY=your-api-key
TAVILIY_API_KEY=your-api-key
SILICONFLOW_API_KEY=your-api-key

# ============ FastAPI 配置 ============
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=false
API_WORKERS=4
LOG_LEVEL=warning
EOF
```

#### 2. SSL 证书配置（HTTPS）

将 SSL 证书放置到 `deployment/nginx/ssl/` 目录：

```bash
# 创建 SSL 目录
mkdir -p deployment/nginx/ssl

# 复制证书文件
cp /path/to/cert.pem deployment/nginx/ssl/
cp /path/to/key.pem deployment/nginx/ssl/

# 设置正确的权限
chmod 600 deployment/nginx/ssl/key.pem
chmod 644 deployment/nginx/ssl/cert.pem
```

#### 3. 启动服务

```bash
# 使用环境变量文件启动
env $(cat .env.production | xargs) docker-compose -f deployment/docker-compose.prod.yml up -d --build

# 查看服务状态
docker-compose -f deployment/docker-compose.prod.yml ps
```

---

## Nginx 配置

### 安装 Nginx

```bash
# Ubuntu/Debian
sudo apt-get install nginx

# CentOS/RHEL
sudo yum install nginx

# macOS
brew install nginx
```

### 配置 Nginx

```nginx
# 复制 Nginx 配置
sudo cp deployment/nginx/nginx.conf /etc/nginx/sites-available/pet-food

# 创建软链接
sudo ln -s /etc/nginx/sites-available/pet-food /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 重启 Nginx
sudo systemctl restart nginx
```

### 生产环境 Nginx 配置

```nginx
server {
    listen 80;
    listen 443 ssl;
    server_name yourdomain.com www.yourdomain.com;

    # SSL 证书
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;

    # SSE 特殊配置（重要）
    proxy_buffering off;
    proxy_cache off;

    # 超时设置
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;

    # 禁用 gzip 对 SSE 的压缩
    location /api/v1/plans/stream {
        gzip off;
        proxy_pass http://api:8000;
    }

    # 反向代理到 FastAPI
    location / {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# 健康检查端点
location /health {
    proxy_pass http://api:8000;
    access_log off;
}
```

---

## 生产环境配置

### 安全配置清单

部署到生产环境前，请务必修改以下配置：

- [ ] 修改 `JWT_SECRET_KEY` 为随机字符串
- [ ] 修改 `SECRET_KEY` 为随机字符串
- [ ] 修改 `DATABASE_URL` 为生产数据库地址
- [ ] 修改 `REDIS_URL` 为生产 Redis 地址
- [ ] 修改 `CORS_ORIGINS` 为实际前端域名
- [ ] 修改 `ALLOWED_HOSTS` 为实际域名
- [ ] 设置 `API_RELOAD=false`
- [ ] 设置 `API_WORKERS` 为合适的进程数（CPU 核心数的 75%）
- [ ] 配置 `LOG_LEVEL=warning` 或 `error`
- [ ] 启用 `RATE_LIMIT_ENABLED=true`
- [ ] 配置 SMTP 邮件参数
- [ ] 设置 SSL 证书

### 生成安全密钥

```bash
# 生成 JWT 密钥
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"

# 生成应用密钥
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"

# 生成数据库密码
openssl rand -hex 16
```

---

## 故障排查

### 常见问题

#### 1. 数据库连接失败

**症状**: 服务启动时提示数据库连接失败

**解决方案**:
```bash
# 检查 PostgreSQL 是否运行
docker-compose ps postgres

# 检查数据库连接字符串
docker-compose exec api env | grep DATABASE_URL

# 查看数据库日志
docker-compose logs postgres
```

#### 2. Redis 连接失败

**症状**: 服务启动时提示 Redis 连接失败

**解决方案**:
```bash
# 检查 Redis 是否运行
docker-compose ps redis

# 检查 Redis 密码
docker-compose exec api env | grep REDIS_URL

# 测试 Redis 连接
docker-compose exec redis redis-cli ping
```

#### 3. API 无法访问

**症状**: 浏览器无法访问 API

**解决方案**:
```bash
# 检查容器状态
docker-compose ps

# 检查端口映射
docker-compose ps

# 检查防火墙
sudo ufw status  # Ubuntu
sudo firewall-cmd --list-all  # CentOS

# 检查 Nginx 配置
sudo nginx -t
```

#### 4. SSE 流式输出中断

**症状**: 流式输出连接意外断开

**解决方案**:
```nginx
# 确保 Nginx 配置中禁用了缓冲
proxy_buffering off;
proxy_cache off;

# 增加超时设置
proxy_read_timeout 300s;
proxy_send_timeout 300s;
```

#### 5. 任务执行超时

**症状**: 创建的任务一直处于 "running" 状态

**解决方案**:
1. 检查 LLM API 密钥是否正确
2. 检查网络连接是否正常
3. 查看任务日志
4. 增加 `TASK_TIMEOUT_SECONDS` 配置

---

## 备份和恢复

### 数据库备份

```bash
# 使用 pg_dump 备份
docker-compose exec postgres pg_dump -U petfood petfood > backup.sql

# 定时备份（crontab）
0 2 * * * * docker-compose exec postgres pg_dump -U petfood petfood > /backup/$(date +\%Y\%m\%d).sql
```

### 数据库恢复

```bash
# 恢复数据库
cat backup.sql | docker-compose exec -T postgres psql -U petfood petfood
```

---

## 相关文档

- [后端开发文档](../backend/README.md)
- [前端对接指南](../frontend/README.md)
- [系统架构](../architecture/README.md)
