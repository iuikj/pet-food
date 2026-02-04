"""
验证码路由
处理验证码发送、验证、注册、找回密码、修改密码等请求
"""
from typing import Optional
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from src.api.dependencies import get_db_session, get_redis_client
from src.api.models.request import (
    SendCodeRequest,
    VerifyCodeRequest,
    RegisterWithCodeRequest,
    ResetPasswordRequest,
    ChangePasswordRequest
)
from src.api.models.response import (
    ApiResponse,
    SendCodeResponse,
    VerifyCodeResponse,
    RegisterResponse,
    TokenResponse
)
from src.api.domain.verification import VerificationCodeType, CodeConfig
from src.api.domain.email_template import EmailTemplateType
from src.api.infrastructure.redis_code_storage import RedisCodeStorage
from src.api.infrastructure.code_generator import NumericCodeGenerator
from src.api.infrastructure.email_providers.smtp_email_sender import SMTPEmailSender
from src.api.services.email_service import EmailService
from src.api.services.verification_service import VerificationService
from src.api.services.auth_service import AuthService
from src.api.utils.errors import (
    to_http_exception,
    ValidationException,
    RateLimitException,
    DuplicateException,
    APIException
)
from src.api.config import settings
from src.api.middleware.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()

# ============ 常量定义 ============

# 验证码类型映射
CODE_TYPE_MAP = {
    "register": VerificationCodeType.REGISTER,
    "password_reset": VerificationCodeType.PASSWORD_RESET,
}

# 邮件模板类型映射
TEMPLATE_TYPE_MAP = {
    VerificationCodeType.REGISTER: EmailTemplateType.VERIFICATION_CODE,
    VerificationCodeType.PASSWORD_RESET: EmailTemplateType.PASSWORD_RESET,
}

# ============ 工厂类 ============

class VerificationServiceFactory:
    """验证码服务工厂"""

    @staticmethod
    def create(redis_client: Redis) -> VerificationService:
        """创建验证码服务实例"""
        # 创建验证码存储
        code_storage = RedisCodeStorage(redis_client)

        # 创建验证码生成器
        code_generator = NumericCodeGenerator()

        # 创建邮件发送器
        email_sender = SMTPEmailSender(
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            smtp_username=settings.smtp_username,
            smtp_password=settings.smtp_password,
            from_email=settings.smtp_from_email,
            from_name="宠物饮食计划智能助手",
            use_tls=settings.smtp_use_tls
        )

        # 创建邮件服务
        email_service = EmailService(email_sender)

        # 创建验证码配置
        config = settings.to_code_config()

        # 创建验证码服务
        return VerificationService(
            code_generator=code_generator,
            code_storage=code_storage,
            email_service=email_service,
            config=config
        )


class AuthServiceFactory:
    """认证服务工厂"""

    @staticmethod
    def create(
        db: AsyncSession,
        redis_client: Redis,
        with_verification: bool = False
    ) -> AuthService:
        """创建认证服务实例"""
        verification_service = None
        if with_verification:
            verification_service = VerificationServiceFactory.create(redis_client)
        return AuthService(db, verification_service)


# ============ 依赖注入函数 ============

async def get_verification_service(
    redis_client: Redis = Depends(get_redis_client)
) -> VerificationService:
    """获取验证码服务"""
    return VerificationServiceFactory.create(redis_client)


async def get_auth_service_with_verification(
    db: AsyncSession = Depends(get_db_session),
    redis_client: Redis = Depends(get_redis_client)
) -> AuthService:
    """获取带验证码服务的认证服务"""
    return AuthServiceFactory.create(db, redis_client, with_verification=True)


# ============ 路由定义 ============

@router.post("/send-code", response_model=ApiResponse[SendCodeResponse], summary="发送验证码")
async def send_verification_code(
    request: SendCodeRequest,
    verification_service: VerificationService = Depends(get_verification_service)
):
    """
    发送验证码

    - **email**: 邮箱地址
    - **code_type**: 验证码类型（register/password_reset）
    """
    try:
        # 转换验证码类型
        code_type = CODE_TYPE_MAP.get(request.code_type)
        if not code_type:
            raise ValidationException("不支持的验证码类型")

        # 选择邮件模板类型
        template_type = TEMPLATE_TYPE_MAP.get(code_type, EmailTemplateType.VERIFICATION_CODE)

        # 发送验证码（传入有效期）
        await verification_service.send_verification_code(
            email=request.email,
            code_type=code_type,
            template_type=template_type,
            expire_minutes=settings.verification_code_expire_minutes
        )

        # 获取剩余信息
        cooldown_seconds = await verification_service.code_storage.check_cooldown(request.email)
        daily_count = await verification_service.code_storage.get_daily_send_count(request.email)

        return ApiResponse(
            code=0,
            message="验证码已发送",
            data=SendCodeResponse(
                email=request.email,
                code_type=request.code_type,
                cooldown_seconds=cooldown_seconds,
                remaining_daily_sends=settings.verification_code_max_daily_sends - daily_count,
                expire_minutes=settings.verification_code_expire_minutes
            )
        )

    except (ValidationException, RateLimitException) as e:
        raise to_http_exception(e)
    except Exception as e:
        logger.error(f"发送验证码失败: email={request.email}, error={e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": -1,
                "message": "发送验证码失败",
                "detail": str(e) if settings.is_dev else "服务器错误"
            }
        )


@router.post("/verify-code", response_model=ApiResponse[VerifyCodeResponse], summary="验证验证码")
async def verify_code(
    request: VerifyCodeRequest,
    verification_service: VerificationService = Depends(get_verification_service)
):
    """
    验证验证码

    - **email**: 邮箱地址
    - **code**: 验证码
    - **code_type**: 验证码类型（register/password_reset）
    """
    try:
        # 转换验证码类型
        code_type = CODE_TYPE_MAP.get(request.code_type)
        if not code_type:
            raise ValidationException("不支持的验证码类型")

        # 验证验证码
        is_valid = await verification_service.verify_code(
            email=request.email,
            code=request.code,
            code_type=code_type
        )

        return ApiResponse(
            code=0,
            message="验证成功",
            data=VerifyCodeResponse(
                is_valid=is_valid,
                message="验证码有效"
            )
        )

    except (ValidationException, RateLimitException) as e:
        raise to_http_exception(e)
    except Exception as e:
        logger.error(f"验证码验证失败: email={request.email}, error={e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": -1,
                "message": "验证失败",
                "detail": str(e) if settings.is_dev else "服务器错误"
            }
        )


@router.post("/verify-register", response_model=ApiResponse[RegisterResponse], summary="使用验证码注册")
async def register_with_code(
    request: RegisterWithCodeRequest,
    auth_service: AuthService = Depends(get_auth_service_with_verification)
):
    """
    使用验证码注册

    - **username**: 用户名（3-50字符，只能包含字母、数字、下划线和连字符）
    - **email**: 邮箱地址
    - **password**: 密码（6-72 字符）
    - **code**: 验证码
    """
    try:
        # 注册用户
        user, tokens = await auth_service.register_with_code(
            username=request.username,
            email=request.email,
            password=request.password,
            code=request.code
        )

        # 构造响应
        tokens_response = TokenResponse.model_validate(tokens)

        logger.info(f"用户注册成功: username={request.username}, email={request.email}")
        return ApiResponse(
            code=0,
            message="注册成功",
            data=RegisterResponse(
                user=user,
                tokens=tokens_response
            )
        )

    except (ValidationException, RateLimitException, DuplicateException) as e:
        raise to_http_exception(e)
    except Exception as e:
        logger.error(f"用户注册失败: username={request.username}, error={e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": -1,
                "message": "注册失败",
                "detail": str(e) if settings.is_dev else "服务器错误"
            }
        )


@router.post("/password/send-code", response_model=ApiResponse[SendCodeResponse], summary="找回密码-发送验证码")
async def send_password_reset_code(
    request: SendCodeRequest,
    verification_service: VerificationService = Depends(get_verification_service),
    db: AsyncSession = Depends(get_db_session)
):
    """
    找回密码 - 发送验证码

    - **email**: 邮箱地址

    注意：为了安全，无论邮箱是否注册，都会返回相同的成功响应
    """
    try:
        # 检查邮箱是否已注册
        from sqlalchemy import select
        from src.db.models import User

        result = await db.execute(
            select(User).where(User.email == request.email)
        )
        user = result.scalars().first()

        # 只有当用户存在时才发送验证码
        if user:
            await verification_service.send_verification_code(
                email=request.email,
                code_type=VerificationCodeType.PASSWORD_RESET,
                template_type=EmailTemplateType.PASSWORD_RESET,
                expire_minutes=settings.verification_code_expire_minutes
            )
            logger.info(f"密码重置验证码已发送: email={request.email}")
        else:
            # 邮箱未注册，为了安全不告知用户，但记录日志
            logger.warning(f"尝试重置未注册的邮箱密码: email={request.email}")

        # 统一返回成功响应（无论邮箱是否存在）
        cooldown_seconds = await verification_service.code_storage.check_cooldown(request.email)
        daily_count = await verification_service.code_storage.get_daily_send_count(request.email)

        return ApiResponse(
            code=0,
            message="如果该邮箱已注册，您将收到验证码",
            data=SendCodeResponse(
                email=request.email,
                code_type="password_reset",
                cooldown_seconds=cooldown_seconds,
                remaining_daily_sends=settings.verification_code_max_daily_sends - daily_count,
                expire_minutes=settings.verification_code_expire_minutes
            )
        )

    except Exception as e:
        logger.error(f"发送密码重置验证码失败: email={request.email}, error={e}", exc_info=True)
        # 即使出错也返回成功响应（防止枚举攻击）
        return ApiResponse(
            code=0,
            message="如果该邮箱已注册，您将收到验证码",
            data=SendCodeResponse(
                email=request.email,
                code_type="password_reset",
                cooldown_seconds=0,
                remaining_daily_sends=settings.verification_code_max_daily_sends,
                expire_minutes=settings.verification_code_expire_minutes
            )
        )


@router.post("/password/reset", summary="找回密码-重置密码")
async def reset_password(
    request: ResetPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service_with_verification)
):
    """
    找回密码 - 重置密码

    - **email**: 邮箱地址
    - **code**: 验证码
    - **new_password**: 新密码（6-72 字符）
    """
    try:
        # 重置密码
        await auth_service.reset_password(
            email=request.email,
            code=request.code,
            new_password=request.new_password
        )

        logger.info(f"密码重置成功: email={request.email}")
        return ApiResponse(
            code=0,
            message="密码重置成功，请使用新密码登录",
            data=None
        )

    except (ValidationException, RateLimitException) as e:
        raise to_http_exception(e)
    except Exception as e:
        logger.error(f"密码重置失败: email={request.email}, error={e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": -1,
                "message": "重置密码失败",
                "detail": str(e) if settings.is_dev else "服务器错误"
            }
        )


@router.put("/password", summary="修改密码（需登录）")
async def change_password(
    request: ChangePasswordRequest,
    current_user_id: str = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service_with_verification)
):
    """
    修改密码（需登录）

    - **old_password**: 旧密码
    - **new_password**: 新密码（6-72 字符）

    需要在请求头中携带有效的访问令牌：
    - **Authorization**: Bearer {access_token}
    """
    try:
        # 修改密码
        await auth_service.change_password(
            user_id=current_user_id,
            old_password=request.old_password,
            new_password=request.new_password
        )

        logger.info(f"密码修改成功: user_id={current_user_id}")
        return ApiResponse(
            code=0,
            message="密码修改成功",
            data=None
        )

    except (ValidationException, RateLimitException) as e:
        raise to_http_exception(e)
    except Exception as e:
        logger.error(f"密码修改失败: user_id={current_user_id}, error={e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": -1,
                "message": "修改密码失败",
                "detail": str(e) if settings.is_dev else "服务器错误"
            }
        )
