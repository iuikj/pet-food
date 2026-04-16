---
name: week-diet-planner
description: "Week agent 制定周饮食计划的完整工作流。分为三个阶段：(1) 前置营养计算（热量+微量营养素目标） (2) 食材选择（类别浏览→搜索→详情） (3) 餐食组装与输出。适用于 week_agent 收到 WeekAssignment 后生成周计划。"
---

# Week Diet Planner

week_agent 的工作流约束：基于真实数据，按固定阶段生成周饮食计划。

---

## 阶段一：前置营养计算（必须最先执行）

在进行任何食材选择之前，**必须先完成营养目标计算**。

### Step 1: 计算每日热量和宏量营养素目标

```
daily_calorie_tool(
  pet_type,        # 从宠物信息获取
  weight_kg,       # 从 pet_information.pet_weight 获取
  age_months,      # 从 pet_information.pet_age 获取
  activity_level,  # 根据健康状况判断，默认 "moderate"
  health_status    # 从 pet_information.health_status 获取
)
```

返回：每日总热量(kcal)、蛋白质(g)、脂肪(g)、碳水(g) 的推荐值和范围。

### Step 2: 计算微量营养素最低标准

```
nutrition_requirement_tool(
  pet_type,
  daily_calories   # 使用 Step 1 返回的 daily_calories_kcal
)
```

返回：各微量营养素（钙、磷、铁、锌等）的每日最低需求。

**这两步返回的数值是后续所有份量计算的基础，不得跳过。**
记住这些数值，后续食材选择和份量计算都要以此为依据。

---

## 阶段二：食材选择（严格遵循查找流程）

食材选择必须遵循 **类别浏览 → 条件搜索 → 详情查询** 的三层流程。
禁止凭空编造食材名称或营养数据。且需要根据传入的相关笔记来设计配方(在"/temp_notes/"下)

### Step 3: 浏览食材类别

```
ingredient_categories_tool()
```

返回数据库中所有可用的食材类别和子类别及各分类下的食材数量。
用于了解"数据库里有什么"，为后续精确查询做准备。

### Step 4: 按条件搜索食材（可多次调用）

根据本周的主题和营养目标，从不同类别中搜索食材：

```
# 例：搜索高蛋白的白肉
ingredient_search_tool(category="白肉", protein_min=20.0)

# 例：搜索蔬菜类
ingredient_search_tool(category="蔬菜")

# 例：搜索富含牛磺酸的内脏（猫用）
ingredient_search_tool(category="内脏", taurine_min=50.0)

# 例：按关键词搜索
ingredient_search_tool(keyword="三文鱼")
```

**原则**：
- 先确定大类别，再在类别内筛选
- 蛋白质来源选 2-3 种（主肉、副肉、可选内脏）
- 蔬菜/碳水来源选 2-3 种
- 注意本周的饮食约束和差异化要求

### Step 5: 获取核心食材的完整营养数据

对选定的 3-6 种核心食材，逐一查询详情：

```
ingredient_detail_tool(name="鸡胸肉")
ingredient_detail_tool(name="南瓜")
...
```

返回完整的宏量+微量营养素数据（每 100g）。
这些数据是份量计算的精确依据。

**食材名称必须与搜索结果中返回的名称完全一致。**

### Step 6: （可选）补充专业知识

```
rag_search_tool(query="猫咪慢性肾病饮食禁忌")
```

仅在需要特定专业知识时使用。当前为占位实现。

---

## 阶段三：餐食组装与输出

### 份量计算规则

食材数据基于每 100g 可食部分。计算实际用量：

```
实际营养素 = (数据库值 / 100) x 实际克数
```

热量分配建议（可根据本周主题调整）：
- 早餐 25-30%
- 午餐 35-40%
- 晚餐 25-30%
- 加餐 5-10%（可选）

### 组装要求

1. **每餐包含**：主蛋白源 + 碳水源 + 蔬菜（可选油脂补充）
2. **份量验证**：各餐食材份量之和应接近 Step 1 计算的每日营养目标
3. **营养素核算**：列出每餐和每日的营养素总量

### Step 7: 输出最终周计划

调用 `write_week_plan(week_number, content)` 写入 Markdown 格式的周计划。

**Markdown 报告结构**：

```markdown
# 第X周饮食计划

## 饮食原则
- [原则1：基于本周主题]
- [原则2：基于健康状况]

## 每日营养目标
- 总热量：[数值] kcal
- 蛋白质：[数值]g
- 脂肪：[数值]g
- 碳水：[数值]g

## 选用食材清单
| 食材 | 类别 | 每日用量(g) | 主要营养贡献 |
|------|------|------------|-------------|
| 鸡胸肉 | 白肉 | 150g | 蛋白质 36.9g |
| ... | ... | ... | ... |

## 每日食谱（统一执行7天）

### 第1餐（08:00 早餐）
**[菜名]**
- 食材：[食材名] [份量]g
- 烹饪方式：[详细步骤]
- 本餐营养素：蛋白质 Xg / 脂肪 Xg / 热量 X kcal

### 第2餐（12:00 午餐）
...

### 第3餐（18:00 晚餐）
...

## 每日总营养素汇总
- 总热量：[数值] kcal（目标 [数值] kcal）
- 蛋白质：[数值]g（目标 [数值]g）
- 脂肪：[数值]g
- 微量营养素：钙 X mg / 磷 X mg / 铁 X mg / 锌 X mg ...

## 特别说明
1. [针对健康状况的说明]
2. [食材替换建议]

## 配套建议
- [建议1]
- [建议2]
```

---

## 禁止事项

- 不得跳过阶段一直接编造营养数据
- 不得在未查询食材数据库的情况下自行选择食材和份量
- 不得使用数据库中不存在的食材名称
- 食材选择必须先浏览类别（Step 3），再在类别内搜索（Step 4）
- 不得输出未经 `write_week_plan` 工具的计划

## 参考文档

- **[diet_plan_structure.md](references/diet_plan_structure.md)** — WeeklyDietPlan 完整 Pydantic 结构和 JSON 示例
- **[ingredient_fields.md](references/ingredient_fields.md)** — 数据库食材表字段和分类列表
- **[rer_formula.md](references/rer_formula.md)** — RER 热量公式和生命阶段系数表
