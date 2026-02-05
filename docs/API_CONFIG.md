# FastAPI 环境变量配置说明

本文档详细说明了 FastAPI 服务所需的各项环境变量配置。

## 配置文件

配置文件位于项目根目录：
- `.env.example` - 环境变量模板（需复制为 `.env` 并修改）
- `.env` - 实际使用的环境变量文件（不提交到 Git）

## 快速开始

1. 复制环境变量模板：
```bash
cp .env.example .env
```

2. 修改 `.env` 文件中的关键配置：
   - `JWT_SECRET_KEY`: JWT 密钥（生产环境必须修改）
   - `DATABASE_URL`: PostgreSQL 连接字符串
   - `REDIS_URL`: Redis 连接字符串
   - `SMTP_*`: 邮件发送配置

3. 启动依赖服务（PostgreSQL 和 Redis）：
```bash
docker-compose -f deployment/docker-compose.dev.yml up -d
```

---

## 配置项详解

### 1. LLM API 配置

| 配置项 | 说明 | 默认值 | 是否必需 |
|--------|------|--------|----------|
| `DASHSCOPE_API_BASE` | 阿里云 DashScope API 地址 | https://dashscope.aliyuncs.com/compatible-mode/v1 | 否 |
| `DASHSCOPE_API_KEY` | 阿里云 DashScope API 密钥 | - | 是* |
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | - | 是* |
| `ZAI_API_KEY` | ZAI API 密钥 | - | 是* |
| `MOONSHOT_API_KEY` | Moonshot API 密钥 | - | 是* |
| `TAVILIY_API_KEY` | Tavily 搜索 API 密钥 | - | 是* |
| `SILICONFLOW_API_BASE` | SiliconFlow API 地址 | https://api.siliconflow.cn | 否 |
| `SILICONFLOW_API_KEY` | SiliconFlow API 密钥 | - | 是* |

*至少需要配置一个 LLM API 密钥

### 2. FastAPI 基础配置

| 配置项 | 说明 | 默认值 | 建议 |
|--------|------|--------|------|
| `API_HOST` | 服务监听地址 | 0.0.0.0 | 开发使用 localhost，生产使用 0.0.0.0 |
| `API_PORT` | 服务监听端口 | 8000 | 8000 或 8080 |
| `API_RELOAD` | 自动重载（开发模式） | true | 生产环境设为 false |
| `API_WORKERS` | 工作进程数 | 1 | 生产环境建议 CPU 核心数 |
| `LOG_LEVEL` | 日志级别 | info | debug / info / warning / error |

### 3. JWT 认证配置

| 配置项 | 说明 | 默认值 | 安全建议 |
|--------|------|--------|----------|
| `JWT_SECRET_KEY` | JWT 签名密钥 | your-super-secret-jwt-key... | **生产环境必须修改为随机字符串** |
| `JWT_ALGORITHM` | JWT 签名算法 | HS256 | 保持默认 |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Access Token 有效期（分钟） | 30 | 15-60 分钟 |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | Refresh Token 有效期（天） | 7 | 7-30 天 |

**生成安全的 JWT 密钥：**
```bash
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"
```

### 4. 数据库配置 (PostgreSQL)

| 配置项 | 说明 | 格式 | 示例 |
|--------|------|------|------|
| `DATABASE_URL` | 异步数据库连接字符串 | `postgresql+asyncpg://user:pass@host:port/db` | `postgresql+asyncpg://postgres:postgres@localhost:5432/pet_food` |
| `DATABASE_ECHO` | 是否打印 SQL 语句 | true / false | 开发环境可设为 true |

**连接字符串组成部分：**
- `postgresql+asyncpg`: 使用 asyncpg 驱动
- `user`: 数据库用户名（默认 postgres）
- `pass`: 数据库密码（默认 postgres）
- `host`: 数据库主机（本地开发用 localhost）
- `port`: 数据库端口（默认 5432）
- `db`: 数据库名（建议 pet_food）

### 5. Redis 配置

| 配置项 | 说明 | 格式 | 示例 |
|--------|------|------|------|
| `REDIS_URL` | Redis 连接字符串 | `redis://[:password@]host:port/db` | `redis://localhost:6379/0` |
| `REDIS_PASSWORD` | Redis 密码（可选） | - | 留空表示无密码 |
| `REDIS_DB` | Redis 数据库编号 | 0-15 | 0 |

**连接字符串格式：**
- 无密码: `redis://localhost:6379/0`
- 有密码: `redis://:password@localhost:6379/0`

### 6. 邮件配置

| 配置项 | 说明 | 默认值 | 说明 |
|--------|------|--------|------|
| `SMTP_HOST` | SMTP 服务器地址 | smtp.qq.com | QQ/Gmail 等 SMTP 地址 |
| `SMTP_PORT` | SMTP 端口 | 587 | TLS 使用 587，SSL 使用 465 |
| `SMTP_USERNAME` | SMTP 用户名 | "" | 登录邮箱地址 |
| `SMTP_PASSWORD` | SMTP 密码 | "" | 登录邮箱密码或授权码 |
| `SMTP_FROM_EMAIL` | 发件人邮箱 | "" | 发件人邮箱 |
| `SMTP_USE_TLS` | 是否使用 TLS | true | SSL 使用 false，TLS 使用 true |

**邮箱配置示例：**

```bash
# QQ 邮箱
SMTP_HOST=smtp.qq.com
SMTP_PORT=587
SMTP_USERNAME=your-email@qq.com
SMTP_PASSWORD=your-authorization-code
SMTP_FROM_EMAIL=your-email@qq.com
SMTP_USE_TLS=true

# Gmail 邮箱
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM_EMAIL=your-email@gmail.com
SMTP_USE_TLS=true
```

**获取邮箱授权码：**
- **QQ 邮箱**: 登录 QQ 邮箱 → 设置 → 账户 → POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务 → 生成授权码
- **Gmail**: 账户 → 安全 → 两步验证 → 应用专用密码 → 生成

### 7. CORS 配置

| 配置项 | 说明 | 默认值 | 生产环境建议 |
|--------|------|--------|--------------|
| `CORS_ORIGINS` | 允许的跨域来源（JSON 数组） | ["http://localhost:3000","http://localhost:8080"] | **修改为实际的前端域名** |
| `CORS_ALLOW_CREDENTIALS` | 允许携带凭证 | true | 根据需求设置 |
| `CORS_ALLOW_METHODS` | 允许的 HTTP 方法 | ["*"] | ["GET","POST","PUT","DELETE"] |
| `CORS_ALLOW_HEADERS` | 允许的请求头 | ["*"] | 根据需求设置 |

**CORS_ORIGINS 配置示例：**
```bash
# 开发环境
CORS_ORIGINS=["http://localhost:3000","http://localhost:8080"]

# 生产环境
CORS_ORIGINS=["https://yourdomain.com","https://www.yourdomain.com"]
```

### 8. 安全配置

| 配置项 | 说明 | 默认值 | 安全建议 |
|--------|------|--------|----------|
| `SECRET_KEY` | 应用密钥 | your-super-secret-key... | **生产环境必须修改为随机字符串** |
| `ALLOWED_HOSTS` | 允许的主机名 | ["*"] | **生产环境设置为实际域名** |
| `MAX_REQUEST_SIZE` | 最大请求大小（字节） | 10485760 (10MB) | 根据需求调整 |

### 9. 任务配置

| 配置项 | 说明 | 默认值 | 调整建议 |
|--------|------|--------|----------|
| `TASK_TIMEOUT_SECONDS` | 任务超时时间（秒） | 3600 (1小时) | 根据实际任务耗时调整 |
| `TASK_MAX_CONCURRENT` | 最大并发任务数 | 5 | 根据服务器性能调整 |

### 10. 速率限制配置

| 配置项 | 说明 | 默认值 | 调整建议 |
|--------|------|--------|----------|
| `RATE_LIMIT_ENABLED` | 是否启用速率限制 | true | 生产环境建议启用 |
| `RATE_LIMIT_TIMES` | 时间窗口内最大请求次数 | 100 | 根据需求调整 |
| `RATE_LIMIT_SECONDS` | 时间窗口（秒） | 60 | 根据需求调整 |

**速率限制示例：**
- `100次/60秒` = 每分钟最多 100 次请求
- `1000次/3600秒` = 每小时最多 1000 次请求

### 11. 验证码配置

| 配置项 | 说明 | 默认值 | 调整建议 |
|--------|------|--------|----------|
| `VERIFICATION_CODE_LENGTH` | 验证码长度 | 6 | 4-8 位 |
| `VERIFICATION_CODE_EXPIRE_MINUTES` | 验证码有效期（分钟） | 10 | 5-30 分钟 |
| `VERIFICATION_CODE_MAX_ATTEMPTS` | 最大验证尝试次数 | 3 | 3-5 次 |
| `VERIFICATION_CODE_COOLDOWN_SECONDS` | 发送冷却时间（秒） | 60 | 30-120 秒 |
| `VERIFICATION_CODE_MAX_DAILY_SENDS` | 每日最大发送次数 | 10 | 5-20 次 |

---

## 开发环境快速启动

### 方式 1：使用 Docker Compose（推荐）

1. 启动 PostgreSQL 和 Redis：
```bash
docker-compose -f deployment/docker-compose.dev.yml up -d
```

2. 安装依赖并启动 FastAPI：
```bash
# 安装依赖
uv pip install -e .

# 启动开发服务器
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

### 方式 2：手动安装依赖服务

1. 安装 PostgreSQL：
```bash
# macOS
brew install postgresql@16
brew services start postgresql@16

# Ubuntu/Debian
sudo apt-get install postgresql-16
sudo systemctl start postgresql

# Windows
# 下载安装器：https://www.postgresql.org/download/windows/
```

2. 安装 Redis：
```bash
# macOS
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis

# Windows
# 下载 Redis for Windows：https://github.com/microsoftarchive/redis/releases
```

3. 创建数据库：
```bash
# 连接到 PostgreSQL
psql -U postgres

# 创建数据库
CREATE DATABASE pet_food;

# 退出
\q
```

---

## 生产环境配置清单

部署到生产环境前，请务必修改以下配置：

- [ ] 修改 `JWT_SECRET_KEY` 为随机字符串
- [ ] 修改 `SECRET_KEY` 为随机字符串
- [ ] 修改 `DATABASE_URL` 为生产数据库地址
- [ ] 修改 `REDIS_URL` 为生产 Redis 地址
- [ ] 修改 `CORS_ORIGINS` 为实际前端域名
- [ ] 修改 `ALLOWED_HOSTS` 为实际域名
- [ ] 设置 `API_RELOAD=false`
- [ ] 设置 `API_WORKERS` 为合适的进程数
- [ ] 配置 `LOG_LEVEL=warning` 或 `error`
- [ ] 启用 `RATE_LIMIT_ENABLED=true`
- [ ] 配置 SMTP 邮件参数

---

## 配置验证

启动服务前，验证配置是否正确：

```bash
# 检查环境变量文件
cat .env

# 测试数据库连接
python -c "from src.db.session import test_connection; import asyncio; asyncio.run(test_connection())"

# 测试 Redis 连接
python -c "from src.db.redis import test_redis_connection; import asyncio; asyncio.run(test_redis_connection())"
```

---

## 常见问题

### Q1: 如何生成安全的密钥？

```bash
# 生成 JWT 密钥
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"

# 生成应用密钥
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32))"
```

### Q2: PostgreSQL 连接失败？

检查以下几点：
1. PostgreSQL 服务是否启动
2. 数据库用户名和密码是否正确
3. 数据库是否已创建
4. 端口 5432 是否被占用

### Q3: Redis 连接失败？

检查以下几点：
1. Redis 服务是否启动
2. Redis 是否设置了密码（REDIS_URL 需包含密码）
3. 端口 6379 是否被占用

### Q4: CORS 错误？

确保 `CORS_ORIGINS` 包含前端域名：
- 开发环境：`http://localhost:3000`
- 生产环境：`https://yourdomain.com`

### Q5: 邮件发送失败？

检查以下几点：
1. SMTP 配置是否正确（主机、端口、用户名、密码）
2. 是否使用了授权码而非登录密码
3. QQ 邮箱需要在设置中开启 SMTP 服务
4. Gmail 需要开启两步验证并生成应用专用密码

---

## 参考资源

- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [SQLAlchemy 异步文档](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [PostgreSQL 官方文档](https://www.postgresql.org/docs/)
- [Redis 官方文档](https://redis.io/docs/)
- [Pydantic Settings 文档](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
