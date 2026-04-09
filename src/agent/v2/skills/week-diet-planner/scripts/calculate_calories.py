#!/usr/bin/env python3
"""
宠物热量计算模块

使用 RER (Resting Energy Requirement) 公式计算宠物每日热量需求。
参考：AAHA (American Animal Hospital Association) 营养指南
"""
from dataclasses import dataclass
from typing import Literal


@dataclass
class CalorieResult:
    """热量计算结果"""
    rer: float           # 静止能量需求 (RER)
    daily_calories: float  # 每日总热量需求 (kcal)
    protein_g: float     # 建议蛋白质摄入量 (g)
    fat_g: float         # 建议脂肪摄入量 (g)
    carb_g: float        # 建议碳水化合物摄入量 (g)


class CalorieCalculator:
    """热量计算器"""

    # 活动系数 (基于 AAHA 指南)
    ACTIVITY_FACTORS = {
        "puppy": {           # 幼犬 (1岁以下)
            "low": 3.0,      # 低活动
            "moderate": 3.5, # 中等活动
            "high": 4.0      # 高活动
        },
        "adult": {           # 成犬 (1-7岁)
            "low": 1.6,      # 久坐/绝育
            "moderate": 2.0, # 正常活动
            "high": 3.0      # 高活动/工作犬
        },
        "senior": {          # 老年犬 (7岁+)
            "low": 1.2,
            "moderate": 1.4,
            "high": 1.8
        },
        "kitten": {          # 幼猫 (1岁以下)
            "low": 2.5,
            "moderate": 3.0,
            "high": 3.5
        },
        "cat_adult": {       # 成猫 (1-7岁)
            "low": 1.2,      # 室内绝育
            "moderate": 1.4, # 室内未绝育
            "high": 1.6      # 室外/活动
        },
        "cat_senior": {      # 老年猫 (7岁+)
            "low": 1.0,
            "moderate": 1.2,
            "high": 1.4
        }
    }

    # 营养素占比 (基于干物质基础)
    NUTRIENT_RATIOS = {
        "dog": {
            "protein_min": 0.18,  # AAFCO 最低标准
            "protein_opt": 0.25,
            "protein_max": 0.35,
            "fat_min": 0.05,
            "fat_opt": 0.15,
            "fat_max": 0.25,
            "carb_opt": 0.50
        },
        "cat": {
            "protein_min": 0.26,  # AAFCO 最低标准
            "protein_opt": 0.35,
            "protein_max": 0.45,
            "fat_min": 0.09,
            "fat_opt": 0.20,
            "fat_max": 0.30,
            "carb_opt": 0.30  # 猫是纯肉食动物，碳水需求更低
        }
    }

    @classmethod
    def calculate_rer(cls, weight_kg: float) -> float:
        """
        计算静止能量需求 (RER)

        公式: RER = 70 × (体重kg)^0.75

        Args:
            weight_kg: 宠物体重（公斤）

        Returns:
            RER 值 (kcal/day)
        """
        return 70 * (weight_kg ** 0.75)

    @classmethod
    def get_life_stage(cls, pet_type: Literal["cat", "dog"], age_months: int) -> str:
        """
        根据年龄确定生命阶段

        Args:
            pet_type: "cat" | "dog"
            age_months: 年龄（月）

        Returns:
            生命阶段标识
        """
        if pet_type == "cat":
            if age_months < 12:
                return "kitten"
            elif age_months >= 84:
                return "cat_senior"
            else:
                return "cat_adult"
        else:  # dog
            if age_months < 12:
                return "puppy"
            elif age_months >= 84:
                return "senior"
            else:
                return "adult"

    @classmethod
    def calculate(
        cls,
        pet_type: Literal["cat", "dog"],
        weight_kg: float,
        age_months: int,
        activity_level: Literal["low", "moderate", "high"] = "moderate",
        health_status: str = "健康"
    ) -> CalorieResult:
        """
        计算每日热量需求和营养素建议

        Args:
            pet_type: 宠物类型 "cat" | "dog"
            weight_kg: 体重（公斤）
            age_months: 年龄（月）
            activity_level: 活动水平 "low" | "moderate" | "high"
            health_status: 健康状况（影响系数调整）

        Returns:
            CalorieResult 计算结果
        """
        # 1. 计算 RER
        rer = cls.calculate_rer(weight_kg)

        # 2. 确定生命阶段
        life_stage = cls.get_life_stage(pet_type, age_months)

        # 3. 获取活动系数
        factor_key = life_stage
        factor = cls.ACTIVITY_FACTORS[factor_key][activity_level]

        # 4. 根据健康状况调整
        if health_status:
            status_lower = health_status.lower()
            if "肥胖" in status_lower or "减重" in status_lower:
                factor *= 0.8  # 减重需要减少热量
            elif "怀孕" in status_lower or "哺乳" in status_lower:
                factor *= 2.0  # 妊娠/哺乳需要增加热量
            elif "恢复" in status_lower or "术后" in status_lower:
                factor *= 1.5  # 恢复期需要增加热量

        # 5. 计算每日总热量
        daily_calories = rer * factor

        # 6. 计算营养素建议量
        ratios = cls.NUTRIENT_RATIOS[pet_type]
        protein_ratio = ratios["protein_opt"]
        fat_ratio = ratios["fat_opt"]
        carb_ratio = ratios["carb_opt"]

        # 蛋白质: 4 kcal/g
        protein_g = (daily_calories * protein_ratio) / 4

        # 脂肪: 9 kcal/g
        fat_g = (daily_calories * fat_ratio) / 9

        # 碳水化合物: 4 kcal/g
        carb_g = (daily_calories * carb_ratio) / 4

        return CalorieResult(
            rer=rer,
            daily_calories=daily_calories,
            protein_g=round(protein_g, 1),
            fat_g=round(fat_g, 1),
            carb_g=round(carb_g, 1)
        )


# 便捷函数
def calculate_daily_needs(
    pet_type: Literal["cat", "dog"],
    weight_kg: float,
    age_months: int,
    activity_level: str = "moderate",
    health_status: str = "健康"
) -> dict:
    """
    快捷计算每日营养需求

    Returns:
        dict: {
            "daily_calories": float,
            "protein_g": float,
            "fat_g": float,
            "carb_g": float,
            "rer": float
        }
    """
    result = CalorieCalculator.calculate(
        pet_type=pet_type,
        weight_kg=weight_kg,
        age_months=age_months,
        activity_level=activity_level,
        health_status=health_status
    )
    return {
        "daily_calories": result.daily_calories,
        "protein_g": result.protein_g,
        "fat_g": result.fat_g,
        "carb_g": result.carb_g,
        "rer": result.rer
    }


if __name__ == "__main__":
    # 测试用例
    print("=== 宠物热量计算器测试 ===\n")

    # 成犬示例
    result = calculate_daily_needs(
        pet_type="dog",
        weight_kg=15.0,
        age_months=24,
        activity_level="moderate"
    )
    print(f"15kg 成犬 (中等活动):")
    print(f"  每日热量: {result['daily_calories']:.0f} kcal")
    print(f"  蛋白质: {result['protein_g']:.1f} g")
    print(f"  脂肪: {result['fat_g']:.1f} g")
    print(f"  碳水: {result['carb_g']:.1f} g")
    print()

    # 幼犬示例
    result = calculate_daily_needs(
        pet_type="dog",
        weight_kg=5.0,
        age_months=4,
        activity_level="moderate"
    )
    print(f"5kg 幼犬 (4月龄):")
    print(f"  每日热量: {result['daily_calories']:.0f} kcal")
    print()

    # 成猫示例
    result = calculate_daily_needs(
        pet_type="cat",
        weight_kg=4.0,
        age_months=24,
        activity_level="low"
    )
    print(f"4kg 成猫 (室内绝育):")
    print(f"  每日热量: {result['daily_calories']:.0f} kcal")
    print(f"  蛋白质: {result['protein_g']:.1f} g")
    print(f"  脂肪: {result['fat_g']:.1f} g")
