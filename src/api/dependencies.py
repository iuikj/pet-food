"""
FastAPI 依赖注入
提供数据库、Redis、用户认证等依赖
"""
from typing import AsyncGenerator
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from src.db.session import get_db
from src.db.redis import get_redis
from src.api.config import settings


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


# ============ 认证依赖（稍后实现） ============
security = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str | None:
    """
    获取当前用户（可选认证）

    如果提供了 Token 则验证并返回用户 ID，否则返回 None
    """
    if credentials is None:
        return None

    # TODO: 实现 JWT 验证
    # token = credentials.credentials
    # payload = decode_token(token)
    # return payload.get("sub")

    return None


async def get_current_user(
    user_id: str | None = Depends(get_current_user_optional),
) -> str:
    """
    获取当前用户（必需认证）

    如果未提供 Token 或 Token 无效，抛出 401 异常
    """
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_id
