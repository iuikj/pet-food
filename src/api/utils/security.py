"""
安全工具
包含密码哈希、JWT Token 生成和验证等功能
"""
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from jose import JWTError, jwt

from src.api.config import settings


def hash_password(password: str) -> str:
    """
    对密码进行哈希
    直接使用 bcrypt 库，避免 passlib 版本兼容问题
    自动截断密码到 72 字节（bcrypt 限制）

    Args:
        password: 明文密码

    Returns:
        哈希后的密码
    """
    # bcrypt 的限制是 72 字节
    max_password_length = 72
    if len(password) > max_password_length:
        password = password[:max_password_length]

    # 将密码转换为 bytes
    password_bytes = password.encode('utf-8')

    # 生成 salt 并哈希密码
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)

    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码

    Args:
        plain_password: 明文密码
        hashed_password: 哈希后的密码

    Returns:
        是否匹配
    """
    try:
        # 将字符串转换为 bytes
        plain_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')

        return bcrypt.checkpw(plain_bytes, hashed_bytes)
    except Exception:
        return False


def create_access_token(
    sub: str,
    username: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    创建访问令牌 (Access Token)

    Args:
        sub: 用户 ID
        username: 用户名
        expires_delta: 过期时间增量，默认使用配置的过期时间

    Returns:
        JWT Token 字符串
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    to_encode = {
        "sub": sub,
        "username": username,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def create_refresh_token(
    sub: str,
    username: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    创建刷新令牌 (Refresh Token)

    Args:
        sub: 用户 ID
        username: 用户名
        expires_delta: 过期时间增量，默认使用配置的过期时间

    Returns:
        JWT Token 字符串
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)

    to_encode = {
        "sub": sub,
        "username": username,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def decode_token(token: str) -> Dict:
    """
    解码 JWT Token

    Args:
        token: JWT Token 字符串

    Returns:
        Token 载荷 (Payload)

    Raises:
        ValueError: Token 无效或已过期
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        return payload
    except JWTError as e:
        raise ValueError(f"Token 无效或已过期: {str(e)}")


def verify_token(token: str, token_type: str = "access") -> Dict:
    """
    验证 Token 并返回载荷

    Args:
        token: JWT Token 字符串
        token_type: Token 类型（access 或 refresh）

    Returns:
        Token 载荷

    Raises:
        ValueError: Token 无效、已过期或类型不匹配
    """
    payload = decode_token(token)

    # 验证 Token 类型
    if payload.get("type") != token_type:
        raise ValueError(f"Token 类型错误，期望 {token_type}，实际 {payload.get('type')}")

    return payload
