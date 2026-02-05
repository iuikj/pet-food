"""
数据库模型定义
使用 SQLAlchemy 异步 ORM
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, Text, Integer, ForeignKey, JSON, Numeric, Date, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.db.session import Base


class User(Base):
    """用户表"""
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    # 用户信息扩展
    nickname: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 会员信息
    is_pro: Mapped[bool] = mapped_column(Boolean, default=False)
    plan_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # 'monthly' | 'yearly'
    subscription_expired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # 基础字段
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # 关系
    tasks: Mapped[list["Task"]] = relationship(
        "Task",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    diet_plans: Mapped[list["DietPlan"]] = relationship(
        "DietPlan",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    pets: Mapped[list["Pet"]] = relationship(
        "Pet",
        back_populates="user",
        cascade="all, delete-orphan"
    )


class Task(Base):
    """任务表"""
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    # 任务信息
    task_type: Mapped[str] = mapped_column(String(50), default="diet_plan", index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    # 进度信息
    progress: Mapped[int] = mapped_column(Integer, default=0)
    current_node: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    # 输入输出
    input_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    output_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # 错误信息
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 时间信息
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # 关系
    user: Mapped["User"] = relationship("User", back_populates="tasks")


class Pet(Base):
    """宠物表"""
    __tablename__ = "pets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    # 宠物基本信息
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # 'cat' | 'dog'
    breed: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    age: Mapped[int] = mapped_column(Integer, nullable=False)  # 月
    weight: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)  # kg
    gender: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # 'male' | 'female'
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    health_status: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    special_requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 软删除
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    # 时间信息
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # 索引
    __table_args__ = (
        Index("idx_user_active", "user_id", "is_active"),
    )

    # 关系
    user: Mapped["User"] = relationship("User", back_populates="pets")
    diet_plans: Mapped[list["DietPlan"]] = relationship(
        "DietPlan",
        back_populates="pet",
        cascade="all, delete-orphan"
    )
    meal_records: Mapped[list["MealRecord"]] = relationship(
        "MealRecord",
        back_populates="pet",
        cascade="all, delete-orphan"
    )


class MealRecord(Base):
    """餐食记录表"""
    __tablename__ = "meal_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    pet_id: Mapped[str] = mapped_column(String(36), ForeignKey("pets.id"), nullable=False, index=True)
    plan_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("diet_plans.id"), nullable=True)
    # 餐食信息
    meal_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    meal_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # 'breakfast' | 'lunch' | 'dinner' | 'snack'
    meal_order: Mapped[int] = mapped_column(Integer, nullable=False)  # 第几餐
    food_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    calories: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # 营养信息（JSON 存储，兼容 PetDietPlan 结构）
    nutrition_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # 完成状态
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 时间信息
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # 索引
    __table_args__ = (
        Index("idx_pet_date", "pet_id", "meal_date"),
        Index("idx_pet_completed", "pet_id", "is_completed"),
        Index("idx_meal_type", "meal_type"),
    )

    # 关系
    pet: Mapped["Pet"] = relationship("Pet", back_populates="meal_records")


class DietPlan(Base):
    """饮食计划表"""
    __tablename__ = "diet_plans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    task_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=True, index=True)
    # 关联宠物
    pet_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("pets.id"), nullable=True, index=True)
    # 宠物信息（兼容历史数据，同时保存快照）
    pet_type: Mapped[str] = mapped_column(String(50), index=True)
    pet_breed: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    pet_age: Mapped[int] = mapped_column(Integer)
    pet_weight: Mapped[int] = mapped_column(Integer)
    health_status: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 饮食计划（完整的 JSON 数据，存储 PetDietPlan 结构）
    plan_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    # 元数据
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # 关系
    user: Mapped["User"] = relationship("User", back_populates="diet_plans")
    pet: Mapped[Optional["Pet"]] = relationship("Pet", back_populates="diet_plans")


class RefreshToken(Base):
    """刷新令牌表（用于 Token 黑名单）"""
    __tablename__ = "refresh_tokens"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(500), unique=True, nullable=False, index=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
