# LangChain Middleware 调研与 `progress_middleware.py` 重构报告

日期：2026-04-29

更新：2026-05-03（AG-UI 标准事件边界校准）

更新：2026-05-04（ProgressEventType 二级枚举与无百分比进度流）

更新：2026-05-04（v2 task subagent 事件隔离与前端分桶契约）

更新：2026-05-05（v2 AG-UI 单链路与 subagent metadata 归属）

更新：2026-05-05（week agent metadata 归属与 AI Elements message 渲染）

更新：2026-05-05（reasoning raw metadata patch 与文档同步）

## 1. 调研结论

结合仓库当前锁定版本与 LangChain 官方最新文档，当前推荐的 middleware 写法已经不是“只用一个 `@wrap_model_call` 装饰器包起来”这么简单，而是两类能力并存：

1. `before_agent / before_model / after_model / after_agent`
   适合表达 agent 生命周期节点。
2. `wrap_model_call / wrap_tool_call`
   适合拦截具体的模型调用与工具调用。
3. 复杂跨切面逻辑，官方推荐直接写 class-based `AgentMiddleware`。

本仓库本地锁定版本：

- `langchain==1.2.15`
- `deepagents==0.5.3`
- `langgraph==1.1.10`

这些版本都已经支持上述完整钩子集，`create_deep_agent(...)` 也直接接受 `AgentMiddleware` 序列。

### 1.1 2026-05-03 补充调研

这次进一步核对了 `langchain`、`deepagents`、`ag_ui_langgraph`、`@ag-ui/client` 的实际行为，结论如下：

1. LangChain 最新 middleware 路线仍是 `create_agent(..., middleware=[...])`，复杂逻辑用 class-based `AgentMiddleware`；生命周期 hook 和 wrap hook 应分工清晰。
2. `TodoListMiddleware` 注入的 `write_todos` 工具返回 `Command(update={"todos": todos, "messages": [ToolMessage(...)]})`，所以 todo UI 最稳定来源是 LangGraph state 的 `todos` key。
3. `ag_ui_langgraph` 已自动把 LangGraph 工具流翻译成 AG-UI 标准 `TOOL_CALL_START/ARGS/END/RESULT`，业务 middleware 不应重复发 `emit_tool_call started/completed`。
4. `@ag-ui/client` 应用 `TOOL_CALL_RESULT` 后还会触发 `onNewMessage(role="tool")`，前端需要用 `toolCallId` 去重，否则会出现 `unknown` 工具调用卡片。
5. AG-UI 标准事件名为 uppercase snake case，例如 `TEXT_MESSAGE_START`、`TOOL_CALL_START`、`REASONING_MESSAGE_START`、`STATE_SNAPSHOT`。

### 1.2 LangChain middleware 写法速记

后续再改 `progress_middleware.py` 时按这个边界写，避免重复查文档：

1. 轻量单 hook 可用 decorator：`@before_agent`、`@after_agent`、`@wrap_model_call`、`@wrap_tool_call`。
2. 多 hook、共享 tracker、需要跨 model/tool/agent 生命周期协作时，直接继承 `AgentMiddleware`。
3. `before_agent / after_agent` 适合发“任务开始/结束/阶段切换”这类业务 lifecycle event。
4. `wrap_model_call / awrap_model_call` 适合围绕一次 LLM 调用做 prompt 改写、fallback、重试、统计，不适合重复发送 AG-UI 文本事件。
5. `wrap_tool_call / awrap_tool_call` 适合围绕一次工具执行做参数修正、错误降级、业务阶段推导，不适合重复发送 AG-UI `TOOL_CALL_*`。
6. hook 的 sync/async 版本要和 agent 调用方式匹配；当前 AG-UI/LangGraph 走 async stream，业务自定义事件用 `await aemit_*` 更稳。
7. middleware 可以声明 `state_schema` 和 `tools`。`TodoListMiddleware` 就是通过 `tools=[write_todos]` 注入工具，并通过 `PlanningState.todos` 扩展 state。

### 1.3 AG-UI reasoning metadata 兼容修复

`ag_ui_langgraph` 从 `on_chat_model_stream` 的 `AIMessageChunk` 中解析 reasoning，并生成 `REASONING_*` AG-UI event；但这些 reasoning event 默认没有带回 LangGraph 原始 `raw_event`，前端拿不到 `rawEvent.metadata.subagent_id` 或 `rawEvent.metadata.week_number`。

当前在 `src/api/agui_agent.py:DataclassAwareLangGraphAGUIAgent` 中做轻量 patch：

1. 在处理 `on_chat_model_stream` 且 chunk 含 reasoning 内容时，临时记录当前 LangGraph raw event。
2. `_dispatch_event` 遇到 `REASONING_START / REASONING_MESSAGE_START / REASONING_MESSAGE_CONTENT / REASONING_MESSAGE_END / REASONING_END` 等 event 时，如果 event 自身没有 `raw_event`，补回当前 raw event。
3. 前端继续统一走 metadata owner 规则，不为 reasoning 单独做 state fallback。

对应测试：`tests/test_agui_agent.py` 验证 `REASONING_MESSAGE_CONTENT` 能保留 `raw_event.metadata.subagent_id`。

## 2. 旧实现问题

旧版 `progress_middleware.py` 的核心问题是：

1. 只监听 `wrap_model_call`。
2. 每次 model 调用结束都直接发“阶段完成”事件。
3. 完全看不到工具层信号，`week_agent` 选材/查询/计算阶段是黑盒。
4. 并行 `week_agent` 曾依赖百分比 tracker，但这些百分比对 AG-UI 页面没有明确语义，反而造成右侧进度条噪音。

直接结果就是：

- `week_plan_ready` 会被过早触发。
- 周计划阶段没有“检索中 / 撰写中”的真实状态。
- 百分比进度不适合继续作为 agent 事件流的核心 UI 信号。

## 3. 重构方案

当前 v2 只保留两类 class-based middleware：

1. `SubAgentProgressMiddleware`
   负责 deepagents task 创建的子 agent：
   - `before_agent` 从 `state["messages"][0]` 读取 subagent 输入，计算 `sha256(normalized_input)[:16]` 作为稳定 `subagent_id`
   - `before_agent` 只发一次 `task_executing` custom event，`detail.view_type=subagent_dispatch`，用于前端创建 subagent 卡片
   - `awrap_model_call` 直接写 `request.model.metadata = {"subagent_id": subagent_id}`，让 AG-UI 标准 message/reasoning 事件带归属
   - `awrap_tool_call` 直接写 `request.tool.metadata = {"subagent_id": subagent_id}`，让 AG-UI 标准 `TOOL_CALL_*` 事件带归属
   - `after_agent` 只发一次 `task_completed` custom event，表示该 subagent 卡片完成
   - 不再为 subagent 内部消息、推理、工具调用重复发 custom progress event

2. `WeekProgressMiddleware`
   负责四周并行阶段：
   - `before_agent` 只发一次 `week_planning` custom event，标记该周 agent 启动
   - `awrap_model_call` 直接写 `request.model.metadata = {"week_number": week_number}`，让 AG-UI 标准 message/reasoning 事件带归属
   - `awrap_tool_call` 直接写 `request.tool.metadata = {"week_number": week_number}`，让 AG-UI 标准 `TOOL_CALL_*` 事件带归属
   - `after_agent` 只发一次 `week_completed` custom event，表示该 week agent 生命周期结束
   - 不再为 week agent 内部业务工具阶段重复发 `week_searching / week_writing` custom event

## 4. 关键设计点

### 4.1 不再发送百分比进度

`progress_middleware.py` 已删除 phase tracker、进度窗口、TTL 清理和单调递增计算。

当前 agent 事件流只表达业务阶段，不再附带 `progress` 百分比字段。任务数据库自身仍可保留 `progress` 字段作为后端任务状态字段，但它不再由 agent 业务事件驱动。

### 4.2 week 生命周期只表达 agent 边界

`WeekProgressMiddleware.after_agent` 不再检查 `structured_response` 或 `week_light_plans`。

在 v2 AG-UI 单链路中，week 内部消息、推理、工具、结构化响应都走 AG-UI / LangGraph 标准事件；middleware 的 `week_completed` 只表示该 week agent 已退出，用于前端更新 week 卡片状态。

### 4.3 兼容前端

保留原有事件字符串值：

- `week_planning`
- `week_searching`
- `week_writing`
- `week_completed`
- `completed`

`week_plan_ready` 仍保留在枚举中用于历史兼容，但当前 v2 middleware 不再主动发送，避免和 `week_writing` 语义重叠。

新代码使用二级枚举入口：

- `ProgressEventType.Research.STARTING`
- `ProgressEventType.Week.PLANNING`
- `ProgressEventType.Result.COMPLETED`
- `ProgressEventType.Run.ERROR`

实际序列化到前端的 `type` 仍是旧字符串值，例如 `research_starting`，不使用点号字符串事件名。

week agent 事件输出：

- week 启动 custom event：`type=week_planning`、`node=week_agent_{week_number}`、`detail.week_number`
- week 完成 custom event：`type=week_completed`、`node=week_agent_{week_number}`、`detail.week_number`
- week 内部 AG-UI 标准事件不再看 LangGraph state fallback，只通过 `rawEvent.metadata.week_number` / `metadata.week_number` 判定归属
- 没有 `week_number` 的标准 message/reasoning/tool event 一律留在外层渲染

task subagent 事件输出：

- subagent 启动 custom event：`type=task_executing`、`node=subagent_{subagent_id}`、`detail.view_type=subagent_dispatch`
- subagent 完成 custom event：`type=task_completed`、`node=subagent_{subagent_id}`、`detail.view_type=subagent_dispatch`
- `detail.subagent_id` 来源：`sha256(normalized(state["messages"][0].content))[:16]`
- 子 agent 内部 AG-UI 标准事件不再看 LangGraph state fallback，只通过 `rawEvent.metadata.subagent_id` / `metadata.subagent_id` 判定归属
- 没有 `subagent_id` 的标准 message/reasoning/tool event 一律留在外层渲染

前端 `TimelineFeed` 的当前契约：

- `week_dispatch` 不再作为主流单行重复渲染，而是进入对应 `weekBuckets[N]`，主流只插入一次 `week_block`
- 带 `detail.week_number` 或 `detail.week` 的 week 事件进入 `weekBuckets[N]`
- 没有 `detail.week_number/detail.week` 的标准事件不通过 `node=week_agent_N` 兜底进周卡片
- 只有带 `detail.subagent_id` 的 `subagent_dispatch` 才进入 `subagentBuckets[subagent_id]`，主流只插入一次 `subagent_block`
- 标准 `task` 工具调用不再被前端投影成 `subagent_spawn`；它作为普通 tool call 在外层展示，subagent 卡片由 before/after custom event 建立和结束
- subagent 内部标准事件只有在 metadata 中带 `subagent_id` 时才进入对应 SubAgent 卡片
- AI message 渲染使用 AI Elements `Conversation` 容器下的 `Message / MessageContent / MessageResponse` 组合，保留 markdown/streamdown 渲染能力

### 4.4 与 AG-UI 标准事件的职责边界

当前 `progress_middleware.py` 的职责是发业务进度与业务语义，不负责复刻 AG-UI 标准协议。

应该保留：

- 研究/周计划/汇总阶段的生命周期业务事件。
- `node / task_name / detail` 等业务上下文。
- todo/subagent 生命周期这类 AG-UI 标准事件没有直接表达的业务语义。

不应该重复发送：

- LLM 文本输出：由 `TEXT_MESSAGE_START/CONTENT/END` 表达。
- 推理输出：由 `REASONING_MESSAGE_START/CONTENT/END` 表达；没有就不渲染。
- 工具调用开始、参数、结束、结果：由 `TOOL_CALL_START/ARGS/END/RESULT` 表达。

补充：reasoning 事件的归属不由 middleware 重发 custom event 解决，而是由 AG-UI adapter patch 给标准 `REASONING_*` event 补 `raw_event`，前端继续读取 `rawEvent.metadata`。

DeepAgents todo 的推荐前端链路是：`write_todos` 更新 state 的 `todos` key → AG-UI `STATE_SNAPSHOT/STATE_DELTA` → `agent.subscribe({ onStateChanged })` → 前端投影成 `plan_board` / AI Elements `Queue`。

## 5. 验证

新增测试：

- `tests/test_progress_middleware.py`
- `tests/test_agui_agent.py`

覆盖点：

1. subagent before/after 生命周期事件正确，model/tool metadata 带 `subagent_id`。
2. week before/after 生命周期事件正确，model/tool metadata 带 `week_number`。
3. week `after_agent` 不依赖最终产物 gate，固定发出生命周期完成事件。
4. reasoning 标准事件保留 LangGraph raw metadata，可按 `subagent_id` / `week_number` 归属。

2026-05-05 本轮验证：

- 后端：`.\.venv\Scripts\python.exe -m pytest tests\test_progress_middleware.py tests\test_agui_agent.py -q`
- 前端：`npm run build`（`frontend/web-app`）

## 6. 参考资料

1. LangChain 官方 Middleware 概览  
   https://docs.langchain.com/oss/python/langchain/middleware/overview
2. LangChain 官方 Custom Middleware 文档  
   https://docs.langchain.com/oss/python/langchain/middleware/custom
3. LangChain 官方源码：`AgentMiddleware` 与钩子定义  
   https://github.com/langchain-ai/langchain/blob/master/libs/langchain/langchain/agents/middleware/types.py
4. LangChain 官方源码：`wrap_tool_call` 装饰器  
   https://github.com/langchain-ai/langchain/blob/master/libs/langchain/langchain/agents/middleware/tool.py
5. LangChain 本地源码：`langchain/agents/middleware/todo.py`
6. AG-UI 本地源码：`@ag-ui/client` 的 `TOOL_CALL_RESULT` / `STATE_SNAPSHOT` apply 行为
7. `ag_ui_langgraph/agent.py`：LangGraph stream event → AG-UI event 翻译层
