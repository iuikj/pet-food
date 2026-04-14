"""
Agent 工具专用数据库查询（同步驱动 + asyncio.to_thread）

asyncpg 在首次连接时调用 os.getcwd()，被 langgraph dev 的
blockbuster 拦截。解决方案：使用 psycopg2 同步驱动，通过
asyncio.to_thread 在独立线程中执行查询，完全绕过 blockbuster。

用法:
    from src.agent.v2.tools.db import run_query
    rows = await run_query(stmt)              # list[Row]
    row  = await run_query(stmt, one=True)    # Row | None
"""
import asyncio
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

_engine = None
_factory: sessionmaker | None = None


def _ensure_factory() -> sessionmaker:
    """延迟创建同步 engine，仅在首次查询时初始化。"""
    global _engine, _factory
    if _factory is not None:
        return _factory

    async_url = os.environ.get("DATABASE_URL", "")
    if not async_url:
        raise RuntimeError("DATABASE_URL 环境变量未设置")

    # postgresql+asyncpg://... → postgresql://... (psycopg2 默认驱动)
    sync_url = async_url.replace("+asyncpg", "")

    _engine = create_engine(
        sync_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    _factory = sessionmaker(_engine, class_=Session, expire_on_commit=False)
    return _factory


def _execute_sync(stmt, one: bool = False, scalars: bool = True):
    """在当前线程中执行 SQL（同步）。

    scalars=True: 返回 ORM 对象列表（适用于 select(Model)）
    scalars=False: 返回原始 Row 列表（适用于 select(col1, col2, ...)）
    """
    factory = _ensure_factory()
    with factory() as session:
        result = session.execute(stmt)
        if one:
            return result.scalar_one_or_none()
        if scalars:
            return result.scalars().all()
        return result.all()


async def run_query(stmt, one: bool = False, scalars: bool = True):
    """将 DB 查询放到独立线程执行，避免 blockbuster 拦截。

    Args:
        stmt: SQLAlchemy select() 语句
        one: True → scalar_one_or_none, False → list
        scalars: True → 返回 ORM 对象, False → 返回原始 Row（用于 group_by 等聚合查询）
    """
    return await asyncio.to_thread(_execute_sync, stmt, one, scalars)
