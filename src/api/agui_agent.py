"""AG-UI 适配层（精简版 + LangGraph 1.x 兼容修复）

ag_ui_langgraph.LangGraphAGUIAgent 的两个标准行为已经满足 99% 的需求：
- `clone()` 在每次请求重新调用 __init__，self.config 是请求私有副本，并发安全。
- `prepare_stream` 把 `config["configurable"]` 整体喂给 `get_stream_kwargs`，再传给
  `astream_events(context=...)`，最终 LangGraph 用 `context_schema(**dict)` 实例化为
  runtime.context（详见 `langgraph/pregel/main.py:_coerce_context`）。

本 wrapper 补五件 ag_ui_langgraph 没做对 / 没做的事：

1. **过滤非标准 role 的历史消息**：`agui_messages_to_langchain` 对 user/assistant/system/tool
   之外的 role（reasoning / thinking 等）会抛 ValueError。中断恢复时前端可能回传残留的
   reasoning role 消息，这里在 super().run 之前过滤。

2. **把前端 forwardedProps 的业务字段透传到 ContextV2**：前端把 `pet_information` /
   `user_id` 放在 forwardedProps 顶层，这里 camelCase→snake_case 后塞进
   `self.config["configurable"]`。

3. **强制传 context 给 astream_events**（关键修复）：
   ag_ui_langgraph 用 `inspect.signature(graph.astream_events)` 判断是否传 context，
   但 LangGraph 1.x 的 `astream_events(input, config, version, **kwargs)` 通过 **kwargs
   接受 context，sig.parameters 看不到 → ag_ui_langgraph 永远跳过传递 →
   runtime.context 永远是 None。
   重写 `get_stream_kwargs` 直接把 config['configurable'] 当 context 传，绕过这个 bug。

4. **注入默认 recursion_limit**：
   `graph.with_config(recursion_limit=1000)` 写在 CompiledStateGraph 的默认 config 里，
   但 ag_ui_langgraph 在 _handle_stream_events 重新构造 config，不继承 graph 默认值，
   所以 with_config 的 recursion_limit 失效，graph 用 LangGraph 默认 25。
   wrapper 的 __init__ 把 recursion_limit 直接放进 self.config，让所有衍生 config 都带上。

5. **给 reasoning 事件补 raw_event**：
   ag_ui_langgraph 从 `on_chat_model_stream` 的 `AIMessageChunk` 解析 reasoning，
   但生成 `REASONING_*` 事件时没有带 raw_event，前端拿不到 metadata.subagent_id。
   这里只在当前 chat model stream 事件处理期间临时补回 raw_event。
"""
import logging
from typing import Any, Dict, Literal, Optional

from ag_ui.core import EventType
from ag_ui_langgraph.types import LangGraphEventTypes
from ag_ui_langgraph.utils import camel_to_snake, resolve_reasoning_content
from copilotkit import LangGraphAGUIAgent
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

logger = logging.getLogger(__name__)


# ─── 模块级：屏蔽 ag_ui_langgraph 的 false positive warning ───
class _SilenceNonToolMessageWarning(logging.Filter):
    """ag_ui_langgraph 的 OnToolEnd 假警报屏蔽器。

    LangChain @tool 的 on_tool_end 事件 data.output 是工具原始返回值（dict/list/str），
    ag_ui_langgraph 期望它是 ToolMessage，不匹配就打 warning。但实际 TOOL_CALL_* 事件
    在 OnChatModelStream 阶段已经发出，这条 warning 不影响功能，仅是日志噪音。
    """

    _NEEDLE = "OnToolEnd received non-ToolMessage output"

    def filter(self, record: logging.LogRecord) -> bool:
        return self._NEEDLE not in record.getMessage()


logging.getLogger("ag_ui_langgraph.agent").addFilter(_SilenceNonToolMessageWarning())


# ag_ui_langgraph.utils.agui_messages_to_langchain 仅支持的 4 种标准 role
_AGUI_STANDARD_ROLES = frozenset({"user", "assistant", "system", "tool"})

# 业务字段白名单：仅这些键会被透传到 ContextV2
_BIZ_KEYS = frozenset({"pet_information", "user_id"})

# v2 graph 拓扑深度：plan_agent + 4 个 week_agent 子图（每个含 tool 循环），25 远不够。
# 设为 1000 与 v2/graph.py 的 with_config(recursion_limit=1000) 保持一致。
_DEFAULT_RECURSION_LIMIT = 1000

_REASONING_EVENT_TYPES = frozenset({
    EventType.REASONING_START,
    EventType.REASONING_MESSAGE_START,
    EventType.REASONING_MESSAGE_CONTENT,
    EventType.REASONING_MESSAGE_END,
    EventType.REASONING_END,
    EventType.REASONING_ENCRYPTED_VALUE,
})


class DataclassAwareLangGraphAGUIAgent(LangGraphAGUIAgent):
    """LangGraphAGUIAgent 的轻量 patch（保留原类名以兼容现有 import 与日志）。"""

    def __init__(
        self,
        *,
        name: str,
        graph: CompiledStateGraph,
        description: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        # 注入默认 recursion_limit（ag_ui_langgraph 不继承 graph.with_config 默认值）
        merged_config: Dict[str, Any] = dict(config or {})
        merged_config.setdefault("recursion_limit", _DEFAULT_RECURSION_LIMIT)
        super().__init__(name=name, graph=graph, description=description, config=merged_config)
        self._current_reasoning_raw_event = None

    async def run(self, input):
        # 1) 过滤 reasoning 等非标准 role 历史消息
        messages = getattr(input, "messages", None)
        if messages:
            filtered = [m for m in messages if m.role in _AGUI_STANDARD_ROLES]
            if len(filtered) < len(messages):
                logger.info(
                    "AGUI Adapter: 过滤 %d 条非标准 role 消息（中断遗留）",
                    len(messages) - len(filtered),
                )
                input = input.copy(update={"messages": filtered})

        # 2) forwardedProps 业务字段 → self.config["configurable"]
        #    (clone 已让 self.config 请求私有，修改不影响其它请求)
        raw_fwd = getattr(input, "forwarded_props", None) or {}
        biz = {
            camel_to_snake(k): v
            for k, v in raw_fwd.items()
            if camel_to_snake(k) in _BIZ_KEYS and v is not None
        }
        if biz:
            base_config = self.config or {}
            self.config = {
                **base_config,
                "configurable": {**(base_config.get("configurable") or {}), **biz},
            }
            logger.debug("AGUI Adapter: 注入 ContextV2 字段 %s", list(biz.keys()))

        async for event in super().run(input):
            yield event

    def _dispatch_event(self, event):
        raw_event = self._current_reasoning_raw_event
        if (
            raw_event is not None
            and getattr(event, "type", None) in _REASONING_EVENT_TYPES
            and getattr(event, "raw_event", None) is None
        ):
            event.raw_event = raw_event
        return super()._dispatch_event(event)

    def _reasoning_raw_event_for(self, event: Any) -> Any | None:
        if event.get("event") != LangGraphEventTypes.OnChatModelStream.value:
            return None

        chunk = (event.get("data") or {}).get("chunk")
        if chunk is not None and resolve_reasoning_content(chunk):
            return event

        if self.active_run and self.active_run.get("reasoning_process") is not None:
            return event

        return None

    async def _handle_single_event(self, event: Any, state):
        previous_raw_event = self._current_reasoning_raw_event
        self._current_reasoning_raw_event = self._reasoning_raw_event_for(event)
        try:
            async for event_str in super()._handle_single_event(event, state):
                yield event_str
        finally:
            self._current_reasoning_raw_event = previous_raw_event

    def get_stream_kwargs(
        self,
        input: Any,
        subgraphs: bool = False,
        version: Literal["v1", "v2"] = "v2",
        config: Optional[RunnableConfig] = None,
        context: Optional[Dict[str, Any]] = None,
        fork: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """重写父类逻辑：父类用 `inspect.signature(astream_events)` 判断是否传 context，
        但 LangGraph 1.x 的 astream_events 通过 **kwargs 接收 context，sig 看不到。
        这里直接强制传 context（合并 config.configurable + 显式 context），让
        LangGraph 的 _coerce_context 能正确实例化 context_schema。
        """
        kwargs: Dict[str, Any] = dict(input=input, subgraphs=subgraphs, version=version)

        # 合并 base_context = config.configurable + 显式 context（后者优先）
        base_context: Dict[str, Any] = {}
        if isinstance(config, dict):
            configurable = config.get("configurable")
            if isinstance(configurable, dict):
                base_context.update(configurable)
        if context:
            base_context.update(context)
        if base_context:
            kwargs["context"] = base_context

        if config:
            # 兜底：父类构造的 config 可能丢失 recursion_limit，再补一次
            if "recursion_limit" not in config:
                config = {**config, "recursion_limit": _DEFAULT_RECURSION_LIMIT}
            kwargs["config"] = config
        if fork:
            kwargs.update(fork)

        return kwargs
