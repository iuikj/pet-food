"""
认证路由
处理用户注册、登录、Token 刷新、获取用户信息等请求
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.api.models.request import RegisterRequest, LoginRequest, RefreshTokenRequest
from src.api.models.response import (
    ApiResponse,
    RegisterResponse,
    LoginResponse,
    UserResponse,
    TokenResponse
)
from src.api.services.auth_service import AuthService
from src.api.utils.errors import to_http_exception, APIException

# 导入认证中间件的 get_current_user 函数
from src.api.middleware.auth import get_current_user

router = APIRouter()


@router.post("/register", response_model=ApiResponse[RegisterResponse], summary="用户注册")
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """
    用户注册

    - **username**: 用户名（3-50字符，只能包含字母、数字、下划线和连字符）
    - **email**: 邮箱地址
    - **password**: 密码（6-72 字符）
    """
    try:
        auth_service = AuthService(db)

        # 注册用户
        user, tokens = await auth_service.register(
            username=request.username,
            email=request.email,
            password=request.password
        )

        # 构造响应
        tokens_response = TokenResponse.model_validate(tokens)

        return ApiResponse(
            code=0,
            message="注册成功",
            data=RegisterResponse(
                user=user,
                tokens=tokens_response
            )
        )

    except APIException as e:
        raise to_http_exception(e)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": -1,
                "message": "注册失败",
                "detail": str(e)
            }
        )


@router.post("/login", response_model=ApiResponse[LoginResponse], summary="用户登录")
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """
    用户登录

    - **username**: 用户名或邮箱
    - **password**: 密码（6-72 字符）
    """
    try:
        auth_service = AuthService(db)

        # 登录用户
        user, tokens = await auth_service.login(
            username=request.username,
            password=request.password
        )

        # 构造响应
        tokens_response = TokenResponse.model_validate(tokens)

        return ApiResponse(
            code=0,
            message="登录成功",
            data=LoginResponse(
                user=user,
                tokens=tokens_response
            )
        )

    except APIException as e:
        raise to_http_exception(e)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": -1,
                "message": "登录失败",
                "detail": str(e)
            }
        )


@router.post("/refresh", response_model=ApiResponse[TokenResponse], summary="刷新 Token")
async def refresh_token(
    request: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """
    刷新访问令牌

    - **refresh_token**: 刷新令牌
    """
    try:
        auth_service = AuthService(db)

        # 刷新令牌
        new_tokens = await auth_service.refresh_tokens(request.refresh_token)

        return ApiResponse(
            code=0,
            message="刷新成功",
            data=TokenResponse.model_validate(new_tokens)
        )

    except APIException as e:
        raise to_http_exception(e)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": -1,
                "message": "刷新令牌失败",
                "detail": str(e)
            }
        )


@router.get("/me", response_model=ApiResponse[UserResponse], summary="获取当前用户信息")
async def get_current_user(
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取当前登录用户的信息

    需要在请求头中携带有效的访问令牌：
    - **Authorization**: Bearer {access_token}
    """
    try:
        auth_service = AuthService(db)

        # 获取用户信息
        user = await auth_service.get_user_by_id(current_user_id)

        return ApiResponse(
            code=0,
            message="获取成功",
            data=user
        )

    except APIException as e:
        raise to_http_exception(e)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": -1,
                "message": "获取用户信息失败",
                "detail": str(e)
            }
        )
