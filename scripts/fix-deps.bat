@echo off
chcp 65001>nul
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

echo =====================================================
echo    Pet Food - 依赖修复和数据库初始化
echo =====================================================

echo.
echo [1/5] 检测并修复依赖...
echo.

:: 卸载旧的 bcrypt 版本
echo - Removing old bcrypt version...
pip uninstall -y passlib bcrypt

:: 安装兼容的 bcrypt 版本
echo - Installing compatible bcrypt version...
uv pip install bcrypt==4.2.0

echo [2/5] 创建数据库...
echo.

:: 检查 PostgreSQL 是否运行
docker-compose -f deployment/docker-compose.dev.yml ps postgres >nul 2>&1
if errorlevel 1 (
    echo   [!] PostgreSQL 未运行，正在启动...
    docker-compose -f deployment/docker-compose.dev.yml up -d postgres
    timeout /t 30 >nul 2>&1
)

echo.
echo [3/5] 检查 Redis 是否运行...
docker-compose -f deployment/docker-compose.dev.yml ps redis >nul 2>&1
if errorlevel 1 (
    echo   [!] Redis 未运行，正在启动...
    docker-compose -f deployment/docker-compose.dev.yml up -d redis
    timeout /t 30 >nul 2>&1
)

echo.
echo [4/5] 创建数据库表...
echo.

:: 使用 Alembic 创建表
echo - Running Alembic migrations...
alembic upgrade head

if errorlevel 1 (
    echo   [!] Alembic 迁移失败
    pause
    goto :error_end
)

echo.
echo [5/5] 完成！
echo.
echo   =====================================================
echo   现在可以启动服务了：
echo   python main.py
echo.
echo   =====================================================
pause
exit /b 0

:error_end
echo.
echo =====================================================
echo   [!] 发生错误！
echo.
echo =====================================================
pause
exit /b 1
