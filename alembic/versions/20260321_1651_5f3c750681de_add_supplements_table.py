"""add_supplements_table

Revision ID: 5f3c750681de
Revises: 38d6b05c5f09
Create Date: 2026-03-21 16:51:01.970417+08:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f3c750681de'
down_revision: Union[str, None] = '38d6b05c5f09'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级数据库"""
    op.create_table('supplements',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False, comment='产品名称'),
    sa.Column('category', sa.String(length=50), nullable=False, comment='类别'),
    sa.Column('has_nutrition_data', sa.Boolean(), nullable=False, comment='是否有营养数据'),
    sa.Column('note', sa.String(length=100), nullable=True, comment='计量备注'),
    sa.Column('calcium', sa.Numeric(precision=10, scale=4), nullable=True, comment='钙 (mg)'),
    sa.Column('magnesium', sa.Numeric(precision=10, scale=4), nullable=True, comment='镁 (mg)'),
    sa.Column('potassium', sa.Numeric(precision=10, scale=4), nullable=True, comment='钾 (mg)'),
    sa.Column('sodium', sa.Numeric(precision=10, scale=4), nullable=True, comment='钠 (mg)'),
    sa.Column('phosphorus', sa.Numeric(precision=10, scale=4), nullable=True, comment='磷 (mg)'),
    sa.Column('iodine', sa.Numeric(precision=10, scale=4), nullable=True, comment='碘 (μg)'),
    sa.Column('manganese', sa.Numeric(precision=10, scale=4), nullable=True, comment='锰 (mg)'),
    sa.Column('iron', sa.Numeric(precision=10, scale=4), nullable=True, comment='铁 (mg)'),
    sa.Column('zinc', sa.Numeric(precision=10, scale=4), nullable=True, comment='锌 (mg)'),
    sa.Column('copper', sa.Numeric(precision=10, scale=4), nullable=True, comment='铜 (mg)'),
    sa.Column('vitamin_d', sa.Numeric(precision=10, scale=4), nullable=True, comment='维生素D (IU)'),
    sa.Column('vitamin_a', sa.Numeric(precision=10, scale=4), nullable=True, comment='维生素A (IU)'),
    sa.Column('vitamin_e', sa.Numeric(precision=10, scale=4), nullable=True, comment='维生素E (mg)'),
    sa.Column('vitamin_b1', sa.Numeric(precision=10, scale=4), nullable=True, comment='维生素B1 (mg)'),
    sa.Column('taurine', sa.Numeric(precision=10, scale=4), nullable=True, comment='牛磺酸 (mg)'),
    sa.Column('epa_dha', sa.Numeric(precision=10, scale=4), nullable=True, comment='EPA&DHA (mg)'),
    sa.Column('epa', sa.Numeric(precision=10, scale=4), nullable=True, comment='EPA (mg)'),
    sa.Column('dha', sa.Numeric(precision=10, scale=4), nullable=True, comment='DHA (mg)'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_supplement_category', 'supplements', ['category'], unique=False)
    op.create_index(op.f('ix_supplements_id'), 'supplements', ['id'], unique=False)
    op.create_index(op.f('ix_supplements_name'), 'supplements', ['name'], unique=True)


def downgrade() -> None:
    """降级数据库"""
    op.drop_index(op.f('ix_supplements_name'), table_name='supplements')
    op.drop_index(op.f('ix_supplements_id'), table_name='supplements')
    op.drop_index('idx_supplement_category', table_name='supplements')
    op.drop_table('supplements')
