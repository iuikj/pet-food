# 多阶段构建 Dockerfile - 生产环境
# 使用 uv 作为包管理器，优化镜像大小

# ============ 阶段 1: 依赖安装 ============
FROM python:3.12-slim AS builder

# 安装 uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制 uv 锁定文件和 pyproject.toml
WORKDIR /app
COPY pyproject.toml uv.lock ./

# 安装依赖
RUN pip install --no-cache-dir uv
RUN uv pip install --system --no-cache --no-deps -e .

# ============ 阶段 2: 运行时镜像 ============
FROM python:3.12-slim AS runtime

# 安装运行时依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 创建非 root 用户
RUN useradd -m -u 1000 appuser && \
    mkdir -p /home/appuser/.cache && \
    chown -R appuser:appuser /home/appuser

# 复制依赖和代码
COPY --from=builder --chown=appuser:appuser /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
WORKDIR /app
COPY --chown=appuser:appuser . .

# 切换到非 root 用户
USER appuser

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/usr/local/lib/python3.12/site-packages \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${API_PORT:-8000}/health || exit 1

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "src.api.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--log-level", "info", \
     "--access-log", "-", \
     "--error-log", "-"]
