"""
FastAPI 应用配置
使用 Pydantic Settings 管理环境变量
"""
import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from pathlib import Path

from src.api.domain.verification import CodeConfig
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# print(f"环境变量检查:{BASE_DIR}")
# print(f"{BASE_DIR / ".env"}")
# print(os.getenv("ZAI_API_KEY"))   

class Settings(BaseSettings):
    """FastAPI 应用配置类"""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # ============ FastAPI 基础配置 ============
    api_host: str = Field(default="0.0.0.0", description="服务监听地址")
    api_port: int = Field(default=8000, description="服务监听端口")
    api_reload: bool = Field(default=True, description="自动重载（开发模式）")
    api_workers: int = Field(default=1, description="工作进程数")
    log_level: str = Field(default="info", description="日志级别")

    # ============ JWT 认证配置 ============
    jwt_secret_key: str = Field(..., description="JWT 签名密钥")
    jwt_algorithm: str = Field(default="HS256", description="JWT 签名算法")
    jwt_access_token_expire_minutes: int = Field(
        default=30,
        description="Access Token 有效期（分钟）"
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7,
        description="Refresh Token 有效期（天）"
    )

    # ============ 数据库配置 ============
    database_url: str = Field(..., description="异步数据库连接字符串")
    database_echo: bool = Field(default=False, description="是否打印 SQL 语句")

    # ============ Redis 配置 ============
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis 连接字符串")
    redis_password: str = Field(default="", description="Redis 密码")
    redis_db: int = Field(default=0, description="Redis 数据库编号")

    # ============ CORS 配置 ============
    cors_origins: List[str] = Field(
        default=["http://localhost:3000","http://localhost:8080","capacitor://localhost","https://localhost","http://localhost","*"],
        description="允许的跨域来源"
    )
    cors_allow_credentials: bool = Field(default=True, description="允许携带凭证")
    cors_allow_methods: List[str] = Field(default=["*"], description="允许的 HTTP 方法")
    cors_allow_headers: List[str] = Field(default=["*"], description="允许的请求头")

    # ============ 安全配置 ============
    secret_key: str = Field(..., description="应用密钥")
    allowed_hosts: List[str] = Field(default=["*"], description="允许的主机名")
    max_request_size: int = Field(default=10485760, description="最大请求大小（字节）")

    # ============ 任务配置 ============
    task_timeout_seconds: int = Field(default=3600, description="任务超时时间（秒）")
    task_max_concurrent: int = Field(default=5, description="最大并发任务数")

    # ============ 速率限制配置 ============
    rate_limit_enabled: bool = Field(default=True, description="是否启用速率限制")
    rate_limit_times: int = Field(default=100, description="时间窗口内最大请求次数")
    rate_limit_seconds: int = Field(default=60, description="时间窗口（秒）")

    # ============ 邮件配置 ============
    smtp_host: str = Field(default="smtp.qq.com", description="SMTP 服务器地址")
    smtp_port: int = Field(default=587, description="SMTP 端口")
    smtp_username: str = Field(default="", description="SMTP 用户名")
    smtp_password: str = Field(default="", description="SMTP 密码")
    smtp_from_email: str = Field(default="", description="发件人邮箱")
    smtp_use_tls: bool = Field(default=True, description="是否使用 TLS")

    # ============ 验证码配置 ============
    verification_code_length: int = Field(default=6, description="验证码长度")
    verification_code_expire_minutes: int = Field(default=10, description="验证码有效期（分钟）")
    verification_code_max_attempts: int = Field(default=3, description="最大验证尝试次数")
    verification_code_cooldown_seconds: int = Field(default=60, description="发送冷却时间（秒）")
    verification_code_max_daily_sends: int = Field(default=10, description="每日最大发送次数")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """解析 CORS_ORIGINS 环境变量（JSON 格式）"""
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                # 如果解析失败，返回默认值
                return ["http://localhost:3000", "http://localhost:8080"]
        return v

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def parse_allowed_hosts(cls, v):
        """解析 ALLOWED_HOSTS 环境变量（JSON 格式）"""
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return ["*"]
        return v

    @property
    def is_dev(self) -> bool:
        """是否为开发环境"""
        return self.api_reload

    @property
    def is_production(self) -> bool:
        """是否为生产环境"""
        return not self.api_reload

    def to_code_config(self) -> CodeConfig:
        """转换为验证码配置"""
        return CodeConfig(
            code_length=self.verification_code_length,
            expire_minutes=self.verification_code_expire_minutes,
            max_attempts=self.verification_code_max_attempts,
            cooldown_seconds=self.verification_code_cooldown_seconds,
            max_daily_sends=self.verification_code_max_daily_sends
        )

    @property
    def database_url_sync(self) -> str:
        """同步数据库连接字符串（用于 Alembic）"""
        return self.database_url.replace("+asyncpg", "")


# 全局配置实例
settings = Settings()
