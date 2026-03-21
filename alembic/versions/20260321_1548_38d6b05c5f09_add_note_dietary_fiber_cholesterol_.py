"""add_note_dietary_fiber_cholesterol_selenium_to_ingredients

Revision ID: 38d6b05c5f09
Revises: 12347785a64c
Create Date: 2026-03-21 15:48:13.293139+08:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '38d6b05c5f09'
down_revision: Union[str, None] = '12347785a64c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """升级数据库"""
    # 新增列
    op.add_column('ingredients', sa.Column('note', sa.String(length=100), nullable=True, comment='计量备注'))
    op.add_column('ingredients', sa.Column('dietary_fiber', sa.Numeric(precision=10, scale=4), nullable=True, comment='膳食纤维 (g)'))
    op.add_column('ingredients', sa.Column('selenium', sa.Numeric(precision=10, scale=4), nullable=True, comment='硒 (μg)'))
    op.add_column('ingredients', sa.Column('cholesterol', sa.Numeric(precision=10, scale=4), nullable=True, comment='胆固醇 (mg)'))

    # 添加中文备注 (comment)
    for col, comment in [
        ('name', '食材名称'), ('category', '大类别'), ('sub_category', '小类别'),
        ('has_nutrition_data', '是否有营养数据'), ('calories', '热量 (kcal)'),
        ('carbohydrates', '碳水化合物 (g)'), ('protein', '蛋白质 (g)'), ('fat', '脂肪 (g)'),
        ('iron', '铁 (mg)'), ('zinc', '锌 (mg)'), ('manganese', '锰 (mg)'),
        ('magnesium', '镁 (mg)'), ('sodium', '钠 (mg)'), ('calcium', '钙 (mg)'),
        ('phosphorus', '磷 (mg)'), ('copper', '铜 (mg)'), ('iodine', '碘 (μg)'),
        ('potassium', '钾 (mg)'), ('vitamin_b1', '维生素B1 (mg)'), ('vitamin_e', '维生素E (mg)'),
        ('vitamin_a', '维生素A (IU)'), ('vitamin_d', '维生素D (IU)'),
        ('epa', 'EPA (mg)'), ('dha', 'DHA (mg)'), ('epa_dha', 'EPA&DHA (mg)'),
        ('bone_content', '骨骼含量 (%)'), ('water', '水分 (g)'),
        ('choline', '胆碱 (mg)'), ('taurine', '牛磺酸 (mg)'),
    ]:
        op.execute(f"COMMENT ON COLUMN ingredients.{col} IS '{comment}'")

    # 为现有食材记录设置 note
    op.execute("UPDATE ingredients SET note = '以每100g计算' WHERE note IS NULL")


def downgrade() -> None:
    """降级数据库"""
    op.drop_column('ingredients', 'cholesterol')
    op.drop_column('ingredients', 'selenium')
    op.drop_column('ingredients', 'dietary_fiber')
    op.drop_column('ingredients', 'note')
