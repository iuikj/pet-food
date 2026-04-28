"""drop_weight_record_unique_constraint

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-28 12:00:00.000000+08:00

允许同一宠物在同一天保存多条体重记录，避免前端重复记录时只保留最后一条。
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级数据库"""
    op.drop_constraint('uq_pet_recorded_date', 'weight_records', type_='unique')


def downgrade() -> None:
    """降级数据库"""
    op.create_unique_constraint(
        'uq_pet_recorded_date',
        'weight_records',
        ['pet_id', 'recorded_date'],
    )
