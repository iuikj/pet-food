"""
认证服务
处理用户注册、登录、Token 刷新等功能
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from src.db.models import User, RefreshToken
from src.api.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_token
)
from src.api.utils.errors import DuplicateException, AuthException, NotFoundException, ValidationException
from src.api.models.response import UserResponse, TokenResponse


class AuthService:
    """认证服务类"""

    def __init__(self, db: AsyncSession, verification_service=None):
        self.db = db
        self.verification_service = verification_service

    def _user_to_response(self, user: User) -> UserResponse:
        """将 SQLAlchemy User 模型转换为 UserResponse"""
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            nickname=user.nickname,
            phone=user.phone,
            avatar_url=user.avatar_url,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            created_at=user.created_at
        )

    async def register(
        self,
        username: str,
        email: str,
        password: str
    ) -> tuple[UserResponse, TokenResponse]:
        """
        用户注册

        Args:
            username: 用户名
            email: 邮箱
            password: 密码

        Returns:
            (用户对象, Token 响应)

        Raises:
            DuplicateException: 用户名或邮箱已存在
        """
        # 检查用户名是否已存在
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        if result.scalars().first():
            raise DuplicateException("用户名已存在")

        # 检查邮箱是否已存在
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        if result.scalars().first():
            raise DuplicateException("邮箱已被注册")

        # 创建新用户
        user = User(
            id=self._generate_uuid(),
            username=username,
            email=email,
            hashed_password=hash_password(password),
            is_active=True,
            is_superuser=False
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        # 生成 Token
        tokens = self._create_tokens(user.id, user.username)

        # 保存刷新令牌到数据库
        await self._save_refresh_token(user.id, tokens.refresh_token)

        # 转换为 UserResponse
        user_response = self._user_to_response(user)

        return user_response, tokens

    async def login(
        self,
        username: str,
        password: str
    ) -> tuple[UserResponse, TokenResponse]:
        """
        用户登录

        Args:
            username: 用户名或邮箱
            password: 密码

        Returns:
            (用户对象, Token 响应)

        Raises:
            AuthException: 用户名或密码错误
            NotFoundException: 用户不存在
        """
        # 查找用户（支持用户名或邮箱登录）
        result = await self.db.execute(
            select(User).where(
                (User.username == username) | (User.email == username)
            )
        )
        user = result.scalars().first()

        if not user:
            raise NotFoundException("用户不存在")

        # 验证密码
        if not verify_password(password, user.hashed_password):
            raise AuthException("用户名或密码错误")

        # 检查用户是否激活
        if not user.is_active:
            raise AuthException("用户已被禁用")

        # 生成 Token
        tokens = self._create_tokens(user.id, user.username)

        # 保存刷新令牌到数据库
        await self._save_refresh_token(user.id, tokens.refresh_token)

        # 转换为 UserResponse
        user_response = self._user_to_response(user)

        return user_response, tokens

    async def refresh_tokens(
        self,
        refresh_token: str
    ) -> TokenResponse:
        """
        刷新访问令牌

        Args:
            refresh_token: 刷新令牌

        Returns:
            新的 Token 响应

        Raises:
            AuthException: 刷新令牌无效或已撤销
        """
        try:
            # 验证刷新令牌
            payload = verify_token(refresh_token, token_type="refresh")
            user_id = payload.get("sub")
            username = payload.get("username")

            # 检查刷新令牌是否在数据库中且未被撤销
            result = await self.db.execute(
                select(RefreshToken).where(
                    RefreshToken.token == refresh_token,
                    RefreshToken.user_id == user_id,
                    RefreshToken.is_revoked == False
                )
            )
            token_record = result.scalars().first()

            if not token_record:
                raise AuthException("刷新令牌无效或已撤销")

            # 检查刷新令牌是否过期
            if token_record.expires_at < datetime.now(timezone.utc):
                raise AuthException("刷新令牌已过期")

            # 生成新的 Token
            new_tokens = self._create_tokens(user_id, username)

            # 撤销旧的刷新令牌
            token_record.is_revoked = True
            await self.db.commit()

            # 保存新的刷新令牌
            await self._save_refresh_token(user_id, new_tokens.refresh_token)

            return new_tokens

        except ValueError as e:
            raise AuthException(f"刷新令牌无效: {str(e)}")

    async def get_user_by_id(self, user_id: str) -> UserResponse:
        """
        根据用户 ID 获取用户信息

        Args:
            user_id: 用户 ID

        Returns:
            用户对象

        Raises:
            NotFoundException: 用户不存在
        """
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalars().first()

        if not user:
            raise NotFoundException("用户不存在")

        return self._user_to_response(user)

    def _create_tokens(self, user_id: str, username: str) -> TokenResponse:
        """
        创建访问令牌和刷新令牌

        Args:
            user_id: 用户 ID
            username: 用户名

        Returns:
            Token 响应
        """
        access_token = create_access_token(user_id, username)
        refresh_token = create_refresh_token(user_id, username)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=30 * 60  # 30 分钟（秒）
        )

    async def _save_refresh_token(self, user_id: str, token: str):
        """
        保存刷新令牌到数据库

        Args:
            user_id: 用户 ID
            token: 刷新令牌
        """
        from src.api.config import settings

        refresh_token_record = RefreshToken(
            id=self._generate_uuid(),
            user_id=user_id,
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)
        )

        self.db.add(refresh_token_record)
        await self.db.commit()

    def _generate_uuid(self) -> str:
        """生成 UUID"""
        import uuid
        return str(uuid.uuid4())

    async def register_with_code(
        self,
        username: str,
        email: str,
        password: str,
        code: str
    ) -> tuple[UserResponse, TokenResponse]:
        """
        使用验证码注册

        Args:
            username: 用户名
            email: 邮箱
            password: 密码
            code: 邮箱验证码

        Returns:
            (用户对象, Token 响应)

        Raises:
            ValidationException: 验证码无效
            DuplicateException: 用户名或邮箱已存在
        """
        from src.api.domain.verification import VerificationCodeType

        # 验证验证码
        if self.verification_service:
            await self.verification_service.verify_code(
                email=email,
                code=code,
                code_type=VerificationCodeType.REGISTER
            )

        # 调用原有注册逻辑
        return await self.register(username, email, password)

    async def reset_password(
        self,
        email: str,
        code: str,
        new_password: str
    ):
        """
        重置密码（通过邮箱验证码）

        Args:
            email: 邮箱
            code: 验证码
            new_password: 新密码

        Raises:
            ValidationException: 验证码无效
            NotFoundException: 用户不存在
        """
        from src.api.domain.verification import VerificationCodeType

        # 验证验证码
        if self.verification_service:
            await self.verification_service.verify_code(
                email=email,
                code=code,
                code_type=VerificationCodeType.PASSWORD_RESET
            )

        # 查找用户
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalars().first()

        if not user:
            raise NotFoundException("用户不存在")

        # 更新密码
        user.hashed_password = hash_password(new_password)
        await self.db.commit()
        await self.db.refresh(user)

    async def change_password(
        self,
        user_id: str,
        old_password: str,
        new_password: str
    ):
        """
        修改密码（需要验证旧密码）

        Args:
            user_id: 用户 ID
            old_password: 旧密码
            new_password: 新密码

        Raises:
            ValidationException: 旧密码错误
            NotFoundException: 用户不存在
        """
        # 查找用户
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalars().first()

        if not user:
            raise NotFoundException("用户不存在")

        # 验证旧密码
        if not verify_password(old_password, user.hashed_password):
            raise ValidationException("旧密码错误")

        # 更新密码
        user.hashed_password = hash_password(new_password)
        await self.db.commit()
        await self.db.refresh(user)
