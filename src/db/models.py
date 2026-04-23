"""
数据库模型定义
使用 SQLAlchemy 异步 ORM
"""
from datetime import datetime, date as date_type
from typing import Optional
from sqlalchemy import String, Boolean, DateTime, Text, Integer, ForeignKey, JSON, Numeric, Date, Index, UniqueConstraint
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
    todos: Mapped[list["TodoItem"]] = relationship(
        "TodoItem",
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
    # 结构化健康偏好（JSON 数组）
    allergens: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    health_issues: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
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
    weight_records: Mapped[list["WeightRecord"]] = relationship(
        "WeightRecord",
        back_populates="pet",
        cascade="all, delete-orphan"
    )
    todos: Mapped[list["TodoItem"]] = relationship(
        "TodoItem",
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
    # 营养顶级字段（提升查询效率，兼容旧数据 fallback 到 JSON）
    protein: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
    fat: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
    carbohydrates: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
    dietary_fiber: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
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
    # 计划应用状态
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    active_start_date: Mapped[Optional[date_type]] = mapped_column(Date, nullable=True)
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

    # 索引
    __table_args__ = (
        Index("idx_pet_active_plan", "pet_id", "is_active"),
    )


class RefreshToken(Base):
    """刷新令牌表（用于 Token 黑名单）"""
    __tablename__ = "refresh_tokens"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(500), unique=True, nullable=False, index=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WeightRecord(Base):
    """体重记录表"""
    __tablename__ = "weight_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    pet_id: Mapped[str] = mapped_column(String(36), ForeignKey("pets.id"), nullable=False, index=True)
    weight: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    recorded_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # 同一宠物同一天只能有一条记录
    __table_args__ = (
        UniqueConstraint("pet_id", "recorded_date", name="uq_pet_recorded_date"),
    )

    # 关系
    pet: Mapped["Pet"] = relationship("Pet", back_populates="weight_records")


class Ingredient(Base):
    """食材营养数据表"""
    __tablename__ = "ingredients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), index=True, nullable=False, comment="食材名称")
    category: Mapped[str] = mapped_column(String(50), nullable=False, comment="大类别")
    sub_category: Mapped[str] = mapped_column(String(50), nullable=False, comment="小类别")
    has_nutrition_data: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否有营养数据")
    note: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="计量备注")

    # 归属 - 区分系统食材与用户自定义食材
    user_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True, index=True, comment="用户 ID（系统食材为 NULL）"
    )
    is_system: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True, comment="是否系统食材（全局只读）"
    )

    # 可视化资产 - 图标与缩略图
    icon_key: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="图标 key，格式 <library>:<name>，如 emoji:fish / mi:restaurant"
    )
    image_url: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="缩略图引用，形如 minio://bucket/ingredients/xxx.jpg"
    )

    # 宏量营养素
    calories: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="热量 (kcal)")
    carbohydrates: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="碳水化合物 (g)")
    protein: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="蛋白质 (g)")
    fat: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="脂肪 (g)")
    dietary_fiber: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="膳食纤维 (g)")

    # 矿物质
    iron: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="铁 (mg)")
    zinc: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="锌 (mg)")
    manganese: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="锰 (mg)")
    magnesium: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="镁 (mg)")
    sodium: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="钠 (mg)")
    calcium: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="钙 (mg)")
    phosphorus: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="磷 (mg)")
    copper: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="铜 (mg)")
    iodine: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="碘 (μg)")
    potassium: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="钾 (mg)")
    selenium: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="硒 (μg)")

    # 维生素
    vitamin_b1: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="维生素B1 (mg)")
    vitamin_e: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="维生素E (mg)")
    vitamin_a: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="维生素A (IU)")
    vitamin_d: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="维生素D (IU)")

    # 脂肪酸
    epa: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="EPA (mg)")
    dha: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="DHA (mg)")
    epa_dha: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="EPA&DHA (mg)")

    # 其他
    bone_content: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="骨骼含量 (%)")
    water: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="水分 (g)")
    choline: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="胆碱 (mg)")
    taurine: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="牛磺酸 (mg)")
    cholesterol: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="胆固醇 (mg)")

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # 索引
    __table_args__ = (
        Index("idx_ingredient_category", "category", "sub_category"),
        Index("idx_ingredient_owner", "user_id", "is_system"),
        UniqueConstraint("user_id", "name", name="uq_ingredient_user_name"),
    )


class Supplement(Base):
    """营养补剂数据表"""
    __tablename__ = "supplements"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False, comment="产品名称")
    category: Mapped[str] = mapped_column(String(50), nullable=False, comment="类别")
    has_nutrition_data: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否有营养数据")
    note: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="计量备注")

    # 矿物质
    calcium: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="钙 (mg)")
    magnesium: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="镁 (mg)")
    potassium: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="钾 (mg)")
    sodium: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="钠 (mg)")
    phosphorus: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="磷 (mg)")
    iodine: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="碘 (μg)")
    manganese: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="锰 (mg)")
    iron: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="铁 (mg)")
    zinc: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="锌 (mg)")
    copper: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="铜 (mg)")

    # 维生素
    vitamin_d: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="维生素D (IU)")
    vitamin_a: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="维生素A (IU)")
    vitamin_e: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="维生素E (mg)")
    vitamin_b1: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="维生素B1 (mg)")

    # 其他
    taurine: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="牛磺酸 (mg)")

    # 脂肪酸
    epa_dha: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="EPA&DHA (mg)")
    epa: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="EPA (mg)")
    dha: Mapped[Optional[float]] = mapped_column(Numeric(10, 4), nullable=True, comment="DHA (mg)")

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # 索引
    __table_args__ = (
        Index("idx_supplement_category", "category"),
    )


class TodoItem(Base):
    """待办事项表"""
    __tablename__ = "todo_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    pet_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("pets.id"), nullable=True, index=True)

    # 待办内容
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # 时间
    due_date: Mapped[date_type] = mapped_column(Date, nullable=False)
    due_time: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)  # "HH:MM"
    is_all_day: Mapped[bool] = mapped_column(Boolean, default=True)

    # 状态
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # 分类与优先级
    priority: Mapped[str] = mapped_column(String(10), default="medium")  # low / medium / high
    category: Mapped[str] = mapped_column(String(20), default="other")   # feeding / health / grooming / shopping / other

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # 索引
    __table_args__ = (
        Index("idx_todo_user_date", "user_id", "due_date"),
        Index("idx_todo_pet", "pet_id"),
    )

    # 关系
    user: Mapped["User"] = relationship("User", back_populates="todos")
    pet: Mapped[Optional["Pet"]] = relationship("Pet", back_populates="todos")
