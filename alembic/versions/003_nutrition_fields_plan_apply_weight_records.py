"""营养字段提升、计划应用系统、体重记录表

meal_records 新增 protein/fat/carbohydrates/dietary_fiber 顶级 Numeric 列
diet_plans 新增 is_active/applied_at/active_start_date 列 + 复合索引
新建 weight_records 表

Revision ID: 003
Revises: 002
Create Date: 2026-03-20 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === meal_records: 营养字段提升 ===
    op.add_column('meal_records', sa.Column('protein', sa.Numeric(8, 2), nullable=True))
    op.add_column('meal_records', sa.Column('fat', sa.Numeric(8, 2), nullable=True))
    op.add_column('meal_records', sa.Column('carbohydrates', sa.Numeric(8, 2), nullable=True))
    op.add_column('meal_records', sa.Column('dietary_fiber', sa.Numeric(8, 2), nullable=True))

    # === diet_plans: 计划应用系统 ===
    op.add_column('diet_plans', sa.Column('is_active', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('diet_plans', sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('diet_plans', sa.Column('active_start_date', sa.Date(), nullable=True))
    op.create_index('idx_diet_plans_is_active', 'diet_plans', ['is_active'])
    op.create_index('idx_pet_active_plan', 'diet_plans', ['pet_id', 'is_active'])

    # === weight_records: 体重记录表 ===
    # 使用 IF NOT EXISTS 避免与 Base.metadata.create_all 冲突
    op.execute("""
        CREATE TABLE IF NOT EXISTS weight_records (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            pet_id VARCHAR(36) NOT NULL REFERENCES pets(id),
            weight NUMERIC(5, 2) NOT NULL,
            recorded_date DATE NOT NULL,
            notes TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
            CONSTRAINT uq_pet_recorded_date UNIQUE (pet_id, recorded_date)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_weight_records_id ON weight_records (id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_weight_records_pet_id ON weight_records (pet_id)")


def downgrade() -> None:
    # weight_records
    op.drop_table('weight_records')

    # diet_plans
    op.drop_index('idx_pet_active_plan', table_name='diet_plans')
    op.drop_index('idx_diet_plans_is_active', table_name='diet_plans')
    op.drop_column('diet_plans', 'active_start_date')
    op.drop_column('diet_plans', 'applied_at')
    op.drop_column('diet_plans', 'is_active')

    # meal_records
    op.drop_column('meal_records', 'dietary_fiber')
    op.drop_column('meal_records', 'carbohydrates')
    op.drop_column('meal_records', 'fat')
    op.drop_column('meal_records', 'protein')
