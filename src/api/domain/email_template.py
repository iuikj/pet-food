"""
邮件模板领域实体
定义邮件模板的结构和渲染逻辑
"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional


class EmailTemplateType(str, Enum):
    """邮件模板类型"""
    VERIFICATION_CODE = "verification_code"
    PASSWORD_RESET = "password_reset"


class EmailTemplate(ABC):
    """邮件模板抽象基类"""

    @abstractmethod
    def get_subject(self) -> str:
        """获取邮件主题"""
        pass

    @abstractmethod
    def get_body(self) -> str:
        """获取邮件正文（HTML）"""
        pass

    @abstractmethod
    def get_text_body(self) -> str:
        """获取纯文本正文"""
        pass


class VerificationCodeEmailTemplate(EmailTemplate):
    """验证码邮件模板"""

    def __init__(
        self,
        code: str,
        app_name: str = "宠物饮食计划智能助手",
        expire_minutes: int = 10
    ):
        self.code = code
        self.app_name = app_name
        self.expire_minutes = expire_minutes

    def get_subject(self) -> str:
        return f"【{self.app_name}】您的验证码是 {self.code}"

    def get_body(self) -> str:
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>验证码</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    background-color: #f5f5f5;
                    margin: 0;
                    padding: 20px;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 30px;
                    background-color: #ffffff;
                    border-radius: 8px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                }}
                .header {{
                    color: #4CAF50;
                    font-size: 24px;
                    margin-bottom: 20px;
                    font-weight: bold;
                }}
                .code-box {{
                    background-color: #f5f5f5;
                    padding: 20px;
                    text-align: center;
                    font-size: 28px;
                    font-weight: bold;
                    margin: 20px 0;
                    letter-spacing: 4px;
                    border-radius: 4px;
                    color: #333;
                }}
                .footer {{
                    color: #999;
                    font-size: 12px;
                    margin-top: 30px;
                    border-top: 1px solid #eee;
                    padding-top: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">{self.app_name}</div>
                <p>您好！</p>
                <p>您正在进行身份验证，验证码为：</p>
                <div class="code-box">{self.code}</div>
                <p>验证码有效期为 <strong>{self.expire_minutes} 分钟</strong>，请尽快使用。</p>
                <p>如果这不是您的操作，请忽略此邮件。</p>
                <div class="footer">
                    此邮件由系统自动发送，请勿直接回复。<br>
                    {self.app_name} © 2025
                </div>
            </div>
        </body>
        </html>
        """

    def get_text_body(self) -> str:
        return f"""
        【{self.app_name}】您的验证码是 {self.code}

        您好！

        您正在进行身份验证，验证码为：{self.code}

        验证码有效期为 {self.expire_minutes} 分钟，请尽快使用。

        如果这不是您的操作，请忽略此邮件。

        ---
        此邮件由系统自动发送，请勿直接回复。
        {self.app_name} © 2025
        """


class PasswordResetEmailTemplate(EmailTemplate):
    """密码重置邮件模板"""

    def __init__(
        self,
        code: str,
        app_name: str = "宠物饮食计划智能助手",
        expire_minutes: int = 10
    ):
        self.code = code
        self.app_name = app_name
        self.expire_minutes = expire_minutes

    def get_subject(self) -> str:
        return f"【{self.app_name}】密码重置验证码"

    def get_body(self) -> str:
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>密码重置</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    background-color: #f5f5f5;
                    margin: 0;
                    padding: 20px;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    padding: 30px;
                    background-color: #ffffff;
                    border-radius: 8px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                }}
                .header {{
                    color: #FF5722;
                    font-size: 24px;
                    margin-bottom: 20px;
                    font-weight: bold;
                }}
                .code-box {{
                    background-color: #fff3e0;
                    padding: 20px;
                    text-align: center;
                    font-size: 28px;
                    font-weight: bold;
                    margin: 20px 0;
                    letter-spacing: 4px;
                    border-radius: 4px;
                    color: #FF5722;
                    border: 2px solid #FF5722;
                }}
                .warning {{
                    background-color: #fff3e0;
                    padding: 15px;
                    border-radius: 4px;
                    margin: 20px 0;
                    color: #FF5722;
                }}
                .footer {{
                    color: #999;
                    font-size: 12px;
                    margin-top: 30px;
                    border-top: 1px solid #eee;
                    padding-top: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">{self.app_name} - 密码重置</div>
                <p>您好！</p>
                <p>您正在重置密码，验证码为：</p>
                <div class="code-box">{self.code}</div>
                <p>验证码有效期为 <strong>{self.expire_minutes} 分钟</strong>。</p>
                <div class="warning">
                    <strong>安全提示：</strong><br>
                    如果这不是您的操作，请立即修改密码或联系客服。
                </div>
                <div class="footer">
                    此邮件由系统自动发送，请勿直接回复。<br>
                    {self.app_name} © 2025
                </div>
            </div>
        </body>
        </html>
        """

    def get_text_body(self) -> str:
        return f"""
        【{self.app_name}】密码重置验证码

        您好！

        您正在重置密码，验证码为：{self.code}

        验证码有效期为 {self.expire_minutes} 分钟。

        【安全提示】
        如果这不是您的操作，请立即修改密码或联系客服。

        ---
        此邮件由系统自动发送，请勿直接回复。
        {self.app_name} © 2025
        """


class TemplateFactory:
    """邮件模板工厂"""

    @staticmethod
    def create(template_type: EmailTemplateType, **kwargs) -> EmailTemplate:
        """
        创建邮件模板

        Args:
            template_type: 模板类型
            **kwargs: 模板参数（code, app_name, expire_minutes 等）

        Returns:
            EmailTemplate: 邮件模板实例

        Raises:
            ValueError: 不支持的模板类型
        """
        if template_type == EmailTemplateType.VERIFICATION_CODE:
            return VerificationCodeEmailTemplate(**kwargs)
        elif template_type == EmailTemplateType.PASSWORD_RESET:
            return PasswordResetEmailTemplate(**kwargs)
        else:
            raise ValueError(f"不支持的模板类型: {template_type}")
