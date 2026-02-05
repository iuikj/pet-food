# 后端开发文档

> FastAPI + SQLAlchemy + PostgreSQL + Redis 后端开发指南

---

## 目录

1. [项目结构](#项目结构)
2. [环境配置](#环境配置)
3. [数据库](#数据库)
4. [中间件](#中间件)
5. [服务层](#服务层)
6. [路由层](#路由层)

---

## 项目结构

```
src/api/
├── main.py                 # FastAPI 应用入口
├── config.py              # Pydantic Settings 配置
├── dependencies.py         # 依赖注入
│
├── middleware/            # 中间件层
│   ├── auth.py          # JWT 认证中间件
│   ├── logging.py       # 请求日志
│   ├── rate_limit.py   # 速率限制
│   └── exceptions.py    # 全局异常处理
│
├── routes/                # 路由层
│   ├── auth.py         # 认证路由
│   ├── verification.py  # 验证码路由
│   ├── plans.py        # 饮食计划路由
│   └── tasks.py        # 任务管理路由
│
├── services/              # 服务层
│   ├── auth_service.py    # 认证服务
│   ├── verification_service.py # 验证码服务
│   ├── email_service.py   # 邮件服务
│   ├── plan_service.py   # 饮食计划服务
│   └── task_service.py   # 任务服务
│
├── domain/                # 领域层
│   ├── verification.py    # 验证码实体
│   └── email_template.py # 邮件模板
│
├── infrastructure/         # 基础设施层
│   ├── interfaces.py     # 接口定义
│   ├── redis_code_storage.py # Redis 实现
│   ├── code_generator.py # 验证码生成
│   └── email_providers/  # 邮件实现
│
└── utils/                 # 工具层
    ├── security.py       # JWT/密码工具
    ├── stream.py         # SSE 流式工具
    └── errors.py         # 错误定义

src/db/
├── models.py              # SQLAlchemy 模型
├── session.py             # Session 管理
└── redis.py              # Redis 连接
```

---

## 环境配置

### 配置文件

**`.env.example`** - 环境变量模板

```env
# ============ LLM API 配置 ============
DASHSCOPE_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
DASHSCOPE_API_KEY=your-dashscope-api-key
DEEPSEEK_API_KEY=your-deepseek-api-key
ZAI_API_KEY=your-zai-api-key
MOONSHOT_API_KEY=your-moonshot-api-key
TAVILIY_API_KEY=your-tavily-api-key
SILICONFLOW_API_KEY=your-siliconflow-api-key

# ============ FastAPI 基础配置 ============
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=true
API_WORKERS=1
LOG_LEVEL=info

# ============ JWT 认证配置 ============
JWT_SECRET_KEY=your-super-secret-jwt-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# ============ 数据库配置 ============
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/pet_food
DATABASE_ECHO=false

# ============ Redis 配置 ============
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=
REDIS_DB=0

# ============ 邮件配置 ============
SMTP_HOST=smtp.qq.com
SMTP_PORT=587
SMTP_USERNAME=your-email@qq.com
SMTP_PASSWORD=your-authorization-code
SMTP_FROM_EMAIL=your-email@qq.com
SMTP_USE_TLS=true

# ============ CORS 配置 ============
CORS_ORIGINS=["http://localhost:3000","http://localhost:8080"]
CORS_ALLOW_CREDENTIALS=true
CORS_ALLOW_METHODS=["*"]
CORS_ALLOW_HEADERS=["*"]

# ============ 安全配置 ============
SECRET_KEY=your-app-secret-key-change-in-production
ALLOWED_HOSTS=["*"]
MAX_REQUEST_SIZE=10485760

# ============ 速率限制配置 ============
RATE_LIMIT_ENABLED=true
RATE_LIMIT_TIMES=100
RATE_LIMIT_SECONDS=60
```

### Pydantic Settings

```python
# src/api/config.py
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
from functools import lru_cache

class Settings(BaseSettings):
    # FastAPI 基础
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_reload: bool = Field(default=True)
    api_workers: int = Field(default=1)
    log_level: str = Field(default="info")

    # JWT
    jwt_secret_key: str = Field(..., env="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(default=30, env="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    jwt_refresh_token_expire_days: int = Field(default=7, env="JWT_REFRESH_TOKEN_EXPIRE_DAYS")

    # 数据库
    database_url: str = Field(..., env="DATABASE_URL")
    database_echo: bool = Field(default=False, env="DATABASE_ECHO")

    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    redis_password: str = Field(default="", env="REDIS_PASSWORD")

    # CORS
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8080"],
        env="CORS_ORIGINS"
    )

    # 验证码
    verification_code_length: int = Field(default=6)
    verification_code_expire_minutes: int = Field(default=10)
    verification_code_max_attempts: int = Field(default=3)
    verification_code_cooldown_seconds: int = Field(default=60)
    verification_code_max_daily_sends: int = Field(default=10)

    @lru_cache()
    def get_verification_code_expire_seconds(self) -> int:
        return self.verification_code_expire_minutes * 60

settings = Settings()
```

---

## 数据库

### 模型定义

```python
# src/db/models.py
from sqlalchemy import String, Boolean, DateTime, Text, Integer, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from src.db.session import Base

class User(Base):
    """用户表"""
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关系
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="user")
    diet_plans: Mapped[list["DietPlan"]] = relationship("DietPlan", back_populates="user")


class Task(Base):
    """任务表"""
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(50), default="diet_plan", index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    current_node: Mapped[str] = mapped_column(String(100), nullable=True)
    input_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    output_data: Mapped[dict] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    started_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关系
    user: Mapped["User"] = relationship("User", back_populates="tasks")


class DietPlan(Base):
    """饮食计划表"""
    __tablename__ = "diet_plans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=True, index=True)
    pet_type: Mapped[str] = mapped_column(String(50), index=True)
    pet_breed: Mapped[str] = mapped_column(String(100), nullable=True)
    pet_age: Mapped[int] = mapped_column(Integer, nullable=False)
    pet_weight: Mapped[int] = mapped_column(Integer, nullable=False)
    health_status: Mapped[str] = mapped_column(Text, nullable=True)
    plan_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # 关系
    user: Mapped["User"] = relationship("User", back_populates="diet_plans")


class RefreshToken(Base):
    """刷新令牌表（用于 Token 黑名单）"""
    __tablename__ = "refresh_tokens"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    expires_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

---

## 中间件

### JWT 认证中间件

```python
# src/api/middleware/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

security = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db_session)
) -> str:
    """获取当前用户 ID"""
    from src.api.services.auth_service import AuthService

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证凭据"
        )

    auth_service = AuthService(db)
    user = await auth_service.verify_token(credentials.credentials)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效或已过期"
        )

    return user.id
```

### 速率限制中间件

```python
# src/api/middleware/rate_limit.py
from fastapi import Request, HTTPException, status
from functools import wraps
import redis.asyncio as redis
from src.api.config import settings
from src.db.redis import get_redis

# 滑动窗口速率限制
async def rate_limit(request: Request, calls: int = 100, period: int = 60) -> bool:
    """滑动窗口速率限制"""
    r = await get_redis()
    key = f"rate:{request.client.host}:{period}"

    current = await r.incr(key)
    if current == 1:
        await r.expire(key, period)

    if current > calls:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="请求过于频繁，请稍后再试"
        )

    return True
```

---

## 服务层

### 认证服务

```python
# src/api/services/auth_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.models import User, RefreshToken
from src.api.utils.security import hash_password, verify_password, create_access_token, create_refresh_token

class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def authenticate_user(self, username: str, password: str) -> User | None:
        """验证用户名密码"""
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        user = result.scalars().first()

        if not user:
            return None

        if not verify_password(password, user.hashed_password):
            return None

        return user

    async def create_tokens(self, user_id: str) -> dict:
        """创建 Access Token 和 Refresh Token"""
        access_token = create_access_token(user_id)
        refresh_token = create_refresh_token(user_id)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.jwt_access_token_expire_minutes * 60
        }

    async def verify_token(self, token: str) -> User | None:
        """验证 Token 并返回用户"""
        payload = verify_token(token)
        if payload is None:
            return None

        user_id = payload.get("sub")

        result = await self.db.execute(
            select(User).where(User.id == user_id, User.is_active == True)
        )
        return result.scalars().first()
```

### 任务服务

```python
# src/api/services/task_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.models import Task
from datetime import datetime, timezone

class TaskService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_task(
        self,
        user_id: str,
        task_type: str,
        input_data: dict
    ) -> Task:
        """创建新任务"""
        task = Task(
            id=str(uuid.uuid4()),
            user_id=user_id,
            task_type=task_type,
            status="pending",
            progress=0,
            input_data=input_data,
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        progress: int = None,
        current_node: str = None,
        error_message: str = None
    ) -> Task:
        """更新任务状态"""
        result = await self.db.execute(
            select(Task).where(Task.id == task_id)
        )
        task = result.scalars().first()

        if not task:
            raise ValueError(f"任务 {task_id} 不存在")

        task.status = status
        if progress is not None:
            task.progress = progress
        if current_node is not None:
            task.current_node = current_node
        if error_message is not None:
            task.error_message = error_message
        if status == "running" and not task.started_at:
            task.started_at = datetime.now(timezone.utc)
        if status in ["completed", "failed", "cancelled"]:
            task.completed_at = datetime.now(timezone.utc)
        task.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(task)
        return task
```

---

## 路由层

### 饮食计划路由

```python
# src/api/routes/plans.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session, get_redis_client, get_current_user
from src.api.services.plan_service import PlanService
from src.api.models.response import ApiResponse

router = APIRouter(prefix="/plans", tags=["plans"])

@router.post("/stream", summary="创建饮食计划（流式）")
async def create_diet_plan_stream(
    pet_info: dict,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """创建饮食计划（流式模式）"""
    plan_service = PlanService(db)

    return StreamingResponse(
        plan_service.execute_diet_plan_stream(
            user_id=current_user_id,
            pet_info=pet_info
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@router.get("/stream", summary="恢复流式连接（重连）")
async def resume_diet_plan_stream(
    task_id: str,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """恢复流式连接（断线重连）"""
    plan_service = PlanService(db)

    return StreamingResponse(
        plan_service.resume_diet_plan_stream(
            user_id=current_user_id,
            task_id=task_id
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
```

---

## 相关文档

- [部署指南](../deployment/README.md)
- [系统架构](../architecture/README.md)
- [前端对接指南](../frontend/README.md)
