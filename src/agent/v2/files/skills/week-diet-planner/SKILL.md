---
name: week-diet-planner
description: "Week agent 制定周饮食计划的完整工作流。分为三个阶段：(1) 前置营养计算（热量+微量营养素目标） (2) 食材选择（类别浏览→搜索→详情） (3) 餐食组装与输出。适用于 week_agent 收到 WeekAssignment 后生成周计划。"
---

# Week Diet Planner

week_agent 的工作流约束：基于真实数据，按固定阶段生成周饮食计划。

---

## 阶段一：前置营养计算（必须最先执行）

在进行任何食材选择之前，**必须先完成营养目标计算**。

### Step 0: 专业知识补充（可选）

如需特定专业知识（如"猫咪慢性肾病饮食禁忌"），优先查询 `/temp_notes/` 下的调研笔记,没有再自己调研；

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


---

## 阶段三：餐食组装与输出

### 份量计算规则

食材数据基于每 100g 可食部分。份量由 week_agent 自行决定，
**实际营养素的精确计算由 Phase 3 组装节点完成**，week_agent 不必在输出里重复计算每一项微量营养素。

热量分配建议（可根据本周主题调整）：
- 早餐 25-30%
- 午餐 35-40%
- 晚餐 25-30%
- 加餐 5-10%（可选）

### 组装要求

1. **每餐包含**：主蛋白源 + 碳水源 + 蔬菜（可选油脂补充）
2. **份量验证**：各餐食材份量之和应接近 Step 1 计算的每日营养目标
3. **食材名称**：`ingredient_name` 必须与 `ingredient_detail_tool` / `ingredient_search_tool` 返回的 `name` 字段**精确一致**

### Step 7: 直接用 function_call 输出 WeekLightPlan

week_agent 配置了 `response_format=WeekLightPlan`，在完成阶段一/二/三思考后，
**最后一条消息**直接产出符合 `WeekLightPlan` 的 function_call

**严禁**：
- 把具体的微量营养素数值写进输出（Phase 3 会从数据库精确计算）
- 编造数据库中不存在的食材名
- 输出 Markdown 报告（旧流程已废弃，不再需要 `write_week_plan` 工具）

## 禁止事项

- 不得跳过阶段一直接编造营养数据
- 不得在未查询食材数据库的情况下自行选择食材和份量
- 不得使用数据库中不存在的食材名称
- 食材选择必须先浏览类别（Step 3），再在类别内搜索（Step 4）


## 参考文档
- **[ingredient_fields.md](references/ingredient_fields.md)** — 数据库食材表字段和分类列表
- **[rer_formula.md](references/rer_formula.md)** — RER 热量公式和生命阶段系数表
