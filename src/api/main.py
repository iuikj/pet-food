"""
FastAPI 主应用
宠物饮食计划智能助手 API 服务
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from src.api.config import settings
from src.db.session import init_db, close_db
from src.db.redis import close_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    print("=" * 60)
    print("FastAPI 服务启动中...")
    print(f"   环境: {'开发' if settings.is_dev else '生产'}")
    print(f"   地址: http://{settings.api_host}:{settings.api_port}")
    print("=" * 60)

    # 测试数据库连接
    print("测试数据库连接...")
    from src.db.session import test_connection, Base

    db_ok = await test_connection()

    # 如果数据库连接成功，检查并创建表
    if db_ok:
        print("数据库连接正常")
        print("检查并创建数据库表...")
        try:
            # 导入数据库引擎
            from src.db.session import engine

            # 创建所有表（如果不存在）
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            print("数据库表已就绪")
        except Exception as e:
            print(f"创建数据库表时出错: {e}")
            # 继续启动，让应用在需要时尝试创建

    # 测试 Redis 连接
    print("测试 Redis 连接...")
    from src.db.redis import test_redis_connection
    redis_ok = await test_redis_connection()

    if db_ok and redis_ok:
        print("所有依赖服务连接正常")
    else:
        print("部分依赖服务连接失败，请检查配置")

    print()

    yield

    # 关闭时执行
    print("\nFastAPI 服务关闭中...")
    await close_db()
    await close_redis()
    print("所有连接已关闭")


# 创建 FastAPI 应用
app = FastAPI(
    title="宠物饮食计划智能助手 API",
    description="基于 LangGraph 多智能体系统的宠物饮食计划生成服务",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc
    openapi_url="/openapi.json",
    lifespan=lifespan,
    debug=settings.is_dev
)


# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)


# 配置 GZip 压缩
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 配置请求日志中间件
from src.api.middleware.logging import RequestLoggingMiddleware
app.add_middleware(RequestLoggingMiddleware)

# 配置速率限制中间件
if settings.rate_limit_enabled:
    from src.api.middleware.rate_limit import RateLimitMiddleware
    from src.api.dependencies import get_redis_client
    app.add_middleware(RateLimitMiddleware, redis_getter=get_redis_client)

# 配置全局异常处理器
from src.api.middleware.exceptions import setup_exception_handlers
setup_exception_handlers(app)


# 全局异常处理器
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理"""
    print(f"[ERROR] 未捕获的异常: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "code": -1,
            "message": "服务器内部错误",
            "detail": str(exc) if settings.is_dev else "请联系管理员",
        },
    )


# 根路由
@app.get("/", tags=["根路由"])
async def root():
    """根路由 - 服务状态"""
    return {
        "code": 0,
        "message": "宠物饮食计划智能助手 API 服务",
        "data": {
            "name": "Pet Food Diet Plan Assistant",
            "version": "1.0.0",
            "status": "running",
            "docs": {
                "swagger": f"http://{settings.api_host}:{settings.api_port}/docs",
                "redoc": f"http://{settings.api_host}:{settings.api_port}/redoc",
            },
        },
    }


# 健康检查路由
@app.get("/health", tags=["健康检查"])
async def health_check():
    """基础健康检查"""
    return {
        "code": 0,
        "message": "服务正常",
        "data": {
            "status": "healthy",
            "version": "1.0.0",
        },
    }


# 详细健康检查
@app.get("/health/detail", tags=["健康检查"])
async def health_check_detail():
    """详细健康检查（包含数据库和 Redis）"""
    # 检查数据库
    from src.db.session import test_connection
    db_status = await test_connection()

    # 检查 Redis
    from src.db.redis import test_redis_connection
    redis_status = await test_redis_connection()

    return {
        "code": 0,
        "message": "服务正常",
        "data": {
            "status": "healthy" if (db_status and redis_status) else "unhealthy",
            "version": "1.0.0",
            "components": {
                "database": {
                    "status": "healthy" if db_status else "unhealthy",
                },
                "redis": {
                    "status": "healthy" if redis_status else "unhealthy",
                },
            },
        },
    }


# 注册路由
from src.api.routes import auth, plans, tasks, verification, pets, meals, calendar, analysis

app.include_router(auth.router, prefix="/api/v1/auth", tags=["认证"])
app.include_router(verification.router, prefix="/api/v1/auth", tags=["验证码"])
app.include_router(pets.router, prefix="/api/v1/pets", tags=["宠物管理"])
app.include_router(meals.router, prefix="/api/v1/meals", tags=["饮食记录"])
app.include_router(calendar.router, prefix="/api/v1/calendar", tags=["日历"])
app.include_router(analysis.router, prefix="/api/v1/analysis", tags=["营养分析"])
app.include_router(plans.router, prefix="/api/v1/plans", tags=["饮食计划"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["任务管理"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level,
    )
