"""
认证中间件
提供 JWT Token 验证和用户认证功能
"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.api.utils.security import verify_token
from src.api.utils.errors import AuthException

# HTTP Bearer 认证方案
security = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[str]:
    """
    获取当前用户 ID（可选认证）

    如果请求头中提供了有效的 Token，返回用户 ID
    如果未提供 Token，返回 None

    Args:
        credentials: HTTP Bearer 凭证

    Returns:
        用户 ID 或 None

    Raises:
        HTTPException: Token 无效
    """
    if credentials is None:
        return None

    try:
        token = credentials.credentials
        payload = verify_token(token, token_type="access")
        user_id = payload.get("sub")
        return user_id

    except ValueError as e:
        # Token 无效，但因为是可选认证，所以返回 None 而不是抛出异常
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """
    获取当前用户 ID（必需认证）

    如果请求头中未提供 Token 或 Token 无效，抛出 401 异常

    Args:
        credentials: HTTP Bearer 凭证

    Returns:
        用户 ID

    Raises:
        HTTPException: 未提供 Token 或 Token 无效
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": 401,
                "message": "未提供认证凭据",
                "detail": None
            },
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        token = credentials.credentials
        payload = verify_token(token, token_type="access")
        user_id = payload.get("sub")

        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "code": 401,
                    "message": "Token 载荷无效",
                    "detail": None
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        return user_id

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": 401,
                "message": str(e),
                "detail": None
            },
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> str:
    """
    获取当前激活用户 ID

    验证用户是否激活（未被封禁）

    Args:
        current_user_id: 当前用户 ID
        db: 数据库会话

    Returns:
        用户 ID

    Raises:
        HTTPException: 用户未激活
    """
    from src.db.models import User
    from sqlalchemy import select

    result = await db.execute(
        select(User).where(User.id == current_user_id)
    )
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": 404,
                "message": "用户不存在",
                "detail": None
            }
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": 403,
                "message": "用户已被禁用",
                "detail": None
            }
        )

    return current_user_id


async def require_superuser(
    current_user_id: str = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db_session)
) -> str:
    """
    要求超级用户权限

    Args:
        current_user_id: 当前用户 ID
        db: 数据库会话

    Returns:
        用户 ID

    Raises:
        HTTPException: 用户不是超级管理员
    """
    from src.db.models import User
    from sqlalchemy import select

    result = await db.execute(
        select(User).where(User.id == current_user_id)
    )
    user = result.scalars().first()

    if not user or not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": 403,
                "message": "需要超级管理员权限",
                "detail": None
            }
        )

    return current_user_id
