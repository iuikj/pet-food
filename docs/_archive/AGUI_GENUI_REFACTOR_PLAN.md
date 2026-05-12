# AG-UI v2 GenUI 重构实施方案

> **目标**：把现有 `/agui-plan/run` 任务式生成页（顶层 PhaseTimeline + WeekAgentGrid 分桶布局）重构为 **chat-like 单一时间流 + 关键节点触发 inline GenUI 嵌入组件** 的形态，并接入 AI Elements (Vercel shadcn AI 组件库)。
>
> **创建**：2026-05-02
> **依赖文档**：[AGUI_INTEGRATION.md](./AGUI_INTEGRATION.md) (协议层踩坑) / [agui-langgraph-learn/06-AI-Elements适配度分析.md](../../agui-langgraph-learn/06-AI-Elements适配度分析.md)

---

## 0. TL;DR

```
┌─ PetHero (顶部宠物 + 总进度环 + 状态 chip)
├─ TimelineFeed (单一聊天式时间流,核心战场)
│   ▸ [phase] 研究启动
│   ▸ [ai] 我先调研... ▾
│   ▸ [tool: ingredient_search] 三文鱼 ▾
│   ▸ [plan_board] todo (默认展开)
│   ▸ [phase] 准备分发
│   ╔══ inline GenUI 嵌入 ══════╗
│   ║  WeekParallelBlock         ║
│   ║   W1 / W2 / W3 / W4        ║
│   ║   每张展开后内嵌子 Timeline║
│   ╚════════════════════════════╝
│   ▸ [phase] 4 周完成
│   ▸ [phase] ✓ 已完成
└─ ActionBar
```

**核心机制**：
1. 主流靠 `timestamp` 排序、按 `detail.view_type` 路由 widget — **不依赖任何 graph 节点名**
2. 第一个 `target=week_agent` 的 `subagent_spawn` 事件 → 主流当场 inline 嵌入一个 `WeekParallelBlock`
3. 此后所有 `node="week_agent_N"` 的事件 **不进主流**，吸附到对应第 N 张卡片
4. 每张卡片展开后内嵌**子 TimelineFeed**，递归同样的渲染逻辑
5. Widget 实现层借用 **AI Elements 的 shadcn 组件**（Tool / Message / Reasoning / Plan / Sources / Conversation），通过 50 行薄适配层把 CopilotKit 数据塑形为 AI SDK 形状

---

## 1. 背景与决策路径

### 1.1 演进历程

| 时间 | 决策 | 状态 |
|---|---|---|
| 2026-04-30 | v2 graph 接 AG-UI / CopilotKit v2 (聊天形态实验) | ✅ AGUITest.jsx 跑通 |
| 2026-05-01 | 决定做任务式（非对话式）GenUI | ✅ 方案 v1 |
| 2026-05-01 | 用户选定方案 A（emit_progress 双发） + Hero+按钮模式 + 独立结果页 + 完整方案 | ✅ 后端双发已落地 |
| 2026-05-02 上午 | 第一版前端落地（PhaseTimeline 三段卡 + WeekAgentGrid 顶层网格） | ❌ 误判用户需求 |
| 2026-05-02 中午 | 用户反驳：要 chat-like 实时流 + GenUI 触发，不要分桶看板 | ✅ 本文档形成 |

### 1.2 已经验证 / 不再变动的决策

- **方案 A：`emit_progress` 双发** — `stream_writer`（保 plan_service SSE）+ `adispatch_custom_event`（喂 AG-UI）
- **触发模式：进入页面显示 Hero + 启动按钮**（不自动启动）
- **结果落地：独立结果页 `/agui-plan/result`**
- **后端 v2 graph 零改业务逻辑** — 只在 progress_middleware 里加事件
- **前端事件接入：`agent.subscribe({ onCustomEvent })`** — 不用 `useRenderCustomMessages`（那是 chat view 专用）
- **节点名解耦：前端不硬编码任何 graph 节点名**，只识别 `node="week_agent_\d"` 这一稳定模式

### 1.3 本次重构的核心调整

| 维度 | v1 方案（已废弃） | v2 方案（本文档） |
|---|---|---|
| 主战场 | PhaseTimeline 三段卡片（research / dispatch / finalize） | TimelineFeed 单一时间流 |
| 4 周展示 | 顶层固定 WeekAgentGrid 网格 | 由 dispatch 事件触发 inline 嵌入 WeekParallelBlock |
| 事件归属 | 按 graph 节点名分桶 | 按 timestamp 排序，view_type 路由 |
| Widget 实现 | 自写折叠卡 + Tailwind 类 | AI Elements (Tool / Message / Reasoning / Plan / Sources) |
| 视觉风格 | 项目自己的 sage green | shadcn base-nova（已在 components.json 启用）+ AI Elements |

---

## 2. 系统现状（已就绪部分）

### 2.1 后端 v2 graph 架构

```
StateGraph (pet_food_v2)
├── plan_agent (deepagents.create_deep_agent)
│   ├── subagents: websearch / nutrition_calc / ingredient_query
│   ├── middleware: plan_agent_prompt + trigger_plan_agent + plan_progress_middleware
│   └── 节点名: "plan_agent"
├── generate_coordination_guide (create_agent + structured_output=CoordinationGuide)
│   └── 节点名: "generate_coordination_guide"
├── dispatch_weeks (纯 Python Send×4)
│   └── 节点名: "dispatch_weeks"
├── week_agent × 4 并行 (create_agent + WEEK_AGENT_TOOLS + week_progress_middleware)
│   ├── 工具: ingredient_search/detail/categories_tool, daily_calorie_tool, nutrition_requirement_tool
│   └── 节点名: "week_agent_{week_number}" (在 progress_middleware 中拼)
└── gather_and_structure (纯 Python 组装 + 1 次 LLM 生成 ai_suggestions)
    └── 节点名: "gather_and_structure"
```

**关键文件**：
- `src/agent/v2/node.py` — graph 节点定义
- `src/agent/v2/middlewares/progress_middleware.py` — `PlanProgressMiddleware` + `WeekProgressMiddleware`
- `src/agent/v2/sub_agents/` — 3 个 deepagents SubAgent
- `src/agent/v2/tools/` — 食材/营养工具

### 2.2 emit_progress 双发机制（已落地）

**文件**：`src/agent/common/stream_events.py`

```python
def emit_progress(event_type, message, **kwargs):
    payload = ProgressEvent(...).to_dict()

    # 通道 ❶ stream_writer (plan_service SSE 走这条)
    try:
        get_stream_writer()(payload)
    except Exception: pass

    # 通道 ❷ adispatch_custom_event (ag_ui_langgraph 走这条 → CopilotKit)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(adispatch_custom_event(event_type.value, payload))
    except RuntimeError:
        # sync 兜底
        dispatch_custom_event(event_type.value, payload)
    except Exception: pass
```

**当前事件来源约定**：
- 文本、reasoning、工具调用：走 AG-UI 标准 `TEXT_MESSAGE_* / REASONING_MESSAGE_* / TOOL_CALL_*`
- todo：优先从 `STATE_SNAPSHOT/STATE_DELTA` 的 `state.todos` 投影为 `plan_board`
- task subagent：`PlanProgressMiddleware.awrap_tool_call(task)` 发送 `detail.view_type=subagent_dispatch`
- weekagent：`dispatch_weeks` 发送 `detail.view_type=week_dispatch`

**`extract_reasoning(response: AIMessage) → (content, reasoning)`** 自动从 `additional_kwargs.reasoning_content` 或 `<think>...</think>` 抽 reasoning。

### 2.3 协议适配层（已就绪）

`src/api/agui_agent.py:DataclassAwareLangGraphAGUIAgent` 已处理：
1. dataclass `ContextV2` 注入（过滤 `thread_id` 等多余 key）
2. forwardedProps 业务字段 → ContextV2 实例化（`pet_information` dict → `PetInformation`）
3. 中断遗留 `role="reasoning"` 消息过滤
4. `get_schema_keys` 短路消除 introspection warning

### 2.4 前端 ContextualHttpAgent（已就绪）

`src/utils/contextualHttpAgent.js` 用闭包 box 共享 forwardedProps，绕开 `HttpAgent.clone()` 不跑 constructor 导致的 instance attribute 丢失（详见 AGUI_INTEGRATION.md Pit 13）。

### 2.5 AG-UI 事件接入（已确认）

CopilotKit v2 `useAgent({ agentId })` 返回的是 `{ agent: AbstractAgent }`，而 `AbstractAgent.subscribe(subscriber)` 可以监听所有 AG-UI 事件，其中：

```ts
interface AgentSubscriber {
    onCustomEvent?({ event }) => void  // event.name = ProgressEventType, event.value = ProgressEvent dict
    onRunFailed?({ error })
    onRunErrorEvent?({ event })
    // ... 还有 15+ 种事件钩子
}
```

**已实测**：浏览器 DEV 控制台能看到 `[AG-UI custom event] research_starting/plan_creating/...` 日志，事件流正常。

---

## 3. UI 形态终稿

### 3.1 顶层结构

```jsx
<AGUIPlanRun>                              // /agui-plan/run
  <CopilotKitProvider agents={{ pet_food_v2: agent }}>
    <PageHeader />
    <main>
      <PetHero progress={overallProgress} phase={phase} />     // 顶部宠物 + 进度环 + 状态 chip
      <TimelineFeed events={events} />                          // 唯一主战场
    </main>
    <PlanGenActionBar isRunning onCancel onStart />
  </CopilotKitProvider>
</AGUIPlanRun>
```

**删除**：
- `<PhaseTimeline events={events} />` — 完全删除文件
- `<WeekAgentGrid buckets={weekBuckets} />` — 完全删除文件

### 3.2 TimelineFeed 工作机制

**输入**：完整的 `events: ProgressEvent[]`

**渲染**：
1. 按 `timestamp` 升序排序
2. 合并 `tool_call started/completed`（同 `call_id`）为同一卡片，用最新 `status`
3. 检测 `view_type === "week_dispatch"` 事件 → 放入 `weekBuckets[N]`，主流只插入虚拟节点 `{ _kind: 'week_block' }`
4. 检测 `view_type === "subagent_dispatch"` 事件 → 放入 `subagentBuckets[subagent_id]`，主流只插入虚拟节点 `{ _kind: 'subagent_block' }`
5. 后续所有 `node` 匹配 `^week_agent_\d$` 的事件 → 不渲染到主流，吸附到 `weekBuckets[N]`
6. 后续所有带 `detail.agent_scope="subagent"` + `detail.subagent_id` 的事件 → 不渲染到主流，吸附到 `subagentBuckets[subagent_id]`
7. 渲染：
   - 普通事件 → `<WidgetSwitch event={ev} />`（按 `view_type` 路由 widget）
   - 虚拟 `week_block` → `<WeekParallelBlock buckets={weekBuckets} />`
   - 虚拟 `subagent_block` → `<SubAgentParallelBlock cards={subagentCards} buckets={subagentBuckets} />`

**核心算法**（伪代码）：

```js
function organizeEvents(events) {
    const sorted = [...events].sort(byTimestamp);
    const merged = mergeToolCalls(sorted);  // 合并 started+completed

    const mainStream = [];
    const weekBuckets = { 1: [], 2: [], 3: [], 4: [] };
    const subagentBuckets = {};
    const subagentCards = new Map();
    let weekBlockInserted = false;
    let subagentBlockInserted = false;

    for (const ev of merged) {
        const m = ev.node?.match(/^week_agent_(\d)$/);
        if (m) {
            // week_agent 事件 → 仅入 bucket，不进主流
            weekBuckets[Number(m[1])].push(ev);
            continue;
        }

        if (ev.detail?.view_type === 'week_dispatch') {
            weekBuckets[ev.detail.week_number]?.push(ev);
            if (!weekBlockInserted) {
                mainStream.push({ _kind: 'week_block' });
                weekBlockInserted = true;
            }
            continue;
        }

        if (ev.detail?.view_type === 'subagent_dispatch') {
            const id = ev.detail.subagent_id || ev.detail.call_id;
            subagentCards.set(id, { id, dispatchEvent: ev });
            subagentBuckets[id] ||= [];
            subagentBuckets[id].push(ev);
            if (!subagentBlockInserted) {
                mainStream.push({ _kind: 'subagent_block' });
                subagentBlockInserted = true;
            }
            continue;
        }

        mainStream.push(ev);
    }
    return { mainStream, weekBuckets, subagentBuckets, subagentCards: [...subagentCards.values()] };
}
```

### 3.3 WeekParallelBlock — GenUI 触发逻辑（核心创新）

```jsx
<WeekParallelBlock buckets={weekBuckets}>
  <Conversation /* AI Elements 容器 */>
    <header>4 周并行 SubAgent</header>
    <Grid cols={2}>
      {[1,2,3,4].map(n => (
        <WeekAgentCard key={n} weekNumber={n} events={buckets[n]} />
      ))}
    </Grid>
  </Conversation>
</WeekParallelBlock>
```

**WeekAgentCard 折叠态**：
- 标题：`第N周 · {主题标签}`
- 状态 chip：从最后一条 `week_*` 事件派生（planning / searching / writing / completed）
- 副标题：最后一条事件的 message
- 进度条：不再渲染，AG-UI run 页面不消费百分比 progress
- 默认折叠

**WeekAgentCard 展开态**：
```jsx
<motion.div>
  {/* 内嵌一个子 TimelineFeed,递归同样的渲染逻辑 */}
  <TimelineFeed events={events} compact />
</motion.div>
```

子 TimelineFeed 使用 `nested: true`，不再二次拆分 week/subagent block，所以表现为纯粹的 widget 列表。

### 3.4 不要做的事（红线）

| ❌ | ✅ |
|---|---|
| 按 graph 节点名硬编码分桶到 PhaseTimeline | 按时间排序 + view_type 路由 |
| 顶层固定 4 张 Week 卡片网格 | 由 week_dispatch 事件触发出现 |
| 每个 phase 一张卡片"装载"对应事件 | 单一 chat-like 时间流 |
| 渲染 graph 拓扑 / 节点连线 | 隐藏 graph 结构，纯事件流 |
| 自己写折叠卡片 / 消息气泡 | 用 AI Elements 的现成组件 |

---

## 4. 后端待补强（v2 progress_middleware）

### 4.1 现状

`v2/middlewares/progress_middleware.py` 已经发：
- `RESEARCH_STARTING / PLAN_CREATING / PLAN_UPDATED / PLAN_CREATED / RESEARCH_TASK_DELEGATING`（plan_agent 阶段）
- `WEEK_PLANNING / WEEK_SEARCHING / WEEK_WRITING / WEEK_PLAN_READY / WEEK_COMPLETED`（week_agent 阶段）
- `RESEARCH_FINALIZING / DISPATCHING / GATHERING / STRUCTURING / STRUCTURED / COMPLETED`（其他节点）

**缺失**：聊天式时间流所需的细粒度事件
- `ai_message`（每次 model_call 之后的 AI 文本输出 — 含 reasoning）
- `tool_call started`（工具调用前）
- `tool_call completed`（工具调用后，含 result）
- `plan_snapshot`（deepagents 的 todo 列表，每次 write_todos / update_todos 后）
- `subagent_dispatch`（plan_agent 调 subagent 时）
- `week_dispatch`（dispatch_weeks 节点的 4 个 Send 之前）

### 4.2 实施位置

#### A. PlanProgressMiddleware.awrap_tool_call

当前只在 deepagents `task` / subagent 类工具上发送业务自定义事件，不重复发送 AG-UI 标准工具事件：

```python
info = SubAgentInfo(
    input_message=tool_args["description"],
    subagent_id=sha256(normalized_description)[:16],
)

emit_progress(
    ProgressEventType.Research.TASK_DELEGATING,
    f"委派 -> {subagent_type}: {info.input_message}",
    node="plan_agent",
    detail={
        "view_type": ViewType.SUBAGENT_DISPATCH.value,
        "subagent_id": info.subagent_id,
        "call_id": tool_call["id"],
        "agent_scope": "subagent",
    },
)

request.state["is_subagent"] = True
request.state["subagent_info"] = info
request.state["parent_call_id"] = tool_call["id"]
```

#### B. SubAgentProgressMiddleware

子 agent 内部事件依赖 `ProgressState.subagent_info` 路由：

```python
emit_progress(
    ProgressEventType.Task.EXECUTING,
    "SubAgent 开始执行",
    node=f"subagent_{subagent_id}",
    detail={"agent_scope": "subagent", "subagent_id": subagent_id},
)
```

#### C. WeekProgressMiddleware

week agent 只发送业务 phase，不重复标准 `TOOL_CALL_*`：

```python
emit_progress(
    ProgressEventType.Week.SEARCHING,
    "第 N 周：正在查询食材营养详情",
    node=f"week_agent_{week_number}",
    detail={"agent_scope": "week", "agent_id": f"week_agent_{week_number}"},
)
```

#### D. dispatch_weeks 节点

`v2/node.py:dispatch_weeks` 在 `for assignment in guide.weekly_assignments:` 之前加：

```python
for assignment in guide.weekly_assignments:
    await aemit_progress(
        ProgressEventType.Task.DELEGATING,
        f"委派 -> week_agent: {task_name}",
        node="dispatch_weeks",
        task_name=task_name,
        detail={
            "view_type": ViewType.WEEK_DISPATCH.value,
            "target": "week_agent",
            "task_name": task_name,
            "week_number": assignment.week_number,
        },
    )
    sends.append(Send(...))
```

### 4.3 风险与降级

- 如果 `last_ai.tool_calls[N].get("name") == "task"` 在 deepagents 中不准（task 工具可能是不同名），降级用 substring 匹配（`"task" in name.lower() or "subagent" in name.lower()`）
- 工具 result 体积不由业务 middleware 承担，前端只消费 AG-UI 标准 `TOOL_CALL_RESULT`
- `plan_snapshot` 优先来自 AG-UI state 的 `todos`，兼容 `write_todos/update_todos` 工具参数作为兜底

---

## 5. 前端重构详情

### 5.1 文件清单

#### 删除（顶层布局错配）
- `src/components/agui-plan/PhaseTimeline.jsx` ❌
- `src/components/agui-plan/WeekAgentGrid.jsx` ❌（顶层网格意图错；WeekAgentCard 改放到 WeekParallelBlock 内）

#### 新建（重构核心）
- `src/components/agui-plan/TimelineFeed.jsx` ⭐ 主时间流容器
- `src/components/agui-plan/WeekParallelBlock.jsx` ⭐ inline GenUI 嵌入组件
- `src/components/agui-plan/WeekAgentCard.jsx` ✏️ 重写：折叠态简化 + 展开嵌入子 TimelineFeed
- `src/lib/aiElementsAdapter.js` ⭐ CopilotKit → AI SDK 形状适配 helper

#### 修改
- `src/pages/AGUIPlanRun.jsx` — 顶层只保留 PetHero + TimelineFeed + ActionBar
- `src/components/agui-plan/PetHero.jsx` — 修 ProgressRing NaN
- `src/utils/aguiPlanEvents.js` — 加 `organizeEventsForTimeline()`、`mergeToolCalls()` 加 call_id 排重
- `src/components/agui-plan/EventStream/widgets/*` — 替换为 AI Elements 实现（详见 §6.2）

#### 不变
- `src/hooks/useAGUIPlanRunner.js` — 事件订阅逻辑正确，保留
- `src/utils/contextualHttpAgent.js` — 闭包 box 正确
- `src/pages/AGUIPlanLanding.jsx` / `AGUIPlanResult.jsx`

### 5.2 TimelineFeed.jsx 实现

```jsx
import { Conversation, ConversationContent, ConversationScrollButton } from '@/components/ai-elements/conversation';
import WidgetSwitch from './EventStream/WidgetSwitch';
import WeekParallelBlock from './WeekParallelBlock';
import { organizeEventsForTimeline, eventKey } from '../../utils/aguiPlanEvents';

export default function TimelineFeed({ events, compact = false }) {
    const { mainStream, weekBuckets } = useMemo(
        () => organizeEventsForTimeline(events),
        [events]
    );

    return (
        <Conversation className={compact ? 'max-h-96' : 'min-h-96'}>
            <ConversationContent>
                <AnimatePresence initial={false}>
                    {mainStream.map((item) => {
                        if (item._kind === 'week_block') {
                            return (
                                <motion.div key="week_block" layout
                                    initial={{ opacity: 0, scale: 0.95 }}
                                    animate={{ opacity: 1, scale: 1 }}>
                                    <WeekParallelBlock buckets={weekBuckets} />
                                </motion.div>
                            );
                        }
                        return (
                            <motion.div key={eventKey(item)} layout
                                initial={{ opacity: 0, y: 6 }}
                                animate={{ opacity: 1, y: 0 }}>
                                <WidgetSwitch event={item} />
                            </motion.div>
                        );
                    })}
                </AnimatePresence>
            </ConversationContent>
            <ConversationScrollButton />
        </Conversation>
    );
}
```

### 5.3 WeekParallelBlock.jsx 实现

```jsx
import WeekAgentCard from './WeekAgentCard';

export default function WeekParallelBlock({ buckets }) {
    return (
        <section className="my-4 rounded-2xl border-2 border-dashed border-primary/30 bg-primary/5 p-4">
            <header className="flex items-center gap-2 mb-3">
                <span className="material-icons-round text-primary">splitscreen</span>
                <h4 className="font-bold text-sm">4 周并行 SubAgent</h4>
                <span className="ml-auto text-[10px] text-text-muted-light">
                    {Object.values(buckets).filter(b => b.length > 0).length}/4 已启动
                </span>
            </header>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {[1, 2, 3, 4].map((n) => (
                    <WeekAgentCard key={n} weekNumber={n} events={buckets[n] || []} />
                ))}
            </div>
        </section>
    );
}
```

### 5.4 事件分流算法（aguiPlanEvents.js 增补）

```js
export function organizeEventsForTimeline(events) {
    const sorted = [...events].sort((a, b) =>
        (a.timestamp || '').localeCompare(b.timestamp || '')
    );
    const merged = mergeToolCalls(sorted);  // 已实现

    const mainStream = [];
    const weekBuckets = { 1: [], 2: [], 3: [], 4: [] };
    const subagentBuckets = {};
    const subagentCards = new Map();
    let weekBlockInserted = false;
    let subagentBlockInserted = false;

    for (const ev of merged) {
        const m = ev.node?.match(/^week_agent_(\d)$/);
        if (m) {
            weekBuckets[Number(m[1])].push(ev);
            continue;
        }

        const isWeekDispatch = ev.detail?.view_type === 'week_dispatch';
        if (isWeekDispatch) {
            weekBuckets[Number(ev.detail?.week_number)]?.push(ev);
            if (!weekBlockInserted) {
                mainStream.push({
                    _kind: 'week_block',
                    timestamp: ev.timestamp,
                });
                weekBlockInserted = true;
            }
            continue;
        }

        const isSubagentDispatch = ev.detail?.view_type === 'subagent_dispatch';
        if (isSubagentDispatch) {
            const id = ev.detail?.subagent_id || ev.detail?.call_id;
            subagentCards.set(id, { id, dispatchEvent: ev });
            (subagentBuckets[id] ||= []).push(ev);
            if (!subagentBlockInserted) {
                mainStream.push({
                    _kind: 'subagent_block',
                    timestamp: ev.timestamp,
                });
                subagentBlockInserted = true;
            }
            continue;
        }

        mainStream.push(ev);
    }
    return { mainStream, weekBuckets };
}
```

### 5.5 WeekAgentCard 重写

```jsx
import { Tool, ToolHeader, ToolContent } from '@/components/ai-elements/tool';
import TimelineFeed from './TimelineFeed';
import { deriveWeekStatus } from '../../utils/aguiPlanEvents';

const WEEK_LABELS = ['基础适应期', '营养强化期', '多样化拓展', '巩固优化期'];

export default function WeekAgentCard({ weekNumber, events }) {
    const status = useMemo(() => deriveWeekStatus(events), [events]);
    const last = events[events.length - 1];

    return (
        <Tool defaultOpen={false}>
            <ToolHeader
                type={`第${weekNumber}周 · ${WEEK_LABELS[weekNumber-1]}`}
                state={mapStatusToToolState(status.key)}
            />
            <ToolContent>
                <p className="text-xs text-text-muted-light truncate">
                    {last?.message || '等待启动...'}
                </p>
                <ProgressBar value={status.progress} />
                {events.length > 0 && (
                    <TimelineFeed events={events} compact />
                )}
            </ToolContent>
        </Tool>
    );
}

// status.key (CopilotKit) → AI SDK ToolUIPart.state
function mapStatusToToolState(key) {
    if (key === 'completed') return 'output-available';
    if (key === 'pending') return 'input-streaming';
    return 'input-available';
}
```

### 5.6 PetHero ProgressRing NaN 修复

```jsx
function ProgressRing({ progress, size = 64 }) {
    const stroke = 4;
    const radius = (size - stroke) / 2;
    const circ = 2 * Math.PI * radius;
    const safeProgress = Math.max(0, Math.min(100, Number(progress) || 0));
    const offset = circ - (safeProgress / 100) * circ;

    return (
        <svg width={size} height={size} className="-rotate-90">
            <circle ... strokeDasharray={circ} />
            <motion.circle
                ...
                strokeDasharray={circ}
                initial={{ strokeDashoffset: circ }}        // ← 修复:给定初值
                animate={{ strokeDashoffset: offset }}
                transition={{ duration: 0.5 }}
                className="text-primary"
            />
        </svg>
    );
}
```

---

## 6. AI Elements 集成

### 6.1 安装

`components.json` 已配置 shadcn (`base-nova` 风格 + `lucide` 图标)。AI Elements 通过 shadcn registry 安装：

```bash
cd frontend/web-app
npx ai-elements@latest add tool message reasoning plan task sources conversation
# 按需追加: shimmer artifact code-block suggestion
```

安装位置：`src/components/ai-elements/{tool,message,reasoning,...}.tsx`（项目是 jsx，需要确认 ai-elements 的 generator 是否支持 `--jsx` 或要手动重命名）。

**Lucide 图标**：AI Elements 默认用 `lucide-react`，项目当前主要用 `material-icons-round`。两套并存即可，不冲突。

### 6.2 Widget → AI Elements 组件映射

| view_type | 当前 Widget（自写） | 替换为 AI Elements | 适配函数 |
|---|---|---|---|
| `ai_message` | `AIMessageWidget.jsx`（MessageFold + 自定义） | `<Message><MessageContent><MessageResponse>` | content/reasoning 字符串直接喂 |
| `reasoning` | `ReasoningWidget.jsx`（CollapsibleCard） | `<Reasoning>`（折叠面板） | content 字符串直接喂 |
| `tool_call_generic` | `GenericToolWidget.jsx` | `<Tool><ToolHeader><ToolContent><ToolInput><ToolOutput>` | `toToolUIPart()` 适配 |
| `tool_search` | `SearchToolWidget.jsx` | `<Tool>` + `<Sources>`（来源链接） | 提取 `result.results` |
| `tool_note_read` | `NoteReadWidget.jsx` | `<Tool>` + `<Artifact>` 显示笔记 markdown | result string 直接喂 |
| `tool_note_write` | `NoteWriteWidget.jsx` | `<Tool>` + `<Artifact>` | content 字符串 |
| `plan_board` | `PlanBoardWidget.jsx` | AI Elements `<Queue>` | `state.todos/detail.items` 分组 |
| `subagent_dispatch` / `week_dispatch` | `SubagentDispatchWidget.jsx` | AI Elements `<Queue>` | 只在对应 agent 卡片内部显示 |
| `phase_marker` | `PhaseMarkerWidget.jsx` | `<Shimmer>`（动画文本）或保留自写 | message 字符串 |

### 6.3 适配 helper：`src/lib/aiElementsAdapter.js`

```js
/**
 * CopilotKit detail.view_type 数据 → AI SDK ToolUIPart 形状
 * AI Elements 的 <Tool> 期望 ToolUIPart {state, input, output, errorText, type, toolCallId}
 */
export function toToolUIPart(event) {
    const d = event.detail || {};
    const stateMap = {
        started: 'input-available',
        completed: d.result !== undefined ? 'output-available' : 'output-error',
        error: 'output-error',
    };
    return {
        type: `tool-${d.tool_name || 'unknown'}`,
        toolCallId: d.call_id || crypto.randomUUID(),
        state: stateMap[d.status] || 'input-streaming',
        input: d.args,
        output: d.result,
        errorText: d.status === 'error' ? String(d.result || '') : undefined,
    };
}

/**
 * detail.items (DeepAgent todo) → AI Elements <Plan> 期望的 plan 对象
 */
export function toAiSdkPlan(event) {
    const items = event.detail?.items || [];
    return {
        title: '任务规划',
        steps: items.map((it, i) => ({
            id: String(i),
            description: it.content,
            status: it.status,
        })),
    };
}

/**
 * detail.result (tavily_search 返回) → AI Elements <Sources> 期望的 sources 数组
 */
export function toAiSdkSources(event) {
    const r = event.detail?.result;
    if (!r) return [];
    if (Array.isArray(r)) return r;
    if (typeof r === 'string') {
        try { return JSON.parse(r)?.results || []; } catch { return []; }
    }
    return r.results || [];
}
```

---

## 7. CopilotKit Slots 适用性分析

### 7.1 Slots 概念

CopilotKit v2 的 `<CopilotChat>` 等容器组件接受 `messageView` / `input` / `suggestionView` / `welcomeScreen` 等 slot props，每个 slot 接受：

```ts
SlotValue<C> = C                          // 替换为另一个组件
              | string                    // 作为 className 注入默认组件
              | Partial<ComponentProps<C>>  // 部分覆盖默认 props
```

### 7.2 是否适用于本方案

**不直接适用**。原因：
- Slots 设计的容器是 `<CopilotChat>`（chat 形态）
- 我们用任务式：自己渲染 `<TimelineFeed>` + `<WeekParallelBlock>`，不经过 `<CopilotChat>`
- 所以无法通过 slots prop 注入

**间接适用**：
- 如果未来想在 `<CopilotSidebar>` 里复用部分 widget（比如开发者工具栏），可用 slot
- `messageView={CustomMessageView}` 模式可以借鉴 — 我们的 `widgetRegistry` 本质就是同样的"组件类型注入表"

### 7.3 借鉴 slots 的设计哲学

写 `widgetRegistry.js` 时遵循同样契约：
1. 注册接受**组件类型**（不是 ReactElement / 不是 props）
2. 替换粒度：单个 view_type → 单个 widget
3. 默认值：`getWidget(viewType)` 在未注册时回退到 GenericToolWidget（类似 slot 的默认实现）

---

## 8. 完整实施步骤

### 8.1 前端（先做，可独立验证）

| # | 任务 | 验证 |
|---|---|---|
| 1 | 修 PetHero ProgressRing NaN（加 `initial={{ strokeDashoffset: circ }}` + safeProgress 转换） | 浏览器 console 不再报 framer-motion warning |
| 2 | 安装 AI Elements：`npx ai-elements@latest add tool message reasoning plan sources conversation shimmer` | `src/components/ai-elements/` 出现新文件 |
| 3 | 创建 `src/lib/aiElementsAdapter.js`（toToolUIPart / toAiSdkPlan / toAiSdkSources） | 单元导出可调用 |
| 4 | 重写 9 个 widget 用 AI Elements | 每个 widget 在 storybook / 测试页可独立渲染 |
| 5 | 增补 `aguiPlanEvents.js`：`organizeEventsForTimeline()` | 单测覆盖 mainStream + weekBuckets 分流 |
| 6 | 创建 `TimelineFeed.jsx` | mock events 喂入能正确渲染（含 week_block 占位） |
| 7 | 创建 `WeekParallelBlock.jsx` + 重写 `WeekAgentCard.jsx` | 4 张卡片显示 + 折叠展开正常 |
| 8 | `AGUIPlanRun.jsx` 顶层换成 `<PetHero> + <TimelineFeed> + <ActionBar>` | 浏览器跑一遍现有 v2 graph 验收 |
| 9 | 删除 `PhaseTimeline.jsx` + `WeekAgentGrid.jsx` | git rm |

### 8.2 后端（后做，让事件更细）

| # | 任务 | 验证 |
|---|---|---|
| 10 | `PlanProgressMiddleware.awrap_tool_call(task)` 发送 `subagent_dispatch` 并注入 `subagent_info` | Task 触发后出现 SubAgent 卡片 |
| 11 | `SubAgentProgressMiddleware` 注册到 v2 subagents | 子 agent 内部事件进入对应 SubAgent 卡片 |
| 12 | `WeekProgressMiddleware` 只发送 week phase 事件 | 第 N 周卡片展开后看到子事件流 |
| 13 | `dispatch_weeks` 节点发送 4 次 `week_dispatch` | 主流出现 WeekParallelBlock，dispatch 行进入周卡片内部 |

### 8.3 验收

最终用户体验链路：
1. 进入 `/agui-plan` → Hero + 启动按钮
2. 点击 → `/agui-plan/run` → PetHero 显示宠物，不显示百分比进度条
3. agent 启动后:
   - 主流第一条:`[phase] 研究阶段启动`（PhaseMarker）
   - AI 文本用 AI Elements `Conversation/Message` 渲染
   - 多个 `[tool] ingredient_search ▾`（Tool 折叠态）
   - todo/state 更新出现 AI Elements `Queue`
4. task 工具触发 → 主流出现 inline `SubAgentParallelBlock`，每个 task 一个可展开 SubAgent 卡片
5. dispatch 阶段 → 主流出现 inline `WeekParallelBlock` 4 张卡片
6. 4 周并行运行，每张卡片实时刷新状态 chip
7. 用户点击任意一张展开 → 看到该 agent 完整子事件流（同样的 chat-like 渲染）
8. 全部完成 → 跳 `/agui-plan/result`

---

## 9. 已知风险与回退

| 风险 | 表现 | 缓解 |
|---|---|---|
| AI Elements 默认是 TSX，项目是 JSX | `npx ai-elements add` 安装出 .tsx 文件 vite 也能编译，但和项目风格不一致 | 安装后批量改后缀；或用 `--language jsx` 标志（如支持） |
| AI Elements 的 Tool/Plan 强依赖 `streamdown` / `lucide-react` | 包体积增大 ~150KB | 树摇能去掉未使用部分；用 dynamic import 懒加载 result 页之外的部分 |
| 后端 deepagents 的 `task` 工具名可能不是固定字符串 | subagent_dispatch 触发不稳 | `_is_subagent_tool()` 使用 `task/subagent/transfer/transfor` 兜底匹配 |
| WeekParallelBlock 在窄屏（手机）展示拥挤 | 4 张卡片 2x2 → 手机 1 列 4 行，纵向滚动累 | grid-cols-1 sm:grid-cols-2 默认就处理了；卡片折叠态高度 < 100px |
| `agent.subscribe.onCustomEvent` 的 event.value 序列化形式 | 后端发 dict，AG-UI 协议层可能转 JSON 字符串 | useAGUIPlanRunner 已加 `safeJsonParse` 兜底 |
| 同 call_id 多次 emit 重复入队 | 时间流出现重复卡片 | seenKeysRef 已按 timestamp+node+type+call_id+status 去重 |

**回退策略**：
- 整套重构在新分支进行，主分支保留当前 PhaseTimeline + WeekAgentGrid 版本作为对照
- 只要 AGUIPlanLanding / Result 页不改，可以两条 UI 路径并存（`?layout=v1|v2` query param 切换）

---

## 附录 A：view_type → AI Element 组件 映射对照表

| view_type | 事件来源 | AI Elements 主组件 | 适配函数 |
|---|---|---|---|
| `ai_message` | AG-UI `TEXT_MESSAGE_*` 标准事件 | `<Message from="assistant">` + `<MessageContent>` | 直接 content |
| `reasoning` | AG-UI `REASONING_MESSAGE_*` 标准事件 | `<Reasoning isStreaming={...}>` 折叠 | 直接 reasoning |
| `tool_call_generic` | AG-UI `TOOL_CALL_*` 标准事件兜底 | `<Tool>` + `<ToolHeader>` + `<ToolContent>` + `<ToolInput>` + `<ToolOutput>` | `toToolUIPart()` |
| `tool_search` | AG-UI `TOOL_CALL_*`，按 tool_name 路由 | `<Tool>` + `<Sources>` | `toToolUIPart` + `toAiSdkSources` |
| `tool_note_read` | AG-UI `TOOL_CALL_*`，按 tool_name 路由 | `<Tool>` + note read widget | `toToolUIPart` + result.text |
| `tool_note_write` | AG-UI `TOOL_CALL_*`，按 tool_name 路由 | `<Tool>` + note write widget | 同上 |
| `tool_food_calc` | AG-UI `TOOL_CALL_*`，按 tool_name 路由 | `<Tool>` + 自定义营养小卡 | 解析 result |
| `plan_board` | AG-UI `STATE_SNAPSHOT/STATE_DELTA` 的 `state.todos` | AI Elements `<Queue>` | `toQueueSections()` |
| `subagent_dispatch` | `PlanProgressMiddleware.awrap_tool_call(task)` | **不渲染到主流**，触发 `<SubAgentParallelBlock>` 插入，并作为卡片内首条事件 | `subagent_id` 分桶 |
| `week_dispatch` | `dispatch_weeks` for-loop | **不渲染到主流**，触发 `<WeekParallelBlock>` 插入，并作为周卡片内首条事件 | `week_number` 分桶 |
| `phase_marker` | 各种 phase 事件兜底 | `<Shimmer>` 或 `<MessageActions>` 单行 | message 字符串 |

---

## 附录 B：v2 后端节点 → emit 调用点对照

> 仅列出本次 §4 计划新增的调用点。已有的（`emit_progress(RESEARCH_STARTING)` 等）保持不变。

| middleware / 节点 | 钩子 | 新增调用 |
|---|---|---|
| `PlanProgressMiddleware` | `awrap_tool_call(task)`（handler 前） | `research_task_delegating` + `detail.view_type=subagent_dispatch` + `detail.subagent_id` |
| `PlanProgressMiddleware` | `awrap_tool_call(task)`（handler 后） | `task_completed` + 同一个 `call_id/subagent_id`，前端合并完成态 |
| `SubAgentProgressMiddleware` | `before_agent / awrap_tool_call / after_agent` | `node=subagent_{subagent_id}` 的子 agent 内部事件流 |
| `WeekProgressMiddleware` | `before_agent / awrap_tool_call / awrap_model_call / after_agent` | `node=week_agent_{N}` 的周 agent 内部事件流 |
| `dispatch_weeks` 节点 | for-loop 内（Send 之前） | `task_delegating` + `detail.view_type=week_dispatch` + `week_number=N` × 4 |

---

## 附录 C：当前已跑通验证的部分（保留不动）

| 已就绪 | 文件 | 说明 |
|---|---|---|
| emit_progress 双发 | `common/stream_events.py` | 双通道发送，已实测 AG-UI 收到 CUSTOM 事件 |
| ProgressEventType 二级枚举 | 同上 | 保持旧字符串值，代码用 `ProgressEventType.Research.STARTING` 等入口 |
| `extract_reasoning` | 同上 | 自动抽 qwen3 thinking / `<think>` |
| 协议适配层 | `src/api/agui_agent.py` | dataclass context 注入 + reasoning role 过滤 + forwardedProps 业务字段透传 |
| 闭包 box | `frontend/utils/contextualHttpAgent.js` | `setForwardedProps` 让所有 clone agent 看到最新值（Pit 13） |
| 事件订阅 | `frontend/hooks/useAGUIPlanRunner.js` | `agent.subscribe({ onCustomEvent })` 实测可收到所有 emit_progress 事件 |
| 路由 | `App.jsx` 已注册 `/agui-plan`、`/agui-plan/run`、`/agui-plan/result` 三条 |
| Landing/Result 页 | `pages/AGUIPlan{Landing,Result}.jsx` | 不需重构，保留 |
| ContextV2 注入流程 | 后端日志已确认 `pet_information` + `user_id` 正确进 graph |

---

## 附录 D：参考资料

- [AGUI_INTEGRATION.md](./AGUI_INTEGRATION.md) — v2 集成踩坑（13 个 Pit）
- [agui-langgraph-learn/01-架构与协议.md](../../agui-langgraph-learn/01-架构与协议.md) — AG-UI / CopilotKit / LangGraph 三层架构
- [agui-langgraph-learn/02-Hook速查表.md](../../agui-langgraph-learn/02-Hook速查表.md) — v2 hook API
- [agui-langgraph-learn/06-AI-Elements适配度分析.md](../../agui-langgraph-learn/06-AI-Elements适配度分析.md) — 49 个 AI Elements 组件适配档评估
- [CopilotKit Slots 文档](https://docs.copilotkit.ai/langgraph/custom-look-and-feel/slots)
- [AI Elements 主页](https://elements.ai-sdk.dev/)
- v2 graph 源码：`src/agent/v2/{node,graph,state}.py` + `src/agent/v2/middlewares/progress_middleware.py`
