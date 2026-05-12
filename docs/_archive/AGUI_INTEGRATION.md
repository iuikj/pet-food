# AG-UI + CopilotKit + LangGraph 适配实战

> 本次实验：在**不改 v2 graph 实现**的前提下，让前端 CopilotKit 直连 FastAPI ag-ui-langgraph 端点，跑通 LangGraph 1.x dataclass `context_schema`。
>
> 完成日期：2026-04-30 → 2026-05-01（v2 迁移完成）；2026-05-02 精简重构

---

## ⚡ 2026-05-02 精简版变更（重要）

基于对 ag_ui_langgraph 与 LangGraph 1.x 的源码深挖（详见 [`agui-langgraph-learn/07-LangGraph1.x接入实战教训.md`](../../agui-langgraph-learn/07-LangGraph1.x接入实战教训.md)），适配层从 230 行缩到 ~110 行：

- **ContextV2** 由 `@dataclass` 改 `Pydantic BaseModel(extra='ignore', arbitrary_types_allowed=True)`：自动吞 `thread_id` 等系统字段、自动从 dict 验证 PetInformation 字段，无需 wrapper 手工过滤
- **wrapper 删除** `_current_forwarded_props` ContextVar、`_coerce_pet_information`、`get_schema_keys` 重写（共 165 行）
- **wrapper 新增** `get_stream_kwargs` 重写：强制传 `context`，绕过 ag_ui_langgraph 的 `inspect.signature` bug（详见 Pit 14）
- **wrapper 新增** `__init__` 注入 `recursion_limit=1000`：因为 `graph.with_config()` 不被 ag_ui_langgraph 继承（详见 Pit 15）
- **emit_progress** 改为 sync `emit_*` + async `aemit_*` 双 API，async graph node 用 `await aemit_*` 同步等待，彻底消除 fire-and-forget 时序风险
- **前端 contextualHttpAgent.js** 仅 override `requestInit` 单 hook（90 行 → 25 行），符合 ag-ui-protocol 官方推荐模式
- **logging filter** 静音 `OnToolEnd received non-ToolMessage output` 假警报（详见 Pit 17）

---

## 0. 版本选择：v1 vs v2

| | CopilotKit v1 | CopilotKit v2 ✅ |
|---|---|---|
| **包结构** | `@copilotkit/react-core` + `@copilotkit/react-ui` | 全部 `@copilotkit/react-core/v2` |
| **Provider** | `<CopilotKit>` | `<CopilotKitProvider>` |
| **publicApiKey** | 必需（或 dummy） | `agents__unsafe_dev_only` 时可选 |
| **agent 配置** | Provider 上 `agent="name"` | `<CopilotChat agentId="name">` |
| **Inspector** | `enableInspector={false}` 关闭 | `showDevConsole="auto"` 本地开 |
| **CSS 兼容** | Tailwind 3.4 兼容 | **需 shim**（v2 CSS 用 Tailwind v4 指令） |

**推荐 v2**：API 更清晰，不需要 dummy key，但需处理 CSS 冲突（见下文 Pit 6）。

---

## 1. 三层定位

| 层 | 角色 | 类比 |
|---|---|---|
| **LangGraph** | Agent 大脑（graph + state + `context_schema`） | 业务逻辑 |
| **AG-UI** | 开放协议（16 类 SSE 事件 + `RunAgentInput`） | HTTP/REST 这种约定 |
| **CopilotKit** | React 框架（消费 AG-UI 的 Hooks + UI 组件） | axios + 一套 UI 库 |

**CopilotKit 是 AG-UI 协议发明者**，与 ag-ui-langgraph 一等公民集成。

---

## 2. 整体架构（v2 最终版）

```
┌─────────────────────────────────────────────────────────────┐
│ 前端 (frontend/web-app)                                      │
│  /plan/create (CreatePlan.jsx)                              │
│    └─ 紫粉色悬浮按钮 (fixed bottom-28 right-6)              │
│        ↓ navigate('/agui-test')                             │
│                                                             │
│  /agui-test (AGUITest.jsx)                                  │
│    ├─ const agent = new HttpAgent({ url: '<base>/langgraph' })
│    └─ <CopilotKitProvider                                   │
│         agents__unsafe_dev_only={{ v2agent: agent }}        │
│         showDevConsole="auto">  ← v2 inspector 本地自动开   │
│         <CopilotChat agentId="v2agent" />  ← agent 在这配   │
│                                                             │
│  vite.config.js                                             │
│    └─ copilotkitV2CssShim (vite plugin)                     │
│        + optimizeDeps.esbuildOptions.plugins (esbuild)      │
│        → 拦截 v2 内部 `import './index.css'`                │
│        → 转成 JS 模块运行时 <style> 注入                     │
│        → 绕过 Tailwind 3.4 PostCSS pipeline                 │
└─────────────────────────────────────────────────────────────┘
                          │  AG-UI 协议 (SSE)
                          │  POST /langgraph
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ 后端 (pet_food_backend/pet-food)                             │
│  src/api/main.py (FastAPI lifespan)                         │
│    ├─ open_v2_checkpointer() → AsyncPostgresSaver           │
│    ├─ compile_v2_graph(checkpointer)                        │
│    └─ add_langgraph_fastapi_endpoint(                       │
│         agent=DataclassAwareLangGraphAGUIAgent(...),  ←关键 │
│         path="/langgraph")                                  │
│                                                             │
│  src/api/agui_agent.py (协议适配层)                          │
│    └─ DataclassAwareLangGraphAGUIAgent                      │
│        ├─ run(): 过滤 reasoning role（中断遗留）            │
│        └─ get_stream_kwargs(): 过滤 thread_id 注入 ContextV2│
│                                                             │
│  src/agent/v2/ (graph 实现，零改动)                          │
│    ├─ graph.py / utils/context.py / middlewares/...         │
│    └─ ctx = request.runtime.context  ← ContextV2 实例 ✅    │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 完整请求链路（v2）

```
[1] 用户点击悬浮按钮
[2] React Router → /agui-test
[3] <CopilotKitProvider> 初始化 → 注册 HttpAgent 实例
[4] 用户在 <CopilotChat> 输入 → useCopilotChat → agent.runAgent(...)
[5] HttpAgent 发送 POST <host>/langgraph (body: RunAgentInput, accept: SSE)
[6] FastAPI 路由 → ag_ui_langgraph.endpoint.event_generator
[7] → DataclassAwareLangGraphAGUIAgent.run (子类)
[8]   → 过滤 input.messages 中非标准 role（reasoning/thinking 等中断遗留）
[9]   → super().run → _handle_stream_events → prepare_stream
[10]  → get_stream_kwargs (被我们 override):
          - super().get_stream_kwargs() 拿到 base kwargs
          - 检测 graph.context_schema 是 dataclass
          - 过滤 base_context: {thread_id, ...} → 只留 ContextV2 字段
          - ContextV2(**filtered) → instance
[11] graph.astream_events(
        input=...,
        context=ContextV2 实例,        ← 关键
        config={configurable: {thread_id: ...}}
     )
[12] v2 graph 节点执行 → runtime.context = ContextV2 实例 ✅
[13] dynamic_prompt_middleware: ctx.research_planner_prompt.format(...) ✅
[14] LangGraph stream → ag_ui_langgraph 转 AG-UI 事件 (TEXT_MESSAGE_*, TOOL_CALL_*, ...)
[15] SSE 推送回前端 → CopilotChat 流式渲染
```

---

## 4. 关键决策与原因

### 4.1 为什么选 v2 而非 v1？

| 优势 | v1 | v2 |
|---|---|---|
| 不需要 dummy `publicApiKey` | ❌ 必需 | ✅ `agents__unsafe_dev_only` 时可选 |
| agent 配置位置 | Provider 上 | `<CopilotChat agentId>` 更灵活 |
| 包结构 | 分散两个包 | 统一 `@copilotkit/react-core/v2` |
| Inspector 控制 | `enableInspector` | `showDevConsole="auto"` 更语义化 |

**代价**：v2 CSS 用 Tailwind v4 指令（`@layer properties`），与项目 Tailwind 3.4 冲突，需 vite + esbuild 双层 shim（见 Pit 6）。

### 4.2 为什么不通过前端 `forwardedProps.config` 注入 context？

阅读 ag-ui-langgraph `agent.py` 源码确认：
- `_handle_stream_events` 第 195 行：`config = ensure_config(self.config.copy() if self.config else {})`
- `forwarded_props` 只用于读 `command`、`node_name`、`stream_subgraphs`
- **`forwarded_props.config` 完全被忽略**

→ 必须在后端 `LangGraphAGUIAgent` 构造时静态注入，或子类化处理。

### 4.3 为什么用子类化而不是给 `ContextV2` 加 `.schema()` 方法？

- introspection 失败的 warning 只影响 `schema_keys["context"]`（给 `langgraph_default_merge_state` 用），**不影响 context 注入路径**
- 真正问题：`base_context = {'thread_id': '...', ...}` 始终包含 `thread_id`（来自 ag-ui-langgraph 自动注入）
- LangGraph 1.x `_coerce_context`：`isinstance(context, dict) and is_dataclass(schema)` → `schema(**context)`
- ContextV2 没有 `thread_id` 字段 → `TypeError` → silent fallback → `runtime.context = None`
- 加 `.schema()` 解决不了 thread_id 冲突

### 4.4 为什么注入 dataclass 实例而不是过滤后的 dict？

- 直接传 dict 给 LangGraph 仍走 `_coerce_context` → 字段不匹配的风险
- 直接构造 `schema(**filtered)` 实例：
  - 错误更显式（构造失败时立即可见，不是 silent None）
  - 语义明确（这就是要传给 graph 的 ContextV2 实例）
  - 兼容未来扩展（前端如果通过其他渠道传值，过滤后塞进来即可）

---

## 5. 踩坑记录

### Pit 1: ~~CopilotKit v1 强制 `publicApiKey`~~（v2 已修复）

| | |
|---|---|
| v1 现象 | `ConfigurationError: Missing required prop: 'runtimeUrl' or 'publicApiKey' or 'publicLicenseKey'` |
| v1 根因 | `validateProps` 在 `copilotkit-Bd0m5HFp.mjs:840` 强制检查 |
| v1 修复 | 加 dummy `publicApiKey="dev-only-experiment"` |
| v2 改进 | `hasLocalAgents` 时跳过校验（`agents__unsafe_dev_only` 提供本地 agent 即可） |

### Pit 2: ag-ui-langgraph 不消费 `forwarded_props.config`

| | |
|---|---|
| 现象 | 前端传 `forwardedProps.config.configurable.user_id` 后端拿不到 |
| 根因 | `agent.py:195` 直接 `config = ensure_config(self.config.copy() ...)`，完全忽略 forwarded_props 里的 config |
| 修复 | 后端子类化 `LangGraphAGUIAgent` 静态注入 |
| 复用 | **不要** 试图通过前端 forwardedProps 动态传 LangGraph config |

### Pit 3: dataclass `context_schema` + `thread_id` 冲突

| | |
|---|---|
| 现象 | `runtime.context = None` → `'NoneType' object has no attribute 'research_planner_prompt'` |
| 根因 | `base_context = {**configurable}` 含 `thread_id`，ContextV2 dataclass 没此字段 → `ContextV2(**dict)` `TypeError` → silent fallback |
| 修复 | 子类化 `LangGraphAGUIAgent.get_stream_kwargs`，按 dataclass `fields()` 过滤 |
| 复用 | **任何 dataclass `context_schema` + ag-ui-langgraph 组合都要这个 wrapper** |

### Pit 4: ~~introspection warning 看似但不是元凶~~（已彻底消除）

| | |
|---|---|
| 现象 | 日志 warning `context_schema introspection failed (AttributeError: 'ContextV2' object has no attribute 'schema')` |
| 真相 | 这只影响 `schema_keys["context"]`（在 ag_ui_langgraph 整个代码库里**没有任何下游消费**，所有 `filter_object_by_schema_keys` 都只用 input/output），**不影响** context 注入路径 |
| 修复（v2 迭代） | wrapper override `get_schema_keys`：dataclass schema 时直接用 `dataclasses.fields()` 短路，给出准确字段名 + 不再触发 warning |
| 教训 | warning ≠ root cause，要看完整异常栈和实际下游使用 |

### Pit 5: ~~`@copilotkit/react-ui` 没有 v2 JS 入口~~（已确认 v2 统一入口）

| | |
|---|---|
| v1 现象 | 试图 `import { CopilotChat } from '@copilotkit/react-ui/v2'` 失败 |
| v1 真相 | `package.json exports` 只有 `./styles.css` 和 `./v2/styles.css`（**仅 CSS**），JS 仍是 v1 |
| v2 改进 | 全部从 `@copilotkit/react-core/v2` 导出（包括 UI 组件） |
| 教训 | 直接读 `package.json` 的 `exports` 字段确认入口，别看文档示例假设 |

### Pit 6: v2 CSS 与 Tailwind 3.4 PostCSS 冲突 ⚠️

| | |
|---|---|
| 现象 | `[postcss] @layer base is used but no matching @tailwind base directive is present` |
| 根因 | v2 CSS 已预编译（含 Tailwind v4 `@layer properties` 等指令），项目用 Tailwind 3.4 PostCSS 处理会炸 |
| 修复（构建） | vite plugin 拦截 v2 内部 `import './index.css'`，转成 JS 模块运行时 `<style>` 注入 |
| 修复（dev） | esbuild plugin 在预 bundle 阶段同样拦截，避免 CJS 依赖裸暴露 |
| 关键点 | 1. 虚拟模块 ID 不能以 `.css` 结尾（vite 按后缀识别）<br>2. dev 模式 esbuild 预 bundle 跳过 vite plugin，需双层 shim<br>3. Windows 路径用反斜杠，`importer.replace(/\\/g, '/')` 归一化 |
| 复用 | **任何 Tailwind 3.x 项目集成 CopilotKit v2 都要这套 shim** |

### Pit 7: 中断后 `role="reasoning"` 遗留崩溃

| | |
|---|---|
| 现象 | 用户中断流式输出 → 下一轮请求 → `ValueError: Unsupported message role: reasoning` |
| 根因 | CopilotKit 把残留的 reasoning message 保留在 thread state，`agui_messages_to_langchain` 只识别 4 种标准 role（user/assistant/system/tool） |
| 修复 | `DataclassAwareLangGraphAGUIAgent.run` 入口过滤掉非标准 role 的历史消息 |
| 复用 | 任何支持 reasoning/thinking 的模型 + 中断恢复场景都需要这个过滤 |

### Pit 8: v2 Inspector 默认关闭

| | |
|---|---|
| 现象 | v2 看不到 inspector（v1 默认开） |
| 根因 | v2 把 prop 改名 `enableInspector` → `showDevConsole`，默认 `false` |
| 修复 | `<CopilotKitProvider showDevConsole="auto">` 仅本地开 |
| 复用 | v2 文档示例用旧 name `enableInspector` 是历史遗留 |

### Pit 9: `showDevConsole="auto"` 浮动 banner 遮挡顶部 header

| | |
|---|---|
| 现象 | 顶部冒出 "CopilotKit v1.50 is now live!" + 紫色钻石头像（InspectorAnchor），浮在 fixed top center 把项目自己的 header 盖掉 |
| 根因 | v2 dev banner / inspector 是全局 fixed 元素，不受外层容器约束 |
| 修复 | 默认 `showDevConsole={false}`，通过 `?dev=1` query param 切换；线上完全不显示 |
| 复用 | 移动端竖屏页面尤其敏感，统一按需开关 |

### Pit 10: `welcomeScreen` 必须传组件类型而非 ReactElement

| | |
|---|---|
| 现象 | `welcomeScreen={<MyCard pet={pet} />}` 完全不生效，仍显示默认 "How can I help you today?" |
| 根因 | v2 slot 类型是 `SlotValue<C> = C \| string \| Partial<ComponentProps<C>>`，**不接受 ReactElement** |
| 修复 | 传组件本身：`welcomeScreen={MyCardComponent}`（要传 props 用 `Partial<props>` 或闭包内层组件） |
| 复用 | 所有 v2 slot prop（`messageView` / `input` / `suggestionView` / `welcomeScreen` 等）都遵循 `SlotValue<C>` 协议 |

### Pit 11: SuggestionPill 在窄容器里挤成横排小灰字

| | |
|---|---|
| 现象 | 三条 suggestion 看着像一句话不分行 |
| 根因 | suggestion `title` 太长（含空格），SuggestionView 默认布局 wrap 不够；移动端窄容器 + 长 title → pill 间距塌缩 |
| 修复 | `title` 用 4-5 字短词（"月度餐单"），`message` 才放完整 prompt；必要时通过 `suggestionView={{ className: 'gap-3 px-4' }}` slot 扩展类名 |
| 复用 | suggestion 数据模型 `{ title, message, isLoading?, className? }`，title 是 pill 文本，message 是发给 agent 的内容 |

### Pit 12: ag-ui-langgraph 不消费 forwardedProps.config，业务上下文需手动 wrapper

| | |
|---|---|
| 现象 | 前端 `setForwardedProps({ config: { configurable: { user_id } } })` 后端拿不到 |
| 根因 | ag-ui-langgraph `prepare_stream` 只读 `forwarded_props.command/node_name/stream_subgraphs`，`config` 完全忽略；`get_stream_kwargs` 只取 `config['configurable']`（来自 self.config，是构造时静态注入的）|
| 修复 | 前端子类化 HttpAgent 添加 `setForwardedProps({ pet_information: {...} })`；后端 wrapper 在 `run()` 用 `ContextVar` 暂存 `input.forwarded_props`，`get_stream_kwargs` 里按 dataclass `fields()` 过滤合并到 raw_ctx，再实例化 `schema(**filtered)` |
| 复用 | **任何需要把 React 端业务数据传到 LangGraph context 的场景都用这个 ContextVar + forwardedProps 模式** |

### Pit 13: ⚠️ HttpAgent.clone() 不跑 constructor，instance attribute 丢失（核心坑）

| | |
|---|---|
| 现象 | 前端调 `agent.setForwardedProps({...})`，后端 log 显示 `forwarded_props keys=(empty)` —— 业务字段一个都没传过来 |
| 根因 | CopilotKit v2 `useAgent({ threadId })` 在 `cloneForThread` 中调用 `source.clone()` 创建 per-thread 实例（见 `copilotkit-Bd0m5HFp.mjs:cloneForThread`）。`HttpAgent.clone()` 用 `Object.create(Object.getPrototypeOf(this))`：**不跑 constructor，不复制实例属性**。所以子类 constructor 里 `this._extraForwardedProps = {}` 在 clone 上不存在；即便 override `clone()` 在那一刻拷贝，后续 `setForwardedProps` 修改的也是 registry agent 的字段，clone 实例完全感知不到 |
| 修复 | **不要用 instance attribute，用工厂函数 + 闭包 box**：`createContextualHttpAgent({ url })` 内部维护一个 `box = { value: {} }`，class 方法通过闭包引用 box；clone 实例与 registry agent 共享同一个 prototype，方法体内引用同一个 box —— 「set 一次，所有实例都看到」 |
| 验证 | 前端开 `import.meta.env.DEV` 在 `requestInit` 里 `console.log` 当前 `box.value`；后端在 `run()` 入口加 `logger.info` 看 `forwarded_props keys=...` 与 `ContextV2 注入完成 user_id=... pet_information=...` |
| 复用 | **任何需要随时间变化的 agent 配置（不只是 forwardedProps；也包括 headers fn、auth token 等）都用这个闭包 box 模式，不要靠 instance attribute** |

---

### Pit 14: ⚠️⚠️ `astream_events` 通过 `**kwargs` 接 `context`，`inspect.signature` 看不到（**最深坑**）

> 这条直接导致 `runtime.context` 永远为 `None`，所有节点 `ctx.research_planner_prompt` 等访问全部抛 `'NoneType' object has no attribute ...`。

| | |
|---|---|
| 现象 | 节点 / middleware 里 `ctx: ContextV2 = request.runtime.context` 拿到 `None`，访问任何字段都崩 |
| 根因 | `ag_ui_langgraph.LangGraphAgent.get_stream_kwargs` 用 `inspect.signature(graph.astream_events)` 判断是否传 context：<br>```python<br>if 'context' in sig.parameters:  # ❌ 永远 False<br>    kwargs['context'] = base_context<br>```<br>但 LangGraph 1.x 的 `astream_events(input, config, version, **kwargs)` 通过 **kwargs 接收 context 转发给内部 astream，sig 看不到。结果 `kwargs['context']` 永远不被设置 → `_coerce_context(schema, None) → None` |
| 实测 | `g.astream_events(context={'user_id': 'u1'}, version='v2')` 在 LangGraph 1.x 上**实际能正确注入** runtime.context，仅是 `inspect.signature` 不显示 context 参数 |
| 修复 | wrapper 重写 `get_stream_kwargs`，去掉 sig 检查直接强制传：<br>```python<br>def get_stream_kwargs(self, input, *, config=None, context=None, **rest):<br>    kwargs = dict(input=input, **rest)<br>    base = {}<br>    if isinstance(config, dict) and isinstance(config.get("configurable"), dict):<br>        base.update(config["configurable"])<br>    if context: base.update(context)<br>    if base: kwargs["context"] = base<br>    if config: kwargs["config"] = config<br>    return kwargs<br>``` |
| 收益 | **删除 200+ 行 wrapper patch**：原来靠 `_current_forwarded_props` ContextVar + `_coerce_pet_information` + `get_stream_kwargs` 重写过滤 thread_id 才让节点拿到 ContextV2。修复 sig 检查后，ag_ui_langgraph 标准路径 + Pydantic `extra='ignore'` 直接生效 |

---

### Pit 15: `graph.with_config(recursion_limit=N)` 在 ag_ui_langgraph 路径失效

| | |
|---|---|
| 现象 | v2 graph 编译时 `.with_config(recursion_limit=1000)`，跑起来仍报 `GraphRecursionError: Recursion limit of 25 reached` |
| 根因 | `with_config` 把默认值挂在 `CompiledStateGraph` 上，但 ag_ui_langgraph 的 `_handle_stream_events` **重新构造** config（`config = ensure_config(self.config.copy() if self.config else {})`），不继承 graph 默认值 |
| 修复 | wrapper 的 `__init__` 把 recursion_limit 直接放 `self.config`：<br>```python<br>def __init__(self, *, name, graph, description=None, config=None):<br>    merged = dict(config or {})<br>    merged.setdefault("recursion_limit", 1000)<br>    super().__init__(..., config=merged)<br>``` |
| 兜底 | `get_stream_kwargs` 里再加一层 `if "recursion_limit" not in config: config = {**config, "recursion_limit": 1000}` 防止父类构造的 config 漏掉 |

---

### Pit 16: `agui_messages_to_langchain` 对 reasoning role 抛 `ValueError`

| | |
|---|---|
| 现象 | 用户在流式 reasoning 输出时中断生成，下一次请求带历史 messages（含 `role="reasoning"`），后端崩 `ValueError: Unsupported message role: reasoning` |
| 根因 | `ag_ui_langgraph/utils.py:280` 仅识别 user/assistant/system/tool 4 种 role，其它直接 `raise ValueError` |
| 修复 | wrapper 的 `run` 在 `super().run` 之前过滤：<br>```python<br>_AGUI_STANDARD_ROLES = frozenset({"user", "assistant", "system", "tool"})<br>if input.messages:<br>    filtered = [m for m in input.messages if m.role in _AGUI_STANDARD_ROLES]<br>    if len(filtered) < len(input.messages):<br>        input = input.copy(update={"messages": filtered})<br>``` |
| 长期 | 前端可在 `agent.subscribe({onMessagesChanged})` 里也跳过 reasoning role 持久化，但后端兜底**始终必要**（agui_messages_to_langchain 是协议层强制） |

---

### Pit 17: `OnToolEnd received non-ToolMessage output` 假警报

| | |
|---|---|
| 现象 | 日志频繁出现 `WARNING ag_ui_langgraph.agent: OnToolEnd received non-ToolMessage output ('dict'); skipping dispatch`，但功能正常 |
| 根因 | LangChain 1.x 的 `@tool` 装饰器在 `on_tool_end` 事件发的是**工具原始返回值**（dict / list / str），ag_ui_langgraph 期望它是 ToolMessage。这条路径上 `TOOL_CALL_*` 已经在 `OnChatModelStream` 阶段从 `tool_call_chunks` 发出，warning 跳过的"补发"对前端无感知 |
| 修复 | 模块加载时给 `ag_ui_langgraph.agent` logger 装 logging filter：<br>```python<br>class _SilenceNonToolMessageWarning(logging.Filter):<br>    _NEEDLE = "OnToolEnd received non-ToolMessage output"<br>    def filter(self, record):<br>        return self._NEEDLE not in record.getMessage()<br>logging.getLogger("ag_ui_langgraph.agent").addFilter(_SilenceNonToolMessageWarning())<br>``` |
| 风险 | 真出现工具返回类型不匹配时也会被静默；但当前所有工具用 `@tool` 装饰，返回值由 LangChain 自动包装，这种风险极低 |

---

## 6. 可复用知识

### 6.1 AG-UI 协议核心

- 16 个标准事件类型：`TEXT_MESSAGE_{START,CONTENT,END}`、`TOOL_CALL_{START,ARGS,END,RESULT}`、`STATE_{SNAPSHOT,DELTA}`、`MESSAGES_SNAPSHOT`、`RUN_{STARTED,FINISHED,ERROR}`、`STEP_{STARTED,FINISHED}`、`CUSTOM`、`RAW`
- 传输：SSE
- 关键概念：`thread_id`（持久化会话）、`run_id`（一次执行）、`forwarded_props`（自定义透传）

### 6.2 CopilotKit v2 组件速查表

> 全部从 `@copilotkit/react-core/v2` 导出（v2 把原 react-ui 包合进去了）。

#### 顶层容器（按场景三选一）

| 组件 | 形态 | 适用场景 | 关键 Props |
|---|---|---|---|
| `<CopilotChat>` | 全屏 / 嵌入式聊天面板 | 主聊天页 | `agentId`、`threadId`、`labels`、`welcomeScreen`、`className`、`messageView`、`input`、`scrollView`、`suggestionView` |
| `<CopilotSidebar>` | 右侧边栏滑出 | 主应用旁挂助手 | 上述 + `defaultOpen`、`CopilotModalHeader` 自定义 |
| `<CopilotPopup>` | 右下角浮动气泡 + 弹层 | 全局 AI 助手 | 同 Sidebar |

**slot 替换写法**：
```jsx
// 替换内部子组件
<CopilotChat
  messageView={CustomMessageView}                      // 整个替换
  suggestionView={{ className: 'gap-3 px-2' }}          // 仅扩展 className
  input={{ disclaimer: CustomDisclaimer }}              // 部分 props 注入
/>
```

#### 细粒度子组件（自己拼装高定制 UI 时用）

| 组件 | 用途 |
|---|---|
| `CopilotChatView` | 不带 agent 自动连接的纯展示版 chat（自己控状态） |
| `CopilotChatInput` | 输入框（含发送、附件、语音按钮） |
| `CopilotChatMessageView` | 消息列表容器（虚拟滚动） |
| `CopilotChatAssistantMessage` | 单条 assistant 消息（含工具调用渲染） |
| `CopilotChatUserMessage` | 单条 user 消息（含 attachments） |
| `CopilotChatToolCallsView` | 工具调用展示（默认收纳，可展开） |
| `CopilotChatReasoningMessage` | reasoning/thinking 块的渲染 |
| `CopilotChatSuggestionView` | 建议气泡列表容器 |
| `CopilotChatSuggestionPill` | 单个建议气泡 |
| `CopilotChatToggleButton` | Popup/Sidebar 的开关按钮 |
| `CopilotChatAttachmentQueue` | 待发送附件队列展示 |
| `CopilotChatAttachmentRenderer` | 单个附件预览 |
| `CopilotChatAudioRecorder` | 麦克风录音按钮 + 状态 |
| `CopilotModalHeader` | Sidebar/Popup 顶栏（标题 + 关闭按钮） |

#### Provider 与开发工具

| 组件 | 用途 |
|---|---|
| `CopilotKitProvider` | 顶层 Provider，挂 agents__unsafe_dev_only / runtimeUrl / showDevConsole |
| `CopilotChatConfigurationProvider` | 在子树里覆盖 labels / agentId / threadId（支持嵌套多 chat） |
| `CopilotKitInspector` | 浮动 inspector（看消息流、配置、错误），通过 `showDevConsole` 控制 |

### 6.3 v2 Hook 速查表

| Hook | 用途 | 何时用 |
|---|---|---|
| `useAgent({ agentId })` | 拿到 agent 实例与运行状态 (`isRunning`、`messages`、`runAgent`) | 自定义状态指示 / 触发主动运行 |
| `useThreads()` | 当前 agent 的会话线程列表 + CRUD | 多会话 UI（侧栏切换 thread） |
| `useConfigureSuggestions({ suggestions, available })` | 配置建议气泡（`available`: `'always' \| 'auto' \| 'manual'`） | 上下文化引导（基于业务数据生成 prompts） |
| `useSuggestions()` | 拿到当前 suggestions、loading、点击回调 | 自定义 SuggestionView 渲染 |
| `useFrontendTool({ name, description, parameters, handler, render })` | 注册前端工具（agent 可调用，也可只渲染 UI） | **生成式 UI** 核心入口 |
| `useRenderTool({ name, render })` | 仅渲染（无 handler）— 把后端工具调用映射到自定义 UI | 后端工具的可视化表达 |
| `useDefaultRenderTool(...)` | 默认所有未注册工具调用的 fallback 渲染 | 兜底 |
| `useRenderToolCall()` | 单条工具调用的渲染 hook | CopilotChatToolCallsView 内部 |
| `useHumanInTheLoop({ name, render })` | 人在回路：渲染中暂停等待用户响应 | 审批 / 编辑 agent 提议 |
| `useInterrupt({ render })` | 处理 LangGraph `interrupt()` 事件 | HITL 与 v2 graph 中断协作 |
| `useRenderActivityMessage(...)` | MCP Apps Activity 流式渲染 | MCP 集成 |
| `useRenderCustomMessages(...)` | 渲染 `CUSTOM` 类型 AG-UI 事件 | 业务自定义事件 |
| `useAttachments(...)` | 上传 / 列举附件 | 多模态输入 |
| `useCapabilities()` | 探测 agent 是否支持工具 / 中断 / 状态等能力 | 渲染能力开关 UI |
| `useComponent(...)` | 获取注册的工具 UI 组件 | 高级生成式 UI |
| `useSandboxFunctions(...)` | 调用 agent 提供的沙箱函数 | 工具执行 |
| `useCopilotChatConfiguration()` | 读 labels / agentId / threadId 配置 | 自定义子组件复用配置 |
| `useCopilotKit()` | 拿到 CopilotKit 全局实例 | 高级整合 |
| `useAgentContext()` | 拿到 AgentContextInput | 子组件读取业务上下文 |

> **v1→v2 hook 改名提示**（迁移时容易踩）：
> - v1 `useCopilotAction` → v2 `useFrontendTool` / `useRenderTool` / `useHumanInTheLoop`（按用法拆分）
> - v1 `useCoAgent` → v2 `useAgent`（拿状态）+ graph state（共享数据通过 LangGraph state 自动同步）
> - v1 `useCopilotReadable` → v2 不再需要：上下文走 graph `context_schema`（见 4.4），或注册成 `useFrontendTool`

### 6.4 AG-UI client 工具（来自 `@ag-ui/client`，v2 透传导出）

| 名称 | 用途 |
|---|---|
| `HttpAgent({ url, headers })` | 直连 SSE 端点的 agent 实例（本项目用） |
| `AbstractAgent` | 自定义 agent 传输（如 WebSocket / 内存） |
| `EventType` 枚举 | 16 种 AG-UI 事件常量，便于自己消费 |

### 6.5 直连 vs Runtime 模式

| 模式 | 优点 | 缺点 |
|---|---|---|
| **CopilotKit Runtime**（Next.js API route）| 自动 properties → configurable 转换；生产稳定 | 需要 Next.js 或 Hono；多一跳 |
| **HttpAgent 直连** + `agents__unsafe_dev_only` | Vite/任意 React 都能用；少一跳 | 失去自动协议转换；标记为 dev_only |

本项目（Vite）只能选直连。

### 6.6 LangGraph 1.x context 注入完整链（v2 修复版）

```
前端 setForwardedProps({pet_information, user_id})
  ↓ HttpAgent.requestInit() 把 box.value spread 进 forwardedProps
  ↓ POST /langgraph
  ↓
DataclassAwareLangGraphAGUIAgent.run(input)
  ↓ ① 过滤 reasoning role 历史消息（agui_messages_to_langchain 不识别）
  ↓ ② 把 forwarded_props 白名单字段 → self.config["configurable"]
  ↓ super().run(input)
  ↓
ag_ui_langgraph._handle_stream_events
  ↓ ③ config = ensure_config(self.config.copy())
  ↓ ④ config["configurable"]["thread_id"] = thread_id
  ↓ ⑤ self.get_stream_kwargs(input, config)  ← wrapper override
  ↓     • base_context = config["configurable"]
  ↓     • kwargs["context"] = base_context  ← 强制传，绕过 sig 检查
  ↓     • 兜底注入 recursion_limit=1000
  ↓ ⑥ graph.astream_events(**kwargs)
  ↓
LangGraph pregel/main.py
  ↓ ⑦ _coerce_context(ContextV2, dict)
  ↓ ⑧ ContextV2(**dict)   ← Pydantic + extra='ignore' 自动吞 thread_id
  ↓     PetInformation 字段从 dict 自动验证
  ↓
节点 / Middleware
  ctx: ContextV2 = request.runtime.context  ← 完整实例 ✅
  ctx.pet_information.pet_type
  ctx.user_id
```

**两个关键 bug 修复点**（详见 Pit 14-15）：

1. **强制传 context**：ag_ui_langgraph 用 `inspect.signature` 判断是否传 context，但 LangGraph 1.x `astream_events` 通过 `**kwargs` 接收，sig 看不到 → 永远跳过传递。wrapper override `get_stream_kwargs` 直接强制传。

2. **强制传 recursion_limit**：`graph.with_config(recursion_limit=1000)` 不被 ag_ui_langgraph 继承（它重新构造 config）。wrapper 的 `__init__` 把它放进 `self.config` 让所有衍生 config 都带上。

**Schema 选型**：用 Pydantic `BaseModel(extra='ignore', arbitrary_types_allowed=True)` 而不是 dataclass。`extra='ignore'` 自动吞 `thread_id` 等系统字段，`PetInformation` 类型字段自动从 dict 验证为实例，**不需要任何 wrapper 过滤代码**。

> 类属性访问坑：dataclass 时代写 `load_chat_model(ContextV2.plan_model)` 直接拿字符串；Pydantic v2 中 `Class.field` 返回 `FieldInfo`，需改成 `ContextV2().plan_model` 实例化访问，或提取模块级常量。

### 6.7 v2 CSS Shim 完整实现（Tailwind 3.x 项目必备）

**问题**：v2 CSS 用 Tailwind v4 指令（`@layer properties`），项目 Tailwind 3.4 PostCSS 不识别。

**解决**：双层拦截（vite plugin + esbuild plugin），把 v2 内部 `import './index.css'` 转成 JS 模块运行时注入。

```js
// vite.config.js
import fs from 'node:fs'
import path from 'path'

const COPILOTKIT_V2_VIRTUAL_ID = '\0virtual:copilotkit-v2-css-shim'

const copilotkitV2CssShim = {
  name: 'copilotkit-v2-css-shim',
  enforce: 'pre',
  resolveId(source, importer) {
    if (!source.endsWith('./index.css') || !importer) return null
    const normalized = importer.replace(/\\/g, '/')
    if (normalized.includes('@copilotkit/react-core') && normalized.includes('/v2/')) {
      return COPILOTKIT_V2_VIRTUAL_ID
    }
    return null
  },
  load(id) {
    if (id === COPILOTKIT_V2_VIRTUAL_ID) {
      const cssPath = path.resolve(__dirname, 'node_modules/@copilotkit/react-core/dist/v2/index.css')
      const css = fs.readFileSync(cssPath, 'utf-8')
      return `
        const css = ${JSON.stringify(css)};
        if (typeof document !== 'undefined' && !document.querySelector('style[data-copilotkit-v2]')) {
          const style = document.createElement('style');
          style.dataset.copilotkitV2 = 'true';
          style.textContent = css;
          document.head.appendChild(style);
        }
        export default css;
      `
    }
    return null
  },
}

export default defineConfig({
  plugins: [copilotkitV2CssShim, react()],
  optimizeDeps: {
    esbuildOptions: {
      plugins: [
        {
          name: 'copilotkit-v2-css-shim-esbuild',
          setup(build) {
            build.onResolve({ filter: /^\.\/index\.css$/ }, (args) => {
              const importer = (args.importer || '').replace(/\\/g, '/')
              if (importer.includes('@copilotkit/react-core') && importer.includes('/v2/')) {
                return { path: args.path, namespace: 'copilotkit-v2-css-shim', pluginData: { importer } }
              }
              return null
            })
            build.onLoad({ filter: /.*/, namespace: 'copilotkit-v2-css-shim' }, (args) => {
              const cssPath = path.resolve(path.dirname(args.pluginData.importer), args.path)
              const css = fs.readFileSync(cssPath, 'utf-8')
              return {
                contents: `
                  const css = ${JSON.stringify(css)};
                  if (typeof document !== 'undefined' && !document.querySelector('style[data-copilotkit-v2]')) {
                    const style = document.createElement('style');
                    style.dataset.copilotkitV2 = 'true';
                    style.textContent = css;
                    document.head.appendChild(style);
                  }
                  export default css;
                `,
                loader: 'js',
              }
            })
          },
        },
      ],
    },
  },
  // ... 其他配置
})
```

**关键点**：
1. 虚拟模块 ID 用 `\0` 前缀且不以 `.css` 结尾（vite 按后缀识别 CSS）
2. dev 模式 esbuild 预 bundle 跳过 vite plugin，需 esbuild plugin 同步拦截
3. Windows 路径反斜杠，用 `replace(/\\/g, '/')` 归一化
4. 清除 `node_modules/.vite` 缓存让新配置生效

### 6.8 v2 视觉主题定制（cpk-* CSS 变量）

v2 内部用 `--cpk-*` 命名空间的 CSS 变量。**不要去改 v2 内部 class**，改变量即可：

| 变量 | 用途 |
|---|---|
| `--cpk-font-sans` | 整体字体（默认 system-ui） |
| `--cpk-font-mono` | 代码块字体 |
| `--cpk-radius-md` / `--cpk-radius-lg` / `--cpk-radius-xl` | 圆角（消息气泡、按钮、容器） |
| `--cpk-color-gray-*` / `--cpk-color-blue-*` 等 | 调色板（按 oklch 定义） |
| `--cpk-default-transition-duration` | 动画时长 |

**最佳实践**：在容器节点 `style={{ '--cpk-*': ... }}` 上注入，scope 化只影响该子树，不污染全局。本项目示例：

```jsx
// AGUITest.jsx
const cpkThemeStyle = {
  '--cpk-font-sans': "'Plus Jakarta Sans', system-ui, sans-serif",
  '--cpk-radius-md': '0.875rem',
  '--cpk-radius-lg': '1.125rem',
  '--cpk-radius-xl': '1.5rem',
};
<div style={cpkThemeStyle}>
  <CopilotKitProvider ...>
    <CopilotChat ... />
  </CopilotKitProvider>
</div>
```

进一步定制（如品牌色映射到 chat 主色），可观察实际渲染节点的 class，对照 `node_modules/@copilotkit/react-core/dist/v2/index.css` 找对应变量再覆盖。**避免直接覆盖 .cpk-* 类名**——升级时易碎。

---

## 7. 关键文件清单

### 后端新增
- `src/api/agui_agent.py` — `DataclassAwareLangGraphAGUIAgent` 子类
  - `get_schema_keys()`: dataclass schema 时用 `fields()` 短路，消除 introspection warning
  - `run()`: 过滤非标准 role（reasoning/thinking 等中断遗留）+ `ContextVar` 暂存 forwarded_props
  - `get_stream_kwargs()`: 过滤 thread_id，合并 forwardedProps 业务字段 → 实例化 ContextV2（pet_information dict 自动 → PetInformation Pydantic 实例）

### 后端修改
- `src/api/main.py:60-86` — lifespan 中替换 `LangGraphAGUIAgent` → `DataclassAwareLangGraphAGUIAgent`

### 前端新增
- `frontend/web-app/src/pages/AGUITest.jsx` — 实验页面，HttpAgent 直连，v2 API
- `frontend/web-app/src/utils/contextualHttpAgent.js` — `createContextualHttpAgent({ url })` 工厂：用闭包 box 共享 forwardedProps，绕开 HttpAgent.clone 不跑 constructor 导致的 instance attribute 丢失（见 Pit 13）；DEV 模式下 `console.log` 每次 prepareRunAgentInput / run 的实际 forwardedProps 用于调试
- `frontend/web-app/.env`（追加）— `VITE_AGUI_BASE_URL`、`VITE_AGUI_AGENT_NAME`

### 前端修改
- `frontend/web-app/src/App.jsx:27, 196` — 注册路由 `/agui-test`
- `frontend/web-app/src/pages/CreatePlan.jsx:319-326` — 紫粉色烧瓶悬浮按钮
- `frontend/web-app/vite.config.js` — 新增 `copilotkitV2CssShim` plugin + esbuild plugin

### 包依赖
- 前端新增：`@copilotkit/react-core@1.56.4`（v2 统一入口）、`@ag-ui/client`（自动装）
- 后端：已预装 `ag-ui-langgraph>=0.0.34`、`copilotkit>=0.1.87`

---

## 8. 启动与验证

```bash
# 后端
cd "pet_food_backend/pet-food"
python main.py
# 等待日志：LangGraph /langgraph endpoint ready

# 前端（首次需清缓存）
cd "frontend/web-app"
rm -rf node_modules/.vite  # Windows: rmdir /s /q node_modules\.vite
npm run dev
```

浏览器：登录 → `/plan/create` → 点右下角紫粉色烧瓶 → `/agui-test` → 输入消息。

**验证点**：
- ✅ 浏览器 Network 面板看到 SSE 流到 `<host>/langgraph`
- ✅ 后端日志看到 `plan_agent` 节点执行 + `emit_progress: research_starting`
- ✅ 没有 `'NoneType' object has no attribute 'research_planner_prompt'`
- ✅ 没有 `Unsupported message role: reasoning`（中断后再发消息）
- ✅ 没有 PostCSS `@layer base` 错误
- ✅ CopilotChat 流式渲染响应
- ✅ 右上角看到 inspector（可拖拽）

---

## 9. 未来扩展方向

| 方向 | 思路 |
|---|---|
| ~~注入业务 context~~ ✅ 已实现 | 前端 ContextualHttpAgent.setForwardedProps + 后端 ContextVar 注入 ContextV2 |
| 生成式 UI | 用 `useCoAgentStateRender` 把 v2 graph 中间状态（research_logs、week_plans）流式渲染为卡片 |
| 人在回路 | 在 `dispatch_weeks` 节点用 LangGraph `interrupt()` + 前端 `useCopilotAction({ renderAndWaitForResponse })` 做用户审批 CoordinationGuide |
| 兼容 BaseModel | 如果未来改用 Pydantic，wrapper 增加 `issubclass(schema, BaseModel)` 分支用 `schema.model_validate(filtered)` |
| 替换主流程 SSE | 把现有 `PlanGenerationContext` 手写 SSE 改成 `useCoAgent`，去掉 fallback 轮询逻辑 |
| 升级 Tailwind v4 | 彻底解决 CSS 冲突（但影响全项目，需评估） |

---

## 10. 协议参考

- AG-UI 协议官网：https://docs.ag-ui.com
- CopilotKit 文档：https://docs.copilotkit.ai
- CopilotKit v2 迁移指南：https://docs.copilotkit.ai/langgraph/troubleshooting/migrate-to-v2
- LangGraph context_schema：https://langchain-ai.github.io/langgraph/concepts/runtime
- ag-ui-langgraph 源码：`pet-food/.venv/Lib/site-packages/ag_ui_langgraph/agent.py`
- LangGraph `_coerce_context`：`pet-food/.venv/Lib/site-packages/langgraph/...`（关键函数，见 deepwiki）

---

## 附录：v1 → v2 迁移 Checklist

- [ ] 前端包：`@copilotkit/react-core` + `@copilotkit/react-ui` → `@copilotkit/react-core/v2`
- [ ] CSS 导入：`@copilotkit/react-ui/styles.css` → 删除（由 vite plugin 注入）
- [ ] Provider：`<CopilotKit>` → `<CopilotKitProvider>`
- [ ] 删除 `publicApiKey` prop（v2 有 `agents__unsafe_dev_only` 时可选）
- [ ] agent 配置：Provider 的 `agent="name"` → `<CopilotChat agentId="name">`
- [ ] Inspector：`enableInspector={false}` → `showDevConsole="auto"`
- [ ] vite.config.js：加 `copilotkitV2CssShim` plugin + esbuild plugin（见 6.6）
- [ ] 清除缓存：`rm -rf node_modules/.vite`
- [ ] 后端：`DataclassAwareLangGraphAGUIAgent.run()` 加 reasoning role 过滤
- [ ] 测试中断恢复：发消息 → 中断 → 再发消息，确认不报 `Unsupported message role`
