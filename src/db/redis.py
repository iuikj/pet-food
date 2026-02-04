"""
Redis 客户端管理
"""
import json
from typing import Any, Optional
import redis.asyncio as redis
from redis.asyncio import ConnectionPool

from src.api.config import settings


# 创建 Redis 连接池
pool: Optional[ConnectionPool] = None


def get_redis_pool() -> ConnectionPool:
    """
    获取 Redis 连接池

    Returns:
        ConnectionPool: Redis 连接池
    """
    global pool
    if pool is None:
        pool = ConnectionPool.from_url(
            settings.redis_url,
            decode_responses=True,  # 自动解码为字符串
            max_connections=50,  # 最大连接数
        )
    return pool


async def get_redis() -> redis.Redis:
    """
    获取 Redis 客户端（依赖注入）

    使用方式:
    ```python
    @app.get("/cache")
    async def get_cache(redis_client: redis.Redis = Depends(get_redis)):
        value = await redis_client.get("key")
        return {"value": value}
    ```
    """
    return redis.Redis(connection_pool=get_redis_pool())


async def close_redis():
    """关闭 Redis 连接池"""
    global pool
    if pool:
        await pool.disconnect()
        pool = None


async def set_json(key: str, value: Any, expire: int = 3600) -> bool:
    """
    存储 JSON 数据

    Args:
        key: Redis 键
        value: 要存储的值（自动序列化为 JSON）
        expire: 过期时间（秒），默认 1 小时

    Returns:
        bool: 是否成功
    """
    try:
        client = await get_redis()
        json_str = json.dumps(value, ensure_ascii=False)
        await client.setex(key, expire, json_str)
        return True
    except Exception as e:
        print(f"[ERROR] Redis set JSON failed: {e}")
        return False


async def get_json(key: str) -> Optional[Any]:
    """
    获取 JSON 数据

    Args:
        key: Redis 键

    Returns:
        解析后的值，不存在或失败返回 None
    """
    try:
        client = await get_redis()
        json_str = await client.get(key)
        if json_str is None:
            return None
        return json.loads(json_str)
    except Exception as e:
        print(f"[ERROR] Redis get JSON failed: {e}")
        return None


async def delete_keys(pattern: str) -> int:
    """
    批量删除键

    Args:
        pattern: 键模式（如 "user:*"）

    Returns:
        int: 删除的键数量
    """
    try:
        client = await get_redis()
        keys = []
        async for key in client.scan_iter(match=pattern):
            keys.append(key)
        if keys:
            return await client.delete(*keys)
        return 0
    except Exception as e:
        print(f"[ERROR] Redis batch delete failed: {e}")
        return 0


async def test_redis_connection() -> bool:
    """测试 Redis 连接"""
    try:
        client = await get_redis()
        await client.ping()
        print("[OK] Redis connection successful")
        return True
    except Exception as e:
        print(f"[ERROR] Redis connection failed: {e}")
        return False
