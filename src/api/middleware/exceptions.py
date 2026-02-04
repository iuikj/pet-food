"""
全局异常处理器
统一处理所有异常并返回标准格式
"""
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging

logger = logging.getLogger(__name__)


def setup_exception_handlers(app: FastAPI):
    """设置全局异常处理器"""

    @app.exception_handler(APIException)
    async def api_exception_handler(request: Request, exc: APIException):
        """处理自定义 API 异常"""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "detail": exc.detail,
            }
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """处理 HTTP 异常"""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.status_code,
                "message": exc.detail,
                "detail": None,
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """处理请求验证异常"""
        errors = []
        for error in exc.errors():
            errors.append({
                "field": ".".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"]
            })

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "code": 422,
                "message": "请求数据验证失败",
                "detail": errors
            }
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """处理所有未捕获的异常"""
        # 记录错误日志
        logger.error(
            f"❌ 未捕获的异常: {exc}",
            exc_info=True,
            extra={
                "path": str(request.url),
                "method": request.method,
                "client_ip": request.client.host if request.client else "unknown"
            }
        )

        # 返回通用错误响应
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "code": -1,
                "message": "服务器内部错误",
                "detail": str(exc) if app.debug else "请联系管理员"
            }
        )


class APIException(Exception):
    """自定义 API 异常基类"""

    def __init__(
        self,
        message: str,
        code: int = -1,
        detail: any = None,
        status_code: int = status.HTTP_400_BAD_REQUEST
    ):
        self.message = message
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(message)
