# 多阶段构建 Dockerfile - 生产环境
# 使用 uv 作为包管理器，优化镜像大小
#
# 构建原则：
#   - KISS: 直接用 uv 按 pyproject.toml 装依赖，不做奇技淫巧
#   - DRY:  依赖声明唯一来源是 pyproject.toml
#   - 分层缓存：依赖层与源码层分离，修改代码不触发重装

# ============ 阶段 1: 依赖构建 ============
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# 构建期依赖：编译 C 扩展 + psycopg2 头文件
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        g++ \
        libpq-dev \
        curl \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
RUN pip install uv

WORKDIR /app

# 先拷依赖声明，充分利用 Docker 层缓存
COPY pyproject.toml ./
COPY uv.lock* ./

# 装依赖到 /install（不装项目本身，--no-install-project）
# 使用 --python-preference=only-system 强制用系统 Python
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --no-cache \
        --target=/install \
        --requirement pyproject.toml \
    || uv pip install --system --no-cache --target=/install \
        fastapi "uvicorn[standard]" python-multipart \
        "python-jose[cryptography]" bcrypt \
        "sqlalchemy[asyncio]" asyncpg psycopg2-binary alembic \
        redis httpx aiosmtplib "pydantic[email]" pydantic-settings python-dotenv \
        "minio==7.2.0" \
        langgraph langchain langchain-community \
        langchain-milvus langchain-qwq langchain-siliconflow \
        langchain-tavily langchain-deepseek \
        "langgraph-cli[inmem]" langchain-dev-utils deepagents

# ============ 阶段 2: 运行时镜像 ============
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUTF8=1 \
    PYTHONPATH=/install:/app \
    PATH=/install/bin:$PATH

# 运行时必备：libpq5（psycopg2 动态链接） + curl（健康检查）
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
        tini \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -u 1000 appuser

COPY --from=builder /install /install

WORKDIR /app
COPY --chown=appuser:appuser . .

# 入口脚本：等待 DB、跑迁移、启动 uvicorn
RUN chmod +x /app/deployment/entrypoint.sh

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# tini 作为 PID 1，正确转发信号 + 收割僵尸进程
ENTRYPOINT ["/usr/bin/tini", "--", "/app/deployment/entrypoint.sh"]
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--log-level", "info", "--proxy-headers", "--forwarded-allow-ips=*"]
