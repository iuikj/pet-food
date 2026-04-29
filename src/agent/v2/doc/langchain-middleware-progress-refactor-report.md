# LangChain Middleware 调研与 `progress_middleware.py` 重构报告

日期：2026-04-29

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

## 2. 旧实现问题

旧版 `progress_middleware.py` 的核心问题是：

1. 只监听 `wrap_model_call`。
2. 每次 model 调用结束都直接发“阶段完成”事件。
3. 完全看不到工具层信号，`week_agent` 选材/查询/计算阶段是黑盒。
4. 并行 `week_agent` 没有统一进度模型，容易出现“事件很多但总进度不可信”。

直接结果就是：

- `week_plan_ready` 会被过早触发。
- 周计划阶段没有“检索中 / 撰写中”的真实状态。
- 若简单按周编号给并行任务打进度，前端进度条还会倒退。

## 3. 重构方案

这次改造改成了两个 class-based middleware：

1. `PlanProgressMiddleware`
   负责研究阶段：
   - `before_agent` 发 `research_starting`
   - `wrap_model_call` 发 `plan_creating / plan_updated / research_task_delegating`
   - `after_agent` 只在真正结束时发 `plan_created`

2. `WeekProgressMiddleware`
   负责四周并行阶段：
   - `before_agent` 发 `week_planning`
   - `wrap_tool_call` 感知 `ingredient_* / nutrition_*` 工具，发 `week_searching` 或计算类 `week_planning`
   - `wrap_model_call` 在工具结果回流后发 `week_writing`
   - 最终输出前发 `week_plan_ready`
   - `after_agent` 只在检测到真实最终产物时发 `week_completed`

## 4. 关键设计点

### 4.1 单调递增总进度

在 `progress_middleware.py` 内新增了按任务隔离的 phase tracker：

- `plan_phase`：研究阶段窗口 `5 -> 28`
- `week_phase`：四周阶段窗口 `40 -> 78`

`week_phase` 不是按“第几周固定百分比”算，而是按 4 个并行单元的阶段平均值计算总进度。这样即使四个 `week_agent` 乱序推进，总进度也只会上升，不会倒退。

### 4.2 不再误报完成

`after_agent` 里的 `week_completed` 增加了最终产物检查：

- 有 `structured_response`
- 或已经收到了 `week_light_plans`

只有满足最终产物条件才会发 completed 类事件，避免结构化重试时提前宣告完成。

### 4.3 兼容前端

保留原有事件类型：

- `week_planning`
- `week_searching`
- `week_writing`
- `week_plan_ready`
- `week_completed`

并且继续输出：

- `node=week_agent_{week}`
- `task_name=第N周饮食计划`
- `detail.week`

这样前端当前的周状态面板和步骤映射无需改动。

## 5. 验证

新增测试：

- `tests/test_progress_middleware.py`

覆盖点：

1. `plan` 阶段事件序列正确。
2. 并行 `week` 事件的 `progress` 单调不下降。
3. `after_agent` 不会在未拿到最终产物时误发 `week_completed`。

## 6. 参考资料

1. LangChain 官方 Middleware 概览  
   https://docs.langchain.com/oss/python/langchain/middleware
2. LangChain 官方 Custom Middleware 文档  
   https://docs.langchain.com/oss/python/langchain/middleware/custom
3. LangChain 官方源码：`AgentMiddleware` 与钩子定义  
   https://github.com/langchain-ai/langchain/blob/master/libs/langchain/langchain/agents/middleware/types.py
4. LangChain 官方源码：`wrap_tool_call` 装饰器  
   https://github.com/langchain-ai/langchain/blob/master/libs/langchain/langchain/agents/middleware/tool.py

