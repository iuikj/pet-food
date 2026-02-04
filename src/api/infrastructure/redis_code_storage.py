"""
Redis 验证码存储实现
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional
from redis.asyncio import Redis

from src.api.domain.verification import VerificationCode, VerificationCodeType
from src.api.infrastructure.interfaces import ICodeStorage

logger = logging.getLogger(__name__)


class RedisCodeStorage(ICodeStorage):
    """Redis 验证码存储实现"""

    # Redis Key 前缀
    CODE_KEY_PREFIX = "verification_code:"
    COOLDOWN_KEY_PREFIX = "send_cooldown:"
    DAILY_COUNT_KEY_PREFIX = "daily_send_count:"

    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    def _build_code_key(self, email: str, code_type: VerificationCodeType) -> str:
        """构建验证码 Redis Key"""
        return f"{self.CODE_KEY_PREFIX}{code_type.value}:{email}"

    def _build_cooldown_key(self, email: str) -> str:
        """构建冷却时间 Redis Key"""
        return f"{self.COOLDOWN_KEY_PREFIX}{email}"

    def _build_daily_count_key(self, email: str) -> str:
        """
        构建每日发送计数 Redis Key

        使用 UTC 时间确保跨时区一致性
        """
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return f"{self.DAILY_COUNT_KEY_PREFIX}{email}:{today}"

    async def save_code(self, code: VerificationCode) -> bool:
        """
        保存验证码到 Redis

        Args:
            code: 验证码实体

        Returns:
            bool: 保存成功返回 True

        Raises:
            StorageException: Redis 操作失败时抛出
        """
        try:
            key = self._build_code_key(code.email, code.code_type)

            # 序列化验证码对象
            code_dict = code.model_dump(mode="json")

            # 保存到 Redis，设置过期时间
            ttl_seconds = int((code.expires_at - datetime.now(timezone.utc)).total_seconds())
            ttl_seconds = max(1, ttl_seconds)  # 至少 1 秒

            await self.redis.setex(
                key,
                ttl_seconds,
                json.dumps(code_dict, ensure_ascii=False)
            )
            logger.debug(f"验证码已保存: email={code.email}, code_type={code.code_type}")
            return True
        except Exception as e:
            logger.error(f"保存验证码失败: email={code.email}, error={e}", exc_info=True)
            raise

    async def get_code(
        self,
        email: str,
        code_type: VerificationCodeType
    ) -> Optional[VerificationCode]:
        """
        从 Redis 获取验证码

        Args:
            email: 邮箱地址
            code_type: 验证码类型

        Returns:
            Optional[VerificationCode]: 验证码实体，不存在返回 None

        Raises:
            StorageException: Redis 操作失败时抛出
        """
        try:
            key = self._build_code_key(email, code_type)
            data = await self.redis.get(key)

            if not data:
                return None

            code_dict = json.loads(data)
            return VerificationCode(**code_dict)
        except Exception as e:
            logger.error(f"获取验证码失败: email={email}, code_type={code_type}, error={e}", exc_info=True)
            raise

    async def update_code(self, code: VerificationCode) -> bool:
        """
        更新验证码

        Args:
            code: 验证码实体

        Returns:
            bool: 更新成功返回 True

        Raises:
            StorageException: Redis 操作失败时抛出
        """
        try:
            # 删除旧的验证码
            await self.delete_code(code.email, code.code_type)
            # 保存新的验证码
            return await self.save_code(code)
        except Exception as e:
            logger.error(f"更新验证码失败: email={code.email}, error={e}", exc_info=True)
            raise

    async def delete_code(self, email: str, code_type: VerificationCodeType) -> bool:
        """
        删除验证码

        Args:
            email: 邮箱地址
            code_type: 验证码类型

        Returns:
            bool: 删除成功返回 True

        Raises:
            StorageException: Redis 操作失败时抛出
        """
        try:
            key = self._build_code_key(email, code_type)
            await self.redis.delete(key)
            logger.debug(f"验证码已删除: email={email}, code_type={code_type}")
            return True
        except Exception as e:
            logger.error(f"删除验证码失败: email={email}, error={e}", exc_info=True)
            raise

    async def set_cooldown(self, email: str, seconds: int):
        """
        设置冷却时间

        Args:
            email: 邮箱地址
            seconds: 冷却时间（秒）

        Raises:
            StorageException: Redis 操作失败时抛出
        """
        try:
            key = self._build_cooldown_key(email)
            await self.redis.setex(key, seconds, "1")
            logger.debug(f"冷却时间已设置: email={email}, seconds={seconds}")
        except Exception as e:
            logger.error(f"设置冷却时间失败: email={email}, error={e}", exc_info=True)
            raise

    async def clear_cooldown(self, email: str):
        """
        清除冷却时间

        Args:
            email: 邮箱地址

        Raises:
            StorageException: Redis 操作失败时抛出
        """
        try:
            key = self._build_cooldown_key(email)
            await self.redis.delete(key)
            logger.debug(f"冷却时间已清除: email={email}")
        except Exception as e:
            logger.error(f"清除冷却时间失败: email={email}, error={e}", exc_info=True)
            raise

    async def check_cooldown(self, email: str) -> int:
        """
        检查冷却时间

        Args:
            email: 邮箱地址

        Returns:
            int: 剩余冷却时间（秒），无冷却返回 0

        Raises:
            StorageException: Redis 操作失败时抛出
        """
        try:
            key = self._build_cooldown_key(email)
            ttl = await self.redis.ttl(key)
            return max(0, ttl)
        except Exception as e:
            logger.error(f"检查冷却时间失败: email={email}, error={e}", exc_info=True)
            raise

    async def increment_daily_send_count(self, email: str) -> int:
        """
        增加当日发送次数

        Args:
            email: 邮箱地址

        Returns:
            int: 当日累计发送次数

        Raises:
            StorageException: Redis 操作失败时抛出
        """
        try:
            key = self._build_daily_count_key(email)
            # 当天 23:59:59 过期（UTC 时间）
            now = datetime.now(timezone.utc)
            tomorrow = now.replace(hour=23, minute=59, second=59, microsecond=999999)
            ttl = int((tomorrow - now).total_seconds())

            count = await self.redis.incr(key)
            if count == 1:
                await self.redis.expire(key, ttl)
            logger.debug(f"发送次数已增加: email={email}, count={count}")
            return count
        except Exception as e:
            logger.error(f"增加发送次数失败: email={email}, error={e}", exc_info=True)
            raise

    async def get_daily_send_count(self, email: str) -> int:
        """
        获取当日发送次数

        Args:
            email: 邮箱地址

        Returns:
            int: 当日累计发送次数，无记录返回 0

        Raises:
            StorageException: Redis 操作失败时抛出
        """
        try:
            key = self._build_daily_count_key(email)
            count = await self.redis.get(key)
            return int(count) if count else 0
        except Exception as e:
            logger.error(f"获取发送次数失败: email={email}, error={e}", exc_info=True)
            raise
