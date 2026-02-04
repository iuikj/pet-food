"""
速率限制中间件
基于 Redis 实现请求速率限制
"""
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import time

from src.api.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    """速率限制中间件"""

    def __init__(self, app, redis_getter):
        """
        初始化速率限制中间件

        Args:
            app: FastAPI 应用
            redis_getter: Redis 客户端获取函数
        """
        super().__init__(app)
        self.redis_getter = redis_getter

    async def dispatch(self, request: Request, call_next):
        """处理请求"""
        # 如果未启用速率限制，直接放行
        if not settings.rate_limit_enabled:
            return await call_next(request)

        try:
            # 获取 Redis 客户端
            redis_client = await self.redis_getter()

            # 生成限制键（基于 IP 或用户 ID）
            identifier = await self._get_identifier(request)
            limit_key = f"rate_limit:{identifier}"

            # 获取当前时间窗口内的请求次数
            current = await redis_client.get(limit_key)

            if current is None:
                # 首次请求或窗口已过期
                await redis_client.setex(
                    limit_key,
                    settings.rate_limit_seconds,
                    1
                )
                return await call_next(request)

            current_count = int(current)

            if current_count >= settings.rate_limit_times:
                # 超过限制
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "code": 429,
                        "message": f"请求过于频繁，请在 {settings.rate_limit_seconds} 秒后重试",
                        "detail": {
                            "limit": settings.rate_limit_times,
                            "window": settings.rate_limit_seconds,
                            "retry_after": settings.rate_limit_seconds
                        }
                    }
                )

            # 增加计数
            await redis_client.incr(limit_key)

            # 继续处理请求
            return await call_next(request)

        except Exception as e:
            # Redis 出错时不影响正常请求
            print(f"⚠️  速率限制中间件错误: {e}")
            return await call_next(request)

    async def _get_identifier(self, request: Request) -> str:
        """
        获取请求标识符

        优先使用用户 ID，其次使用 IP 地址

        Args:
            request: 请求对象

        Returns:
            标识符字符串
        """
        # 尝试从请求头获取用户 ID
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            # 注意：这里简化处理，实际应该解析 JWT
            # 为性能考虑，这里直接使用 IP
            pass

        # 使用 IP 地址
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # 取第一个 IP（客户端真实 IP）
            ip = forwarded.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"

        return ip
