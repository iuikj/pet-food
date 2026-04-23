"""add_pet_allergens_and_health_issues

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-21 22:00:00.000000+08:00

为 pets 表新增结构化的健康偏好字段：
- allergens (JSON, nullable)：过敏原数组，如 ["鸡肉", "乳制品"]
- health_issues (JSON, nullable)：健康问题数组，如 ["肠胃敏感", "体重异常"]

旧的自由文本字段 health_status / special_requirements 保留不动，
数组字段为新数据通道，避免破坏历史记录。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级数据库"""
    op.add_column(
        'pets',
        sa.Column('allergens', sa.JSON(), nullable=True),
    )
    op.add_column(
        'pets',
        sa.Column('health_issues', sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    """降级数据库"""
    op.drop_column('pets', 'health_issues')
    op.drop_column('pets', 'allergens')
