#!/usr/bin/env python3
"""
营养补剂数据导入脚本

从 docs/嗷呜食材数据/补剂.md 导入补剂数据到独立的 supplements 表。
补剂数据的特点：值自带单位（如 350.0 mg），计量基准在备注列中。

用法:
    cd pet_food_backend/pet-food
    uv run python scripts/import_supplements.py
"""
import asyncio
import os
import re
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

# ============ 列名映射: 补剂 MD 表头 -> 数据库字段 ============

COLUMN_MAP = {
    "钙": "calcium",
    "镁": "magnesium",
    "钾": "potassium",
    "钠": "sodium",
    "磷": "phosphorus",
    "碘": "iodine",
    "VD": "vitamin_d",
    "VA": "vitamin_a",
    "VE": "vitamin_e",
    "VB1": "vitamin_b1",
    "锰": "manganese",
    "牛磺酸": "taurine",
    "铁": "iron",
    "锌": "zinc",
    "铜": "copper",
    "EPA&DHA": "epa_dha",
    "EPA": "epa",
    "DHA": "dha",
}

# 所有营养字段（排序保证稳定）
NUTRITION_FIELDS = sorted(set(COLUMN_MAP.values()))

# 数据源
DATA_FILE = PROJECT_ROOT.parent.parent / "docs" / "嗷呜食材数据" / "补剂.md"


def parse_numeric_value(raw: str) -> float | None:
    """解析带单位的数值。例：'350.0 mg' -> 350.0, '-' -> None"""
    raw = raw.strip()
    if not raw or raw == "-":
        return None
    match = re.match(r"^([0-9]+(?:\.[0-9]+)?)", raw)
    if match:
        try:
            return float(Decimal(match.group(1)))
        except (InvalidOperation, ValueError):
            return None
    return None


def normalize_note(raw_note: str) -> str:
    """标准化备注文本"""
    raw_note = raw_note.strip()
    if not raw_note or raw_note == "-":
        return "未知"
    return raw_note


def parse_supplement_table(filepath: Path) -> list[dict]:
    """解析补剂 Markdown 表格"""
    content = filepath.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.strip().split("\n") if line.strip()]

    if len(lines) < 3:
        print(f"  [跳过] {filepath.name}: 行数不足")
        return []

    headers = [h.strip() for h in lines[0].split("|") if h.strip()]
    data_lines = lines[2:]

    records = []
    for line in data_lines:
        cells = [c.strip() for c in line.split("|") if c.strip()]
        if len(cells) < 3:
            continue

        category = cells[0].strip()
        name = cells[1].strip()

        # 最后一列是备注
        note_raw = cells[-1].strip() if len(cells) == len(headers) else "未知"
        note = normalize_note(note_raw)

        record = {
            "category": category,
            "name": name,
            "note": note,
        }

        all_none = True
        for i, header in enumerate(headers):
            if i < 2 or header == "备注":
                continue
            if i >= len(cells):
                break
            db_field = COLUMN_MAP.get(header)
            if db_field:
                value = parse_numeric_value(cells[i])
                record[db_field] = value
                if value is not None:
                    all_none = False

        record["has_nutrition_data"] = not all_none
        records.append(record)

    return records


def build_upsert_sql() -> str:
    """构建 supplements 表的 UPSERT SQL"""
    all_fields = ["id", "name", "category", "has_nutrition_data", "note"] + NUTRITION_FIELDS
    columns = ", ".join(all_fields)
    placeholders = ", ".join(f":{f}" for f in all_fields)
    update_fields = [f for f in all_fields if f not in ("id", "name")]
    update_set = ", ".join(f"{f} = EXCLUDED.{f}" for f in update_fields)

    return f"""
        INSERT INTO supplements ({columns})
        VALUES ({placeholders})
        ON CONFLICT (name) DO UPDATE SET
            {update_set},
            updated_at = now()
    """


async def main():
    print("=" * 60)
    print("营养补剂数据导入工具 (supplements 表)")
    print("=" * 60)

    if not DATA_FILE.exists():
        print(f"错误: 数据文件不存在: {DATA_FILE}")
        sys.exit(1)

    records = parse_supplement_table(DATA_FILE)
    print(f"  {DATA_FILE.name}: 解析到 {len(records)} 条记录")

    # 去重
    supplements: dict[str, dict] = {}
    for record in records:
        name = record["name"]
        if name in supplements:
            print(f"    [覆盖] '{name}'")
        supplements[name] = record

    print(f"\n去重后总计: {len(supplements)} 条补剂")
    no_data_count = sum(1 for r in supplements.values() if not r.get("has_nutrition_data", True))
    print(f"无营养数据行: {no_data_count} 条")

    engine = create_async_engine(settings.database_url, echo=False)
    upsert_sql = text(build_upsert_sql())

    inserted = 0
    updated = 0

    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT name FROM supplements"))
        existing_names = {row[0] for row in result.fetchall()}

        for name, record in supplements.items():
            params = {
                "id": str(uuid.uuid4()),
                "name": record["name"],
                "category": record["category"],
                "has_nutrition_data": record.get("has_nutrition_data", True),
                "note": record.get("note", "未知"),
            }
            for field in NUTRITION_FIELDS:
                val = record.get(field)
                params[field] = float(val) if val is not None else None

            await conn.execute(upsert_sql, params)

            if name in existing_names:
                updated += 1
            else:
                inserted += 1

    # 验证
    async with engine.connect() as conn:
        total = (await conn.execute(text("SELECT count(*) FROM supplements"))).scalar()
        cats = (await conn.execute(
            text("SELECT category, count(*) FROM supplements GROUP BY category ORDER BY count(*) DESC")
        )).fetchall()
        notes = (await conn.execute(
            text("SELECT note, count(*) FROM supplements GROUP BY note ORDER BY count(*) DESC")
        )).fetchall()
        no_data = (await conn.execute(
            text("SELECT count(*) FROM supplements WHERE has_nutrition_data = false")
        )).scalar()

    print("\n" + "=" * 60)
    print("导入完成!")
    print("=" * 60)
    print(f"  新增: {inserted} 条")
    print(f"  更新: {updated} 条")
    print(f"  总计: {total} 条")
    print(f"  无营养数据: {no_data} 条")
    print("\n类别统计:")
    for cat, count in cats:
        print(f"  {cat}: {count} 条")
    print("\n计量基准统计:")
    for note, count in notes:
        print(f"  {note}: {count} 条")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
