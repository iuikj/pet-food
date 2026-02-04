"""
SMTP 邮件发送实现
使用 aiosmtplib 异步发送邮件
"""
import logging
from email.message import EmailMessage
from typing import Optional

import aiosmtplib

from src.api.infrastructure.interfaces import IEmailSender, EmailException
from src.api.domain.email_template import EmailTemplate

logger = logging.getLogger(__name__)


class SMTPEmailSender(IEmailSender):
    """SMTP 邮件发送器"""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_username: str,
        smtp_password: str,
        from_email: str,
        from_name: str = "宠物饮食计划智能助手",
        use_tls: bool = True
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.from_email = from_email
        self.from_name = from_name
        self.use_tls = use_tls

        # 验证必要配置
        if not smtp_host or not smtp_username or not smtp_password or not from_email:
            logger.warning("SMTP 配置不完整，邮件发送可能失败")

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None,
        from_name: Optional[str] = None
    ) -> bool:
        """
        发送邮件

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
            # 创建邮件对象
            message = EmailMessage()
            message["Subject"] = subject
            message["From"] = f"{from_name or self.from_name} <{self.from_email}>"
            message["To"] = to_email

            # 添加 HTML 内容
            message.add_alternative(html_body, subtype="html")

            # 如果有纯文本，也添加进去
            if text_body:
                message.add_alternative(text_body, subtype="plain")

            # 连接 SMTP 服务器并发送
            # 根据配置决定是否使用 starttls
            async with aiosmtplib.SMTP(
                hostname=self.smtp_host,
                port=self.smtp_port,
                timeout=10,
                start_tls=False,  # 不自动启用 TLS，手动控制
            ) as server:
                # 先调用 EHLO
                await server.ehlo()

                # 根据配置启用 TLS（仅在未加密时调用）
                if self.use_tls:
                    # 检查连接是否已加密
                    if not server.is_connected:
                        raise EmailException("SMTP connection failed")

                    # 只有在连接未使用 TLS 时才调用 starttls
                    # 如果服务器端已强制 TLS（如 465 端口），则跳过
                    try:
                        await server.starttls()
                        # TLS 升级后需要重新 EHLO
                        await server.ehlo()
                    except aiosmtplib.SMTPException as e:
                        # 如果已在使用 TLS，忽略错误继续
                        if "already using TLS" not in str(e).lower():
                            raise EmailException(f"TLS setup failed: {e}") from e

                # 登录
                await server.login(self.smtp_username, self.smtp_password)
                # 发送邮件
                await server.send_message(message)

            logger.debug(f"Email sent: {to_email}, subject={subject}")
            return True

        except aiosmtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}", exc_info=True)
            raise EmailException("SMTP authentication failed, please check email config") from e

        except aiosmtplib.SMTPException as e:
            logger.error(f"SMTP error: {to_email}, error={e}", exc_info=True)
            raise EmailException(f"Email sending failed: {e}") from e

        except Exception as e:
            logger.error(f"Email sending exception: {to_email}, error={e}", exc_info=True)
            raise EmailException(f"Email sending failed: {e}") from e

    async def send_template_email(
        self,
        to_email: str,
        template: EmailTemplate,
        from_name: Optional[str] = None
    ) -> bool:
        """
        发送模板邮件

        Args:
            to_email: 收件人邮箱
            template: 邮件模板对象
            from_name: 发件人名称（可选）

        Returns:
            bool: 是否发送成功

        Raises:
            EmailException: 邮件发送失败时抛出
        """
        return await self.send_email(
            to_email=to_email,
            subject=template.get_subject(),
            html_body=template.get_body(),
            text_body=template.get_text_body(),
            from_name=from_name
        )
