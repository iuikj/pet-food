"""
基础设施层接口定义
定义可替换的外部服务接口
"""
from abc import ABC, abstractmethod
from typing import Optional

from src.api.domain.verification import VerificationCode, VerificationCodeType
from src.api.domain.email_template import EmailTemplate


class StorageException(Exception):
    """存储服务异常"""
    pass


class EmailException(Exception):
    """邮件发送异常"""
    pass


class IEmailSender(ABC):
    """邮件发送接口"""

    @abstractmethod
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
        pass

    @abstractmethod
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
        pass


class ICodeGenerator(ABC):
    """验证码生成器接口"""

    @abstractmethod
    def generate(self, length: int = 6) -> str:
        """
        生成验证码

        Args:
            length: 验证码长度

        Returns:
            str: 生成的验证码
        """
        pass


class ICodeStorage(ABC):
    """验证码存储接口"""

    @abstractmethod
    async def save_code(self, code: VerificationCode) -> bool:
        """
        保存验证码

        Args:
            code: 验证码实体

        Returns:
            bool: 保存成功返回 True

        Raises:
            StorageException: 存储失败时抛出
        """
        pass

    @abstractmethod
    async def get_code(
        self,
        email: str,
        code_type: VerificationCodeType
    ) -> Optional[VerificationCode]:
        """
        获取验证码

        Args:
            email: 邮箱地址
            code_type: 验证码类型

        Returns:
            Optional[VerificationCode]: 验证码实体，不存在返回 None

        Raises:
            StorageException: 存储失败时抛出
        """
        pass

    @abstractmethod
    async def update_code(self, code: VerificationCode) -> bool:
        """
        更新验证码

        Args:
            code: 验证码实体

        Returns:
            bool: 更新成功返回 True

        Raises:
            StorageException: 存储失败时抛出
        """
        pass

    @abstractmethod
    async def delete_code(self, email: str, code_type: VerificationCodeType) -> bool:
        """
        删除验证码

        Args:
            email: 邮箱地址
            code_type: 验证码类型

        Returns:
            bool: 删除成功返回 True

        Raises:
            StorageException: 存储失败时抛出
        """
        pass

    @abstractmethod
    async def set_cooldown(self, email: str, seconds: int):
        """
        设置冷却时间

        Args:
            email: 邮箱地址
            seconds: 冷却时间（秒）

        Raises:
            StorageException: 存储失败时抛出
        """
        pass

    @abstractmethod
    async def clear_cooldown(self, email: str):
        """
        清除冷却时间

        Args:
            email: 邮箱地址

        Raises:
            StorageException: 存储失败时抛出
        """
        pass

    @abstractmethod
    async def check_cooldown(self, email: str) -> int:
        """
        检查冷却时间

        Args:
            email: 邮箱地址

        Returns:
            int: 剩余冷却时间（秒），0 表示可发送

        Raises:
            StorageException: 存储失败时抛出
        """
        pass

    @abstractmethod
    async def increment_daily_send_count(self, email: str) -> int:
        """
        增加当日发送次数

        Args:
            email: 邮箱地址

        Returns:
            int: 当日累计发送次数

        Raises:
            StorageException: 存储失败时抛出
        """
        pass

    @abstractmethod
    async def get_daily_send_count(self, email: str) -> int:
        """
        获取当日发送次数

        Args:
            email: 邮箱地址

        Returns:
            int: 当日累计发送次数，无记录返回 0

        Raises:
            StorageException: 存储失败时抛出
        """
        pass
