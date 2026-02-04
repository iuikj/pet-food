"""
验证码服务
负责验证码的生成、存储、验证等核心业务逻辑
"""
import logging
import secrets
from datetime import datetime, timezone

from src.api.domain.verification import VerificationCode, VerificationCodeType, CodeConfig
from src.api.domain.email_template import EmailTemplateType
from src.api.infrastructure.interfaces import ICodeGenerator, ICodeStorage
from src.api.services.email_service import EmailService
from src.api.utils.errors import ValidationException, RateLimitException

logger = logging.getLogger(__name__)


class VerificationService:
    """验证码服务类"""

    def __init__(
        self,
        code_generator: ICodeGenerator,
        code_storage: ICodeStorage,
        email_service: EmailService,
        config: CodeConfig | None = None
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
        expire_minutes: int = 10
    ) -> str:
        """
        发送验证码

        使用示例:
        ```python
        try:
            code = await verification_service.send_verification_code(
                email="user@example.com",
                code_type=VerificationCodeType.REGISTER,
                template_type=EmailTemplateType.VERIFICATION_CODE
            )
            logger.info(f"验证码已发送: {code}")
        except RateLimitException as e:
            logger.warning(f"发送过于频繁: {e.message}")
        ```

        Args:
            email: 邮箱地址
            code_type: 验证码类型
            template_type: 邮件模板类型

        Returns:
            str: 生成的验证码

        Raises:
            RateLimitException: 超过速率限制
            Exception: 邮件发送失败
        """
        # 1. 检查冷却时间
        cooldown_seconds = await self.code_storage.check_cooldown(email)
        if cooldown_seconds > 0:
            raise RateLimitException(
                message=f"发送过于频繁，请 {cooldown_seconds} 秒后再试",
                detail={"remaining_seconds": cooldown_seconds}
            )

        # 2. 检查每日发送次数
        daily_count = await self.code_storage.get_daily_send_count(email)
        if daily_count >= self.config.max_daily_sends:
            raise RateLimitException(
                message="今日发送次数已达上限，请明天再试",
                detail={"daily_limit": self.config.max_daily_sends, "daily_count": daily_count}
            )

        # 3. 生成验证码
        code = self.code_generator.generate(self.config.code_length)

        # 4. 创建验证码实体
        verification_code = VerificationCode(
            code=code,
            email=email,
            code_type=code_type,
            expires_at=datetime.now(timezone.utc) + self.config.expire_timedelta,
            is_used=False,
            attempt_count=0
        )

        # 5. 保存验证码
        await self.code_storage.save_code(verification_code)

        try:
            # 6. 设置冷却时间
            await self.code_storage.set_cooldown(email, self.config.cooldown_seconds)

            # 7. 增加每日发送次数
            await self.code_storage.increment_daily_send_count(email)

            # 8. 发送邮件
            success = await self.email_service.send_verification_code(
                to_email=email,
                code=code,
                template_type=template_type,
                expire_minutes=expire_minutes
            )

            if not success:
                # 发送失败，清理所有状态（事务回滚）
                logger.error(f"邮件发送失败，清理状态: email={email}")
                await self._rollback_send_state(email, code_type)
                raise Exception("邮件发送失败，请稍后重试")

            logger.info(f"验证码发送成功: email={email}, code_type={code_type}")
            return code

        except Exception as e:
            # 发生任何异常，清理状态
            logger.error(f"发送验证码时发生异常，清理状态: email={email}, error={e}")
            await self._rollback_send_state(email, code_type)
            raise

    async def _rollback_send_state(self, email: str, code_type: VerificationCodeType):
        """
        回滚发送验证码时的状态

        Args:
            email: 邮箱地址
            code_type: 验证码类型
        """
        try:
            # 删除验证码
            await self.code_storage.delete_code(email, code_type)
            # 清除冷却时间
            await self.code_storage.clear_cooldown(email)
            # 减少每日发送计数（可选，因为冷却时间已清除）
            logger.debug(f"状态回滚完成: email={email}")
        except Exception as e:
            logger.error(f"状态回滚失败: email={email}, error={e}")

    async def verify_code(
        self,
        email: str,
        code: str,
        code_type: VerificationCodeType
    ) -> bool:
        """
        验证验证码

        Args:
            email: 邮箱地址
            code: 验证码
            code_type: 验证码类型

        Returns:
            bool: 是否验证成功

        Raises:
            ValidationException: 验证码无效、过期或已使用
            RateLimitException: 验证尝试次数超限
        """
        # 1. 获取验证码
        verification_code = await self.code_storage.get_code(email, code_type)

        if not verification_code:
            raise ValidationException(message="验证码不存在或已过期")

        # 2. 检查验证码是否有效
        if not verification_code.is_valid(self.config.max_attempts):
            if verification_code.is_expired():
                raise ValidationException(message="验证码已过期")
            if verification_code.is_used:
                raise ValidationException(message="验证码已使用")
            if verification_code.attempt_count >= self.config.max_attempts:
                logger.warning(f"验证码错误次数过多: email={email}, attempt_count={verification_code.attempt_count}")
                raise RateLimitException(
                    message="验证码错误次数过多，请重新获取",
                    detail={"max_attempts": self.config.max_attempts}
                )

        # 3. 使用恒定时间比较防止时序攻击
        if not secrets.compare_digest(verification_code.code, code):
            # 增加尝试次数
            verification_code.increment_attempt()
            await self.code_storage.update_code(verification_code)
            logger.warning(f"验证码错误: email={email}, attempt_count={verification_code.attempt_count}")
            raise ValidationException(message="验证码错误")

        # 4. 验证成功，标记为已使用
        verification_code.mark_as_used()
        await self.code_storage.update_code(verification_code)
        logger.info(f"验证码验证成功: email={email}, code_type={code_type}")

        return True

    async def invalidate_code(
        self,
        email: str,
        code_type: VerificationCodeType
    ):
        """
        使验证码失效

        Args:
            email: 邮箱地址
            code_type: 验证码类型
        """
        await self.code_storage.delete_code(email, code_type)
        logger.debug(f"验证码已失效: email={email}, code_type={code_type}")
