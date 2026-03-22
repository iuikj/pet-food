"""
数据库会话与连接管理。

这里保留连接池配置，但把事务提交责任交给 service / route 层，
避免依赖注入在所有请求末尾都执行一次无意义的 commit。
"""
import logging
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.api.config import settings

logger = logging.getLogger(__name__)


# 统一复用异步引擎，减少连接创建开销。
engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)


# 统一的异步 Session 工厂。
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """SQLAlchemy ORM 基类。"""


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    提供请求级数据库会话。

    只负责在异常时回滚，不再自动提交事务。
    写操作需要由 service 或 route 显式 commit，事务边界更清晰。
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """开发阶段创建表结构。生产环境应优先使用 Alembic。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """关闭数据库连接池。"""
    await engine.dispose()


async def test_connection() -> bool:
    """执行轻量探活查询，确认数据库连接可用。"""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("数据库连接检测失败: %s", exc)
        return False
