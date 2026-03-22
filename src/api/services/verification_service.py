"""
验证码服务。

这里负责验证码生成、限流、发送和校验逻辑。
第二轮优化里把发送后的计数直接返回给路由层，
避免接口尾部重复读取 Redis。
"""
import logging
import secrets
from datetime import datetime, timezone

from src.api.domain.email_template import EmailTemplateType
from src.api.domain.verification import CodeConfig, VerificationCode, VerificationCodeType
from src.api.infrastructure.interfaces import ICodeGenerator, ICodeStorage
from src.api.services.email_service import EmailService
from src.api.utils.errors import RateLimitException, ValidationException

logger = logging.getLogger(__name__)


class VerificationService:
    """验证码业务服务。"""

    def __init__(
        self,
        code_generator: ICodeGenerator,
        code_storage: ICodeStorage,
        email_service: EmailService,
        config: CodeConfig | None = None,
    ):
        self.code_generator = code_generator
        self.code_storage = code_storage
        self.email_service = email_service
        self.config = config or CodeConfig()

    async def send_verification_code(
        self,
        email: str,
        code_type: VerificationCodeType,
        template_type: EmailTemplateType = EmailTemplateType.VERIFICATION_CODE,
        expire_minutes: int = 10,
    ) -> dict:
        """
        发送验证码。

        返回值直接包含发送后的冷却时间和日发送计数，
        这样路由层无需再补两次 Redis 查询。
        """
        cooldown_seconds = await self.code_storage.check_cooldown(email)
        if cooldown_seconds > 0:
            raise RateLimitException(
                message=f"发送过于频繁，请在 {cooldown_seconds} 秒后重试",
                detail={"remaining_seconds": cooldown_seconds},
            )

        daily_count = await self.code_storage.get_daily_send_count(email)
        if daily_count >= self.config.max_daily_sends:
            raise RateLimitException(
                message="今日发送次数已达上限",
                detail={
                    "daily_limit": self.config.max_daily_sends,
                    "daily_count": daily_count,
                },
            )

        code = self.code_generator.generate(self.config.code_length)
        verification_code = VerificationCode(
            code=code,
            email=email,
            code_type=code_type,
            expires_at=datetime.now(timezone.utc) + self.config.expire_timedelta,
            is_used=False,
            attempt_count=0,
        )
        await self.code_storage.save_code(verification_code)

        try:
            # 先写入冷却和计数，再发信，失败时统一回滚。
            await self.code_storage.set_cooldown(email, self.config.cooldown_seconds)
            await self.code_storage.increment_daily_send_count(email)

            success = await self.email_service.send_verification_code(
                to_email=email,
                code=code,
                template_type=template_type,
                expire_minutes=expire_minutes,
            )
            if not success:
                logger.error("验证码邮件发送失败: email=%s", email)
                await self._rollback_send_state(email, code_type)
                raise Exception("验证码邮件发送失败")

            logger.info("验证码发送成功: email=%s, code_type=%s", email, code_type)
            return {
                "code": code,
                "cooldown_seconds": self.config.cooldown_seconds,
                "daily_count": daily_count + 1,
            }
        except Exception as exc:
            logger.error("发送验证码失败: email=%s, error=%s", email, exc)
            await self._rollback_send_state(email, code_type)
            raise

    async def _rollback_send_state(self, email: str, code_type: VerificationCodeType):
        """发送失败时回滚 Redis 中的验证码与冷却状态。"""
        try:
            await self.code_storage.delete_code(email, code_type)
            await self.code_storage.clear_cooldown(email)
            logger.debug("验证码发送状态已回滚: email=%s", email)
        except Exception as exc:
            logger.error("回滚验证码发送状态失败: email=%s, error=%s", email, exc)

    async def verify_code(
        self,
        email: str,
        code: str,
        code_type: VerificationCodeType,
    ) -> bool:
        """校验验证码是否有效。"""
        verification_code = await self.code_storage.get_code(email, code_type)
        if not verification_code:
            raise ValidationException(message="验证码不存在或已失效")

        if not verification_code.is_valid(self.config.max_attempts):
            if verification_code.is_expired():
                raise ValidationException(message="验证码已过期")
            if verification_code.is_used:
                raise ValidationException(message="验证码已使用")
            if verification_code.attempt_count >= self.config.max_attempts:
                logger.warning(
                    "验证码尝试次数超限: email=%s, attempt_count=%s",
                    email,
                    verification_code.attempt_count,
                )
                raise RateLimitException(
                    message="验证码尝试次数过多，请重新获取",
                    detail={"max_attempts": self.config.max_attempts},
                )

        # 使用常量时间比较，降低时序攻击风险。
        if not secrets.compare_digest(verification_code.code, code):
            verification_code.increment_attempt()
            await self.code_storage.update_code(verification_code)
            logger.warning(
                "验证码校验失败: email=%s, attempt_count=%s",
                email,
                verification_code.attempt_count,
            )
            raise ValidationException(message="验证码错误")

        verification_code.mark_as_used()
        await self.code_storage.update_code(verification_code)
        logger.info("验证码校验成功: email=%s, code_type=%s", email, code_type)
        return True

    async def invalidate_code(
        self,
        email: str,
        code_type: VerificationCodeType,
    ):
        """主动失效指定验证码。"""
        await self.code_storage.delete_code(email, code_type)
        logger.debug("验证码已失效: email=%s, code_type=%s", email, code_type)
