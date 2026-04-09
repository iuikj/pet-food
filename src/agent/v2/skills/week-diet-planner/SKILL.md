---
name: week-diet-planner
description: "Generate weekly pet diet plans by querying local ingredient database, calculating calorie requirements using RER formula, and outputting structured Pydantic models. Use when week_agent needs to create a weekly diet plan based on CoordinationGuide with (1) Ingredient selection from database, (2) Calorie calculation by pet weight/age, (3) Structured WeeklyDietPlan output, (4) Nutrition-balanced meal planning"
---

# Week Diet Planner Skill

为 week_agent 提供基于本地食材数据库的周饮食计划生成能力，自动计算热量需求并输出结构化数据。

## 快速开始

```python
from scripts.week_meal_planner import WeekMealPlanner

# 初始化
planner = WeekMealPlanner(
    pet_type="dog",      # "cat" | "dog"
    weight_kg=15.0,      # 宠物体重
    age_months=24,       # 年龄（月）
    breed="拉布拉多",
    health_status="健康"
)

# 根据 CoordinationGuide 生成周计划
weekly_plan = planner.generate_week_plan(
    week_number=1,
    theme="高蛋白恢复期",
    focus_nutrients=["protein", "taurine"],
    constraints=["避免鸡肉", "低脂"],
    ingredient_categories=["白肉", "蔬菜"]
)

# 输出结构化数据
print(weekly_plan.model_dump_json(indent=2))
```

## 工作流

```
1. 热量计算 (calculate_calories.py)
   └─> 使用 RER 公式: 70 × (体重kg)^0.75 × 系数

2. 食材查询 (query_ingredients.py)
   └─> 从 ingredients 表筛选
   └─> 按类别、营养素过滤

3. 餐食构建 (build_meal_plan.py)
   └─> 分配热量到各餐
   └─> 选择食材组合
   └─> 计算营养素总量

4. 结构化输出
   └─> WeeklyDietPlan Pydantic 模型
```

## 脚本说明

### scripts/calculate_calories.py

计算宠物每日热量需求（RER 公式）：

```python
# 幼犬 (1岁以下): 系数 3.0
# 成犬 (1-7岁): 系数 1.6-2.0 (活动量调整)
# 老年犬 (7岁+): 系数 1.2-1.4

calories = 70 * (weight_kg ** 0.75) * activity_factor
```

### scripts/query_ingredients.py

查询本地食材数据库：

```python
from query_ingredients import IngredientQuerier

querier = IngredientQuerier(db_session)

# 按类别查询
chicken_meats = querier.by_category("白肉", "鸡")

# 按营养素筛选（高蛋白）
high_protein = querier.by_nutrient_min("protein", 20.0)

# 组合查询
ingredients = querier.search(
    categories=["白肉", "蔬菜"],
    protein_min=15.0,
    fat_max=10.0
)
```

### scripts/build_meal_plan.py

构建完整餐食计划：

```python
from build_meal_plan import MealPlanBuilder

builder = MealPlanBuilder(querier, calculator)

# 生成单餐
meal = builder.build_single_meal(
    target_calories=300,
    protein_ratio=0.3,  # 蛋白质占比 30%
    ingredients_pool=available_ingredients
)

# 生成全天计划
daily = builder.build_daily_plan(
    breakfast_calories=300,
    lunch_calories=400,
    dinner_calories=400,
    snack_calories=100
)
```

## 参考文档

- **[ingredient_fields.md](references/ingredient_fields.md)** - Ingredient 表完整字段列表
- **[diet_plan_structure.md](references/diet_plan_structure.md)** - WeeklyDietPlan 模型结构
- **[rer_formula.md](references/rer_formula.md)** - RER 公式详细说明和系数表

## 集成到 week_agent

在 `src/agent/v1/week_agent/` 中添加工具：

```python
from skills.week_diet_planner import WeekMealPlanner

@tool
async def generate_weekly_diet_plan(
    week_number: int,
    theme: str,
    focus_nutrients: list[str],
    constraints: list[str],
    pet_info: dict
) -> dict:
    """根据 CoordinationGuide 生成结构化周饮食计划"""
    planner = WeekMealPlanner(**pet_info)
    return planner.generate_week_plan(
        week_number=week_number,
        theme=theme,
        focus_nutrients=focus_nutrients,
        constraints=constraints
    ).model_dump()
```

## 输出格式

直接输出 `WeeklyDietPlan` Pydantic 模型，可与现有 `structure_agent` 无缝对接：

```python
class WeeklyDietPlan(BaseModel):
    oder: int                          # 第几周
    diet_adjustment_principle: str      # 饮食调整原则
    weekly_diet_plan: DailyDietPlan    # 本周食谱（7天统一）
    weekly_special_adjustment_note: str # 特殊调整说明
    suggestions: list[str]             # 建议
```
