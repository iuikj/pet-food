# V2 Agent 重构方案：Skill 驱动 + 工具化 + 文件记忆

> 日期: 2026-04-12  
> 状态: **Phase 1 已实施** — 工具化 + DB 接入完成，文件记忆待实施  
> 基于: DeepAgent SDK + LangGraph StateGraph

---

## 实施进度

### 已完成 (2026-04-12)

| 变更 | 文件 |
|------|------|
| ContextV2 添加 `db_session_factory` | `utils/context.py` |
| 营养计算工具 (`daily_calorie_tool`, `nutrition_requirement_tool`) | `tools/nutrition_tools.py` |
| 食材 DB 查询工具 (`ingredient_search_tool`, `ingredient_detail_tool`, `ingredient_categories_tool`) | `tools/ingredient_tools.py` |
| RAG 占位工具 (`rag_search_tool`) | `tools/rag_tools.py` |
| 计划输出工具 (`write_week_plan`) | `tools/plan_output_tools.py` |
| 营养计算 SubAgent | `sub_agents/nutrition_calc_agent.py` |
| 食材查询 SubAgent | `sub_agents/ingredient_query_agent.py` |
| week_agent 从 LocalShellBackend+skills 改为直接绑定工具 | `node.py` |
| WEEK_PLANNER_PROMPT 添加工具使用流程 | `prompts/agent_prompt.py` |
| week_agent_prompt 移除 skill 引用 | `middlewares/dynamic_prompt_middleware.py` |

### 待实施

- [ ] **文件记忆系统**: `research-memory` Skill, `files/notes/` 分层目录, `FilesystemBackend(virtual_mode=False)`
- [ ] **RAG 真实接入**: `rag_search_tool` 对接 `src/rag/milvus.py`
- [ ] **Phase 3 优化**: `write_week_plan` 改为直接输出结构化 JSON，跳过 structure_report

---

## 一、现状分析

### 1.1 当前 V2 架构总览

```
plan_agent (deepagent)      研究阶段，含 websearch_sub_agent
  ↓
generate_coordination_guide  结构化输出 CoordinationGuide
  ↓
dispatch_weeks              Send x4 并行分发
  ↓
week_agent (deepagent)      LocalShellBackend + skills/week-diet-planner/
  ↓
END                         weekly_diet_plans 自动合并
```

### 1.2 存在的问题

| 编号 | 问题 | 详情 |
|------|------|------|
| **P1** | **Skill 执行依赖 Shell 脚本** | `week-diet-planner` 通过 `LocalShellBackend` 运行 Python 脚本（`week_meal_planner.py`），Agent 需要自己写代码调用脚本，不可控且容易出错 |
| **P2** | **Skill 无流程约束** | 当前 SKILL.md 只提供了"快速开始"示例，Agent 可以自由跳过步骤（如跳过热量计算直接编造数据） |
| **P3** | **笔记系统退化** | V2 的 `NoteMiddleware` 仍基于 State dict 存储，运行结束即丢失。已有的 `files/` 目录有手动放置的 Markdown 文件，但未形成系统性的记忆机制 |
| **P4** | **无记忆复用** | 每次运行都从零开始调研，即使上次已经调研过"金毛营养需求"，下次同品种请求仍然重新搜索 |
| **P5** | **工具组未分化** | plan_agent 和 week_agent 各自携带所有工具，没有将专业工具绑定到专业 sub-agent |
| **P6** | **RAG 缺失** | 已有 `src/rag/` 模块和 Milvus 知识库，但 V2 未接入 |

---

## 二、核心设计思路

### 2.1 三大改造方向

```
改造一: 脚本 → 工具
  将 week-diet-planner/scripts/*.py 中的功能改造为 @tool 装饰的 LangGraph 工具
  Agent 不再需要"写代码调用脚本"，而是直接调用工具获得结构化返回

改造二: Skill 作为流程约束
  SKILL.md 明确定义"必须按顺序调用哪些工具"
  Skill = 领域知识 + 工具调用顺序 + 输出格式规范

改造三: 文件记忆系统
  调研结果写入 files/ 目录下的分层文件夹
  plan_agent 启动时先检查是否已有可复用的调研记录
  这个"检查-复用"流程本身抽象为一个 Skill
```

### 2.2 改造后的整体架构

```
plan_agent (deepagent)
  ├── Skill: research-memory      ← 新增：调研记忆检查与复用
  ├── SubAgent: web_search_agent  ← 保留：网络搜索
  ├── SubAgent: rag_search_agent  ← 新增：RAG 知识库检索（占位）
  ├── Tool: query_note            ← 保留
  └── Tool: get_state             ← 保留
  ↓
generate_coordination_guide       ← 保留
  ↓
dispatch_weeks                    ← 保留
  ↓
week_agent (deepagent)            ← 重构核心
  ├── Skill: week-diet-planner    ← 重写：定义工具调用流程
  ├── SubAgent: nutrition_calc    ← 新增：营养计算专家
  ├── SubAgent: ingredient_query  ← 新增：食材查询专家
  └── Tool: write_week_plan       ← 新增：结构化写入工具
```

---

## 三、Skill 重新设计

### 3.1 设计原则：Skill = 流程约束 + 领域知识

```
Skill 不执行代码，而是告诉 Agent：
  1. 你必须调用哪些工具/sub-agent
  2. 调用的顺序是什么
  3. 每一步的输入从哪来、输出到哪去
  4. 什么情况下可以跳过某步
```

### 3.2 Skill: `week-diet-planner`（重写）

```
skills/week-diet-planner/
├── SKILL.md                          # 流程约束定义
├── references/
│   ├── workflow.md                   # 详细工作流步骤
│   ├── diet_plan_structure.md        # WeeklyDietPlan 结构说明（保留）
│   ├── rer_formula.md                # RER 公式参考（保留）
│   ├── ingredient_fields.md          # 食材字段说明（保留）
│   └── nutrition_standards.md        # AAFCO/FEDIAF 营养标准参考
└── (无 scripts/ 目录 —— 脚本已改造为工具)
```

**SKILL.md 核心内容设计：**

```markdown
---
name: week-diet-planner
description: >
  宠物周饮食计划生成的完整工作流。定义了从热量计算到食材选择到餐食
  构建的严格步骤顺序。使用此 Skill 时，必须按照 workflow 中定义的
  步骤顺序调用对应的 sub-agent 和 tool。适用场景：(1) week_agent
  收到 WeekAssignment 后生成周计划 (2) 需要基于宠物信息计算营养
  并选择食材 (3) 需要输出结构化 WeeklyDietPlan
allowed-tools: write_week_plan
---

# Week Diet Planner

## 强制工作流（必须严格按顺序执行）

### Step 1: 计算营养需求
委派给 `nutrition_calc` sub-agent：
- 输入: pet_information (体重、年龄、品种、健康状况)
- 输出: daily_kcal, protein_g, fat_g, carbs_g, 微量营养素目标

### Step 2: 查询可用食材
委派给 `ingredient_query` sub-agent：
- 输入: Step 1 的营养目标 + week_assignment 的 constraints/focus_nutrients
- 输出: 符合条件的食材列表（含营养成分）

### Step 3: 构建餐食计划
基于 Step 1 + Step 2 的结果，规划每日餐食分配：
- 参考 references/workflow.md 中的热量分配比例
- 确保食材组合满足营养目标

### Step 4: 写入结构化计划
调用 `write_week_plan` 工具：
- 输入: 完整的周计划数据
- 输出: WeeklyDietPlan 结构化 JSON

## 禁止事项
- 不得跳过 Step 1 直接编造营养数据
- 不得在未查询食材数据库的情况下自行选择食材
- 不得输出 Markdown 格式（必须使用 write_week_plan 工具）

## 详细参考
- 完整工作流步骤: [workflow.md](references/workflow.md)
- 输出结构: [diet_plan_structure.md](references/diet_plan_structure.md)
- 热量公式: [rer_formula.md](references/rer_formula.md)
```

### 3.3 Skill: `research-memory`（新增）

```
skills/research-memory/
├── SKILL.md
└── references/
    └── file_structure.md             # 记忆文件的目录规范
```

**SKILL.md 核心内容设计：**

```markdown
---
name: research-memory
description: >
  调研记忆管理技能。plan_agent 在开始调研前，先检查 files/ 目录下
  是否已有可复用的调研结果。如果找到匹配的记忆文件，直接读取复用，
  跳过重复调研。适用场景：(1) plan_agent 开始新的调研任务前
  (2) 需要查找历史调研结果 (3) 需要保存新的调研成果到文件系统
---

# Research Memory

## 核心逻辑

```
开始调研任务前:
  1. 用 ls/glob 检查 files/notes/{pet_type}/{breed}/ 下是否有相关文件
  2. 如果找到匹配文件 → read_file 读取 → 直接作为调研结果使用
  3. 如果未找到 → 执行正常调研流程（web_search / rag_search）
  4. 调研完成后 → write_file 保存到对应目录

目录结构规范见 references/file_structure.md
```

## 匹配规则
- 按 pet_type + breed 匹配目录
- 按任务关键词匹配文件名
- 文件内容包含时间戳，超过 30 天视为过期
```

---

## 四、工具组分化与 SubAgent 绑定

### 4.1 Sub-Agent 设计

#### SubAgent: `nutrition_calc`（营养计算专家）

```python
nutrition_calc = SubAgent(
    name="nutrition_calc",
    description="计算宠物每日营养需求。输入宠物基本信息，输出热量、蛋白质、脂肪等目标值。",
    system_prompt=NUTRITION_CALC_PROMPT,
    tools=[
        daily_calorie_tool,           # RER 公式计算
        nutrition_requirement_tool,    # AAFCO/FEDIAF 标准查询
    ],
    model="dashscope:qwen-flash",     # 纯计算任务，轻量模型足够
)
```

**工具：`daily_calorie_tool`**

```python
@tool
def daily_calorie_tool(
    pet_type: Literal["cat", "dog"],
    weight_kg: float,
    age_months: int,
    activity_level: Literal["low", "medium", "high"] = "medium",
) -> dict:
    """
    基于 RER 公式计算宠物每日热量需求。
    
    Returns:
        {
            "rer_kcal": float,         # 基础代谢
            "daily_kcal": float,       # 每日总热量
            "meals_per_day": int,      # 建议餐数
            "kcal_per_meal": dict,     # 各餐热量分配
            "calculation_basis": str,  # 计算依据说明
        }
    """
    # 复用 calculate_calories.py 中的 CalorieCalculator 逻辑
    from skills.week_diet_planner.scripts.calculate_calories import CalorieCalculator
    calc = CalorieCalculator(pet_type, weight_kg, age_months)
    result = calc.calculate(activity_level)
    return result.to_dict()
```

**工具：`nutrition_requirement_tool`**

```python
@tool
def nutrition_requirement_tool(
    pet_type: Literal["cat", "dog"],
    weight_kg: float,
    age_months: int,
    daily_kcal: float,
    health_conditions: list[str] = [],
) -> dict:
    """
    基于 AAFCO/FEDIAF 标准，计算每日宏/微量营养素目标范围。
    
    Returns:
        {
            "protein_g": {"min": float, "max": float},
            "fat_g": {"min": float, "max": float},
            "carbs_g": {"min": float, "max": float},
            "calcium_mg": {"min": float, "max": float},
            "phosphorus_mg": {"min": float, "max": float},
            "taurine_mg": {"min": float} | None,
            "adjustments_applied": list[str],
        }
    """
```

#### SubAgent: `ingredient_query`（食材查询专家）

```python
ingredient_query = SubAgent(
    name="ingredient_query",
    description="查询食材数据库，根据营养目标和约束条件筛选合适的食材。",
    system_prompt=INGREDIENT_QUERY_PROMPT,
    tools=[
        ingredient_search_tool,     # 数据库查询
        ingredient_detail_tool,     # 单个食材详情
        rag_search_tool,            # RAG 知识库检索（占位）
    ],
    model="dashscope:qwen-flash",
)
```

**工具：`ingredient_search_tool`**

```python
@tool
def ingredient_search_tool(
    categories: list[str] = [],
    protein_min: float | None = None,
    fat_max: float | None = None,
    exclude_ingredients: list[str] = [],
    limit: int = 20,
) -> list[dict]:
    """
    从食材数据库中按条件筛选食材。
    
    Args:
        categories: 食材类别 ["白肉", "红肉", "蔬菜", "谷物", ...]
        protein_min: 最低蛋白质含量 (g/100g)
        fat_max: 最高脂肪含量 (g/100g)
        exclude_ingredients: 排除的食材名称
        limit: 返回数量上限
    
    Returns:
        [{"name": str, "category": str, "calories_per_100g": float,
          "protein": float, "fat": float, "carbs": float, ...}]
    """
    # 复用 query_ingredients.py 中的 IngredientQuerier 逻辑
    from skills.week_diet_planner.scripts.query_ingredients import IngredientQuerier
    querier = IngredientQuerier()
    return querier.search(
        categories=categories,
        protein_min=protein_min,
        fat_max=fat_max,
        exclude=exclude_ingredients,
        limit=limit,
    )
```

**工具：`ingredient_detail_tool`**

```python
@tool
def ingredient_detail_tool(
    ingredient_name: str,
    weight_g: float = 100.0,
) -> dict:
    """
    查询单个食材的完整营养信息（含微量营养素）。
    
    Returns:
        {
            "name": str, "weight_g": float,
            "macro": {"protein": float, "fat": float, "carbs": float, "fiber": float},
            "micro": {"calcium_mg": float, "phosphorus_mg": float, ...},
            "pet_safety_notes": list[str],
        }
    """
```

**工具：`rag_search_tool`（占位）**

```python
@tool
async def rag_search_tool(
    query: str,
    top_k: int = 5,
) -> list[dict]:
    """
    查询宠物营养知识库（Milvus RAG），返回相关知识片段。
    适合查询：食材禁忌、品种特殊需求、疾病饮食限制等专业知识。
    
    Args:
        query: 检索问题，如"猫咪慢性肾病饮食禁忌"
        top_k: 返回结果数量
    
    Returns:
        [{"content": str, "source": str, "score": float}]
    """
    # --- 占位实现 ---
    # TODO: 对接 src/rag/ 模块的 hybrid_search
    # from src.rag.retriever import hybrid_search
    # results = await hybrid_search(query, top_k=top_k)
    # return [{"content": r.page_content, "source": r.metadata.get("source"), "score": r.metadata.get("score")} for r in results]
    
    return [{
        "content": f"[RAG 占位] 未找到关于 '{query}' 的知识库结果。请使用网络搜索获取信息。",
        "source": "placeholder",
        "score": 0.0,
    }]
```

#### SubAgent: `rag_search_agent`（plan_agent 用，占位）

```python
rag_search_agent = SubAgent(
    name="rag_search_agent",
    description="从宠物营养知识库（RAG）中检索专业知识。用于查询品种特殊需求、疾病饮食限制、食材禁忌等。",
    system_prompt=RAG_SEARCH_PROMPT,
    tools=[
        rag_search_tool,    # 占位
    ],
    model="dashscope:qwen-flash",
)
```

### 4.2 Week Agent 专用工具：`write_week_plan`

```python
@tool
def write_week_plan(
    week_number: int,
    diet_adjustment_principle: str,
    daily_meals: list[dict],
    suggestions: list[str],
    special_adjustment_note: str,
) -> dict:
    """
    将周饮食计划写入为结构化数据。
    Agent 必须先通过 nutrition_calc 和 ingredient_query 获取数据后，
    再调用此工具。
    
    Args:
        week_number: 第几周 (1-4)
        diet_adjustment_principle: 本周饮食调整原则
        daily_meals: 每日餐食列表，格式:
            [{"order": 1, "time": "08:00", "food_items": [...], "cook_method": "..."}]
        suggestions: 本周饮食建议
        special_adjustment_note: 特殊调整说明
    
    Returns:
        {"status": "success", "week_number": int, "plan": WeeklyDietPlan}
    """
    # 直接构造并验证 Pydantic 模型
    plan = WeeklyDietPlan(
        oder=week_number,
        diet_adjustment_principle=diet_adjustment_principle,
        weekly_diet_plan=DailyDietPlan(daily_diet_plans=[
            SingleMealPlan(**meal) for meal in daily_meals
        ]),
        weekly_special_adjustment_note=special_adjustment_note,
        suggestions=suggestions,
    )
    return {
        "status": "success",
        "week_number": week_number,
        "plan": plan.model_dump(),
    }
```

---

## 五、文件记忆系统

### 5.1 设计目标

取代 State dict 中的 Note 系统，将调研结果持久化到文件系统，实现跨运行的知识复用。

### 5.2 目录结构规范

```
files/
├── notes/                                  # 通用调研笔记
│   ├── {pet_type}/                         # 按宠物类型分
│   │   ├── {breed}/                        # 按品种分
│   │   │   ├── 营养需求标准.md             # 品种特定营养需求
│   │   │   ├── 常见健康问题饮食.md         # 品种特定健康饮食
│   │   │   └── 烹饪搭配指南.md             # 品种特定烹饪建议
│   │   └── _common/                        # 该宠物类型的通用知识
│   │       ├── 基础营养标准.md
│   │       └── 食材安全清单.md
│   └── _shared/                            # 跨宠物类型的通用知识
│       ├── 食材禁忌总表.md
│       └── 烹饪方法指南.md
│
├── plans/                                  # 历史生成的计划（可选复用）
│   └── {pet_type}/{breed}/
│       └── {date}_{theme}.json             # 结构化 WeeklyDietPlan
│
└── notebooks/                              # 临时工作区（运行中的中间产物）
    └── {session_id}/
        ├── research_phase.md
        └── week_{n}_draft.md
```

### 5.3 文件元数据约定

每个记忆文件的头部包含 YAML frontmatter：

```markdown
---
created: 2026-04-12T10:30:00
updated: 2026-04-12T10:30:00
pet_type: dog
breed: golden_retriever
tags: [营养需求, AAFCO标准]
ttl_days: 30
source: tavily_search + rag
---

# 金毛犬营养需求标准

## 每日热量需求
...
```

### 5.4 记忆检查流程（research-memory Skill）

```
plan_agent 收到调研任务: "调查{breed}的营养需求"
  ↓
Step 1: glob 搜索文件
  路径模式: files/notes/{pet_type}/{breed}/*营养*
  ↓
Step 2: 判断是否匹配
  ├── 找到文件 → read_file 读取
  │   ├── 检查 ttl_days 是否过期
  │   │   ├── 未过期 → 直接使用，跳过调研
  │   │   └── 已过期 → 标记为"需要更新"，走正常调研
  │   └── 返回文件内容
  └── 未找到 → 走正常调研流程
  ↓
Step 3: 调研完成后保存
  write_file 到 files/notes/{pet_type}/{breed}/
  文件头包含 created/updated/tags/ttl_days
```

### 5.5 与 DeepAgent FilesystemBackend 的集成

```python
# plan_agent 使用 FilesystemBackend，root_dir 指向 files/
plan_agent = create_deep_agent(
    backend=FilesystemBackend(
        root_dir="src/agent/v2/files",
        virtual_mode=False,  # 改为 False，直接读写磁盘
    ),
    skills=[
        "/skills/research-memory/",   # 记忆管理技能
    ],
    ...
)

# week_agent 也使用 FilesystemBackend，可以读取 notes/ 下的调研结果
week_agent = create_deep_agent(
    backend=FilesystemBackend(
        root_dir="src/agent/v2/files",
        virtual_mode=False,
    ),
    skills=[
        "/skills/week-diet-planner/",  # 周计划流程技能
    ],
    ...
)
```

**关键改变：**  
- `virtual_mode=False` → 文件直接读写磁盘，持久化
- DeepAgent 内置的 `read_file`, `write_file`, `ls`, `glob`, `grep` 工具自动可用
- 不再需要 NoteMiddleware（文件系统取代 State dict）

### 5.6 与 State 中 Note 系统的关系

| 维度 | 旧 Note 系统 (State dict) | 新文件记忆系统 |
|------|--------------------------|--------------|
| 持久性 | 运行结束即丢失 | 写入磁盘，跨运行保留 |
| 查询方式 | `query_note(file_name)` | `read_file` + `glob` + `grep` |
| 写入方式 | `write_note(content, type)` | `write_file(path, content)` |
| 组织结构 | 扁平 dict | 分层文件夹 |
| 跨运行复用 | 不可能 | 自动检查并复用 |
| 作为 week_agent 输入 | `shared_notes` 参数传递 | week_agent 直接 `read_file` |

**迁移策略：**
- `NoteMiddleware` 保留为可选兼容层（中间状态）
- 新流程优先使用文件系统
- `dispatch_weeks` 不再传递 `shared_notes` 参数，week_agent 自行从 `files/notes/` 读取

---

## 六、重构后的完整节点代码设计

### 6.1 `plan_agent` 节点

```python
plan_agent = create_deep_agent(
    model=load_chat_model(ContextV2.plan_model),
    tools=[
        get_state,                  # 获取运行时状态
    ],
    subagents=[
        websearch_sub_agent,        # 保留：网络搜索
        rag_search_agent,           # 新增：RAG 检索（占位）
    ],
    backend=FilesystemBackend(
        root_dir="src/agent/v2/files",
        virtual_mode=False,
    ),
    skills=[
        "/skills/research-memory/",  # 新增：调研记忆管理
    ],
    middleware=[
        plan_agent_prompt,           # 保留：动态提示词
    ],
    context_schema=ContextV2,
)
```

### 6.2 `week_agent` 节点

```python
week_agent = create_deep_agent(
    name="week_agent",
    model=load_chat_model(ContextV2.week_model),
    tools=[
        write_week_plan,             # 新增：结构化写入工具
    ],
    subagents=[
        nutrition_calc,              # 新增：营养计算专家
        ingredient_query,            # 新增：食材查询专家
    ],
    backend=FilesystemBackend(
        root_dir="src/agent/v2/files",
        virtual_mode=False,
    ),
    skills=[
        "/skills/week-diet-planner/", # 重写：流程约束
    ],
    context_schema=ContextV2,
)
```

### 6.3 `dispatch_weeks`（简化）

```python
async def dispatch_weeks(state: State) -> Command[Literal["week_agent"]]:
    guide: CoordinationGuide = state["coordination_guide"]
    ctx: ContextV2 = get_runtime().context

    sends = []
    for assignment in guide.weekly_assignments:
        sends.append(
            Send(
                node="week_agent",
                arg={
                    "pet_information": ctx.pet_information,
                    "week_assignment": assignment,
                    # 不再传递 shared_notes —— week_agent 自行从 files/ 读取
                    "shared_constraints": guide.shared_constraints,
                    "ingredient_rotation_strategy": guide.ingredient_rotation_strategy,
                    "age_adaptation_note": guide.age_adaptation_note,
                },
            )
        )
    return Command(goto=sends)
```

### 6.4 汇总阶段（简化 Phase 3）

由于 `write_week_plan` 工具直接输出结构化的 `WeeklyDietPlan`，Phase 3 的 `structure_report` 子图可以大幅简化甚至跳过。

```python
# 方案 A：直接在 week_agent 输出中收集（推荐）
# week_agent 返回 structured_response 或通过 State 的 weekly_diet_plans 汇总

# 方案 B：保留 structure_report 作为降级路径
# 仅在 write_week_plan 失败时，对 Markdown 笔记走 LLM 解析
```

---

## 七、文件变更清单

### 7.1 新增文件

| 文件 | 职责 |
|------|------|
| `skills/research-memory/SKILL.md` | 调研记忆管理技能定义 |
| `skills/research-memory/references/file_structure.md` | 记忆文件目录规范 |
| `skills/week-diet-planner/references/workflow.md` | 详细工作流步骤 |
| `skills/week-diet-planner/references/nutrition_standards.md` | AAFCO/FEDIAF 营养标准 |
| `sub_agents/nutrition_calc_agent.py` | 营养计算 sub-agent |
| `sub_agents/ingredient_query_agent.py` | 食材查询 sub-agent |
| `sub_agents/rag_search_agent.py` | RAG 检索 sub-agent（占位） |
| `tools/nutrition_tools.py` | `daily_calorie_tool` + `nutrition_requirement_tool` |
| `tools/ingredient_tools.py` | `ingredient_search_tool` + `ingredient_detail_tool` |
| `tools/rag_tools.py` | `rag_search_tool`（占位） |
| `tools/plan_output_tools.py` | `write_week_plan` |

### 7.2 修改文件

| 文件 | 变更内容 |
|------|----------|
| `node.py` | 更新 plan_agent 和 week_agent 的创建参数 |
| `state.py` | `weekly_diet_plans` 改为从 week_agent 结构化输出直接收集 |
| `skills/week-diet-planner/SKILL.md` | 全面重写为流程约束模式 |

### 7.3 可删除文件

| 文件 | 原因 |
|------|------|
| `skills/week-diet-planner/scripts/*.py` | 逻辑转移到 `tools/` 下的工具中 |
| `middlewares/note_middleware.py` | 被文件记忆系统取代（或保留为兼容层） |

---

## 八、实施路线

```
Phase 0: 基础设施                            预计 1 天
  ├── 创建 tools/ 目录结构
  ├── 创建 sub_agents/ 新文件
  └── 建立 files/notes/ 目录规范

Phase 1: 工具化 (P0)                         预计 2 天
  ├── 将 calculate_calories.py → daily_calorie_tool
  ├── 将 query_ingredients.py → ingredient_search_tool + ingredient_detail_tool
  ├── 实现 nutrition_requirement_tool
  ├── 实现 write_week_plan 工具
  └── 实现 rag_search_tool 占位

Phase 2: SubAgent 分化 (P1)                  预计 1 天
  ├── 创建 nutrition_calc sub-agent
  ├── 创建 ingredient_query sub-agent
  ├── 创建 rag_search_agent 占位
  └── 更新 week_agent 绑定

Phase 3: Skill 重写 (P1)                     预计 1 天
  ├── 重写 week-diet-planner SKILL.md
  ├── 编写 workflow.md 详细步骤
  ├── 创建 research-memory SKILL.md
  └── 编写 file_structure.md

Phase 4: 文件记忆系统 (P2)                   预计 1 天
  ├── FilesystemBackend 切换到 virtual_mode=False
  ├── 迁移已有 files/ 内容到规范目录结构
  ├── 更新 dispatch_weeks 移除 shared_notes
  └── 测试记忆复用流程

Phase 5: 汇总阶段优化 (P3)                   预计 0.5 天
  ├── 跳过 structure_report（write_week_plan 已结构化）
  ├── 保留降级路径
  └── 端到端测试
```

---

## 九、风险与决策记录

### 9.1 关键决策

| 决策 | 选项 | 选择 | 原因 |
|------|------|------|------|
| 脚本代码去向 | 丢弃 / 改为工具内部调用 | **改为工具内部调用** | 脚本中 CalorieCalculator 等类逻辑完善，直接在 @tool 中 import 复用 |
| 文件系统模式 | virtual_mode / 磁盘 | **磁盘** | 记忆必须跨运行持久化 |
| NoteMiddleware | 删除 / 保留为兼容层 | **保留为可选** | 渐进式迁移，不破坏已有流程 |
| Phase 3 structure_report | 删除 / 保留为降级 | **保留为降级** | 防止 write_week_plan 格式错误时无法兜底 |

### 9.2 风险项

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| Skill 流程约束不够强，Agent 仍跳过步骤 | 中 | Skill 中明确"禁止事项" + 提示词强化 |
| 文件系统并发写入冲突（4 个 week_agent 并行） | 低 | 每个 week_agent 写入不同目录 (`week_1/`, `week_2/`) |
| rag_search_tool 占位影响调研质量 | 中 | 占位返回明确提示"请使用网络搜索"，不会误导 Agent |
| 食材数据库数据不足（当前仅 3 条示例数据） | 高 | Phase 1 优先补充食材数据，或对接外部 API |

---

## 十、附录：工具与 SubAgent 对比总览

```
┌─────────────────────────────────────────────────────────┐
│                      plan_agent                          │
│                                                          │
│  Tools:     get_state                                    │
│  SubAgents: websearch_sub_agent (网络搜索)               │
│             rag_search_agent (RAG检索, 占位)             │
│  Skills:    research-memory (记忆管理)                   │
│  Backend:   FilesystemBackend (磁盘模式)                 │
│                                                          │
│  内置工具(DeepAgent): read_file, write_file, ls,         │
│                       glob, grep, write_todos            │
└──────────────────────────┬──────────────────────────────┘
                           │
                   coordination_guide
                           │
                    dispatch_weeks
                     ┌──┬──┬──┐
                     │  │  │  │  (Send x4)
┌────────────────────▼──▼──▼──▼────────────────────────────┐
│                     week_agent                            │
│                                                           │
│  Tools:     write_week_plan (结构化写入)                  │
│  SubAgents: nutrition_calc (热量+营养素计算)              │
│               └─ daily_calorie_tool                       │
│               └─ nutrition_requirement_tool                │
│             ingredient_query (食材查询)                    │
│               └─ ingredient_search_tool                   │
│               └─ ingredient_detail_tool                   │
│               └─ rag_search_tool (占位)                   │
│  Skills:    week-diet-planner (流程约束)                  │
│  Backend:   FilesystemBackend (磁盘模式)                  │
│                                                           │
│  内置工具(DeepAgent): read_file, write_file, ls,          │
│                       glob, grep, write_todos             │
└───────────────────────────────────────────────────────────┘
```
