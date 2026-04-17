"""
Phase 3 组装工具

将 week_agent 的轻量输出 (WeekLightPlan) + Ingredient 数据库行
按 per-100g 比例精确计算出完整的 WeeklyDietPlan (含所有微量营养素与单位)。

设计要点：
- 纯 Python 计算，无 LLM 调用
- 单位契约完全由 MICRO_UNIT_MAP 与 ADDITIONAL_UNIT_MAP 保证
- DB 列为 NULL 时营养素回退为 0.0（而非缺省字段），不抛异常
- 未命中的食材记录 warning 并跳过，不影响其他食材
- 批量预取通过 ingredients_by_name() 一次性获取，避免 N+1
"""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Iterable, Optional

from sqlalchemy import select, func

from src.agent.common.utils.struct import (
    DailyDietPlan,
    FoodItem,
    Macronutrients,
    Micronutrients,
    NutrientAmount,
    SingleMealPlan,
    WeeklyDietPlan,
)
from src.agent.v2.models import IngredientAllocation, MealLight, WeekLightPlan
from src.agent.v2.tools.db import run_query
from src.db.models import Ingredient

logger = logging.getLogger(__name__)


# ──────────────────────────── 单位映射 ────────────────────────────

# Micronutrients 的 12 个固定字段 → (Ingredient 列名, 单位)
# 若 Ingredient 列为 None / 不存在，则填 0.0 并保留单位
MICRO_FIELD_TO_COLUMN: dict[str, tuple[str, str]] = {
    "vitamin_a": ("vitamin_a", "IU"),
    "vitamin_c": ("vitamin_c", "mg"),  # DB 无该列 → 始终 0.0
    "vitamin_d": ("vitamin_d", "IU"),
    "vitamin_e": ("vitamin_e", "mg"),
    "calcium": ("calcium", "mg"),
    "iron": ("iron", "mg"),
    "sodium": ("sodium", "mg"),
    "potassium": ("potassium", "mg"),
    "phosphorus": ("phosphorus", "mg"),
    "zinc": ("zinc", "mg"),
    "taurine": ("taurine", "mg"),
    "cholesterol": ("cholesterol", "mg"),
}

# additional_nutrients 字典的扩展字段 → (Ingredient 列名, 单位)
ADDITIONAL_FIELD_MAP: dict[str, tuple[str, str]] = {
    "EPA": ("epa", "mg"),
    "DHA": ("dha", "mg"),
    "EPA_DHA": ("epa_dha", "mg"),
    "copper": ("copper", "mg"),
    "manganese": ("manganese", "mg"),
    "magnesium": ("magnesium", "mg"),
    "iodine": ("iodine", "ug"),
    "selenium": ("selenium", "ug"),
    "vitamin_b1": ("vitamin_b1", "mg"),
    "choline": ("choline", "mg"),
}


# ──────────────────────────── 工具函数 ────────────────────────────

def _num(v) -> float:
    """把 DB Numeric/Decimal 转为 float，None 视为 0.0。"""
    if v is None:
        return 0.0
    if isinstance(v, Decimal):
        return float(v)
    return float(v)


def _scale(row_value, weight_g: float) -> float:
    """per-100g 值按实际克数等比缩放，保留 4 位小数。"""
    return round(_num(row_value) * weight_g / 100.0, 4)


def _build_macro(row: Ingredient, weight_g: float) -> Macronutrients:
    return Macronutrients(
        protein=_scale(row.protein, weight_g),
        fat=_scale(row.fat, weight_g),
        carbohydrates=_scale(row.carbohydrates, weight_g),
        dietary_fiber=_scale(row.dietary_fiber, weight_g),
    )


def _build_micro(row: Ingredient, weight_g: float) -> Micronutrients:
    fixed: dict[str, NutrientAmount] = {}
    for field, (col, unit) in MICRO_FIELD_TO_COLUMN.items():
        raw = getattr(row, col, None)
        fixed[field] = NutrientAmount(value=_scale(raw, weight_g), unit=unit)

    additional: dict[str, NutrientAmount] = {}
    for label, (col, unit) in ADDITIONAL_FIELD_MAP.items():
        raw = getattr(row, col, None)
        if raw is None:
            continue
        scaled = _scale(raw, weight_g)
        if scaled <= 0:
            continue
        additional[label] = NutrientAmount(value=scaled, unit=unit)

    return Micronutrients(**fixed, additional_nutrients=additional)


def _build_food_item(allocation: IngredientAllocation, row: Ingredient) -> FoodItem:
    return FoodItem(
        name=row.name,
        weight=allocation.weight_g,
        macro_nutrients=_build_macro(row, allocation.weight_g),
        micro_nutrients=_build_micro(row, allocation.weight_g),
        recommend_reason=allocation.recommend_reason or "",
    )


def _build_meal(meal: MealLight, rows_by_name: dict[str, Ingredient]) -> SingleMealPlan:
    food_items: list[FoodItem] = []
    for alloc in meal.ingredients:
        row = rows_by_name.get(alloc.ingredient_name)
        if row is None:
            logger.warning(
                "assemble: 食材 %r 未命中数据库，已跳过 (meal oder=%s)",
                alloc.ingredient_name,
                meal.oder,
            )
            continue
        food_items.append(_build_food_item(alloc, row))
    return SingleMealPlan(
        oder=meal.oder,
        time=meal.time,
        food_items=food_items,
        cook_method=meal.cook_method,
    )


# ──────────────────────────── DB 查询 ────────────────────────────

async def fetch_ingredients_by_names(names: Iterable[str]) -> dict[str, Ingredient]:
    """批量按 name 精确查询 Ingredient；对未命中的做 ILIKE 模糊匹配兜底。

    返回: { requested_name: Ingredient_row }
    未能命中的 name 不出现在返回字典中。
    """
    wanted = [n for n in {n.strip() for n in names if n and n.strip()}]
    if not wanted:
        return {}

    # 1) 精确匹配
    stmt = select(Ingredient).where(Ingredient.name.in_(wanted))
    exact_rows: list[Ingredient] = await run_query(stmt)
    by_exact = {r.name: r for r in exact_rows}

    result: dict[str, Ingredient] = {n: by_exact[n] for n in wanted if n in by_exact}

    # 2) 对剩余未命中的名称做模糊匹配
    missing = [n for n in wanted if n not in result]
    for name in missing:
        fuzzy_stmt = (
            select(Ingredient)
            .where(Ingredient.name.ilike(f"%{name}%"))
            .limit(1)
        )
        row: Optional[Ingredient] = await run_query(fuzzy_stmt, one=True)
        if row is not None:
            logger.warning(
                "assemble: 食材 %r 未精确命中，已回退为模糊匹配结果 %r",
                name, row.name,
            )
            result[name] = row
        else:
            logger.warning("assemble: 食材 %r 未命中 (精确+模糊均失败)", name)

    return result


# ──────────────────────────── 主入口 ────────────────────────────

def assemble_weekly_plan(
    light: WeekLightPlan,
    rows_by_name: dict[str, Ingredient],
) -> WeeklyDietPlan:
    """根据轻量周计划 + 食材行字典，组装完整的 WeeklyDietPlan。

    周内 7 天统一食谱：一个 DailyDietPlan 即代表本周每日菜单。
    """
    meals: list[SingleMealPlan] = [
        _build_meal(m, rows_by_name) for m in light.meals
    ]
    daily = DailyDietPlan(daily_diet_plans=meals)

    return WeeklyDietPlan(
        oder=light.week_number,
        diet_adjustment_principle=light.diet_adjustment_principle,
        weekly_diet_plan=daily,
        weekly_special_adjustment_note=light.weekly_special_adjustment_note or "",
        suggestions=list(light.suggestions or []),
    )


def collect_ingredient_names(plans: Iterable[WeekLightPlan]) -> list[str]:
    """收集所有 WeekLightPlan 中提到的全部食材名，用于一次性批量查询。"""
    names: set[str] = set()
    for p in plans:
        for meal in p.meals:
            for alloc in meal.ingredients:
                if alloc.ingredient_name:
                    names.add(alloc.ingredient_name.strip())
    return sorted(names)
