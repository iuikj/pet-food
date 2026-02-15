#!/bin/bash
# FastAPI 开发环境快速启动脚本 (Linux/macOS)

set -e

echo "========================================"
echo "宠物饮食计划助手 - 开发环境启动脚本"
echo "========================================"
echo ""

# 检查 .env 文件是否存在
if [ ! -f ".env" ]; then
    echo "[警告] 未找到 .env 文件"
    echo "正在从 .env.example 复制..."
    cp .env.example .env
    echo ""
    echo "[重要] 请修改 .env 文件中的以下配置："
    echo "  - JWT_SECRET_KEY（生产环境必须修改）"
    echo "  - DATABASE_URL"
    echo "  - REDIS_URL"
    echo "  - LLM API 密钥"
    echo ""
    read -p "按回车键继续..."
fi

# 检查 Docker 是否运行
if ! docker info > /dev/null 2>&1; then
    echo "[错误] Docker 未运行，请先启动 Docker"
    exit 1
fi

# 启动 PostgreSQL 和 Redis
echo "[1/3] 启动 PostgreSQL 和 Redis..."
docker-compose -f deployment/docker-compose.dev.yml up -d

if [ $? -ne 0 ]; then
    echo "[错误] Docker 服务启动失败"
    exit 1
fi

echo "[完成] PostgreSQL 和 Redis 已启动"
echo ""

# 等待数据库就绪
echo "[2/3] 等待数据库就绪..."
sleep 3

# 安装依赖
echo "[3/3] 检查 Python 依赖..."
uv pip install -e . --quiet

if [ $? -ne 0 ]; then
    echo "[错误] 依赖安装失败"
    exit 1
fi

echo "[完成] Python 依赖已安装"
echo ""

# 显示启动命令
echo "========================================"
echo "开发环境已准备就绪！"
echo "========================================"
echo ""
echo "数据库信息："
echo "  PostgreSQL: localhost:5432"
echo "  Redis:      localhost:6379"
echo "  pgAdmin:    http://localhost:5050 (可选)"
echo "  Redis Cmd:  http://localhost:8081 (可选)"
echo ""
echo "启动 FastAPI 服务器，请运行："
echo ""
echo "  uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "或使用启动脚本："
echo "  python scripts/run_api.py"
echo ""
echo "API 文档地址："
echo "  Swagger UI: http://localhost:8000/docs"
echo "  ReDoc:      http://localhost:8000/redoc"
echo ""
