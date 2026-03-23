"""
测试配置文件
配置 pytest 和测试数据库，提供完整的 fixture 体系
"""
import os
import uuid

import pytest
import pytest_asyncio
from typing import AsyncGenerator
from datetime import datetime, date, timezone, timedelta

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# 添加项目根目录到 Python 路径
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 在导入 app 之前设置环境变量，避免配置验证失败
# DATABASE_URL 保持 PostgreSQL 格式让 settings 通过验证（模块级引擎不会用于测试）
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-pytest-only")
os.environ.setdefault("SECRET_KEY", "test-app-secret-key-for-pytest-only")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

from src.db.session import Base
from src.api.main import app
from src.api.dependencies import get_db_session
from src.api.utils.security import create_access_token, hash_password


# ==================== 数据库引擎 & 会话 ====================

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

AsyncTestSession = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ==================== 核心 Fixtures ====================

@pytest_asyncio.fixture(scope="session")
async def test_db():
    """创建测试数据库（session 级，整个测试会话共享）"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_db) -> AsyncGenerator[AsyncSession, None]:
    """每个测试函数独立的数据库会话，测试结束后回滚保证隔离"""
    async with test_engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncTestSession(bind=conn)
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()


@pytest_asyncio.fixture
async def client(test_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    FastAPI 测试客户端，自动覆盖数据库依赖注入。
    保证每次请求使用测试数据库而非生产数据库。
    """
    async def _override_db():
        yield test_session

    app.dependency_overrides[get_db_session] = _override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


# ==================== 用户相关 Fixtures ====================

@pytest.fixture
def test_user_data():
    """测试用户数据"""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpass123"
    }


@pytest_asyncio.fixture
async def test_user(test_session: AsyncSession):
    """在数据库中创建一个测试用户，返回 User ORM 对象"""
    from src.db.models import User

    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        username=f"testuser_{user_id[:8]}",
        email=f"test_{user_id[:8]}@example.com",
        hashed_password=hash_password("testpass123"),
        is_active=True,
        is_superuser=False,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user) -> dict:
    """生成已认证用户的请求头"""
    access_token = create_access_token(test_user.id, test_user.username)
    return {"Authorization": f"Bearer {access_token}"}


@pytest_asyncio.fixture
async def second_user(test_session: AsyncSession):
    """创建第二个测试用户，用于权限隔离测试"""
    from src.db.models import User

    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        username=f"otheruser_{user_id[:8]}",
        email=f"other_{user_id[:8]}@example.com",
        hashed_password=hash_password("otherpass123"),
        is_active=True,
        is_superuser=False,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def second_auth_headers(second_user) -> dict:
    """第二个用户的认证请求头"""
    access_token = create_access_token(second_user.id, second_user.username)
    return {"Authorization": f"Bearer {access_token}"}


# ==================== 宠物相关 Fixtures ====================

@pytest_asyncio.fixture
async def test_pet(test_session: AsyncSession, test_user):
    """创建一个测试宠物"""
    from src.db.models import Pet

    pet = Pet(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        name="测试猫咪",
        type="cat",
        breed="英短",
        age=12,
        weight=4.5,
        gender="male",
        health_status="健康",
        special_requirements=None,
        is_active=True,
    )
    test_session.add(pet)
    await test_session.commit()
    await test_session.refresh(pet)
    return pet


@pytest_asyncio.fixture
async def test_pet_dog(test_session: AsyncSession, test_user):
    """创建一个测试狗"""
    from src.db.models import Pet

    pet = Pet(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        name="测试狗狗",
        type="dog",
        breed="金毛",
        age=24,
        weight=25.0,
        gender="female",
        health_status="健康",
        is_active=True,
    )
    test_session.add(pet)
    await test_session.commit()
    await test_session.refresh(pet)
    return pet


# ==================== 餐食相关 Fixtures ====================

@pytest_asyncio.fixture
async def test_meals(test_session: AsyncSession, test_pet):
    """为测试宠物创建今日餐食记录"""
    from src.db.models import MealRecord

    today = date.today()
    meals = []
    meal_configs = [
        ("breakfast", 1, "鸡胸肉粥", 200),
        ("lunch", 2, "牛肉蔬菜", 350),
        ("dinner", 3, "三文鱼沙拉", 300),
    ]

    for meal_type, order, food_name, calories in meal_configs:
        meal = MealRecord(
            id=str(uuid.uuid4()),
            pet_id=test_pet.id,
            meal_date=today,
            meal_type=meal_type,
            meal_order=order,
            food_name=food_name,
            calories=calories,
            protein=20.0,
            fat=10.0,
            carbohydrates=30.0,
            dietary_fiber=5.0,
            nutrition_data={
                "macro_nutrients": {
                    "protein": 20.0,
                    "fat": 10.0,
                    "carbohydrates": 30.0,
                    "dietary_fiber": 5.0,
                },
                "food_items": [{"name": food_name, "amount": "100g"}],
                "cook_method": "蒸煮",
                "recommend_reason": "营养均衡",
            },
            is_completed=False,
        )
        test_session.add(meal)
        meals.append(meal)

    await test_session.commit()
    for m in meals:
        await test_session.refresh(m)
    return meals


# ==================== 任务相关 Fixtures ====================

@pytest_asyncio.fixture
async def test_task(test_session: AsyncSession, test_user):
    """创建一个测试任务"""
    from src.db.models import Task

    task = Task(
        id=str(uuid.uuid4()),
        user_id=test_user.id,
        task_type="diet_plan",
        status="pending",
        progress=0,
        input_data={"pet_type": "cat", "pet_breed": "英短"},
        created_at=datetime.now(timezone.utc),
    )
    test_session.add(task)
    await test_session.commit()
    await test_session.refresh(task)
    return task


# ==================== 体重记录 Fixtures ====================

@pytest_asyncio.fixture
async def test_weight_record(test_session: AsyncSession, test_pet):
    """创建一条测试体重记录"""
    from src.db.models import WeightRecord

    record = WeightRecord(
        id=str(uuid.uuid4()),
        pet_id=test_pet.id,
        weight=4.5,
        recorded_date=date.today(),
        notes="常规称重",
    )
    test_session.add(record)
    await test_session.commit()
    await test_session.refresh(record)
    return record
