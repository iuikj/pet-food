"""add_ingredients_table

Revision ID: 12347785a64c
Revises: 003
Create Date: 2026-03-21 14:56:40.736454+08:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '12347785a64c'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级数据库"""
    op.create_table('ingredients',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('category', sa.String(length=50), nullable=False),
    sa.Column('sub_category', sa.String(length=50), nullable=False),
    sa.Column('has_nutrition_data', sa.Boolean(), nullable=False),
    sa.Column('calories', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('carbohydrates', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('protein', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('fat', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('iron', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('zinc', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('manganese', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('magnesium', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('sodium', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('calcium', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('phosphorus', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('copper', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('iodine', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('potassium', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('vitamin_b1', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('vitamin_e', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('vitamin_a', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('vitamin_d', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('epa', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('dha', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('epa_dha', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('bone_content', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('water', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('choline', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('taurine', sa.Numeric(precision=10, scale=4), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_ingredient_category', 'ingredients', ['category', 'sub_category'], unique=False)
    op.create_index(op.f('ix_ingredients_id'), 'ingredients', ['id'], unique=False)
    op.create_index(op.f('ix_ingredients_name'), 'ingredients', ['name'], unique=True)


def downgrade() -> None:
    """降级数据库"""
    op.drop_index(op.f('ix_ingredients_name'), table_name='ingredients')
    op.drop_index(op.f('ix_ingredients_id'), table_name='ingredients')
    op.drop_index('idx_ingredient_category', table_name='ingredients')
    op.drop_table('ingredients')
