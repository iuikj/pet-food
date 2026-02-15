"""添加宠物管理、餐食记录和用户信息扩展

创建 pets 和 meal_records 表
修改 users 表添加昵称、手机号、头像、会员信息字段
修改 diet_plans 表添加 pet_id 外键关联

Revision ID: 002
Revises: 001
Create Date: 2025-02-05 16:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级数据库"""

    # 1. 修改 users 表，添加用户信息扩展字段
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('nickname', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('phone', sa.String(20), nullable=True))
        batch_op.add_column(sa.Column('avatar_url', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('is_pro', sa.Boolean(), default=False))
        batch_op.add_column(sa.Column('plan_type', sa.String(20), nullable=True))
        batch_op.add_column(sa.Column('subscription_expired_at', sa.DateTime(timezone=True), nullable=True))
    print("✅ users 表字段扩展成功")

    # 2. 创建 pets 表（必须先于 diet_plans 外键创建）
    op.create_table(
        'pets',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        # 宠物基本信息
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('type', sa.String(10), nullable=False, index=True),  # 'cat' | 'dog'
        sa.Column('breed', sa.String(100), nullable=True),
        sa.Column('age', sa.Integer(), nullable=False),  # 月
        sa.Column('weight', sa.Numeric(5, 2), nullable=False),  # kg
        sa.Column('gender', sa.String(10), nullable=True),  # 'male' | 'female'
        sa.Column('avatar_url', sa.Text(), nullable=True),
        sa.Column('health_status', sa.Text(), nullable=True),
        sa.Column('special_requirements', sa.Text(), nullable=True),
        # 软删除
        sa.Column('is_active', sa.Boolean(), default=True, index=True),
        # 时间信息
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    # 创建组合索引
    op.create_index('idx_pets_user_active', 'pets', ['user_id', 'is_active'])
    print("✅ pets 表创建成功")

    # 4. 创建 meal_records 表
    op.create_table(
        'meal_records',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('pet_id', sa.String(36), sa.ForeignKey('pets.id'), nullable=False, index=True),
        sa.Column('plan_id', sa.String(36), sa.ForeignKey('diet_plans.id'), nullable=True),
        # 餐食信息
        sa.Column('meal_date', sa.Date(), nullable=False),
        sa.Column('meal_type', sa.String(20), nullable=False, index=True),  # 'breakfast' | 'lunch' | 'dinner' | 'snack'
        sa.Column('meal_order', sa.Integer(), nullable=False),  # 第几餐
        sa.Column('food_name', sa.String(100), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('calories', sa.Integer(), nullable=True),
        # 营养信息（JSON 存储兼容 PetDietPlan 结构）
        sa.Column('nutrition_data', sa.JSON(), nullable=True),
        # 完成状态
        sa.Column('is_completed', sa.Boolean(), default=False, index=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        # 时间信息
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    # 创建索引
    op.create_index('idx_meal_records_pet_date', 'meal_records', ['pet_id', 'meal_date'])
    op.create_index('idx_meal_records_pet_completed', 'meal_records', ['pet_id', 'is_completed'])
    op.create_index('idx_meal_records_meal_type', 'meal_records', ['meal_type'])
    print("✅ meal_records 表创建成功")

    # 4. 修改 diet_plans 表，添加 pet_id 外键（pets 表已存在）
    with op.batch_alter_table('diet_plans') as batch_op:
        batch_op.add_column(
            sa.Column('pet_id', sa.String(36), nullable=True)
        )
    # 创建外键（使用单独的操作）
    op.create_foreign_key(
        'fk_diet_plans_pet_id',
        'diet_plans', 'pets',
        ['pet_id'], ['id'],
        ondelete='SET NULL'
    )
    # 创建索引
    op.create_index('idx_diet_plans_pet_id', 'diet_plans', ['pet_id'])
    print("✅ diet_plans 表 pet_id 字段添加成功")


def downgrade() -> None:
    """降级数据库"""

    # 删除索引
    op.drop_index('idx_meal_records_meal_type', table_name='meal_records')
    op.drop_index('idx_meal_records_pet_completed', table_name='meal_records')
    op.drop_index('idx_meal_records_pet_date', table_name='meal_records')
    print("❌ meal_records 索引已删除")

    op.drop_index('idx_pets_user_active', table_name='pets')
    print("❌ pets 索引已删除")

    op.drop_index('idx_diet_plans_pet_id', table_name='diet_plans')
    print("❌ diet_plans 索引已删除")

    # 删除表
    op.drop_table('meal_records')
    print("❌ meal_records 表已删除")

    op.drop_table('pets')
    print("❌ pets 表已删除")

    # 修改 diet_plans 表
    with op.batch_alter_table('diet_plans') as batch_op:
        batch_op.drop_constraint('fk_diet_plans_pet_id', type_='foreignkey')
        batch_op.drop_column('pet_id')
    print("❌ diet_plans 表 pet_id 字段已删除")

    # 修改 users 表
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('subscription_expired_at')
        batch_op.drop_column('plan_type')
        batch_op.drop_column('is_pro')
        batch_op.drop_column('avatar_url')
        batch_op.drop_column('phone')
        batch_op.drop_column('nickname')
    print("❌ users 表扩展字段已删除")
