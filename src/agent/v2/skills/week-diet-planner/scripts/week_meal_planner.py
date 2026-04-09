#!/usr/bin/env python3
"""
Week Meal Planner - 周饮食计划生成器主入口

整合所有模块，提供统一的 API 供 week_agent 使用。
"""
from typing import List, Literal, Dict, Any, Optional
from dataclasses import dataclass

from calculate_calories import CalorieCalculator, CalorieResult
from query_ingredients import IngredientQuerier, IngredientInfo
from build_meal_plan import (
    MealPlanBuilder, WeeklyDietPlan, DailyDietPlan,
    SingleMealPlan, FoodItem
)


@dataclass
class PetInfo:
    """宠物信息"""
    pet_type: Literal["cat", "dog"]
    weight_kg: float
    age_months: int
    breed: str = ""
    health_status: str = "健康"
    activity_level: Literal["low", "moderate", "high"] = "moderate"


@dataclass
class WeekAssignmentInput:
    """周任务分配输入（对应 CoordinationGuide 中的 WeekAssignment）"""
    week_number: int
    theme: str
    focus_nutrients: List[str]
    constraints: List[str]
    differentiation_note: str = ""
    search_keywords: List[str] = None


class WeekMealPlanner:
    """
    周饮食计划生成器

    用法:
        planner = WeekMealPlanner(
            pet_type="dog",
            weight_kg=15.0,
            age_months=24
        )

        result = planner.generate_week_plan(
            week_number=1,
            theme="高蛋白恢复期",
            focus_nutrients=["protein"],
            constraints=["避免鸡肉"]
        )
    """

    def __init__(
        self,
        pet_type: Literal["cat", "dog"],
        weight_kg: float,
        age_months: int,
        breed: str = "",
        health_status: str = "健康",
        activity_level: Literal["low", "moderate", "high"] = "moderate",
        ingredients_data: Optional[List[dict]] = None
    ):
        """
        初始化计划器

        Args:
            pet_type: 宠物类型 "cat" | "dog"
            weight_kg: 体重（公斤）
            age_months: 年龄（月）
            breed: 品种
            health_status: 健康状况
            activity_level: 活动水平
            ingredients_data: 食材数据（从数据库加载），如果为 None 使用示例数据
        """
        self.pet_info = PetInfo(
            pet_type=pet_type,
            weight_kg=weight_kg,
            age_months=age_months,
            breed=breed,
            health_status=health_status,
            activity_level=activity_level
        )

        # 计算热量需求
        self.calorie_result = CalorieCalculator.calculate(
            pet_type=pet_type,
            weight_kg=weight_kg,
            age_months=age_months,
            activity_level=activity_level,
            health_status=health_status
        )

        # 初始化食材查询器
        if ingredients_data is None:
            # 使用示例数据
            from query_ingredients import SAMPLE_INGREDIENTS
            ingredients_data = SAMPLE_INGREDIENTS

        self.querier = IngredientQuerier(ingredients_data)

        # 初始化构建器
        self.builder = MealPlanBuilder(
            querier=self.querier,
            calorie_result=self.calorie_result,
            pet_type=pet_type
        )

    def load_ingredients_from_db(self, db_session) -> None:
        """
        从数据库加载食材数据

        Args:
            db_session: SQLAlchemy 异步会话
        """
        # 这里需要实现从数据库查询
        # 示例代码（需要根据实际数据库调整）:
        # from src.db.models import Ingredient
        # result = await db_session.execute(select(Ingredient))
        # ingredients = [self.querier.load_from_db_row(row) for row in result.scalars()]
        # self.querier = IngredientQuerier(ingredients)
        pass

    def generate_week_plan(
        self,
        week_number: int,
        theme: str,
        focus_nutrients: List[str],
        constraints: List[str],
        ingredient_categories: Optional[List[str]] = None,
        suggestions: Optional[List[str]] = None,
        differentiation_note: str = ""
    ) -> WeeklyDietPlan:
        """
        生成周饮食计划

        Args:
            week_number: 第几周 (1-4)
            theme: 本周主题
            focus_nutrients: 重点营养素列表
            constraints: 饮食约束
            ingredient_categories: 食材类别筛选，默认使用主要类别
            suggestions: 额外建议
            differentiation_note: 差异化说明

        Returns:
            WeeklyDietPlan 结构化周计划
        """
        # 默认食材类别
        if ingredient_categories is None:
            ingredient_categories = ["白肉", "红肉", "内脏", "蔬菜"]

        # 查询可用食材
        available_ingredients = self.querier.search(
            categories=ingredient_categories
        )

        # 生成周计划
        weekly_plan = self.builder.build_weekly_plan(
            week_number=week_number,
            theme=theme,
            focus_nutrients=focus_nutrients,
            constraints=constraints,
            available_ingredients=available_ingredients,
            suggestions=suggestions
        )

        # 添加差异化说明
        if differentiation_note:
            weekly_plan.weekly_special_adjustment_note += f" {differentiation_note}"

        return weekly_plan

    def generate_from_assignment(
        self,
        assignment: WeekAssignmentInput,
        ingredient_categories: Optional[List[str]] = None
    ) -> WeeklyDietPlan:
        """
        从 WeekAssignment 生成周计划

        Args:
            assignment: 周任务分配对象
            ingredient_categories: 食材类别

        Returns:
            WeeklyDietPlan 结构化周计划
        """
        return self.generate_week_plan(
            week_number=assignment.week_number,
            theme=assignment.theme,
            focus_nutrients=assignment.focus_nutrients,
            constraints=assignment.constraints,
            ingredient_categories=ingredient_categories,
            differentiation_note=assignment.differentiation_note
        )

    def get_nutrition_summary(self) -> Dict[str, Any]:
        """
        获取宠物营养需求摘要

        Returns:
            营养需求摘要字典
        """
        return {
            "daily_calories": self.calorie_result.daily_calories,
            "rer": self.calorie_result.rer,
            "protein_target_g": self.calorie_result.protein_g,
            "fat_target_g": self.calorie_result.fat_g,
            "carb_target_g": self.calorie_result.carb_g,
            "pet_info": {
                "type": self.pet_info.pet_type,
                "weight_kg": self.pet_info.weight_kg,
                "age_months": self.pet_info.age_months,
                "life_stage": CalorieCalculator.get_life_stage(
                    self.pet_info.pet_type,
                    self.pet_info.age_months
                )
            }
        }


# 便捷函数：从 CoordinationGuide 格式生成
def generate_from_coordination_guide(
    pet_info: Dict[str, Any],
    week_assignment: Dict[str, Any],
    ingredients_data: List[dict]
) -> Dict[str, Any]:
    """
    从 CoordinationGuide 格式生成周计划

    Args:
        pet_info: 宠物信息字典
            {
                "pet_type": "dog" | "cat",
                "weight_kg": float,
                "age_months": int,
                "breed": str (optional),
                "health_status": str (optional),
                "activity_level": str (optional)
            }
        week_assignment: 周分配字典
            {
                "week_number": int,
                "theme": str,
                "focus_nutrients": list[str],
                "constraints": list[str],
                "differentiation_note": str,
                "search_keywords": list[str]
            }
        ingredients_data: 食材数据列表

    Returns:
        dict: 可序列化的周计划
    """
    planner = WeekMealPlanner(
        pet_type=pet_info.get("pet_type", "dog"),
        weight_kg=pet_info["weight_kg"],
        age_months=pet_info["age_months"],
        breed=pet_info.get("breed", ""),
        health_status=pet_info.get("health_status", "健康"),
        activity_level=pet_info.get("activity_level", "moderate"),
        ingredients_data=ingredients_data
    )

    result = planner.generate_week_plan(
        week_number=week_assignment["week_number"],
        theme=week_assignment["theme"],
        focus_nutrients=week_assignment["focus_nutrients"],
        constraints=week_assignment["constraints"],
        differentiation_note=week_assignment.get("differentiation_note", "")
    )

    return result.to_dict()


if __name__ == "__main__":
    # 完整测试
    from query_ingredients import SAMPLE_INGREDIENTS

    print("=== Week Meal Planner 完整测试 ===\n")

    # 模拟 CoordinationGuide 输入
    pet_info = {
        "pet_type": "dog",
        "weight_kg": 15.0,
        "age_months": 24,
        "breed": "拉布拉多",
        "health_status": "健康",
        "activity_level": "moderate"
    }

    week_assignment = {
        "week_number": 1,
        "theme": "高蛋白恢复期",
        "focus_nutrients": ["protein", "taurine"],
        "constraints": ["避免鸡肉", "低脂"],
        "differentiation_note": "第一周以易消化食材为主",
        "search_keywords": ["牛肉", "鱼肉", "羊肉"]
    }

    result = generate_from_coordination_guide(
        pet_info=pet_info,
        week_assignment=week_assignment,
        ingredients_data=SAMPLE_INGREDIENTS
    )

    print(f"=== 第{result['oder']}周饮食计划 ===")
    print(f"原则: {result['diet_adjustment_principle']}")
    print(f"\n每日营养:")
    summary = result['daily_nutrition_summary']
    print(f"  热量: {summary['total_calories']:.0f} kcal")
    print(f"  蛋白质: {summary['protein']:.1f} g")
    print(f"  脂肪: {summary['fat']:.1f} g")
    print(f"  碳水: {summary['carbohydrates']:.1f} g")

    print(f"\n餐食明细:")
    for meal in result['weekly_diet_plan']['daily_diet_plans']:
        print(f"\n  第{meal['oder']}餐 ({meal['time']}):")
        for item in meal['food_items']:
            macro = item['macro_nutrients']
            print(f"    - {item['name']} {item['weight']}g "
                  f"(热量: {macro['calories']:.0f}kcal, "
                  f"蛋白质: {macro['protein']:.1f}g)")

    print(f"\n建议:")
    for s in result['suggestions']:
        print(f"  - {s}")
