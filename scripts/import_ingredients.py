#!/usr/bin/env python3
"""
食材营养数据导入脚本

从 docs/嗷呜食材数据/ 下的 Markdown 文件导入食材营养数据到 ingredients 表。
支持幂等导入（基于食材名称去重，后出现的记录覆盖先前的）。

用法:
    cd pet_food_backend/pet-food
    uv run python scripts/import_ingredients.py
"""
import asyncio
import os
import sys
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("PYTHONUTF8", "1")

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from src.api.config import settings

# ============ 列名映射: Markdown 表头 -> 数据库字段 ============

COLUMN_MAP = {
    "热量 (kcal)": "calories",
    "碳水化合物 (g)": "carbohydrates",
    "蛋白质 (g)": "protein",
    "脂肪 (g)": "fat",
    "铁 (mg)": "iron",
    "锌 (mg)": "zinc",
    "锰 (mg)": "manganese",
    "镁 (mg)": "magnesium",
    "钠 (mg)": "sodium",
    "VB1 (mg)": "vitamin_b1",
    "VE (mg)": "vitamin_e",
    "EPA (mg)": "epa",
    "EPA&DHA (mg)": "epa_dha",
    "骨骼含量 (%)": "bone_content",
    "水份 (g)": "water",
    "水分 (g)": "water",  # 兼容两种写法
    "胆碱 (mg)": "choline",
    "钙 (mg)": "calcium",
    "磷 (mg)": "phosphorus",
    "铜 (mg)": "copper",
    "碘 (μg)": "iodine",
    "钾 (mg)": "potassium",
    "VA (IU)": "vitamin_a",
    "VD (IU)": "vitamin_d",
    "牛磺酸 (mg)": "taurine",
    "DHA (mg)": "dha",
}

# 所有营养字段名（排序以保证稳定顺序）
NUTRITION_FIELDS = sorted(set(COLUMN_MAP.values()))

# 数据源文件（按顺序处理，后出现的覆盖先前的）
DATA_DIR = PROJECT_ROOT.parent.parent / "docs" / "嗷呜食材数据"
DATA_FILES = [DATA_DIR / f"{i}.md" for i in range(1, 6)]


def parse_value(raw: str) -> Decimal | None:
    """解析单元格值，`-` 或空值返回 None"""
    raw = raw.strip()
    if not raw or raw == "-":
        return None
    try:
        return Decimal(raw)
    except InvalidOperation:
        return None


def parse_markdown_table(filepath: Path) -> list[dict]:
    """解析 Markdown 表格文件，返回食材记录列表"""
    content = filepath.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.strip().split("\n") if line.strip()]

    if len(lines) < 3:
        print(f"  [跳过] {filepath.name}: 行数不足")
        return []

    # 解析表头
    header_line = lines[0]
    headers = [h.strip() for h in header_line.split("|") if h.strip()]

    # 跳过分隔行 (第 2 行)
    data_lines = lines[2:]

    records = []
    for line in data_lines:
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) < 3:
            continue

        # 前 3 列为分类信息
        record = {
            "category": cells[0].strip(),
            "sub_category": cells[1].strip(),
            "name": cells[2].strip(),
        }

        # 营养字段映射
        all_none = True
        for i, header in enumerate(headers):
            if i < 3:
                continue  # 跳过前 3 列
            if i >= len(cells):
                break
            db_field = COLUMN_MAP.get(header)
            if db_field:
                value = parse_value(cells[i])
                record[db_field] = value
                if value is not None:
                    all_none = False

        record["has_nutrition_data"] = not all_none
        records.append(record)

    return records


def build_upsert_sql() -> str:
    """构建 PostgreSQL UPSERT SQL (asyncpg 使用 $N 占位符)"""
    all_fields = ["id", "name", "category", "sub_category", "has_nutrition_data"] + NUTRITION_FIELDS
    columns = ", ".join(all_fields)
    placeholders = ", ".join(f":{f}" for f in all_fields)

    # ON CONFLICT 更新除 id 和 name 之外的所有字段
    update_fields = [f for f in all_fields if f not in ("id", "name")]
    update_set = ", ".join(f"{f} = EXCLUDED.{f}" for f in update_fields)

    return f"""
        INSERT INTO ingredients ({columns})
        VALUES ({placeholders})
        ON CONFLICT (name) DO UPDATE SET
            {update_set},
            updated_at = now()
    """


async def main():
    print("=" * 60)
    print("食材营养数据导入工具")
    print("=" * 60)

    # 检查数据目录
    if not DATA_DIR.exists():
        print(f"错误: 数据目录不存在: {DATA_DIR}")
        sys.exit(1)

    # 解析所有文件，后出现的覆盖先前的（去重）
    all_ingredients: dict[str, dict] = {}  # name -> record

    for filepath in DATA_FILES:
        if not filepath.exists():
            print(f"  [跳过] {filepath.name}: 文件不存在")
            continue

        records = parse_markdown_table(filepath)
        print(f"  {filepath.name}: 解析到 {len(records)} 条记录")

        for record in records:
            name = record["name"]
            if name in all_ingredients:
                print(f"    [覆盖] '{name}' (来自 {filepath.name})")
            all_ingredients[name] = record

    print(f"\n去重后总计: {len(all_ingredients)} 条唯一食材")

    no_data_count = sum(1 for r in all_ingredients.values() if not r.get("has_nutrition_data", True))
    print(f"无营养数据行: {no_data_count} 条")

    # 使用 asyncpg 连接
    engine = create_async_engine(settings.database_url, echo=False)

    upsert_sql = text(build_upsert_sql())

    inserted = 0
    updated = 0

    async with engine.begin() as conn:
        # 查询已有记录
        result = await conn.execute(text("SELECT name FROM ingredients"))
        existing_names = {row[0] for row in result.fetchall()}

        for name, record in all_ingredients.items():
            params = {
                "id": str(uuid.uuid4()),
                "name": record["name"],
                "category": record["category"],
                "sub_category": record["sub_category"],
                "has_nutrition_data": record.get("has_nutrition_data", True),
            }
            for field in NUTRITION_FIELDS:
                val = record.get(field)
                # asyncpg 需要 float 而非 Decimal
                params[field] = float(val) if val is not None else None

            await conn.execute(upsert_sql, params)

            if name in existing_names:
                updated += 1
            else:
                inserted += 1

    # 验证
    async with engine.connect() as conn:
        total = (await conn.execute(text("SELECT count(*) FROM ingredients"))).scalar()
        categories = (await conn.execute(
            text("SELECT category, count(*) FROM ingredients GROUP BY category ORDER BY count(*) DESC")
        )).fetchall()
        no_data = (await conn.execute(
            text("SELECT count(*) FROM ingredients WHERE has_nutrition_data = false")
        )).scalar()

    print("\n" + "=" * 60)
    print("导入完成!")
    print("=" * 60)
    print(f"  新增: {inserted} 条")
    print(f"  更新: {updated} 条")
    print(f"  总计: {total} 条")
    print(f"  无营养数据: {no_data} 条")
    print("\n分类统计:")
    for cat, count in categories:
        print(f"  {cat}: {count} 条")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
