"""
验证码领域实体
定义验证码相关的核心业务对象
"""
import re
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, field_validator

# 邮箱验证正则表达式
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')


class VerificationCodeType(str, Enum):
    """验证码类型枚举"""
    REGISTER = "register"                     # 注册验证码
    PASSWORD_RESET = "password_reset"           # 找回密码验证码
    PASSWORD_CHANGE = "password_change"          # 修改密码验证码

    @classmethod
    def from_string(cls, value: str) -> Optional["VerificationCodeType"]:
        """从字符串转换为枚举"""
        try:
            return cls(value)
        except ValueError:
            return None


class VerificationCode(BaseModel):
    """验证码实体"""
    code: str = Field(..., min_length=6, max_length=6, description="6位验证码")
    email: str = Field(..., description="邮箱地址")
    code_type: VerificationCodeType = Field(..., description="验证码类型")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="创建时间")
    expires_at: datetime = Field(..., description="过期时间")
    is_used: bool = Field(default=False, description="是否已使用")
    used_at: Optional[datetime] = Field(None, description="使用时间")
    attempt_count: int = Field(default=0, description="验证尝试次数")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        """验证邮箱格式"""
        if not EMAIL_REGEX.match(v):
            raise ValueError("邮箱格式不正确")
        return v.lower()

    def is_expired(self) -> bool:
        """验证码是否过期"""
        return datetime.now(timezone.utc) > self.expires_at

    def is_valid(self, max_attempts: int = 3) -> bool:
        """
        验证码是否有效（未过期、未使用、尝试次数未超限）

        Args:
            max_attempts: 最大尝试次数，默认为 3

        Returns:
            bool: 是否有效
        """
        return (
            not self.is_expired() and
            not self.is_used and
            self.attempt_count < max_attempts
        )

    def mark_as_used(self):
        """标记验证码为已使用"""
        self.is_used = True
        self.used_at = datetime.now(timezone.utc)

    def increment_attempt(self):
        """增加验证尝试次数"""
        self.attempt_count += 1


class CodeConfig(BaseModel):
    """验证码配置"""
    code_length: int = Field(default=6, ge=4, le=8, description="验证码长度")
    expire_minutes: int = Field(default=10, ge=1, le=60, description="过期时间（分钟）")
    max_attempts: int = Field(default=3, ge=1, le=10, description="最大尝试次数")
    cooldown_seconds: int = Field(default=60, ge=30, le=300, description="发送冷却时间（秒）")
    max_daily_sends: int = Field(default=10, ge=5, le=50, description="每日最大发送次数")

    @property
    def expire_timedelta(self) -> timedelta:
        """获取过期时间差"""
        return timedelta(minutes=self.expire_minutes)
