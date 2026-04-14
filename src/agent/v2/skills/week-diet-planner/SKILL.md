---
name: week-diet-planner
description: "Week agent 制定周饮食计划的工作流。定义了从热量计算到食材查询到餐食组装的严格 7 步工具调用顺序。使用场景：(1) week_agent 收到 WeekAssignment 后生成周计划 (2) 需要基于宠物体重/年龄计算营养需求 (3) 需要从真实数据库查询食材并计算份量 (4) 需要输出符合 WeeklyDietPlan 格式的周饮食计划"
---

# Week Diet Planner

week_agent 的工作流约束：按固定顺序调用工具，基于真实数据生成周计划。

## 强制 7 步流程

```
Step 1: daily_calorie_tool       → 得到每日热量和宏量营养素目标
Step 2: nutrition_requirement_tool → 得到 AAFCO 微量营养素最低标准
Step 3: ingredient_categories_tool → 了解数据库有哪些食材分类
Step 4: ingredient_search_tool    → 按条件搜索食材（可多次调用）
Step 5: ingredient_detail_tool    → 获取核心食材的完整营养数据
Step 6: rag_search_tool           → (可选) 补充专业知识
Step 7: write_week_plan           → 写入最终周计划
```

## Step 1-2: 营养目标计算

```
daily_calorie_tool(pet_type, weight_kg, age_months, activity_level, health_status)
  → { daily_calories_kcal, protein_g, fat_g, carb_g, protein_range_g, fat_range_g }

nutrition_requirement_tool(pet_type, daily_calories)
  → { calcium: {min_daily, unit}, phosphorus: {...}, ..., taurine(猫): {...} }
```

这两步返回的数值是后续所有份量计算的基础。**不得跳过。**

## Step 3-5: 食材选择

先用 `ingredient_categories_tool` 看分类，再组合查询：

```
# 例：高蛋白肉类
ingredient_search_tool(category="白肉", protein_min=20.0)

# 例：富含牛磺酸的内脏（猫用）
ingredient_search_tool(category="内脏", taurine_min=50.0)

# 例：蔬菜类
ingredient_search_tool(category="蔬菜")
```

选定 3-6 种核心食材后，逐一调用 `ingredient_detail_tool(name)` 获取完整营养数据。

## 份量计算规则

食材数据基于每 100g 可食部分。计算实际用量：

```
实际营养素 = (数据库值 / 100) × 实际克数
```

热量分配建议：早餐 25% / 午餐 35% / 晚餐 30% / 加餐 10%

## Step 7: 输出格式

调用 `write_week_plan(week_number, content)` 写入 Markdown。
输出结构参考 [diet_plan_structure.md](references/diet_plan_structure.md)。

## 禁止事项

- 不得跳过 Step 1/2 直接编造营养数据
- 不得在未查询食材数据库的情况下自行选择食材和份量
- 不得输出未经 `write_week_plan` 工具的计划
- 食材名称必须与数据库中的名称完全一致

## 参考文档

- **[diet_plan_structure.md](references/diet_plan_structure.md)** — WeeklyDietPlan 完整结构和 JSON 示例
- **[ingredient_fields.md](references/ingredient_fields.md)** — 数据库食材表字段和分类列表
- **[rer_formula.md](references/rer_formula.md)** — RER 热量公式和生命阶段系数表
