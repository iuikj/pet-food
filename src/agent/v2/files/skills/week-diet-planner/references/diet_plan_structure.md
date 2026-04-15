# WeeklyDietPlan 结构说明

对应 `src/utils/strtuct.py` 中的饮食计划数据结构。

## WeeklyDietPlan（周计划）

```python
class WeeklyDietPlan(BaseModel):
    oder: int                          # 第几周 (1-4)
    diet_adjustment_principle: str      # 饮食调整原则
    weekly_diet_plan: DailyDietPlan    # 本周食谱（7天统一）
    weekly_special_adjustment_note: str # 特殊调整说明
    suggestions: list[str]             # 建议
```

## DailyDietPlan（每日计划）

```python
class DailyDietPlan(BaseModel):
    daily_diet_plans: list[SingleMealPlan]  # 每日餐食列表
```

## SingleMealPlan（单餐计划）

```python
class SingleMealPlan(BaseModel):
    oder: int                    # 第几餐 (1-4)
    time: str                    # 时间 "HH:MM"
    food_items: list[FoodItem]   # 食材列表
    cook_method: str             # 烹饪方式
    description: str             # 描述
    recommend_reason: str        # 推荐理由
```

## FoodItem（食材项）

```python
class FoodItem(BaseModel):
    name: str                                          # 食材名称
    weight: float                                       # 重量（克）
    macro_nutrients: Macronutrients                    # 宏量营养素
    micro_nutrients: Micronutrients                    # 微量营养素
    recommend_reason: str = ""                         # 推荐理由
```

## Macronutrients（宏量营养素）

```python
class Macronutrients(BaseModel):
    protein: float          # 蛋白质 (g)
    fat: float              # 脂肪 (g)
    carbohydrates: float    # 碳水化合物 (g)
    dietary_fiber: float    # 膳食纤维 (g)
```

## Micronutrients（微量营养素）

```python
class Micronutrients(BaseModel):
    vitamin_a: Optional[str]      # "维生素A": {"value": 100, "unit": "IU"}
    vitamin_c: Optional[str]
    vitamin_d: Optional[str]
    vitamin_e: Optional[str]
    calcium: Optional[str]
    iron: Optional[str]
    sodium: Optional[str]
    potassium: Optional[str]
    cholesterol: Optional[str]
    additional_nutrients: dict    # 额外营养素
```

## 输出示例

```json
{
  "oder": 1,
  "diet_adjustment_principle": "本周主题：高蛋白恢复期。重点营养素：protein, taurine。",
  "weekly_diet_plan": {
    "daily_diet_plans": [
      {
        "oder": 1,
        "time": "08:00",
        "food_items": [
          {
            "name": "鸡胸肉",
            "weight": 150.0,
            "macro_nutrients": {
              "calories": 177.0,
              "protein": 36.9,
              "fat": 2.85,
              "carbohydrates": 0.9,
              "dietary_fiber": 0.0
            },
            "micro_nutrients": {
              "calcium": {"value": 16.5, "unit": "mg"},
              "phosphorus": {"value": 261.0, "unit": "mg"}
            },
            "recommend_reason": "高蛋白低脂肪，适合恢复期"
          }
        ],
        "cook_method": "蒸熟后切碎",
        "description": "早餐",
        "recommend_reason": ""
      },
      {
        "oder": 2,
        "time": "12:00",
        "food_items": [...]
      },
      {
        "oder": 3,
        "time": "18:00",
        "food_items": [...]
      }
    ]
  },
  "weekly_special_adjustment_note": "第1周饮食计划，统一执行7天",
  "suggestions": [
    "确保充足饮水",
    "观察消化情况"
  ]
}
```

## 与 Agent 的集成

生成的 `WeeklyDietPlan` 可以直接：
1. 添加到 `State.weekly_diet_plans` 列表
2. 在 `gather` 节点汇总为 `MonthlyDietPlan`
3. 最终输出 `PetDietPlan` 报告

跳过 `structure_agent` 解析步骤，直接使用结构化数据。
