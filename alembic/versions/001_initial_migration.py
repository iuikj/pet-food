"""初始数据库迁移

创建用户表、任务表、饮食计划表和刷新令牌表

Revision ID: 001
Revises:
Create Date: 2025-01-29 21:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级数据库 - 创建所有表"""

    # 创建用户表
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('username', sa.String(50), unique=True, nullable=False, index=True),
        sa.Column('email', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_superuser', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    print("✅ 用户表创建成功")

    # 创建任务表
    op.create_table(
        'tasks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('task_type', sa.String(50), default='diet_plan', index=True),
        sa.Column('status', sa.String(20), default='pending', index=True),
        sa.Column('progress', sa.Integer(), default=0),
        sa.Column('current_node', sa.String(100), nullable=True),
        sa.Column('input_data', sa.JSON(), nullable=False),
        sa.Column('output_data', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    print("✅ 任务表创建成功")

    # 创建饮食计划表
    op.create_table(
        'diet_plans',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('task_id', sa.String(36), sa.ForeignKey('tasks.id'), nullable=True, index=True),
        sa.Column('pet_type', sa.String(50), index=True),
        sa.Column('pet_breed', sa.String(100), nullable=True),
        sa.Column('pet_age', sa.Integer(), nullable=False),
        sa.Column('pet_weight', sa.Integer(), nullable=False),
        sa.Column('health_status', sa.Text(), nullable=True),
        sa.Column('plan_data', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    print("✅ 饮食计划表创建成功")

    # 创建刷新令牌表
    op.create_table(
        'refresh_tokens',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('token', sa.String(500), unique=True, nullable=False, index=True),
        sa.Column('is_revoked', sa.Boolean(), default=False, index=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    print("✅ 刷新令牌表创建成功")


def downgrade() -> None:
    """降级数据库 - 删除所有表"""

    op.drop_table('refresh_tokens')
    print("❌ 刷新令牌表已删除")

    op.drop_table('diet_plans')
    print("❌ 饮食计划表已删除")

    op.drop_table('tasks')
    print("❌ 任务表已删除")

    op.drop_table('users')
    print("❌ 用户表已删除")
