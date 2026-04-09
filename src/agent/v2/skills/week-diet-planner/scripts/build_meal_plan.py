#!/usr/bin/env python3
"""
餐食计划构建模块

整合热量计算和食材查询，生成结构化的周饮食计划。
输出格式符合 WeeklyDietPlan Pydantic 模型。
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Literal
from decimal import Decimal

from calculate_calories import CalorieCalculator, CalorieResult
from query_ingredients import IngredientQuerier, IngredientInfo


@dataclass
class FoodItem:
    """食物项（对应 Pydantic 模型中的 FoodItem）"""
    name: str
    weight: float  # 克数
    macro_nutrients: Dict[str, float]
    micro_nutrients: Dict[str, Any]

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "weight": self.weight,
            "macro_nutrients": self.macro_nutrients,
            "micro_nutrients": self.micro_nutrients,
            "recommend_reason": ""
        }


@dataclass
class SingleMealPlan:
    """单餐计划"""
    oder: int  # 第几餐
    time: str
    food_items: List[FoodItem]
    cook_method: str = ""
    description: str = ""
    recommend_reason: str = ""

    def get_total_nutrition(self) -> Dict[str, float]:
        """计算本餐总营养"""
        total = {
            "calories": 0,
            "protein": 0,
            "fat": 0,
            "carbohydrates": 0,
            "dietary_fiber": 0,
        }
        micro_nutrients = {}

        for item in self.food_items:
            # 宏量营养素累加
            total["calories"] += item.macro_nutrients.get("calories", 0) * (item.weight / 100)
            total["protein"] += item.macro_nutrients.get("protein", 0) * (item.weight / 100)
            total["fat"] += item.macro_nutrients.get("fat", 0) * (item.weight / 100)
            total["carbohydrates"] += item.macro_nutrients.get("carbohydrates", 0) * (item.weight / 100)
            total["dietary_fiber"] += item.macro_nutrients.get("dietary_fiber", 0) * (item.weight / 100)

            # 微量营养素累加
            for nutrient, value in item.micro_nutrients.items():
                if isinstance(value, (int, float)):
                    micro_nutrients[nutrient] = micro_nutrients.get(nutrient, 0) + value * (item.weight / 100)

        total["micro_nutrients"] = micro_nutrients
        return total

    def to_dict(self) -> dict:
        nutrition = self.get_total_nutrition()
        micro = nutrition.pop("micro_nutrients", {})

        return {
            "oder": self.oder,
            "time": self.time,
            "food_items": [item.to_dict() for item in self.food_items],
            "cook_method": self.cook_method,
            "description": self.description,
            "recommend_reason": self.recommend_reason,
            # 营养摘要
            "nutrition_summary": {
                "calories": round(nutrition["calories"], 1),
                "protein": round(nutrition["protein"], 1),
                "fat": round(nutrition["fat"], 1),
                "carbohydrates": round(nutrition["carbohydrates"], 1),
                "micro_nutrients": {k: round(v, 2) for k, v in micro.items()}
            }
        }


@dataclass
class DailyDietPlan:
    """每日饮食计划（一周内统一执行）"""
    daily_diet_plans: List[SingleMealPlan]

    def to_dict(self) -> dict:
        return {
            "daily_diet_plans": [meal.to_dict() for meal in self.daily_diet_plans]
        }

    def get_daily_totals(self) -> Dict[str, float]:
        """计算全天营养总量"""
        totals = {
            "calories": 0,
            "protein": 0,
            "fat": 0,
            "carbohydrates": 0,
            "dietary_fiber": 0,
        }

        for meal in self.daily_diet_plans:
            nutrition = meal.get_total_nutrition()
            totals["calories"] += nutrition["calories"]
            totals["protein"] += nutrition["protein"]
            totals["fat"] += nutrition["fat"]
            totals["carbohydrates"] += nutrition["carbohydrates"]
            totals["dietary_fiber"] += nutrition["dietary_fiber"]

        return totals


@dataclass
class WeeklyDietPlan:
    """周饮食计划（符合 Agent 的 Pydantic 模型结构）"""
    oder: int  # 第几周
    diet_adjustment_principle: str
    weekly_diet_plan: DailyDietPlan
    weekly_special_adjustment_note: str = ""
    suggestions: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        daily_totals = self.weekly_diet_plan.get_daily_totals()

        return {
            "oder": self.oder,
            "diet_adjustment_principle": self.diet_adjustment_principle,
            "weekly_diet_plan": self.weekly_diet_plan.to_dict(),
            "weekly_special_adjustment_note": self.weekly_special_adjustment_note,
            "suggestions": self.suggestions,
            # 营养摘要
            "daily_nutrition_summary": {
                "total_calories": round(daily_totals["calories"], 1),
                "protein": round(daily_totals["protein"], 1),
                "fat": round(daily_totals["fat"], 1),
                "carbohydrates": round(daily_totals["carbohydrates"], 1),
                "dietary_fiber": round(daily_totals["dietary_fiber"], 1),
            }
        }


class MealPlanBuilder:
    """餐食计划构建器"""

    # 各餐热量分配比例
    MEAL_RATIOS = {
        "breakfast": 0.25,   # 早餐 25%
        "lunch": 0.35,       # 午餐 35%
        "dinner": 0.30,      # 晚餐 30%
        "snack": 0.10,       # 加餐 10%
    }

    MEAL_TIMES = {
        "breakfast": "08:00",
        "lunch": "12:00",
        "dinner": "18:00",
        "snack": "15:00",
    }

    # 营养素占比目标
    NUTRIENT_RATIOS = {
        "dog": {"protein": 0.25, "fat": 0.15, "carb": 0.50},
        "cat": {"protein": 0.35, "fat": 0.20, "carb": 0.30},
    }

    def __init__(
        self,
        querier: IngredientQuerier,
        calorie_result: CalorieResult,
        pet_type: Literal["dog", "cat"]
    ):
        """
        初始化构建器

        Args:
            querier: 食材查询器
            calorie_result: 热量计算结果
            pet_type: 宠物类型
        """
        self.querier = querier
        self.calorie_result = calorie_result
        self.pet_type = pet_type
        self.target_ratios = self.NUTRIENT_RATIOS[pet_type]

    def _select_ingredients_for_meal(
        self,
        target_calories: float,
        available_ingredients: List[IngredientInfo],
        constraints: List[str] = None
    ) -> List[FoodItem]:
        """
        为单餐选择食材组合

        Args:
            target_calories: 目标热量
            available_ingredients: 可用食材池
            constraints: 约束条件（如过敏食材）

        Returns:
            食材列表
        """
        constraints = constraints or []
        exclude_names = []
        for c in constraints:
            if "避免" in c or "过敏" in c or "不吃" in c:
                # 提取避免的食材名称
                for ing in available_ingredients:
                    if ing.name in c:
                        exclude_names.append(ing.name)

        # 过滤掉排除的食材
        pool = [ing for ing in available_ingredients if ing.name not in exclude_names]

        if not pool:
            pool = available_ingredients  # 如果过滤后为空，使用全部

        # 按类别分组
        by_category = {}
        for ing in pool:
            if ing.category not in by_category:
                by_category[ing.category] = []
            by_category[ing.category].append(ing)

        selected = []
        remaining_calories = target_calories

        # 优先选择高蛋白食材（肉类）
        protein_sources = [ing for ing in pool if ing.protein and ing.protein > 15]
        if protein_sources:
            main_protein = protein_sources[0]
            # 计算需要的重量（热量）
            if main_protein.calories:
                weight = (target_calories * 0.6) / main_protein.calories * 100  # 60% 热量来自蛋白质
                selected.append(self._create_food_item(main_protein, weight))
                remaining_calories -= target_calories * 0.6

        # 添加蔬菜/纤维源
        fiber_sources = [ing for ing in pool if ing.dietary_fiber and ing.dietary_fiber > 2]
        if fiber_sources:
            fiber = fiber_sources[0]
            weight = 50  # 固定 50g 蔬菜
            selected.append(self._create_food_item(fiber, weight))
            if fiber.calories:
                remaining_calories -= fiber.calories * weight / 100

        # 添加碳水源（如果需要）
        if remaining_calories > 50:
            carb_sources = [ing for ing in pool if ing.carbohydrates and ing.carbohydrates > 10]
            if carb_sources:
                carb = carb_sources[0]
                if carb.calories:
                    weight = remaining_calories / carb.calories * 100
                    selected.append(self._create_food_item(carb, weight))

        return selected

    def _create_food_item(self, ingredient: IngredientInfo, weight: float) -> FoodItem:
        """创建食物项"""
        # 计算该重量下的营养含量
        factor = weight / 100  # 营养数据通常是每100g

        macro = {
            "calories": (ingredient.calories or 0) * factor,
            "protein": (ingredient.protein or 0) * factor,
            "fat": (ingredient.fat or 0) * factor,
            "carbohydrates": (ingredient.carbohydrates or 0) * factor,
            "dietary_fiber": (ingredient.dietary_fiber or 0) * factor,
        }

        micro = {}
        if ingredient.calcium:
            micro["calcium"] = {"value": ingredient.calcium * factor, "unit": "mg"}
        if ingredient.phosphorus:
            micro["phosphorus"] = {"value": ingredient.phosphorus * factor, "unit": "mg"}
        if ingredient.iron:
            micro["iron"] = {"value": ingredient.iron * factor, "unit": "mg"}
        if ingredient.zinc:
            micro["zinc"] = {"value": ingredient.zinc * factor, "unit": "mg"}
        if ingredient.vitamin_a:
            micro["vitamin_a"] = {"value": ingredient.vitamin_a * factor, "unit": "IU"}
        if ingredient.vitamin_d:
            micro["vitamin_d"] = {"value": ingredient.vitamin_d * factor, "unit": "IU"}
        if ingredient.vitamin_e:
            micro["vitamin_e"] = {"value": ingredient.vitamin_e * factor, "unit": "mg"}
        if ingredient.taurine:
            micro["taurine"] = {"value": ingredient.taurine * factor, "unit": "mg"}

        return FoodItem(
            name=ingredient.name,
            weight=round(weight, 1),
            macro_nutrients=macro,
            micro_nutrients=micro
        )

    def build_single_meal(
        self,
        meal_type: Literal["breakfast", "lunch", "dinner", "snack"],
        available_ingredients: List[IngredientInfo],
        constraints: List[str] = None
    ) -> SingleMealPlan:
        """
        构建单餐计划

        Args:
            meal_type: 餐型
            available_ingredients: 可用食材
            constraints: 约束条件

        Returns:
            单餐计划
        """
        ratio = self.MEAL_RATIOS[meal_type]
        target_calories = self.calorie_result.daily_calories * ratio

        food_items = self._select_ingredients_for_meal(
            target_calories,
            available_ingredients,
            constraints
        )

        meal_num = {"breakfast": 1, "lunch": 2, "dinner": 3, "snack": 4}[meal_type]

        return SingleMealPlan(
            oder=meal_num,
            time=self.MEAL_TIMES[meal_type],
            food_items=food_items,
            cook_method="蒸熟后切碎",
            description=f"{meal_type} 包含 {len(food_items)} 种食材"
        )

    def build_daily_plan(
        self,
        available_ingredients: List[IngredientInfo],
        constraints: List[str] = None
    ) -> DailyDietPlan:
        """
        构建全天饮食计划

        Args:
            available_ingredients: 可用食材
            constraints: 约束条件

        Returns:
            每日饮食计划
        """
        meals = []

        # 早餐
        meals.append(self.build_single_meal(
            "breakfast", available_ingredients, constraints
        ))

        # 午餐
        meals.append(self.build_single_meal(
            "lunch", available_ingredients, constraints
        ))

        # 晚餐
        meals.append(self.build_single_meal(
            "dinner", available_ingredients, constraints
        ))

        # 加餐（可选）
        if self.calorie_result.daily_calories > 500:  # 只有大热量需求才加餐
            meals.append(self.build_single_meal(
                "snack", available_ingredients, constraints
            ))

        return DailyDietPlan(daily_diet_plans=meals)

    def build_weekly_plan(
        self,
        week_number: int,
        theme: str,
        focus_nutrients: List[str],
        constraints: List[str],
        available_ingredients: List[IngredientInfo],
        suggestions: List[str] = None
    ) -> WeeklyDietPlan:
        """
        构建周饮食计划

        Args:
            week_number: 第几周
            theme: 本周主题
            focus_nutrients: 重点营养素
            constraints: 约束条件
            available_ingredients: 可用食材
            suggestions: 额外建议

        Returns:
            周饮食计划
        """
        # 构建原则描述
        principle = f"本周主题：{theme}。重点营养素：{', '.join(focus_nutrients)}。"
        if constraints:
            principle += f" 饮食约束：{'; '.join(constraints)}。"

        # 构建每日计划
        daily_plan = self.build_daily_plan(available_ingredients, constraints)

        # 生成建议
        auto_suggestions = []
        totals = daily_plan.get_daily_totals()
        protein_ratio = totals["protein"] * 4 / totals["calories"] if totals["calories"] > 0 else 0

        if protein_ratio < 0.2:
            auto_suggestions.append("蛋白质比例偏低，建议额外添加高蛋白零食")
        if totals["fat"] * 9 / totals["calories"] > 0.3:
            auto_suggestions.append("脂肪比例偏高，注意控制体重")

        all_suggestions = (suggestions or []) + auto_suggestions

        return WeeklyDietPlan(
            oder=week_number,
            diet_adjustment_principle=principle,
            weekly_diet_plan=daily_plan,
            weekly_special_adjustment_note=f"第{week_number}周饮食计划，统一执行7天",
            suggestions=all_suggestions
        )


# 便捷函数
def generate_week_plan(
    pet_type: Literal["cat", "dog"],
    weight_kg: float,
    age_months: int,
    activity_level: str,
    week_number: int,
    theme: str,
    focus_nutrients: List[str],
    constraints: List[str],
    ingredients_data: List[dict],
    health_status: str = "健康",
    suggestions: List[str] = None
) -> dict:
    """
    快速生成周饮食计划

    Returns:
        dict: 可序列化为 JSON 的周计划数据
    """
    # 1. 计算热量需求
    calorie_result = CalorieCalculator.calculate(
        pet_type=pet_type,
        weight_kg=weight_kg,
        age_months=age_months,
        activity_level=activity_level,
        health_status=health_status
    )

    # 2. 初始化查询器
    querier = IngredientQuerier(ingredients_data)

    # 3. 构建计划
    builder = MealPlanBuilder(querier, calorie_result, pet_type)

    # 4. 生成周计划
    weekly_plan = builder.build_weekly_plan(
        week_number=week_number,
        theme=theme,
        focus_nutrients=focus_nutrients,
        constraints=constraints,
        available_ingredients=querier.search(
            categories=["白肉", "红肉", "内脏", "蔬菜"]
        ),
        suggestions=suggestions
    )

    return weekly_plan.to_dict()


if __name__ == "__main__":
    # 测试用例
    from query_ingredients import SAMPLE_INGREDIENTS

    print("=== 餐食计划构建测试 ===\n")

    result = generate_week_plan(
        pet_type="dog",
        weight_kg=15.0,
        age_months=24,
        activity_level="moderate",
        week_number=1,
        theme="高蛋白恢复期",
        focus_nutrients=["protein", "taurine"],
        constraints=["避免鸡肉"],
        ingredients_data=SAMPLE_INGREDIENTS,
        suggestions=["每周补充一次卵磷脂"]
    )

    print(f"第{result['oder']}周饮食计划:")
    print(f"原则: {result['diet_adjustment_principle']}")
    print(f"\n每日营养摘要:")
    summary = result['daily_nutrition_summary']
    print(f"  总热量: {summary['total_calories']:.0f} kcal")
    print(f"  蛋白质: {summary['protein']:.1f} g")
    print(f"  脂肪: {summary['fat']:.1f} g")
    print(f"  碳水: {summary['carbohydrates']:.1f} g")

    print(f"\n餐食安排:")
    for meal in result['weekly_diet_plan']['daily_diet_plans']:
        print(f"  第{meal['oder']}餐 ({meal['time']}): {len(meal['food_items'])} 种食材")
        for item in meal['food_items']:
            print(f"    - {item['name']} {item['weight']}g")
