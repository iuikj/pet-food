"""add_ingredient_icon_and_image

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-21 20:00:00.000000+08:00

为 ingredients 表添加可视化资产字段：
- icon_key (String(64), nullable)：图标 key，格式 <library>:<name>
- image_url (Text, nullable)：缩略图 MinIO 引用

系统食材按 sub_category 批量回填 icon_key（emoji 兜底）。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 系统食材按 sub_category / category 批量回填 icon_key 的映射表。
# 仅对 is_system=true 且 icon_key 为空的记录生效，管理员手动改过的不受影响。
SUBCATEGORY_TO_ICON = {
    # 肉类 - 子类别
    '鸡': 'emoji:chicken',
    '火鸡': 'emoji:turkey',
    '鸭': 'emoji:duck',
    '牛': 'emoji:beef',
    '羊': 'emoji:lamb',
    '猪': 'emoji:pork',
    '兔': 'emoji:rabbit',
    # 水产 - 子类别
    '鱼': 'emoji:fish',
    '三文鱼': 'emoji:salmon',
    '鳕鱼': 'emoji:cod',
    '虾': 'emoji:shrimp',
    '蟹': 'emoji:crab',
    '贝类': 'emoji:oyster',
    # 蛋奶
    '蛋': 'emoji:egg',
    '奶': 'emoji:milk',
    # 蔬菜 - 子类别
    '叶菜': 'emoji:leafy_green',
    '根菜': 'emoji:carrot',
    '瓜果': 'emoji:pumpkin',
    '菌菇': 'emoji:mushroom',
    '豆类': 'emoji:bean',
    # 水果
    '浆果': 'emoji:strawberry',
    '仁果': 'emoji:apple',
    '柑橘': 'emoji:orange',
    # 谷物
    '大米': 'emoji:rice',
    '燕麦': 'emoji:oat',
    '麦': 'emoji:wheat',
    # 油脂
    '植物油': 'emoji:olive',
    # 补剂
    '矿物': 'emoji:supplement',
    '维生素': 'emoji:supplement',
}

CATEGORY_TO_ICON = {
    '白肉': 'emoji:chicken',
    '红肉': 'emoji:beef',
    '内脏': 'emoji:beef',
    '海鲜': 'emoji:fish',
    '蛋类': 'emoji:egg',
    '蔬菜': 'emoji:leafy_green',
    '水果': 'emoji:apple',
    '谷物': 'emoji:rice',
    '主食': 'emoji:rice',
    '骨头': 'emoji:bone',
    '补剂': 'emoji:supplement',
    '油脂': 'emoji:oil',
}


def upgrade() -> None:
    """升级数据库"""
    # 1. 新增字段
    op.add_column(
        'ingredients',
        sa.Column('icon_key', sa.String(length=64), nullable=True),
    )
    op.add_column(
        'ingredients',
        sa.Column('image_url', sa.Text(), nullable=True),
    )

    # 2. 系统食材 icon_key 批量回填
    #    先按 sub_category 精确匹配，再按 category 兜底，最后默认 emoji:mixed
    bind = op.get_bind()
    for sub_cat, icon in SUBCATEGORY_TO_ICON.items():
        bind.execute(
            sa.text("""
                UPDATE ingredients
                SET icon_key = :icon
                WHERE is_system = true
                  AND icon_key IS NULL
                  AND sub_category = :sub_cat
            """),
            {"icon": icon, "sub_cat": sub_cat},
        )
    for cat, icon in CATEGORY_TO_ICON.items():
        bind.execute(
            sa.text("""
                UPDATE ingredients
                SET icon_key = :icon
                WHERE is_system = true
                  AND icon_key IS NULL
                  AND category = :cat
            """),
            {"icon": icon, "cat": cat},
        )
    # 所有剩余系统食材使用默认值
    bind.execute(
        sa.text("""
            UPDATE ingredients
            SET icon_key = 'emoji:mixed'
            WHERE is_system = true AND icon_key IS NULL
        """)
    )


def downgrade() -> None:
    """降级数据库"""
    op.drop_column('ingredients', 'image_url')
    op.drop_column('ingredients', 'icon_key')
