"""
认证中间件。

负责解析 JWT、校验用户状态，并为路由提供可复用的认证依赖。
"""

from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.api.utils.security import verify_token
from src.db.models import User


# 允许部分接口在未登录时继续访问，因此这里关闭默认报错。
security = HTTPBearer(auto_error=False)


def _build_auth_error(status_code: int, message: str) -> HTTPException:
    """统一构造认证相关异常，避免重复拼接响应结构。"""
    headers = {"WWW-Authenticate": "Bearer"} if status_code == status.HTTP_401_UNAUTHORIZED else None
    return HTTPException(
        status_code=status_code,
        detail={
            "code": status_code,
            "message": message,
            "detail": None,
        },
        headers=headers,
    )


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[str]:
    """可选认证：有合法 Token 时返回用户 ID，没有则返回 None。"""
    if credentials is None:
        return None

    try:
        payload = verify_token(credentials.credentials, token_type="access")
    except ValueError:
        return None

    return payload.get("sub")


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    """强制认证：解析访问令牌并返回当前用户 ID。"""
    if credentials is None:
        raise _build_auth_error(status.HTTP_401_UNAUTHORIZED, "未提供认证凭据")

    try:
        payload = verify_token(credentials.credentials, token_type="access")
    except ValueError as exc:
        raise _build_auth_error(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise _build_auth_error(status.HTTP_401_UNAUTHORIZED, "Token 载荷无效")

    return user_id


async def get_current_active_user_record(
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """
    返回已校验的用户对象。

    这里直接返回 ORM 实体，供后续依赖和路由复用，避免同一个请求里重复查询用户。
    """
    result = await db.execute(select(User).where(User.id == current_user_id))
    user = result.scalars().first()

    if user is None:
        raise _build_auth_error(status.HTTP_404_NOT_FOUND, "用户不存在")

    if not user.is_active:
        raise _build_auth_error(status.HTTP_403_FORBIDDEN, "用户已被禁用")

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_active_user_record),
) -> str:
    """兼容旧接口：保留返回用户 ID 的依赖定义。"""
    return current_user.id


async def require_superuser(
    current_user: User = Depends(get_current_active_user_record),
) -> str:
    """要求当前用户具备超级管理员权限。"""
    if not current_user.is_superuser:
        raise _build_auth_error(status.HTTP_403_FORBIDDEN, "需要超级管理员权限")

    return current_user.id
