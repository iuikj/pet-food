"""
宠物营养计算工具

基于 AAHA 指南的 RER 公式计算每日热量需求，
基于 AAFCO/NRC 标准计算微量营养素目标。
纯计算逻辑，无外部依赖。
"""
from typing import Annotated, Literal

from langchain.tools import tool

# ──────────────────────────── 常量表 ────────────────────────────

# 生命阶段活动系数 (MER = RER × factor)
# 来源: AAHA Nutritional Assessment Guidelines
ACTIVITY_FACTORS: dict[str, dict[str, float]] = {
    # 犬
    "puppy":      {"low": 2.5, "moderate": 3.0, "high": 3.5},
    "adult":      {"low": 1.4, "moderate": 1.8, "high": 2.5},
    "senior":     {"low": 1.2, "moderate": 1.4, "high": 1.6},
    # 猫
    "kitten":     {"low": 2.0, "moderate": 2.5, "high": 3.0},
    "cat_adult":  {"low": 1.0, "moderate": 1.2, "high": 1.4},
    "cat_senior": {"low": 0.8, "moderate": 1.0, "high": 1.2},
}

# 宏量营养素占热量比例 (AAFCO 最低标准 + 推荐范围)
# protein/carb: 1g = 4 kcal, fat: 1g = 9 kcal
NUTRIENT_RATIOS: dict[str, dict[str, float]] = {
    "dog": {
        "protein_min": 0.18, "protein_opt": 0.25, "protein_max": 0.35,
        "fat_min": 0.05,     "fat_opt": 0.15,     "fat_max": 0.25,
        "carb_opt": 0.50,
    },
    "cat": {
        "protein_min": 0.26, "protein_opt": 0.35, "protein_max": 0.45,
        "fat_min": 0.09,     "fat_opt": 0.20,     "fat_max": 0.30,
        "carb_opt": 0.25,
    },
}

# AAFCO 每日最低微量营养素需求 (per 1000 kcal ME)
MICRONUTRIENT_REQUIREMENTS: dict[str, dict[str, float]] = {
    "dog": {
        "calcium_mg": 1250,
        "phosphorus_mg": 1000,
        "iron_mg": 10,
        "zinc_mg": 20,
        "copper_mg": 1.83,
        "manganese_mg": 1.25,
        "selenium_ug": 87.5,
        "iodine_ug": 250,
        "potassium_mg": 1500,
        "sodium_mg": 200,
        "magnesium_mg": 150,
        "vitamin_a_iu": 1250,
        "vitamin_d_iu": 125,
        "vitamin_e_mg": 12.5,
        "vitamin_b1_mg": 0.56,
    },
    "cat": {
        "calcium_mg": 1500,
        "phosphorus_mg": 1250,
        "iron_mg": 20,
        "zinc_mg": 18.5,
        "copper_mg": 1.25,
        "manganese_mg": 1.88,
        "selenium_ug": 75,
        "iodine_ug": 87.5,
        "potassium_mg": 1500,
        "sodium_mg": 170,
        "magnesium_mg": 100,
        "vitamin_a_iu": 833,
        "vitamin_d_iu": 70,
        "vitamin_e_mg": 10,
        "vitamin_b1_mg": 1.4,
        "taurine_mg": 62.5,  # 猫必需氨基酸
    },
}


# ──────────────────────────── 内部函数 ────────────────────────────

def _get_life_stage(pet_type: str, age_months: int) -> str:
    """根据宠物类型和月龄确定生命阶段。"""
    if pet_type == "cat":
        if age_months < 12:
            return "kitten"
        elif age_months >= 84:
            return "cat_senior"
        return "cat_adult"
    # dog
    if age_months < 12:
        return "puppy"
    elif age_months >= 84:
        return "senior"
    return "adult"


def _apply_health_modifier(factor: float, health_status: str) -> float:
    """根据健康状况调整活动系数。"""
    if not health_status:
        return factor
    s = health_status.lower()
    if any(k in s for k in ("肥胖", "减重", "超重")):
        return factor * 0.8
    if any(k in s for k in ("怀孕", "妊娠")):
        return factor * 1.5
    if any(k in s for k in ("哺乳", "泌乳")):
        return factor * 2.0
    if any(k in s for k in ("恢复", "术后", "康复")):
        return factor * 1.3
    return factor


# ──────────────────────────── 工具定义 ────────────────────────────

@tool
async def daily_calorie_tool(
    pet_type: Annotated[Literal["cat", "dog"], "宠物类型"],
    weight_kg: Annotated[float, "宠物体重(千克)"],
    age_months: Annotated[int, "宠物年龄(月龄)"],
    activity_level: Annotated[Literal["low", "moderate", "high"], "活动水平"] = "moderate",
    health_status: Annotated[str, "健康状况描述"] = "",
) -> dict:
    """计算宠物每日热量需求和宏量营养素目标。

    基于 AAHA 指南 RER 公式: RER = 70 × (体重kg)^0.75,
    再乘以生命阶段×活动水平系数得到 DER (每日能量需求)。
    同时返回蛋白质、脂肪、碳水的推荐克数和允许范围。
    """
    rer = 70 * (weight_kg ** 0.75)
    life_stage = _get_life_stage(pet_type, age_months)
    factor = ACTIVITY_FACTORS[life_stage].get(activity_level, 1.8)
    factor = _apply_health_modifier(factor, health_status)
    daily_calories = round(rer * factor, 1)

    ratios = NUTRIENT_RATIOS.get(pet_type, NUTRIENT_RATIOS["dog"])
    # protein/carb: 1g=4kcal, fat: 1g=9kcal
    protein_g = round((daily_calories * ratios["protein_opt"]) / 4, 1)
    fat_g = round((daily_calories * ratios["fat_opt"]) / 9, 1)
    carb_g = round((daily_calories * ratios["carb_opt"]) / 4, 1)

    return {
        "rer_kcal": round(rer, 1),
        "daily_calories_kcal": daily_calories,
        "life_stage": life_stage,
        "activity_factor": round(factor, 2),
        "protein_g": protein_g,
        "fat_g": fat_g,
        "carb_g": carb_g,
        "protein_range_g": {
            "min": round((daily_calories * ratios["protein_min"]) / 4, 1),
            "max": round((daily_calories * ratios["protein_max"]) / 4, 1),
        },
        "fat_range_g": {
            "min": round((daily_calories * ratios["fat_min"]) / 9, 1),
            "max": round((daily_calories * ratios["fat_max"]) / 9, 1),
        },
        "calculation_basis": (
            f"RER={round(rer, 1)}kcal × 系数{round(factor, 2)} "
            f"(生命阶段:{life_stage}, 活动:{activity_level})"
        ),
    }


@tool
async def nutrition_requirement_tool(
    pet_type: Annotated[Literal["cat", "dog"], "宠物类型"],
    daily_calories: Annotated[float, "每日热量目标(kcal)，来自 daily_calorie_tool"],
) -> dict:
    """获取宠物每日微量营养素最低需求标准(基于 AAFCO 标准)。

    根据每日热量摄入量，按比例缩放各微量营养素最低日摄入量。
    基准数据为 AAFCO 每 1000 kcal ME 的推荐值。
    """
    base = MICRONUTRIENT_REQUIREMENTS.get(pet_type, MICRONUTRIENT_REQUIREMENTS["dog"])
    scale = daily_calories / 1000.0

    result = {}
    for key, per_1000kcal in base.items():
        # 从 "calcium_mg" 拆出 "calcium" 和 "mg"
        parts = key.rsplit("_", 1)
        name = parts[0]
        unit = parts[1] if len(parts) > 1 else ""
        result[name] = {
            "min_daily": round(per_1000kcal * scale, 2),
            "unit": unit,
        }

    # 补充钙磷比说明
    result["calcium_phosphorus_ratio"] = "1.2:1 ~ 1.4:1"
    return result
