"""
自定义异常类
定义 API 相关的异常类型
"""
from typing import Optional, Any
from fastapi import HTTPException, status


class APIException(Exception):
    """API 基础异常"""

    def __init__(
        self,
        message: str,
        code: int = -1,
        detail: Optional[Any] = None,
        status_code: int = status.HTTP_400_BAD_REQUEST
    ):
        self.message = message
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(message)


class AuthException(APIException):
    """认证异常"""

    def __init__(
        self,
        message: str = "认证失败",
        detail: Optional[Any] = None
    ):
        super().__init__(
            message=message,
            code=401,
            detail=detail,
            status_code=status.HTTP_401_UNAUTHORIZED
        )


class UnauthorizedException(APIException):
    """未授权异常"""

    def __init__(
        self,
        message: str = "未授权访问",
        detail: Optional[Any] = None
    ):
        super().__init__(
            message=message,
            code=403,
            detail=detail,
            status_code=status.HTTP_403_FORBIDDEN
        )


class NotFoundException(APIException):
    """资源未找到异常"""

    def __init__(
        self,
        message: str = "资源未找到",
        detail: Optional[Any] = None
    ):
        super().__init__(
            message=message,
            code=404,
            detail=detail,
            status_code=status.HTTP_404_NOT_FOUND
        )


class ValidationException(APIException):
    """数据验证异常"""

    def __init__(
        self,
        message: str = "数据验证失败",
        detail: Optional[Any] = None
    ):
        super().__init__(
            message=message,
            code=422,
            detail=detail,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )


class DuplicateException(APIException):
    """重复资源异常"""

    def __init__(
        self,
        message: str = "资源已存在",
        detail: Optional[Any] = None
    ):
        super().__init__(
            message=message,
            code=409,
            detail=detail,
            status_code=status.HTTP_409_CONFLICT
        )


class RateLimitException(APIException):
    """速率限制异常"""

    def __init__(
        self,
        message: str = "请求过于频繁",
        detail: Optional[Any] = None
    ):
        super().__init__(
            message=message,
            code=429,
            detail=detail,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS
        )


class TaskException(APIException):
    """任务异常"""

    def __init__(
        self,
        message: str = "任务执行失败",
        detail: Optional[Any] = None
    ):
        super().__init__(
            message=message,
            code=500,
            detail=detail,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# 将自定义异常转换为 HTTPException
def to_http_exception(exc: APIException) -> HTTPException:
    """
    将自定义异常转换为 FastAPI HTTPException

    Args:
        exc: 自定义异常

    Returns:
        HTTPException
    """
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "code": exc.code,
            "message": exc.message,
            "detail": exc.detail,
        }
    )
