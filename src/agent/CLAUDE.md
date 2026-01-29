# Agent 模块文档

[根目录](../../CLAUDE.md) > **src/agent**

---

## 变更记录 (Changelog)

### 2025-01-29
- 初始化 Agent 模块文档
- 完成多智能体架构分析
- 添加节点和工具详细说明

---

## 模块职责

Agent 模块是项目的**核心模块**，实现了基于 LangGraph 的**多智能体协作系统**，负责：

- 🎯 **任务规划与分解**: 主智能体将用户需求拆分为可执行的子任务
- 🤝 **智能体协调**: 管理主智能体、子智能体、写入智能体和结构化智能体的协作
- 📝 **笔记管理**: 维护任务执行过程中的笔记系统
- 📊 **状态管理**: 管理多智能体系统的状态流转
- 🛠️ **工具调用**: 提供任务执行所需的工具集
- 📄 **报告生成**: 将执行结果结构化为最终的宠物饮食计划报告

---

## 目录结构

```
src/agent/
├── __init__.py
├── graph.py              # 主图构建（LangGraph StateGraph）
├── state.py              # 状态定义（StateInput, State, StateOutput）
├── node.py               # 主节点实现（call_model, gather, tool_node）
├── tools.py              # 工具定义（9个工具函数）
├── prompts/              # 提示词模块
│   ├── __init__.py
│   └── prompt.py         # 5个核心提示词
├── utils/                # 工具模块
│   ├── __init__.py
│   ├── struct.py         # 数据结构（7个Pydantic模型）
│   └── context.py        # 运行时上下文（Context数据类）
├── entity/               # 实体模块
│   ├── __init__.py
│   └── note.py           # 笔记实体（Note类和工具工厂）
├── sub_agent/            # 子智能体模块
│   ├── __init__.py
│   ├── graph.py          # 子智能体图构建
│   ├── state.py          # 子智能体状态
│   └── node.py           # 子智能体节点
├── write_agent/          # 写入智能体模块
│   ├── __init__.py
│   ├── graph.py          # 写入智能体图构建
│   ├── state.py          # 写入智能体状态
│   └── node.py           # 写入智能体节点
└── structrue_agent/      # 结构化智能体模块（注意拼写：structrue）
    ├── __init__.py
    ├── graph.py          # 结构化智能体图构建
    ├── state.py          # 结构化智能体状态
    └── node.py           # 结构化智能体节点
```

---

## 入口与启动

### 主图入口

**文件**: `graph.py`
**函数**: `build_graph_with_langgraph_studio()`

```python
def build_graph_with_langgraph_studio():
    """构建主图，供 LangGraph Studio 使用"""
    graph = StateGraph(State, input_schema=StateInput, output_schema=StateOutput, context_schema=Context)
    graph.add_node("call_model", call_model)
    graph.add_node("tools", tool_node)
    graph.add_node("subagent", build_sub_agent())
    graph.add_node("write_note", build_write_agent())
    graph.add_node("structure_report", build_structure_agent())
    graph.add_node("gather", gather)

    # 定义边连接
    graph.add_edge("__start__", "call_model")
    graph.add_edge("tools", "call_model")
    graph.add_edge("subagent", "write_note")
    graph.add_edge("write_note", "call_model")
    graph.add_edge("structure_report", "gather")

    return graph.compile()
```

### LangGraph 配置

**文件**: `langgraph.json` (项目根目录)

```json
{
    "dependencies": ["."],
    "graphs": {
        "pet_food": "./src/agent/graph.py:build_graph_with_langgraph_studio"
    }
}
```

### 启动方式

```bash
# 使用 LangGraph Studio
langgraph dev

# 访问 UI 测试 pet_food 图
```

---

## 对外接口

### 主图节点

| 节点名 | 文件 | 职责 | 输入 | 输出 |
|--------|------|------|------|------|
| **call_model** | `node.py` | 主智能体LLM调用，任务规划 | State | Command[工具/子智能体/结构化] |
| **tools** | `node.py` | 计划管理工具执行 | State | State (更新plan和messages) |
| **subagent** | `sub_agent/graph.py` | 子智能体执行具体任务 | State | State (task_messages) |
| **write_note** | `write_agent/graph.py` | 写入智能体保存笔记 | State | State (note, messages) |
| **structure_report** | `structrue_agent/graph.py` | 结构化智能体解析周计划 | StructState | State (weekly_diet_plans) |
| **gather** | `node.py` | 汇总生成最终报告 | State | StateOutput (report) |

### 子智能体节点

| 节点名 | 职责 | 输入 | 输出 |
|--------|------|------|------|
| **subagent_call_model** | 子智能体LLM调用，执行任务 | SubAgentState | Command[工具/结束] |
| **sub_tools** | 子智能体工具执行（搜索、查询） | SubAgentState | SubAgentState |

### 写入智能体节点

| 节点名 | 职责 | 输入 | 输出 |
|--------|------|------|------|
| **write** | 格式化任务结果，调用write_note | WriteState | WriteState (temp_write_note_messages) |
| **write_tool** | 执行write_note工具 | WriteState | WriteState (note) |
| **summary** | 生成任务摘要 | WriteState | WriteState (messages) |

### 结构化智能体节点

| 节点名 | 职责 | 输入 | 输出 |
|--------|------|------|------|
| **structure_report** | 将笔记解析为WeeklyDietPlan | StructState | Command[更新周计划/结束] |

---

## 关键依赖与配置

### 依赖包

**核心依赖**:
- `langgraph>=0.6.6`: 图状态管理
- `langchain>=0.3.27`: LLM 集成
- `langchain-dev-utils`: 开发工具（PlanStateMixin, 工具工厂）
- `pydantic`: 数据验证

**集成依赖**:
- `langchain-deepseek`: DeepSeek 模型
- `langchain-tavily`: Tavily 搜索
- `python-dotenv`: 环境变量

### 运行时上下文配置

**文件**: `utils/context.py`

```python
@dataclass
class Context:
    # 模型配置
    plan_model: str = "dashscope:qwen3-max"           # 主智能体模型
    sub_model: str = "zai:glm-4.7"                    # 子智能体模型
    write_model: str = "dashscope:qwen-flash"         # 写入智能体模型
    summary_model: str = "dashscope:qwen-flash"       # 摘要模型
    report_model: str = "zai:glm-4.7"                 # 报告生成模型

    # 提示词配置
    plan_prompt: str = PLAN_MODEL_PROMPT
    sub_prompt: str = SUBAGENT_PROMPT
    write_prompt: str = WRITE_PROMPT
    summary_prompt: str = SUMMARY_PROMPT
```

### 环境变量

```bash
# 必需
DASHSCOPE_API_KEY=<your-key>        # 阿里云DashScope
TAVILIY_API_KEY=<your-key>          # Tavily搜索

# 可选
ZAI_API_KEY=<your-key>              # ZAI模型
DEEPSEEK_API_KEY=<your-key>         # DeepSeek模型
MOONSHOT_API_KEY=<your-key>         # Moonshot模型
SILICONFLOW_API_KEY=<your-key>      # SiliconFlow模型
```

---

## 数据模型

### 状态继承关系

```
MessagesState (langchain_core)
    ↓
StateInput
    ├── messages: list[AnyMessage]
    └── pet_information: PetInformation

MessagesState + PlanStateMixin + NoteStateMixin
    ↓
State
    ├── messages: list[AnyMessage]
    ├── plan: list[Todo]              # 待办事项列表
    ├── note: dict[str, Note]         # 笔记字典
    ├── pet_information: PetInformation
    ├── task_messages: list[AnyMessage]
    ├── weekly_diet_plans: list[WeeklyDietPlan]
    └── report: PetDietPlan

StateInput + report
    ↓
StateOutput
    ├── messages: list[AnyMessage]
    ├── pet_information: PetInformation
    └── report: PetDietPlan
```

### 核心数据结构

**文件**: `utils/struct.py`

| 数据结构 | 字段 | 用途 |
|----------|------|------|
| **PetInformation** | pet_type, pet_breed, age, pet_weight, pet_health_status | 宠物基本信息 |
| **Macronutrients** | protein, fat, carbohydrates, dietary_fiber | 宏量营养素 |
| **Micronutrients** | vitamin_a/c/d, calcium, iron, sodium, potassium, cholesterol, additional_nutrients | 微量营养素 |
| **FoodItem** | name, weight, macro_nutrients, micro_nutrients, recommend_reason | 食物项 |
| **SingleMealPlan** | oder, time, food_items, cook_method | 单餐计划 |
| **DailyDietPlan** | daily_diet_plans: list[SingleMealPlan] | 每日计划 |
| **WeeklyDietPlan** | oder, diet_adjustment_principle, weekly_diet_plan, weekly_special_adjustment_note, suggestions | 每周计划 |
| **MonthlyDietPlan** | monthly_diet_plan: list[WeeklyDietPlan] (max 4周) | 月度计划 |
| **PetDietPlan** | pet_information, ai_suggestions, pet_diet_plan | 最终报告 |

---

## 核心工具系统

### 工具分类

#### 1. 计划管理工具（主智能体）

**文件**: `tools.py`

| 工具 | 说明 | 调用限制 | 参数 |
|------|------|----------|------|
| `write_plan` | 初始化任务列表 | **仅一次**，在开始时 | plan: list[str] |
| `update_plan` | 更新任务状态 | 可多次调用 | update_plans: list[Todo] |

#### 2. 笔记管理工具（主智能体）

| 工具 | 说明 | 参数 |
|------|------|------|
| `ls` | 列出所有笔记名称 | 无 |
| `query_note` | 查询笔记内容 | file_name: str |

#### 3. 任务委派工具（主智能体）

| 工具 | 说明 | 参数 |
|------|------|------|
| `transfor_task_to_subagent` | 委派任务给子智能体 | content: str (必须与todo内容一致) |

#### 4. 搜索和查询工具（子智能体）

| 工具 | 说明 | 调用限制 |
|------|------|----------|
| `tavily_search` | 互联网搜索 | **每任务一次** |
| `query_note` | 查询历史笔记 | 无限制 |
| `get_weather` | 查询天气（示例） | 无限制 |

#### 5. 笔记写入工具（写入智能体）

| 工具 | 说明 | 参数 |
|------|------|------|
| `write_note` | 写入笔记 | file_name, content, type: Literal["research", "diet_plan"] |
| `update_note` | 更新笔记 | file_name, origin_content, new_content |

### 工具实现示例

```python
# 计划管理工具（来自 langchain_dev_utils）
write_plan = create_write_plan_tool(
    name="write_plan",
    description="""用于写入计划的工具,只能使用一次，在最开始的时候使用"""
)

update_plan = create_update_plan_tool(
    name="update_plan",
    description="""用于更新计划的工具，可以多次使用来更新计划进度"""
)

# 笔记管理工具（来自 entity/note.py）
ls = create_ls_tool(
    name="ls",
    description="""用于列出所有已保存的笔记名称"""
)

query_note = create_query_note_tool(
    name="query_note",
    description="""用于查询笔记"""
)

write_note = create_write_note_tool(
    name="write_note",
    description="""用于写入笔记的工具""",
    message_key="temp_write_note_messages"  # 使用独立的消息键
)
```

---

## 提示词系统

### 提示词列表

**文件**: `prompts/prompt.py`

#### PLAN_MODEL_PROMPT（主智能体）

**目标**: 指导主智能体进行任务规划和委派

**关键内容**:
```python
"""
你是一个智能任务助手，专门帮助用户高效完成各种任务。

角色特性：
你现在主要的任务场景是为用户制定宠物食谱：
定制一个月的营养计划，并分为四周，每周之间不一样，但是每周内统一食谱饮食方便采购食材。

请严格按照以下步骤执行用户任务：
1. 任务分解 - 将用户任务拆分为具体的子任务，并调用write_plan工具创建完整的任务列表
2. 任务执行 - 按顺序执行任务列表中的每个子任务：
   - 首次必须调用write_plan工具写入任务列表
   - 完成每个任务后，立即调用update_plan工具更新任务状态
3. 结果总结 - 当所有任务都完成后，向用户提供完整的执行总结报告

重要提醒：
- 必须首先使用write_plan工具初始化任务列表
- 每完成一个任务都要及时更新任务状态
- 每个任务都必须实际执行，且你只需要将任务委派给sub agent
- 对于任务执行结果的查询：你可以通过ls工具查看文件记录，也可以通过query_note查询相关笔记内容
"""
```

#### SUBAGENT_PROMPT（子智能体）

**目标**: 指导子智能体执行具体任务

**关键内容**:
```python
"""
你是一个专业的AI任务执行助手，专注于高效完成指定的子任务。

## 任务上下文
用户总体需求：{user_requirement}
**当前子任务：{task_name}**

## 执行准则
1. 精准理解 - 仔细分析任务的核心目标和具体要求
2. 智能规划 - 评估可用工具和资源，选择最优执行路径
3. 高效执行 - 提供准确、可操作的解决方案
4. 简洁沟通 - 直接回应任务要求，避免冗余解释

## 历史信息查询
当前可用的历史任务记录：{history_files}

**重要提示：**
- 如果当前任务需要依赖之前的执行结果，请优先使用 query_note 工具查询相关历史记录
- 工具使用约束：**tavily_search**工具在每个任务仅限调用一次

## 如果任务是制定具体的单周营养计划，遵循下面的报告模式：
[详细的饮食计划模板]
"""
```

#### WRITE_PROMPT（写入智能体）

**目标**: 指导写入智能体格式化并保存笔记

```python
"""
请根据当前的任务的返回结果，调用`write_note`函数将笔记内容进行写入
{task_result}

如果是确切的某周宠物餐食计划，写note的type应是diet_plan
请确保笔记内容是Markdown格式，且你应该对当前任务的返回结果进行概述和重写，确保语义通顺。
文件名请使用简洁明确的名称，无需包含文件扩展名。
"""
```

#### SUMMARY_PROMPT（写入智能体）

**目标**: 生成简洁的任务摘要

```python
"""
请根据当前的任务的返回结果，写一个简洁明了的概括
{task_result}

请确保摘要的内容简短，不能长篇大论，且摘要的内容要简洁明了，不能有冗余信息。
"""
```

#### report_prompt（结构化智能体）

**目标**: 指导结构化智能体解析笔记为结构化数据

```python
"""
请你根据我给出的内容生成结构化报告
"""
```

---

## 节点实现详解

### call_model 节点（主智能体）

**文件**: `node.py`

**职责**: 主智能体的核心决策节点

**工作流程**:

1. **加载模型和工具**
```python
model = load_chat_model(model=run_time.context.plan_model, max_retries=3)
tools = [write_plan, update_plan, transfor_task_to_subagent, ls, query_note]
bind_model = model.bind_tools(tools, parallel_tool_calls=False)
```

2. **构建提示词**
```python
messages = [
    SystemMessage(content=run_time.context.plan_prompt.format(pet_information=info)),
    *state["messages"]
]
```

3. **调用LLM**
```python
response = await bind_model.ainvoke(messages)
```

4. **路由决策**
```python
if has_tool_calling(response):
    name, _ = parse_tool_calling(response, first_tool_call_only=True)
    if name == "transfor_task_to_subagent":
        return Command(goto="subagent", update={...})
    else:
        return Command(goto="tools", update={...})
else:
    # 所有任务完成，触发结构化智能体
    return Command(goto=[Send("structure_report", {...}) for note in notes])
```

**关键特性**:
- 第一次调用使用 thinking 模式（深度思考）
- 后续调用使用普通模式（提高效率）
- 工具调用串行执行（parallel_tool_calls=False）
- 使用 Send 并行触发结构化智能体

### gather 节点

**文件**: `node.py`

**职责**: 汇总所有周计划，生成最终报告

```python
async def gather(state: State):
    return {
        "report": PetDietPlan(
            pet_information=state["pet_information"],
            pet_diet_plan=MonthlyDietPlan(
                monthly_diet_plan=state["weekly_diet_plans"]
            ),
            ai_suggestions=state["messages"][-1].content,
        )
    }
```

### subagent_call_model 节点（子智能体）

**文件**: `sub_agent/node.py`

**职责**: 子智能体执行具体任务

**工作流程**:

1. **提取任务名称**
```python
last_ai_message = state["messages"][-1]
_, args = parse_tool_calling(last_ai_message, first_tool_call_only=True)
task_name = args.get("content", "")
```

2. **加载模型和工具**
```python
model = load_chat_model(model=run_time.context.sub_model, max_retries=3).bind_tools(
    [get_weather, tavily_search, query_note]
)
```

3. **构建提示词**
```python
messages = [
    SystemMessage(content=run_time.context.sub_prompt.format(
        task_name=task_name,
        history_files=list(notes.keys()),
        user_requirement=state["messages"][0].content
    )),
    HumanMessage(content=f"我的任务是：{task_name}，请帮我完成,宠物的基础信息是{state['pet_information']}"),
    *state["temp_task_messages"]  # 历史交互
]
```

4. **路由决策**
```python
if has_tool_calling(response):
    return Command(goto="sub_tools", update={"temp_task_messages": [response]})
else:
    return Command(goto="__end__", update={"task_messages": [...response]})
```

**关键特性**:
- 使用独立的消息键 `temp_task_messages`（避免污染主消息）
- 提供历史笔记列表供查询
- 每任务搜索限制（通过提示词控制）

### write 和 summary 节点（写入智能体）

**文件**: `write_agent/node.py`

**write 节点**:
```python
async def write(state: WriteState):
    write_model = load_chat_model(model=run_time.context.write_model).bind_tools(
        [write_note], tool_choice="write_note"  # 强制调用
    )
    response = await write_model.ainvoke(
        run_time.context.write_prompt.format(task_result=task_content)
    )
    return {"temp_write_note_messages": [response]}
```

**summary 节点**:
```python
async def summary(state: WriteState):
    summary_model = load_chat_model(model=run_time.context.summary_model, max_retries=3)
    response = await summary_model.ainvoke(
        run_time.context.summary_prompt.format(task_result=task_content)
    )
    return {"messages": [ToolMessage(content=f"任务执行完成！此任务结果摘要：{response.content}")]}
```

**关键特性**:
- write 和 summary 并行执行（提高效率）
- write 使用 `tool_choice="write_note"` 强制调用
- 使用独立的消息键 `temp_write_note_messages`

### structure_report 节点（结构化智能体）

**文件**: `structrue_agent/node.py`

**职责**: 将笔记解析为结构化数据

**工作流程**:

1. **判断笔记类型**
```python
if state["temp_note"].type == "diet_plan":
    structure_model = model.with_structured_output(WeeklyDietPlan, include_raw=True)
```

2. **解析笔记**
```python
if state.get("failed_reason"):
    # 重试：使用失败原因
    response = await structure_model.ainvoke([
        SystemMessage(content=run_time.context.report_prompt),
        HumanMessage(content=state["failed_reason"])
    ])
else:
    # 首次：使用笔记内容
    response = await structure_model.ainvoke([
        SystemMessage(content=run_time.context.report_prompt),
        HumanMessage(content=state["temp_note"].content)
    ])
```

3. **处理结果**
```python
if response.get("parsed"):
    return Command(goto="__end__", update={"weekly_diet_plans": [response.get("parsed")]})
else:
    # 解析失败，重试
    return Command(goto="structure_report", update={"failed_reason": f"raw:{response.get('raw')}, error:{response.get('parsing_error')}"})
```

**关键特性**:
- 仅处理 `diet_plan` 类型的笔记
- 使用 LLM 的结构化输出功能（`with_structured_output`）
- 支持解析失败重试
- 使用 Send 并行处理多个笔记

---

## 笔记实体系统

### Note 数据结构

**文件**: `entity/note.py`

```python
class Note(BaseModel):
    content: str  # Markdown 格式的笔记内容
    type: Literal["research", "diet_plan", "diet_plan_summary"]
```

### 笔记状态管理

```python
class NoteStateMixin(TypedDict):
    note: Annotated[dict[str, Note], note_reducer]

def note_reducer(left: dict | None, right: dict | None):
    """合并笔记字典"""
    if left is None:
        return right
    elif right is None:
        return left
    else:
        return {**left, **right}
```

### 工具工厂函数

**文件**: `entity/note.py`

| 函数 | 说明 | 返回 |
|------|------|------|
| `create_write_note_tool()` | 创建写入笔记工具 | BaseTool |
| `create_ls_tool()` | 创建列出笔记工具 | BaseTool |
| `create_query_note_tool()` | 创建查询笔记工具 | BaseTool |
| `create_update_note_tool()` | 创建更新笔记工具 | BaseTool |

**示例**:
```python
write_note = create_write_note_tool(
    name="write_note",
    description="用于写入笔记的工具",
    message_key="temp_write_note_messages"  # 使用独立的消息键
)
```

---

## 工作流程示例

### 完整的饮食计划生成流程

```
1. 用户输入
   └─> StateInput(pet_information)

2. call_model (主智能体)
   ├─> 调用 write_plan 初始化任务列表
   └─> 调用 update_plan + transfor_task_to_subagent 委派第一个任务

3. subagent (子智能体)
   ├─> subagent_call_model
   │   ├─> 调用 tavily_search (每任务一次)
   │   ├─> 调用 query_note 查询历史
   │   └─> 返回任务结果
   └─> 返回 SubAgentState

4. write_note (写入智能体)
   ├─> write: 格式化内容，调用 write_note
   ├─> summary: 生成任务摘要
   └─> write_tool: 保存笔记到状态

5. 回到 call_model
   ├─> 调用 update_plan 更新任务状态
   └─> 调用 transfor_task_to_subagent 委派下一个任务

6. 重复步骤 3-5，直到所有任务完成

7. structure_report (结构化智能体，并行)
   ├─> 接收所有笔记 (通过 Send)
   ├─> 仅处理 type="diet_plan" 的笔记
   ├─> 使用 LLM 解析为 WeeklyDietPlan
   └─> 返回 weekly_diet_plans

8. gather
   └─> 汇总生成 PetDietPlan 报告

9. 输出
   └─> StateOutput(report)
```

---

## 测试与质量

### 测试状态

当前**未发现测试文件**。

### 建议的测试结构

```
tests/
├── __init__.py
├── conftest.py                    # pytest 配置
├── test_agent/                    # Agent 模块测试
│   ├── test_graph.py              # 图构建测试
│   ├── test_state.py              # 状态管理测试
│   ├── test_nodes.py              # 节点功能测试
│   ├── test_tools.py              # 工具测试
│   └── test_integration.py        # 集成测试
├── test_sub_agent/                # 子智能体测试
├── test_write_agent/              # 写入智能体测试
├── test_structure_agent/          # 结构化智能体测试
└── fixtures/                      # 测试夹具
    ├── pet_info.json
    └── mock_responses.json
```

### 测试建议

1. **单元测试**
   - 测试每个节点的输入输出
   - 测试工具函数的参数验证
   - 测试状态更新逻辑

2. **集成测试**
   - 测试完整的任务执行流程
   - 测试多智能体协作
   - 测试错误处理和重试

3. **Mock 测试**
   - Mock LLM 调用（避免实际 API 调用）
   - Mock 搜索工具
   - 使用预定义的响应

---

## 常见问题 (FAQ)

### Q1: 如何添加新的工具？

1. 在 `tools.py` 定义工具函数
2. 在对应节点的 `bind_tools` 中注册
3. 更新 `ToolNode` 的工具列表
4. 在提示词中添加工具使用说明

**示例**:
```python
# 1. 定义工具
@tool
async def new_tool(param: str):
    """工具描述"""
    return f"结果：{param}"

# 2. 注册到节点
model = load_chat_model(...).bind_tools([...new_tool])

# 3. 更新 ToolNode
tool_node = ToolNode([...new_tool])
```

### Q2: 如何修改任务规划逻辑？

修改 `prompts/prompt.py` 中的 `PLAN_MODEL_PROMPT`，确保：
- 明确任务分解的准则
- 强调使用 `write_plan` 初始化
- 强调使用 `update_plan` 更新
- 强调通过 `transfor_task_to_subagent` 委派任务

### Q3: 如何调整饮食计划模板？

修改 `prompts/prompt.py` 中的 `SUBAGENT_PROMPT`，在"##如果任务是制定具体的单周营养计划"部分添加或修改模板格式。

### Q4: 为什么子智能体每次只能搜索一次？

这是为了：
- 控制成本（Tavily API 按次收费）
- 避免上下文过长
- 强制子智能体精心设计搜索查询

如需修改，调整 `SUBAGENT_PROMPT` 中的搜索限制说明。

### Q5: 如何处理结构化解析失败？

系统已实现自动重试机制：
1. 首次失败时，保存 `failed_reason`
2. 使用失败原因重新调用 LLM
3. 最多重试一次（可通过循环增加次数）

如需改进，可考虑：
- 使用更强大的模型（如 GPT-4）
- 提供更详细的 prompt
- 使用 Few-Shot 示例

### Q6: 为什么笔记保存后查询不到？

检查：
1. 笔记是否正确保存到 `state["note"]`
2. `query_note` 工具的文件名是否正确
3. 是否在正确的智能体中查询（主智能体和子智能体都可查询）

### Q7: 如何调试多智能体系统？

1. **使用 LangGraph Studio**
   - 可视化查看图结构
   - 实时查看状态变化
   - 追踪消息流转

2. **添加日志**
```python
import logging
logging.basicConfig(level=logging.INFO)

async def call_model(state: State):
    logging.info(f"call_model 输入: {state}")
    # ...
    logging.info(f"call_model 输出: {command}")
    return command
```

3. **打印中间结果**
```python
async def gather(state: State):
    print(f"汇总的周计划数量: {len(state['weekly_diet_plans'])}")
    # ...
```

---

## 相关文件清单

### 核心文件

| 文件 | 行数估计 | 职责 |
|------|----------|------|
| `graph.py` | ~30 | 主图构建 |
| `state.py` | ~24 | 状态定义 |
| `node.py` | ~100 | 主节点实现 |
| `tools.py` | ~150 | 工具定义 |

### 提示词和数据

| 文件 | 行数估计 | 职责 |
|------|----------|------|
| `prompts/prompt.py` | ~130 | 5个核心提示词 |
| `utils/struct.py` | ~90 | 7个Pydantic模型 |
| `utils/context.py` | ~36 | 运行时上下文 |
| `entity/note.py` | ~200 | 笔记实体和工具工厂 |

### 子智能体模块

| 文件 | 行数估计 | 职责 |
|------|----------|------|
| `sub_agent/graph.py` | ~15 | 子智能体图构建 |
| `sub_agent/state.py` | ~11 | 子智能体状态 |
| `sub_agent/node.py` | ~80 | 子智能体节点 |

### 写入智能体模块

| 文件 | 行数估计 | 职责 |
|------|----------|------|
| `write_agent/graph.py` | ~19 | 写入智能体图构建 |
| `write_agent/state.py` | ~12 | 写入智能体状态 |
| `write_agent/node.py` | ~64 | 写入智能体节点 |

### 结构化智能体模块

| 文件 | 行数估计 | 职责 |
|------|----------|------|
| `structrue_agent/graph.py` | ~12 | 结构化智能体图构建 |
| `structrue_agent/state.py` | ~8 | 结构化智能体状态 |
| `structrue_agent/node.py` | ~76 | 结构化智能体节点 |

---

## 性能优化建议

1. **并行执行**
   - write 和 summary 节点已并行执行
   - structure_report 使用 Send 并行处理多个笔记
   - 考虑并行执行独立的子任务

2. **模型选择**
   - 主智能体使用强大模型（qwen3-max）确保规划质量
   - 子智能体使用平衡模型（glm-4.7）平衡成本和效果
   - 写入和摘要使用快速模型（qwen-flash）提高速度

3. **上下文管理**
   - 使用独立的消息键（`temp_task_messages`, `temp_write_note_messages`）避免消息污染
   - 限制搜索次数控制上下文长度
   - 定期清理不必要的消息历史

4. **缓存策略**
   - 考虑缓存搜索结果
   - 考虑缓存 LLM 响应（使用 langchain_cache）
   - 笔记已自动缓存在状态中

---

## 与其他模块的交互

### 与 RAG 模块

当前 Agent 模块**未直接使用** RAG 模块。

RAG 模块可能用于：
- 提供宠物营养知识库
- 检索食材营养信息
- 检索宠物健康建议

**集成方式**:
```python
# 在子智能体中添加 RAG 工具
from src.rag.milvus import MilvusManager

@tool
async def search_knowledge(query: str):
    """搜索宠物营养知识库"""
    milvus = MilvusManager()
    results = await milvus.search_with_hybrid_rerank(query, k=3)
    return results
```

### 与 Utils 模块

当前 Agent 模块内部的 `utils/` 提供数据结构和上下文，与项目根的 `src/utils/` 模块**无交互**。

---

## 扩展建议

### 1. 增强任务规划

- 添加任务优先级
- 支持任务依赖关系
- 支持任务并行执行

### 2. 增强笔记系统

- 支持笔记标签
- 支持笔记搜索
- 支持笔记导出

### 3. 增强错误处理

- 添加任务失败重试机制
- 添加异常捕获和恢复
- 添加任务回滚功能

### 4. 增强监控和日志

- 添加任务执行时间统计
- 添加工具调用次数统计
- 添加成本追踪

---

## 参考资源

- [LangGraph 文档](https://langchain-ai.github.io/langgraph/)
- [LangChain 文档](https://python.langchain.com/)
- [Pydantic 文档](https://docs.pydantic.dev/)
- 项目根文档: [../../CLAUDE.md](../../CLAUDE.md)
- RAG 模块文档: [../rag/CLAUDE.md](../rag/CLAUDE.md)
