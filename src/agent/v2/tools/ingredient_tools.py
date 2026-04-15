"""
食材查询工具 -- 接入真实 PostgreSQL 数据库

通过 asyncio.to_thread 将 DB 查询放到独立线程执行，
完全绕过 langgraph dev 的 blockbuster 对 asyncpg os.getcwd() 的拦截。
使用同步 psycopg2 驱动，线程安全。
"""
import json
from typing import Annotated, Optional

from langchain.tools import tool
from sqlalchemy import select, func

from src.db.models import Ingredient
from src.agent.v2.tools.db import run_query


# ──────────────────────────── 辅助函数 ────────────────────────────

def _row_to_dict(row, detail: bool = False) -> dict:
    """将查询结果行转为 dict。

    detail=False: 摘要模式，返回 7 个核心字段（节省 LLM 上下文）
    detail=True:  完整模式，返回全部 30+ 个营养字段
    """
    def _f(v) -> Optional[float]:
        return round(float(v), 4) if v is not None else None

    base = {
        "name": row.name,
        "category": row.category,
        "sub_category": row.sub_category,
        "calories_kcal": _f(row.calories),
        "protein_g": _f(row.protein),
        "fat_g": _f(row.fat),
        "carbohydrates_g": _f(row.carbohydrates),
    }

    if not detail:
        return base

    base.update({
        "dietary_fiber_g": _f(row.dietary_fiber),
        "note": row.note,
        # 矿物质
        "calcium_mg": _f(row.calcium),
        "phosphorus_mg": _f(row.phosphorus),
        "iron_mg": _f(row.iron),
        "zinc_mg": _f(row.zinc),
        "manganese_mg": _f(row.manganese),
        "magnesium_mg": _f(row.magnesium),
        "sodium_mg": _f(row.sodium),
        "copper_mg": _f(row.copper),
        "iodine_ug": _f(row.iodine),
        "potassium_mg": _f(row.potassium),
        "selenium_ug": _f(row.selenium),
        # 维生素
        "vitamin_a_iu": _f(row.vitamin_a),
        "vitamin_d_iu": _f(row.vitamin_d),
        "vitamin_e_mg": _f(row.vitamin_e),
        "vitamin_b1_mg": _f(row.vitamin_b1),
        # 脂肪酸
        "epa_mg": _f(row.epa),
        "dha_mg": _f(row.dha),
        "epa_dha_mg": _f(row.epa_dha),
        # 其他
        "bone_content_pct": _f(row.bone_content),
        "water_g": _f(row.water),
        "choline_mg": _f(row.choline),
        "taurine_mg": _f(row.taurine),
        "cholesterol_mg": _f(row.cholesterol),
    })
    return base


# ──────────────────────────── 工具定义 ────────────────────────────

@tool
async def ingredient_search_tool(
    keyword: Annotated[Optional[str], "食材名称关键词(模糊匹配)，如'鸡''三文鱼'"] = None,
    category: Annotated[Optional[str], "大类别，如'白肉''红肉''内脏''海鲜''蔬菜''水果''蛋类''骨头'"] = None,
    sub_category: Annotated[Optional[str], "小类别，如'鸡''牛''猪''鸭'"] = None,
    protein_min: Annotated[Optional[float], "蛋白质最小值(g/100g)"] = None,
    protein_max: Annotated[Optional[float], "蛋白质最大值(g/100g)"] = None,
    fat_min: Annotated[Optional[float], "脂肪最小值(g/100g)"] = None,
    fat_max: Annotated[Optional[float], "脂肪最大值(g/100g)"] = None,
    calcium_min: Annotated[Optional[float], "钙最低值(mg/100g)"] = None,
    taurine_min: Annotated[Optional[float], "牛磺酸最低值(mg/100g)，猫粮选材常用"] = None,
    limit: Annotated[int, "返回条数上限"] = 20,
) -> list[dict]:
    """按条件组合搜索食材数据库。所有营养素数值基于每 100g 可食部分。

    支持按类别、关键词、营养素范围等多种筛选条件组合查询。
    返回摘要信息（名称、类别、热量、三大营养素），
    如需完整营养数据请使用 ingredient_detail_tool。
    """
    stmt = select(Ingredient).where(Ingredient.has_nutrition_data.is_(True))

    if keyword:
        stmt = stmt.where(Ingredient.name.ilike(f"%{keyword}%"))
    if category:
        stmt = stmt.where(Ingredient.category == category)
    if sub_category:
        stmt = stmt.where(Ingredient.sub_category == sub_category)
    if protein_min is not None:
        stmt = stmt.where(Ingredient.protein >= protein_min)
    if protein_max is not None:
        stmt = stmt.where(Ingredient.protein <= protein_max)
    if fat_min is not None:
        stmt = stmt.where(Ingredient.fat >= fat_min)
    if fat_max is not None:
        stmt = stmt.where(Ingredient.fat <= fat_max)
    if calcium_min is not None:
        stmt = stmt.where(Ingredient.calcium >= calcium_min)
    if taurine_min is not None:
        stmt = stmt.where(Ingredient.taurine >= taurine_min)

    stmt = stmt.order_by(Ingredient.name).limit(limit)

    rows = await run_query(stmt)

    # 构建筛选条件描述
    filters = []
    if keyword:
        filters.append(f"关键词='{keyword}'")
    if category:
        filters.append(f"类别='{category}'")
    if sub_category:
        filters.append(f"子类别='{sub_category}'")
    if protein_min is not None:
        filters.append(f"蛋白质≥{protein_min}g")
    if fat_max is not None:
        filters.append(f"脂肪≤{fat_max}g")
    filter_desc = ", ".join(filters) if filters else "无特定筛选"

    if not rows:
        return f"未找到符合条件的食材。搜索条件: {filter_desc}。请尝试放宽筛选条件。"

    items = []
    for row in rows:
        d = _row_to_dict(row, detail=False)
        items.append(
            f"- {d['name']} ({d['category']}/{d.get('sub_category', '')}): "
            f"蛋白质 {d['protein_g']}g, 脂肪 {d['fat_g']}g, "
            f"碳水 {d['carbohydrates_g']}g, 热量 {d['calories_kcal']}kcal (每100g)"
        )

    return (
        f"食材搜索完成（条件: {filter_desc}），共找到 {len(rows)} 种食材：\n"
        + "\n".join(items)
    )


@tool
async def ingredient_detail_tool(
    name: Annotated[str, "食材名称(精确匹配)"],
) -> dict:
    """获取指定食材的完整营养数据，含所有矿物质、维生素、脂肪酸等。
    所有数值基于每 100g 可食部分。
    """
    stmt = select(Ingredient).where(Ingredient.name == name)
    row = await run_query(stmt, one=True)

    if row is None:
        return f"食材详情查询失败 — 食材 '{name}' 不存在，请检查名称是否正确。"

    d = _row_to_dict(row, detail=True)
    summary = (
        f"食材详情查询完成 — {d['name']}（{d['category']}/{d.get('sub_category', '')}）:\n"
        f"每100g可食部分：热量 {d['calories_kcal']}kcal, 蛋白质 {d['protein_g']}g, "
        f"脂肪 {d['fat_g']}g, 碳水 {d['carbohydrates_g']}g, "
        f"膳食纤维 {d.get('dietary_fiber_g', 'N/A')}g\n"
        f"矿物质: 钙 {d.get('calcium_mg', 'N/A')}mg, 磷 {d.get('phosphorus_mg', 'N/A')}mg, "
        f"铁 {d.get('iron_mg', 'N/A')}mg, 锌 {d.get('zinc_mg', 'N/A')}mg, "
        f"钠 {d.get('sodium_mg', 'N/A')}mg, 钾 {d.get('potassium_mg', 'N/A')}mg\n"
        f"维生素: A {d.get('vitamin_a_iu', 'N/A')}IU, D {d.get('vitamin_d_iu', 'N/A')}IU, "
        f"E {d.get('vitamin_e_mg', 'N/A')}mg\n"
    )
    if d.get('taurine_mg') is not None:
        summary += f"牛磺酸: {d['taurine_mg']}mg\n"
    if d.get('epa_dha_mg') is not None:
        summary += f"EPA+DHA: {d['epa_dha_mg']}mg\n"

    summary += f"\n完整数据: {json.dumps(d, ensure_ascii=False)}"
    return summary


@tool
async def ingredient_categories_tool() -> list[dict]:
    """获取食材数据库中所有可用的类别和子类别列表及各分类下的食材数量。
    用于了解数据库中有哪些食材分类，以便后续精确查询。
    """
    stmt = (
        select(
            Ingredient.category,
            Ingredient.sub_category,
            func.count(Ingredient.id).label("count"),
        )
        .where(Ingredient.has_nutrition_data.is_(True))
        .group_by(Ingredient.category, Ingredient.sub_category)
        .order_by(Ingredient.category, Ingredient.sub_category)
    )

    rows = await run_query(stmt, scalars=False)

    if not rows:
        return "食材分类查询完成，数据库中暂无食材数据。"

    lines = [f"食材分类查询完成，共 {len(rows)} 个分类：\n"]
    for r in rows:
        lines.append(f"- {r.category}/{r.sub_category}: {r.count} 种食材")

    return "\n".join(lines)
