"""
测试配置文件
配置 pytest 和测试数据库
"""
import os
import asyncio
import pytest
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import uvicorn

# 添加项目根目录到 Python 路径
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# 测试数据库 URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# 创建测试数据库引擎
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)


# 创建测试会话工厂
AsyncTestSession = sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
async def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_db():
    """创建测试数据库"""
    from src.db.models import Base

    # 创建所有表
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    # 清理
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def test_session(test_db) -> AsyncGenerator[AsyncSession, None]:
    """创建测试会话"""
    async with AsyncTestSession() as session:
        yield session


@pytest.fixture
def test_user_data():
    """测试用户数据"""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpass123"
    }


@pytest.fixture
def auth_headers(test_user_data, test_session) -> dict:
    """创建认证请求头"""
    import json

    # 创建测试用户并获取 Token
    from src.api.services.auth_service import AuthService

    async def get_token():
        auth_service = AuthService(test_session)
        user, tokens = await auth_service.register(
            username=test_user_data["username"],
            email=test_user_data["email"],
            password=test_user_data["password"]
        )
        return tokens

    token_data = asyncio.run(get_token())

    return {
        "Authorization": f"Bearer {token_data.access_token}"
    }
