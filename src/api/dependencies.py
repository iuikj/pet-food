"""
FastAPI 依赖注入
提供数据库、Redis 等依赖

注意：认证依赖已迁移至 src/api/middleware/auth.py
      本文件仅保留基础设施依赖（数据库、Redis）
"""
from typing import AsyncGenerator, TYPE_CHECKING
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from src.db.session import get_db
from src.db.redis import get_redis

if TYPE_CHECKING:
    # 仅用于类型标注；minio 客户端仅在真正使用头像/存储路径时才加载。
    from src.api.infrastructure.minio_storage import MinioManager


# ============ 数据库依赖 ============
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话（依赖注入）

    使用方式:
    ```python
    @app.get("/users")
    async def get_users(db: AsyncSession = Depends(get_db_session)):
        result = await db.execute(select(User))
        return result.scalars().all()
    ```
    """
    async for session in get_db():
        yield session


# ============ Redis 依赖 ============
async def get_redis_client() -> redis.Redis:
    """
    获取 Redis 客户端（依赖注入）

    使用方式:
    ```python
    @app.get("/cache")
    async def get_cache(redis_client: redis.Redis = Depends(get_redis_client)):
        value = await redis_client.get("key")
        return {"value": value}
    ```
    """
    return await get_redis()


def get_minio_storage() -> "MinioManager":
    """
    获取 MinIO 存储客户端
    """
    from src.api.infrastructure.minio_storage import get_minio_client

    return get_minio_client()
