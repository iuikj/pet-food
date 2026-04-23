"""add_ingredient_ownership

Revision ID: a1b2c3d4e5f6
Revises: 53f28db7acbd
Create Date: 2026-04-21 15:00:00.000000+08:00

为 ingredients 表添加归属字段：
- user_id (nullable FK → users.id)：自定义食材的创建人
- is_system (boolean, default False)：是否系统内建食材

同时：
- 将 name 列的唯一约束替换为 (user_id, name) 联合唯一，允许不同用户有同名食材
- 现有记录回填为 is_system=True（视作系统食材）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '53f28db7acbd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级数据库"""
    # 1. 新增归属字段（is_system 先用 server_default=true 回填现有记录）
    op.add_column(
        'ingredients',
        sa.Column('user_id', sa.String(length=36), nullable=True),
    )
    op.add_column(
        'ingredients',
        sa.Column(
            'is_system',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('true'),
        ),
    )

    # 2. 创建外键 + 索引
    op.create_foreign_key(
        'fk_ingredients_user_id_users',
        'ingredients',
        'users',
        ['user_id'],
        ['id'],
        ondelete='CASCADE',
    )
    op.create_index('ix_ingredients_user_id', 'ingredients', ['user_id'], unique=False)
    op.create_index('ix_ingredients_is_system', 'ingredients', ['is_system'], unique=False)
    op.create_index(
        'idx_ingredient_owner',
        'ingredients',
        ['user_id', 'is_system'],
        unique=False,
    )

    # 3. name 的唯一索引 → 替换为 (user_id, name) 联合唯一约束
    #    老的 ix_ingredients_name 是 unique=True，需要 drop 重建
    op.drop_index('ix_ingredients_name', table_name='ingredients')
    op.create_index('ix_ingredients_name', 'ingredients', ['name'], unique=False)
    op.create_unique_constraint(
        'uq_ingredient_user_name',
        'ingredients',
        ['user_id', 'name'],
    )

    # 4. 回填完成后移除 server_default，让应用层控制默认值（模型定义为 default=False）
    op.alter_column('ingredients', 'is_system', server_default=None)


def downgrade() -> None:
    """降级数据库"""
    op.drop_constraint('uq_ingredient_user_name', 'ingredients', type_='unique')
    op.drop_index('ix_ingredients_name', table_name='ingredients')
    op.create_index('ix_ingredients_name', 'ingredients', ['name'], unique=True)

    op.drop_index('idx_ingredient_owner', table_name='ingredients')
    op.drop_index('ix_ingredients_is_system', table_name='ingredients')
    op.drop_index('ix_ingredients_user_id', table_name='ingredients')
    op.drop_constraint('fk_ingredients_user_id_users', 'ingredients', type_='foreignkey')
    op.drop_column('ingredients', 'is_system')
    op.drop_column('ingredients', 'user_id')
