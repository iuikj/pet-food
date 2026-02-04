# 部署文档

## 概述

本文档描述了宠物饮食计划智能助手 API 服务的完整部署流程。

---

## 目录

1. [部署方式](#部署方式)
2. [环境准备](#环境准备)
3. [Docker 部署](#docker-部署)
4. [手动部署](#手动部署)
5. [Nginx 配置](#nginx-配置)
6. [监控和日志](#监控和日志)
7. [故障排查](#故障排查)

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
cp .env.example .env
# 编辑 .env 文件，修改生产环境配置

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
- **反向代理**: Nginx 1.18+（生产环境）

---

## Docker 部署

### 开发环境部署

```bash
# 1. 克隆代码仓库
git clone <repository-url>
cd pet-food

# 2. 复制环境变量模板
cp .env.example .env

# 3. 编辑 .env 文件
# - 修改 LLM API 密钥
# - 其他配置可使用默认值

# 4. 启动服务
docker-compose -f deployment/docker-compose.dev.yml up -d

# 5. 查看服务状态
docker-compose -f deployment/docker-compose.dev.yml ps

# 6. 查看日志
docker-compose -f deployment/docker-compose.dev.yml logs -f api
```

### 生产环境部署

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

# ============ 任务配置 ============
TASK_TIMEOUT_SECONDS=3600
TASK_MAX_CONCURRENT=10

# ============ 速率限制配置 ============
RATE_LIMIT_ENABLED=true
RATE_LIMIT_TIMES=100
RATE_LIMIT_SECONDS=60

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

#### 4. 数据库迁移

```bash
# 进入 API 容器执行迁移
docker-compose -f deployment/docker-compose.prod.yml exec api alembic upgrade head

# 或者使用临时容器
docker run --rm \
  -v $(pwd)/alembic:/app/alembic \
  -v $(pwd)/.env:/app/.env \
  python:3.12 \
  alembic upgrade head
```

---

## 手动部署

### 系统依赖安装

#### 1. 安装 PostgreSQL

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install postgresql-16 postgresql-client-16

# macOS
brew install postgresql@16
brew services start postgresql@16

# 创建数据库
sudo -u postgres psql
CREATE DATABASE petfood;
CREATE USER petfood WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE petfood TO petfood;
\q
```

#### 2. 安装 Redis

```bash
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis-server

# macOS
brew install redis
brew services start redis
```

#### 3. 安装 Python 依赖

```bash
# 安装 uv
pip install uv

# 安装项目依赖
uv pip install -e .
```

#### 4. 运行数据库迁移

```bash
alembic upgrade head
```

#### 5. 启动服务

```bash
# 使用 Gunicorn 启动
gunicorn src.api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile /var/log/pet-food/access.log \
  --error-logfile /var/log/pet-food/error.log \
  --log-level info \
  --timeout 300
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

```bash
# 复制 Nginx 配置
sudo cp deployment/nginx/nginx.conf /etc/nginx/sites-available/pet-food

# 创建软链接
sudo ln -s /etc/nginx/sites-available/pet-food /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 重启 Nginx
sudo systemctl restart nginx
```

### SSL 证书配置

使用 Let's Encrypt 获取免费 SSL 证书：

```bash
# 安装 Certbot
sudo apt-get install certbot python3-certbot-nginx

# 获取证书
sudo certbot --nginx -d yourdomain.com

# 自动续期
sudo certbot renew --dry-run
```

---

## 监控和日志

### 日志查看

#### Docker 容器日志

```bash
# 查看所有服务日志
docker-compose -f deployment/docker-compose.prod.yml logs

# 跟踪特定服务日志
docker-compose -f deployment/docker-compose.prod.yml logs -f api

# 查看最近 100 行
docker-compose -f deployment/docker-compose.prod.yml logs --tail=100 api
```

#### 日志配置

FastAPI 日志级别可在 `.env` 中配置：

| 级别 | 用途 |
|------|------|
| `debug` | 详细的调试信息（仅开发环境） |
| `info` | 一般信息（推荐生产环境） |
| `warning` | 警告信息 |
| `error` | 仅错误信息 |

### 健康检查

```bash
# 基础健康检查
curl http://localhost/health

# 详细健康检查
curl http://localhost/health/detail

# 返回示例
{
  "code": 0,
  "message": "服务正常",
  "data": {
    "status": "healthy",
    "components": {
      "database": {"status": "healthy"},
      "redis": {"status": "healthy"}
    }
  }
}
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
docker-compose ps  # 查看端口映射

# 检查防火墙
sudo ufw status  # Ubuntu
sudo firewall-cmd --list-all  # CentOS

# 检查 Nginx 配置
sudo nginx -t
```

#### 4. 任务执行超时

**症状**: 创建的任务一直处于 "running" 状态

**解决方案**:
1. 检查 LLM API 密钥是否正确
2. 检查网络连接是否正常
3. 查看任务日志
4. 增加 `TASK_TIMEOUT_SECONDS` 配置

#### 5. SSE 流式输出中断

**症状**: 流式输出连接意外断开

**解决方案**:
1. 检查 Nginx 配置中的超时设置
2. 确保 `proxy_buffering off` 和 `proxy_cache off`
3. 增加 Nginx `proxy_read_timeout` 配置

---

## 性能优化

### 数据库优化

```sql
-- 创建索引（已在模型中定义）
CREATE INDEX IF NOT EXISTS idx_tasks_user_status ON tasks(user_id, status);
CREATE INDEX IF NOT EXISTS idx_diet_plans_user ON diet_plans(user_id);
```

### 应用优化

| 优化项 | 配置 | 说明 |
|--------|------|------|
| 工作进程数 | `API_WORKERS=4` | CPU 核数的 75% |
| 数据库连接池 | 已在 `session.py` 中配置 | pool_size=10, max_overflow=20 |
| GZip 压缩 | 已在 Nginx 中启用 | 减少传输数据量 |
| 速率限制 | 已在中间件中实现 | 防止 DDoS 攻击 |

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

## 安全建议

1. **使用强密钥**
   - JWT 密钥至少 256 位
   - 生产环境禁止使用默认密钥

2. **启用 HTTPS**
   - 生产环境必须使用 HTTPS
   - 使用有效的 SSL 证书

3. **防火墙配置**
   - 只开放必要端口（80, 443）
   - 限制数据库直接访问

4. **定期更新**
   - 及时更新依赖包
   - 修复已知安全漏洞

5. **监控和告警**
   - 配置日志监控
   - 设置异常告警
