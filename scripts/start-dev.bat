@echo off
REM FastAPI 开发环境快速启动脚本 (Windows)

echo ========================================
echo 宠物饮食计划助手 - 开发环境启动脚本
echo ========================================
echo.

REM 检查 .env 文件是否存在
if not exist ".env" (
    echo [警告] 未找到 .env 文件
    echo 正在从 .env.example 复制...
    copy .env.example .env
    echo.
    echo [重要] 请修改 .env 文件中的以下配置：
    echo   - JWT_SECRET_KEY（生产环境必须修改）
    echo   - DATABASE_URL
    echo   - REDIS_URL
    echo   - LLM API 密钥
    echo.
    pause
)

REM 检查 Docker 是否运行
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] Docker 未运行，请先启动 Docker Desktop
    pause
    exit /b 1
)

REM 启动 PostgreSQL 和 Redis
echo [1/3] 启动 PostgreSQL 和 Redis...
docker-compose -f deployment/docker-compose.dev.yml up -d

if %errorlevel% neq 0 (
    echo [错误] Docker 服务启动失败
    pause
    exit /b 1
)

echo [完成] PostgreSQL 和 Redis 已启动
echo.

REM 等待数据库就绪
echo [2/3] 等待数据库就绪...
timeout /t 3 /nobreak >nul

REM 安装依赖
echo [3/3] 检查 Python 依赖...
uv pip install -e . --quiet

if %errorlevel% neq 0 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)

echo [完成] Python 依赖已安装
echo.

REM 显示启动命令
echo ========================================
echo 开发环境已准备就绪！
echo ========================================
echo.
echo 数据库信息：
echo   PostgreSQL: localhost:5432
echo   Redis:      localhost:6379
echo   pgAdmin:    http://localhost:5050 (可选)
echo   Redis Cmd:  http://localhost:8081 (可选)
echo.
echo 启动 FastAPI 服务器，请运行：
echo.
echo   uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
echo.
echo 或使用启动脚本：
echo   python scripts/run_api.py
echo.
echo API 文档地址：
echo   Swagger UI: http://localhost:8000/docs
echo   ReDoc:      http://localhost:8000/redoc
echo.

pause
