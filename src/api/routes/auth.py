"""
认证路由
处理用户注册、登录、Token 刷新、获取用户信息等请求
"""
import mimetypes
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session, get_minio_storage
from src.api.infrastructure.minio_storage import MinioManager
from src.api.models.request import (
    RegisterRequest, LoginRequest, RefreshTokenRequest,
    UpdateProfileRequest
)
from src.api.models.response import (
    ApiResponse,
    RegisterResponse,
    LoginResponse,
    UserResponse,
    UserProfileResponse,
    AvatarUploadResponse, TokenResponse
)
from src.api.services.auth_service import AuthService
from src.api.utils.errors import to_http_exception, APIException
from src.api.middleware.auth import get_current_active_user_record
from src.db.models import User

router = APIRouter()


@router.get(
    "/avatar/object/{object_name:path}",
    include_in_schema=False,
    name="get_user_avatar_object",
)
async def get_user_avatar_object(
    object_name: str,
    storage: MinioManager = Depends(get_minio_storage),
):
    """通过后端统一主机地址代理 MinIO 中的用户头像。"""
    file_content = await storage.adownload_file(object_name)
    if file_content is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": 3001,
                "message": "头像文件不存在",
                "detail": None,
            }
        )

    file_info = await storage.aget_file_info(object_name) or {}
    media_type = (
        file_info.get("content_type")
        or mimetypes.guess_type(object_name)[0]
        or "application/octet-stream"
    )

    return Response(
        content=file_content,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=3600"},
    )


def _resolve_user_avatar_url(
    avatar_url: Optional[str],
    storage: MinioManager,
    request: Request | None = None,
) -> Optional[str]:
    """解析用户头像访问地址：优先生成后端代理 URL，否则回退到预签名 URL。"""
    object_name = storage.extract_object_name(avatar_url)
    if object_name and request:
        return str(request.url_for("get_user_avatar_object", object_name=object_name))

    request_host = request.url.hostname if request else None
    return storage.resolve_file_url(avatar_url, request_host=request_host)


def _build_user_response(user: User, storage: MinioManager | None = None, request: Request | None = None) -> UserResponse:
    """将用户 ORM 对象转换为标准用户响应。"""
    avatar_url = user.avatar_url
    if storage:
        avatar_url = _resolve_user_avatar_url(avatar_url, storage, request)
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        nickname=user.nickname,
        phone=user.phone,
        avatar_url=avatar_url,
        is_pro=user.is_pro or False,
        plan_type=user.plan_type,
        subscription_expired_at=user.subscription_expired_at,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        created_at=user.created_at,
    )


def _build_user_profile_response(user: User, storage: MinioManager | None = None, request: Request | None = None) -> UserProfileResponse:
    """提取资料页需要的用户字段，避免重复手写映射。"""
    avatar_url = user.avatar_url
    if storage:
        avatar_url = _resolve_user_avatar_url(avatar_url, storage, request)
    return UserProfileResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        nickname=user.nickname,
        phone=user.phone,
        avatar_url=avatar_url,
        is_pro=user.is_pro or False,
        plan_type=user.plan_type,
        subscription_expired_at=user.subscription_expired_at,
        created_at=user.created_at,
    )


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
async def get_me(
    http_request: Request,
    current_user: User = Depends(get_current_active_user_record),
    storage: MinioManager = Depends(get_minio_storage),
):
    """
    获取当前登录用户的信息

    需要在请求头中携带有效的访问令牌：
    - **Authorization**: Bearer {access_token}
    """
    try:
        return ApiResponse(
            code=0,
            message="获取成功",
            data=_build_user_response(current_user, storage, http_request)
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


@router.put("/profile", response_model=ApiResponse[UserProfileResponse], summary="更新用户信息")
async def update_profile(
    http_request: Request,
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_active_user_record),
    db: AsyncSession = Depends(get_db_session),
    storage: MinioManager = Depends(get_minio_storage),
):
    """
    更新当前用户的信息

    - **nickname**: 昵称（可选）
    - **phone**: 手机号（可选，11位数字）

    需要在请求头中携带有效的访问令牌：
    - **Authorization**: Bearer {access_token}
    """
    try:
        # 更新字段
        if request.nickname is not None:
            current_user.nickname = request.nickname
        if request.phone is not None:
            current_user.phone = request.phone

        # 提交到数据库
        await db.commit()
        await db.refresh(current_user)

        # 返回更新后的用户信息
        return ApiResponse(
            code=0,
            message="更新成功",
            data=_build_user_profile_response(current_user, storage, http_request)
        )

    except APIException as e:
        raise to_http_exception(e)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": -1,
                "message": "更新用户信息失败",
                "detail": str(e)
            }
        )


@router.post("/avatar", response_model=ApiResponse[AvatarUploadResponse], summary="上传用户头像")
async def upload_avatar(
    http_request: Request,
    file: UploadFile = File(..., description="头像文件"),
    current_user: User = Depends(get_current_active_user_record),
    db: AsyncSession = Depends(get_db_session),
    storage: MinioManager = Depends(get_minio_storage),
):
    """
    上传用户头像

    - **file**: 头像文件（支持 jpg, png, webp，最大 2MB）

    需要在请求头中携带有效的访问令牌：
    - **Authorization**: Bearer {access_token}
    """
    uploaded_object_name: Optional[str] = None
    try:
        # 验证文件类型
        allowed_types = ["image/jpeg", "image/png", "image/webp"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": 5002,
                    "message": f"不支持的文件类型: {file.content_type}",
                    "detail": f"支持的类型: {', '.join(allowed_types)}"
                }
            )

        # 验证文件大小（2MB）
        max_file_size = 2 * 1024 * 1024
        content = await file.read()
        if len(content) > max_file_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": 5003,
                    "message": "文件大小超过限制",
                    "detail": "最大支持 2MB"
                }
            )

        # 推导文件扩展名
        allowed_extensions = {".jpg", ".jpeg", ".png", ".webp"}
        file_ext = ""
        if file.filename:
            parts = file.filename.rsplit(".", maxsplit=1)
            if len(parts) == 2:
                file_ext = f".{parts[1].lower()}"
        if file_ext not in allowed_extensions:
            content_type_to_ext = {
                "image/jpeg": ".jpg",
                "image/png": ".png",
                "image/webp": ".webp",
            }
            file_ext = content_type_to_ext[file.content_type]

        # 上传至 MinIO
        uploaded_object_name = f"avatars/users/{current_user.id}/{uuid4().hex}{file_ext}"
        upload_success = await storage.aupload_file(
            object_name=uploaded_object_name,
            file_data=content,
            content_type=file.content_type,
        )
        if not upload_success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "code": 5004,
                    "message": "头像文件上传失败",
                    "detail": "MinIO 存储写入失败"
                }
            )

        # 更新数据库
        old_avatar_reference = current_user.avatar_url
        avatar_reference = storage.build_object_reference(uploaded_object_name)
        current_user.avatar_url = avatar_reference
        await db.commit()
        await db.refresh(current_user)

        # 清理旧头像
        old_object_name = storage.extract_object_name(old_avatar_reference)
        if old_object_name and old_object_name != uploaded_object_name:
            await storage.adelete_file(old_object_name)

        # 解析为可访问 URL
        avatar_url = _resolve_user_avatar_url(current_user.avatar_url, storage, request=http_request)
        if not avatar_url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "code": 5005,
                    "message": "头像访问地址生成失败",
                    "detail": "MinIO 预签名 URL 生成失败"
                }
            )

        return ApiResponse(
            code=0,
            message="上传成功",
            data=AvatarUploadResponse(avatar_url=avatar_url)
        )

    except HTTPException:
        if uploaded_object_name:
            await storage.adelete_file(uploaded_object_name)
        raise
    except Exception as e:
        if uploaded_object_name:
            await storage.adelete_file(uploaded_object_name)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": 5000,
                "message": "上传头像失败",
                "detail": str(e)
            }
        )


@router.get("/subscription", response_model=ApiResponse[dict], summary="获取订阅状态")
async def get_subscription(
    current_user: User = Depends(get_current_active_user_record),
):
    """
    获取当前用户的订阅状态

    需要在请求头中携带有效的访问令牌：
    - **Authorization**: Bearer {access_token}
    """
    try:
        # 计算订阅状态
        now = datetime.now(timezone.utc)
        is_expired = False
        days_remaining = None

        if current_user.subscription_expired_at:
            is_expired = current_user.subscription_expired_at < now
            if not is_expired:
                days_remaining = max(0, (current_user.subscription_expired_at - now).days)

        return ApiResponse(
            code=0,
            message="获取成功",
            data={
                "is_pro": current_user.is_pro or False,
                "plan_type": current_user.plan_type,
                "subscription_expired_at": current_user.subscription_expired_at,
                "is_expired": is_expired,
                "days_remaining": days_remaining
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": -1,
                "message": "获取订阅状态失败",
                "detail": str(e)
            }
        )
