"""
邮件服务
负责邮件发送的核心业务逻辑
"""
import logging
from typing import Optional

from src.api.infrastructure.interfaces import IEmailSender, EmailException
from src.api.domain.email_template import EmailTemplate, EmailTemplateType, TemplateFactory

logger = logging.getLogger(__name__)


class EmailService:
    """邮件服务类"""

    def __init__(self, email_sender: IEmailSender):
        self.email_sender = email_sender

    async def send_verification_code(
        self,
        to_email: str,
        code: str,
        template_type: EmailTemplateType = EmailTemplateType.VERIFICATION_CODE,
        from_name: Optional[str] = None,
        expire_minutes: int = 10
    ) -> bool:
        """
        发送验证码邮件

        Args:
            to_email: 收件人邮箱
            code: 验证码
            template_type: 邮件模板类型
            from_name: 发件人名称（可选）
            expire_minutes: 验证码有效期（分钟）

        Returns:
            bool: 是否发送成功

        Raises:
            EmailException: 邮件发送失败时抛出
        """
        try:
            # 创建邮件模板，传入有效期
            template = TemplateFactory.create(
                template_type,
                code=code,
                expire_minutes=expire_minutes
            )

            # 发送邮件
            success = await self.email_sender.send_template_email(
                to_email=to_email,
                template=template,
                from_name=from_name
            )

            if success:
                logger.info(f"验证码邮件发送成功: {to_email}, type={template_type}")
            else:
                logger.warning(f"验证码邮件发送失败: {to_email}, type={template_type}")

            return success
        except Exception as e:
            logger.error(f"发送验证码邮件异常: {to_email}, error={e}", exc_info=True)
            raise EmailException(f"邮件发送失败: {e}") from e

    async def send_custom_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
        from_name: Optional[str] = None
    ) -> bool:
        """
        发送自定义邮件

        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            html_body: HTML 正文
            text_body: 纯文本正文（可选）
            from_name: 发件人名称（可选）

        Returns:
            bool: 是否发送成功

        Raises:
            EmailException: 邮件发送失败时抛出
        """
        try:
            return await self.email_sender.send_email(
                to_email=to_email,
                subject=subject,
                html_body=html_body,
                text_body=text_body,
                from_name=from_name
            )
        except Exception as e:
            logger.error(f"发送自定义邮件异常: {to_email}, error={e}", exc_info=True)
            raise EmailException(f"邮件发送失败: {e}") from e
