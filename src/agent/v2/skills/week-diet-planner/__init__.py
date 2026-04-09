"""
Week Diet Planner Skill

为 week_agent 提供基于本地食材数据库的周饮食计划生成能力。
"""

from .scripts.week_meal_planner import (
    WeekMealPlanner,
    PetInfo,
    WeekAssignmentInput,
    generate_from_coordination_guide,
)

from .scripts.calculate_calories import (
    CalorieCalculator,
    CalorieResult,
    calculate_daily_needs,
)

from .scripts.query_ingredients import (
    IngredientQuerier,
    IngredientInfo,
)

from .scripts.build_meal_plan import (
    MealPlanBuilder,
    WeeklyDietPlan,
    DailyDietPlan,
    SingleMealPlan,
    FoodItem,
)

__all__ = [
    # 主入口
    "WeekMealPlanner",
    "generate_from_coordination_plan",
    # 数据模型
    "PetInfo",
    "WeekAssignmentInput",
    "WeeklyDietPlan",
    "DailyDietPlan",
    "SingleMealPlan",
    "FoodItem",
    "IngredientInfo",
    "CalorieResult",
    # 工具类
    "CalorieCalculator",
    "IngredientQuerier",
    "MealPlanBuilder",
    # 便捷函数
    "calculate_daily_needs",
]
