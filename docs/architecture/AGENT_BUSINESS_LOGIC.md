# Agent 多智能体业务逻辑深度解析

> 本文档记录宠物饮食规划智能体系统的完整业务逻辑，供后续开发、调试和迭代参考。

---

## 一、业务目标

给定一只宠物的信息（类型、品种、月龄、体重、健康状况），**自动生成一份科学的月度饮食计划**：

- 分 **4 周**，每周内食谱统一（方便采购），各周间食谱不同（营养均衡）
- 精确到每餐的每种食材的**宏量 / 微量营养素含量**
- 充分考虑宠物的品种特性、年龄阶段、健康状况等个性化因素

---

## 二、多智能体角色分工

系统模拟一个**专业宠物营养师团队**的协作模式，由 4 个专职智能体组成：

| 角色 | 智能体 | 核心节点 | 职责 | 类比 |
|------|--------|----------|------|------|
| 项目经理 | 主智能体 | `call_model` | 任务分解、委派、进度跟踪 | 只管不做 |
| 调研员 | 子智能体 | `subagent_call_model` | 搜索资料、查阅历史、执行具体任务 | 干活的人 |
| 秘书 | 写入智能体 | `write` + `summary` | 格式化记录成果、生成摘要汇报 | 做笔记的人 |
| 编辑 | 结构化智能体 | `structure_report` | 把 Markdown 文本解析为结构化数据 | 排版出版 |

### 协作流程

```
用户输入 (PetInformation)
    │
    ▼
┌─ 项目经理 (主智能体) ─────────────────────────┐
│  1. 分析宠物信息                                │
│  2. 拆解为 ~6 个子任务                          │
│  3. 逐个委派给调研员                            │
│  4. 跟踪进度 (update_plan)                     │
│  5. 全部完成后触发结构化阶段                     │
└──────────┬────────────────────────────────────┘
           │ 逐个委派
           ▼
┌─ 调研员 (子智能体) ──────────────────────────┐
│  1. 接收任务 + 宠物信息 + 历史笔记列表         │
│  2. 搜索互联网 (限1次) / 查阅历史笔记          │
│  3. 生成研究报告或具体周计划                    │
└──────────┬────────────────────────────────────┘
           │ 执行结果
           ▼
┌─ 秘书 (写入智能体) ── 并行 ──────────────────┐
│  write 分支: 格式化 → 存入笔记系统              │
│  summary 分支: 一句话摘要 → 回报项目经理        │
└──────────┬────────────────────────────────────┘
           │ 回到项目经理 → 循环至全部完成
           ▼
┌─ 编辑 (结构化智能体) ── Send 并行 ──────────┐
│  仅处理 diet_plan 类型笔记                     │
│  Markdown → with_structured_output             │
│  → WeeklyDietPlan (Pydantic 模型)              │
└──────────┬────────────────────────────────────┘
           │ 4 个 WeeklyDietPlan
           ▼
┌─ 汇总 (gather) ──────────────────────────────┐
│  组装最终报告 PetDietPlan                      │
│  = 宠物信息 + AI建议 + MonthlyDietPlan         │
└──────────────────────────────────────────────┘
```

---

## 三、典型任务拆解策略

主智能体（项目经理）收到宠物信息后，会将工作拆解为以下典型子任务：

```
① 研究该品种/月龄的营养需求和注意事项        → type: research
② 研究适合的食材和烹饪方式                    → type: research
③ 制定第1周饮食计划                           → type: diet_plan
④ 制定第2周饮食计划                           → type: diet_plan
⑤ 制定第3周饮食计划                           → type: diet_plan
⑥ 制定第4周饮食计划                           → type: diet_plan
```

**不包含**"对四周饮食计划汇总"的子任务——汇总由系统自动在结构化阶段完成。

### 任务间的知识依赖

```
任务① 营养需求研究
   ↓ 提供营养学基础知识
任务② 食材研究
   ↓ 查阅任务①笔记 → 综合判断
任务③ 第1周计划
   ↓ 查阅任务①②笔记 → 基于研究制定
任务④ 第2周计划
   ↓ 查阅任务①②③笔记 → 确保不重复、营养互补
任务⑤ 第3周计划
   ↓ 查阅全部历史 → 递进差异化
任务⑥ 第4周计划
   ↓ 查阅全部历史 → 收尾平衡
```

每个后续任务都能通过 `query_note` 读取所有之前的笔记，形成**渐进式知识积累**。

---

## 四、核心业务规则

### 4.1 "周内统一、周间差异"原则

```
月度计划 (MonthlyDietPlan)
├── 第1周: 鸡胸肉为主 (一周7天相同食谱)
├── 第2周: 牛肉为主   (一周7天相同食谱)
├── 第3周: 鱼肉为主   (一周7天相同食谱)
└── 第4周: 混合搭配   (一周7天相同食谱)
```

- **周内统一**：实际可操作性，宠物主人一次采购一周食材
- **周间差异**：营养全面性，4 周轮换确保营养素摄入多样化
- 体现在数据结构上：`WeeklyDietPlan.weekly_diet_plan` 是单数的 `DailyDietPlan`

### 4.2 营养素双层精细度

每种食材 (`FoodItem`) 同时携带宏量和微量营养素：

```
FoodItem (如"鸡胸肉 100g")
├── Macronutrients (宏量营养素)
│   ├── protein: 31.0g        蛋白质
│   ├── fat: 3.6g             脂肪
│   ├── carbohydrates: 0g     碳水化合物
│   └── dietary_fiber: 0g     膳食纤维
│
└── Micronutrients (微量营养素)
    ├── vitamin_a: 0.009mg    维生素A
    ├── vitamin_c: 0mg        维生素C
    ├── vitamin_d: 0.001mg    维生素D
    ├── calcium: 15mg         钙
    ├── iron: 1.0mg           铁
    ├── sodium: 74mg          钠
    ├── potassium: 256mg      钾
    ├── cholesterol: 85mg     胆固醇
    └── additional_nutrients:  其他营养素 (开放字典)
        {"硒": 0.024, "Omega-3": 1.2, "葡萄糖胺": 50}
```

`additional_nutrients: Dict[str, float]` 是开放字典，兼容不同宠物的特殊营养需求（如皮肤病→Omega-3、关节问题→葡萄糖胺、肾病→需监控磷含量）。

### 4.3 宠物信息驱动的个性化

```python
PetInformation:
  pet_type: cat/dog          # → 决定基础营养标准 (猫需要牛磺酸，狗不需要)
  pet_breed: "金毛寻回犬"     # → 品种特有的健康风险 (金毛易患关节炎)
  pet_age: 3 (月)            # → 年龄阶段差异 (幼犬/成犬/老犬)
  pet_weight: 5.0 (kg)      # → 热量需求计算基础
  health_status: "轻微皮肤过敏" # → 特殊饮食限制
```

**月龄的时间维度考量**：提示词中明确要求"考虑宠物年龄，这一个月的年龄变化（幼犬）"。3 月龄幼犬到第 4 周已接近 4 月龄，营养需求可能变化。`WeeklyDietPlan.diet_adjustment_principle` 字段说明"这周为什么要调整"。

### 4.4 搜索策略的成本控制

- `tavily_search` 每个子任务**仅限调用一次**
- 迫使 LLM 精心设计搜索查询，而非随便搜 10 次碰运气
- 前期 research 任务搜索通用知识，后期 diet_plan 任务更多依赖 `query_note` 复用历史成果

### 4.5 笔记类型的分流处理

| 类型 | 含义 | 结构化阶段的处理 |
|------|------|-----------------|
| `research` | 过程性知识（营养需求研究、食材调研） | **跳过**，不进入最终报告 |
| `diet_plan` | 交付物（具体周计划） | **解析**为 `WeeklyDietPlan` 结构化数据 |
| `diet_plan_summary` | 饮食计划摘要 | 用于中间汇报 |

---

## 五、饮食计划模板

子智能体在制定具体周计划时，遵循以下模板（定义于 `SUBAGENT_PROMPT`）：

```markdown
饮食原则
- [原则1: 如高蛋白低脂肪]
- [原则2: 如补充关节营养]
- [原则n]

第k周每日食谱（统一执行7天）

第j餐（[时间]）
[菜名]
- 食材：[主要食材及份量]
- 烹饪方式：[详细步骤]
- 营养素含量：
  - [基础营养素]：[数值]g（[占比]%）
  - [维生素/矿物质]：[数值][单位]（[功效说明]）（来源：[说明]）

每日总营养素
- 总热量：[数值]kcal（说明）
- 蛋白质总量：[数值]g（[占比]%）
- 脂肪总量：[数值]g（[占比]%）
- Omega-3总量：[数值]g（[功能说明]）
- 微量营养素：
  - 维生素A：[数值]IU
  - 维生素E：[数值]mg
  - 锌：[数值]mg
  - 硒：[数值]μg
  - 叶黄素：[数值]mg
  - 益生菌：[数值]CFU

特别说明
1. [说明1: 如食材过敏注意事项]
2. [说明2: 如喂食频率建议]

配套建议
- [建议1: 如补充饮水量]
- [建议2: 如运动建议]
```

---

## 六、数据结构层次关系

```
PetDietPlan (最终输出)
├── pet_information: PetInformation          # 原始宠物信息
├── ai_suggestions: str                      # 主智能体的综合建议
└── pet_diet_plan: MonthlyDietPlan           # 月度计划
    └── monthly_diet_plan: list[WeeklyDietPlan]  (max=4)
        │
        └── WeeklyDietPlan (每周计划)
            ├── oder: int                          # 第几周
            ├── diet_adjustment_principle: str      # 本周饮食调整原则
            ├── weekly_diet_plan: DailyDietPlan     # 一周的每日食谱(统一)
            │   └── daily_diet_plans: list[SingleMealPlan]  # 一天的各餐
            │       │
            │       └── SingleMealPlan (每餐计划)
            │           ├── oder: int                  # 第几餐
            │           ├── time: str                  # 时间 (如 "08:00")
            │           ├── food_items: list[FoodItem]  # 食物列表
            │           │   │
            │           │   └── FoodItem (单个食材)
            │           │       ├── name: str               # 食材名
            │           │       ├── weight: float            # 重量(g)
            │           │       ├── macro_nutrients: Macronutrients
            │           │       │   ├── protein: float       # 蛋白质(g)
            │           │       │   ├── fat: float           # 脂肪(g)
            │           │       │   ├── carbohydrates: float # 碳水(g)
            │           │       │   └── dietary_fiber: float # 膳食纤维(g)
            │           │       ├── micro_nutrients: Micronutrients
            │           │       │   ├── vitamin_a: float     # 维A(mg)
            │           │       │   ├── vitamin_c: float     # 维C(mg)
            │           │       │   ├── vitamin_d: float     # 维D(mg)
            │           │       │   ├── calcium: float       # 钙(mg)
            │           │       │   ├── iron: float          # 铁(mg)
            │           │       │   ├── sodium: float        # 钠(mg)
            │           │       │   ├── potassium: float     # 钾(mg)
            │           │       │   ├── cholesterol: float   # 胆固醇(mg)
            │           │       │   └── additional_nutrients: Dict[str, float]
            │           │       └── recommend_reason: str    # 推荐理由
            │           └── cook_method: str            # 烹饪方式
            │
            ├── weekly_special_adjustment_note: str  # 本周特殊调整说明
            └── suggestions: list[str]               # 配套建议
```

---

## 七、数据转化链路

```
             自然语言层                              结构化数据层
             ──────────                              ──────────

用户输入     PetInformation ──────────────────────→ PetDietPlan.pet_information
  │
  ▼
主智能体     "研究需求; 制定第1-4周计划"
  │          (plan: list[Todo])
  ▼
子智能体     tavily_search 搜索结果
  │          + LLM 生成的 Markdown 饮食计划
  ▼
写入智能体   笔记 (research / diet_plan)
  │          diet_plan 笔记内容:
  │          "饮食原则: ...
  │           第1周每日食谱:
  │           第1餐(早8:00): 鸡胸肉蒸饭
  │           - 食材: 鸡胸肉100g, 糙米50g...
  │           - 蛋白质31g, 脂肪3.6g..."
  │
  ▼                    关键转化点
结构化智能体 ──── with_structured_output ──────→ WeeklyDietPlan
  │          Markdown → Pydantic 模型             (嵌套5层结构)
  ▼
汇总         主智能体的总结 ──────────────────→ PetDietPlan.ai_suggestions
             4个 WeeklyDietPlan ────────────→ PetDietPlan.pet_diet_plan
```

**核心转化点**：`structure_report` 节点中 Markdown 到 Pydantic 模型的结构化跳跃，是整个系统最脆弱的环节（故有重试机制）。

---

## 八、状态管理与消息隔离

### 状态层次

```
State (主状态)
├── messages: list[AnyMessage]           # 主智能体消息流 (全局)
├── plan: list[Todo]                     # 任务计划 (PlanStateMixin)
├── note: dict[str, Note]               # 笔记存储 (NoteStateMixin)
├── pet_information: PetInformation      # 宠物信息
├── task_messages: list[AnyMessage]      # 子任务结果消息
├── weekly_diet_plans: list[WeeklyDietPlan]  # 周计划列表 (operator.add 累加)
└── report: PetDietPlan                  # 最终报告

SubAgentState (子智能体)
└── temp_task_messages: list[AnyMessage]  # 子智能体临时消息 (独立键)

WriteState (写入智能体)
└── temp_write_note_messages: list[AnyMessage]  # 写入临时消息 (独立键)

StructState (结构化智能体)
├── temp_note: Note                       # 当前处理的笔记
└── failed_reason: str                    # 失败重试原因
```

### 消息隔离策略

| 消息键 | 所属 | 用途 | 生命周期 |
|--------|------|------|----------|
| `messages` | 主智能体 | 全局消息流，项目经理视角 | 贯穿全程 |
| `temp_task_messages` | 子智能体 | 单次任务的工具调用交互 | 任务结束后丢弃 |
| `task_messages` | 主→写入 | 子智能体的最终结果 | 传递给写入智能体 |
| `temp_write_note_messages` | 写入智能体 | write_note 工具调用消息 | 笔记保存后丢弃 |

**设计意图**：避免子图执行过程中的中间消息污染主智能体上下文，既节省 token 又避免决策干扰。

---

## 九、笔记系统：共享记忆机制

笔记 (`note: dict[str, Note]`) 是多智能体之间的**共享知识库**：

| 操作 | 执行者 | 工具 | 说明 |
|------|--------|------|------|
| 写入 | 写入智能体 | `write_note` | 保存任务成果，标记 type |
| 读取列表 | 主智能体 | `ls` | 查看所有笔记名称 |
| 读取内容 | 主智能体 / 子智能体 | `query_note` | 获取具体笔记内容 |
| 更新 | 写入智能体 | `update_note` | 修改已有笔记 |
| 消费 | 结构化智能体 | (直接读取 state) | 仅处理 diet_plan 类型 |

### 笔记命名示例

```
"golden_retriever_puppy_nutrition"    → type: research
"suitable_ingredients_for_puppy"       → type: research
"week_1_diet_plan"                     → type: diet_plan
"week_2_diet_plan"                     → type: diet_plan
"week_3_diet_plan"                     → type: diet_plan
"week_4_diet_plan"                     → type: diet_plan
```

### 防重名机制

```python
# note.py:75-78
if file_name in state["note"]:
    file_name = file_name + "_" + str(len(notes[file_name].content))
```

---

## 十、工具体系

### 按智能体分类

#### 主智能体工具 (5个)

| 工具 | 来源 | 调用限制 | 用途 |
|------|------|----------|------|
| `write_plan` | langchain_dev_utils | 仅一次 | 初始化任务列表 |
| `update_plan` | langchain_dev_utils | 多次 | 更新任务状态 (done/in_progress) |
| `transfor_task_to_subagent` | 自定义 | 每任务一次 | 委派任务给子智能体 |
| `ls` | note.py | 无限制 | 列出所有笔记名称 |
| `query_note` | note.py | 无限制 | 查询笔记内容 |

#### 子智能体工具 (3个)

| 工具 | 来源 | 调用限制 | 用途 |
|------|------|----------|------|
| `tavily_search` | langchain_tavily | **每任务仅一次** | 互联网搜索 (max_results=3) |
| `query_note` | note.py | 无限制 | 查询历史笔记 |
| `get_weather` | 自定义 | 无限制 | 天气查询 (示例工具) |

#### 写入智能体工具 (2个)

| 工具 | 来源 | 调用方式 | 用途 |
|------|------|----------|------|
| `write_note` | note.py | `tool_choice` 强制调用 | 写入笔记 |
| `update_note` | note.py | 按需调用 | 更新笔记 |

### 工具绑定配置

```python
# 主智能体: 串行调用，防止同时触发多个子任务
model.bind_tools(tools, parallel_tool_calls=False)

# 写入智能体: 强制调用 write_note，确保结果一定被保存
model.bind_tools([write_note], tool_choice="write_note")
```

---

## 十一、模型分级策略

| 模型角色 | 当前配置 | 特点 | 选型理由 |
|----------|---------|------|----------|
| plan_model (主规划) | dashscope:qwen3.5-plus | 强大 | 关键决策：任务分解质量决定全局 |
| sub_model (子执行) | dashscope:qwen3.5-plus | 强大 | 核心产出：饮食计划质量直接影响用户 |
| write_model (写入) | dashscope:qwen-flash | 快速 | 仅格式化文本，不需要强推理 |
| summary_model (摘要) | dashscope:qwen-flash | 快速 | 仅生成一句话摘要 |
| report_model (结构化) | dashscope:qwen3.5-plus | 强大 | 结构化解析需要精确理解 |

**首次规划使用 thinking 模式**（深度思考），后续迭代使用普通模式提高效率。

---

## 十二、流式进度事件体系

### 19 种事件覆盖全生命周期

| 阶段 | 事件类型 | 触发时机 | progress 范围 |
|------|---------|---------|---------------|
| **规划** | `plan_creating` | 首次调用，无 plan | 5% |
| | `plan_created` | write_plan 完成 | 10% |
| | `plan_updated` | update_plan 完成 | 10-80% (动态) |
| **委派** | `task_delegating` | transfor_task_to_subagent | 10-80% |
| **执行** | `task_executing` | 子智能体开始 | - |
| | `task_searching` | 调用 tavily_search | - |
| | `task_querying_note` | 调用 query_note | - |
| | `task_completed` | 子智能体完成 | - |
| **记录** | `note_saving` | write 开始 | - |
| | `note_saved` | write 完成 | - |
| | `summary_generating` | summary 开始 | - |
| | `summary_generated` | summary 完成 | - |
| **结构化** | `structuring` | 开始解析笔记 | - |
| | `structuring_retry` | 解析失败重试 | - |
| | `structured` | 解析成功 | 85% |
| **汇总** | `gathering` | 所有任务完成 | 80% |
| | `completed` | 最终报告生成 | 100% |
| **通用** | `error` / `info` | 异常或信息 | - |

### 进度估算算法

```python
def _estimate_progress(state) -> int:
    """根据 plan 完成比例映射到 10-80% 区间"""
    done_count / total_count → 10% + (ratio * 70%)
    # 结构化阶段占 80-100%
```

### 流式传输架构

```
Agent 节点 → emit_progress() → get_stream_writer()
                                    ↓
                         LangGraph custom stream
                                    ↓  (子图事件自动冒泡)
                         API 层 stream.py
                         astream(stream_mode=["custom", "updates"])
                                    ↓
                         SSE 格式化 → 前端进度条
```

---

## 十三、关键设计决策及其业务原因

| 设计决策 | 业务原因 |
|---------|---------|
| 主智能体"只管不做" | 避免单 LLM 上下文过长导致质量下降；项目经理不需要懂营养学细节 |
| 子智能体先搜索后引用笔记 | 模拟真实调研流程——先查外部资料，再结合已有知识综合判断 |
| write 和 summary 并行 | 摘要只是回给项目经理的"一句话汇报"，与笔记保存无依赖 |
| 结构化阶段 Send 并行 | 4 周计划相互独立，并行避免单个失败阻塞全部 |
| 模型分级 (plus/flash) | 关键决策用强模型，格式化用快模型，平衡质量与成本 |
| `additional_nutrients` 开放字典 | 不同宠物的特殊营养需求无法穷举，开放兼容 |
| 月龄用 `int`（月）而非年 | 幼犬/幼猫成长以月计，3月龄和6月龄营养需求差异巨大 |
| `tavily_search` 每任务限一次 | 控制成本 + 迫使 LLM 精心设计搜索查询 |
| `parallel_tool_calls=False` | 确保主智能体串行决策，避免同时委派多个任务导致混乱 |
| `tool_choice="write_note"` | 强制写入智能体必须调用保存工具，确保成果不丢失 |
| `final_output` dict 累积 | 避免 astream 后再调 ainvoke 导致图被执行两次 |
| 结构化解析失败重试 | 这是 Markdown→Pydantic 的最脆弱环节，重试提高成功率 |

---

## 十四、LLM 调用成本估算

对于一次完整的月度饮食计划生成（假设 6 个子任务）：

| 阶段 | 调用次数 | 使用模型 | 说明 |
|------|---------|---------|------|
| 主智能体规划 | 2-3 次 | qwen3.5-plus | 首次深度思考 + 后续迭代 |
| 主智能体调度 | ~12 次 | qwen3.5-plus | 每个任务: 委派1次 + 更新1次 |
| 子智能体执行 | ~10 次 | qwen3.5-plus | 每任务 1-2 次 (含工具调用) |
| 写入智能体 | 6 次 | qwen-flash | 每任务 1 次 |
| 摘要生成 | 6 次 | qwen-flash | 每任务 1 次 |
| 结构化解析 | 4-8 次 | qwen3.5-plus | 4 个周计划，含可能的重试 |
| **总计** | **~40-45 次** | - | - |

---

## 十五、已知约束与注意事项

### 不可违反

- `astream` 完成后**绝对不能**再调用 `ainvoke`（图会执行两次）
- `tavily_search` 每子任务**仅限一次**
- `write_plan` **仅能调用一次**（初始化）
- 主智能体**不直接执行任务**，必须通过 `transfor_task_to_subagent` 委派

### 需要注意

- 结构化解析是**最脆弱的环节**，依赖 LLM 正确理解 Pydantic Schema
- 子智能体的饮食计划模板质量直接影响结构化解析成功率
- `note_reducer` 是简单的 dict merge，后写入的同名笔记会覆盖前面的
- `emit_progress` 在 `ainvoke` 模式下静默跳过，无需条件判断

---

## 十六、文件索引

| 文件路径 | 职责 | 业务关联 |
|----------|------|---------|
| `src/agent/graph.py` | 主图构建 | 定义智能体间连接关系 |
| `src/agent/state.py` | 状态定义 | 数据流的骨架 |
| `src/agent/node.py` | call_model + gather | 任务分解决策 + 最终汇总 |
| `src/agent/tools.py` | 工具定义 | 所有可用能力 |
| `src/agent/stream_events.py` | 进度事件 | 前端可观测性 |
| `src/agent/prompts/prompt.py` | 提示词 | 业务规则的核心载体 |
| `src/agent/utils/struct.py` | 数据结构 | 营养学领域模型 |
| `src/agent/utils/context.py` | 运行时配置 | 模型选择与提示词配置 |
| `src/agent/entity/note.py` | 笔记系统 | 共享记忆机制 |
| `src/agent/sub_agent/node.py` | 子智能体 | 任务执行核心逻辑 |
| `src/agent/write_agent/node.py` | 写入智能体 | 知识记录与摘要 |
| `src/agent/structrue_agent/node.py` | 结构化智能体 | 自然语言→结构化数据 |
| `src/utils/strtuct.py` | PetInformation | 宠物信息输入模型 |
| `src/api/services/plan_service.py` | API 服务层 | 流式执行与结果收集 |
| `src/api/utils/stream.py` | 流式工具 | SSE 事件转发 |
