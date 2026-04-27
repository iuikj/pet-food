"""
FastAPI 应用入口。

这里保留开发环境下的自动建表体验，但生产环境不再执行 create_all，
避免每次启动都把 schema 检查成本放到运行时。
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from src.api.config import settings
from src.db.redis import close_redis, test_redis_connection
from src.db.session import close_db, test_connection
from src.__version__ import __version__

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动阶段只做基础探活，生产模式跳过 create_all。
    logger.info("=" * 60)
    logger.info("Starting FastAPI application")
    logger.info("  environment: %s", "development" if settings.is_dev else "production")
    logger.info("  bind: http://%s:%s", settings.api_host, settings.api_port)
    logger.info("=" * 60)

    db_ok = await test_connection()
    if db_ok and settings.is_dev:
        logger.info("Database connection ok; create_all remains enabled in dev")
        try:
            from src.db.session import engine, Base

            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("Database metadata ensured")
        except Exception as exc:
            logger.error("Database metadata init failed: %s", exc)
    elif db_ok:
        logger.info("Database connection ok; skip create_all outside dev")

    # Redis 只做轻量探活，不在启动阶段执行额外预热逻辑。
    redis_ok = await test_redis_connection()
    if db_ok and redis_ok:
        logger.info("Infrastructure health check passed")
    else:
        logger.warning("Infrastructure health check degraded")

    yield

    # 应用退出时统一关闭连接池。
    logger.info("Shutting down FastAPI application")
    await close_db()
    await close_redis()
    logger.info("Shutdown complete")


app = FastAPI(
    title="Pet Food Diet Plan Assistant API",
    description="Backend API for diet plan generation, meals, pets, tasks, and analysis.",
    version=__version__,
    docs_url="/docs" if settings.is_dev else None,
    redoc_url="/redoc" if settings.is_dev else None,
    openapi_url="/openapi.json" if settings.is_dev else None,
    lifespan=lifespan,
    debug=settings.is_dev,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

from src.api.middleware.logging import RequestLoggingMiddleware

app.add_middleware(RequestLoggingMiddleware)

if settings.rate_limit_enabled:
    from src.api.dependencies import get_redis_client
    from src.api.middleware.rate_limit import RateLimitMiddleware

    app.add_middleware(RateLimitMiddleware, redis_getter=get_redis_client)

from src.api.middleware.exceptions import setup_exception_handlers

setup_exception_handlers(app)


@app.get("/", tags=["system"])
async def root():
    return {
        "code": 0,
        "message": "Pet Food Diet Plan Assistant API is running",
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


@app.get("/health", tags=["system"])
async def health_check():
    return {
        "code": 0,
        "message": "ok",
        "data": {"status": "healthy", "version": __version__},
    }


@app.get("/health/detail", tags=["system"])
async def health_check_detail():
    db_status = await test_connection()
    redis_status = await test_redis_connection()
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "status": "healthy" if (db_status and redis_status) else "unhealthy",
            "version": __version__,
            "components": {
                "database": {"status": "healthy" if db_status else "unhealthy"},
                "redis": {"status": "healthy" if redis_status else "unhealthy"},
            },
        },
    }


from src.api.routes import analysis, auth, calendar, ingredients, meals, pets, plans, tasks, todos, verification, weights

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(verification.router, prefix="/api/v1/auth", tags=["verification"])
app.include_router(pets.router, prefix="/api/v1/pets", tags=["pets"])
app.include_router(meals.router, prefix="/api/v1/meals", tags=["meals"])
app.include_router(calendar.router, prefix="/api/v1/calendar", tags=["calendar"])
app.include_router(analysis.router, prefix="/api/v1/analysis", tags=["analysis"])
app.include_router(weights.router, prefix="/api/v1/weights", tags=["weights"])
app.include_router(plans.router, prefix="/api/v1/plans", tags=["plans"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(todos.router, prefix="/api/v1/todos", tags=["todos"])
app.include_router(ingredients.router, prefix="/api/v1/ingredients", tags=["ingredients"])


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level,
    )
