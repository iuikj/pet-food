"""
请求日志中间件
记录所有 API 请求的详细信息
"""
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import time
import logging

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""

    async def dispatch(self, request: Request, call_next):
        """处理请求并记录日志"""

        # 记录请求开始时间
        start_time = time.time()

        # 获取请求信息
        method = request.method
        url = str(request.url)
        path = request.url.path
        client_ip = self._get_client_ip(request)

        # 跳过健康检查日志
        if path in ["/health", "/health/detail", "/"]:
            return await call_next(request)

        # 记录请求开始
        logger.info(f"📥 请求开始: {method} {path} from {client_ip}")

        # 处理请求
        try:
            response = await call_next(request)

            # 计算处理时间
            process_time = time.time() - start_time

            # 记录请求完成
            status_code = response.status_code
            logger.info(
                f"📤 请求完成: {method} {path} - "
                f"状态码: {status_code} - "
                f"耗时: {process_time:.3f}s"
            )

            # 添加响应头（处理时间）
            response.headers["X-Process-Time"] = str(round(process_time, 3))

            return response

        except Exception as e:
            # 计算处理时间
            process_time = time.time() - start_time

            # 记录请求错误
            logger.error(
                f"❌ 请求错误: {method} {path} - "
                f"错误: {str(e)} - "
                f"耗时: {process_time:.3f}s"
            )

            raise

    def _get_client_ip(self, request: Request) -> str:
        """
        获取客户端真实 IP

        Args:
            request: 请求对象

        Returns:
            IP 地址字符串
        """
        # 检查代理头
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # 直接连接
        return request.client.host if request.client else "unknown"
