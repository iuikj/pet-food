"""AG-UI 适配层（精简版 + LangGraph 1.x context 强制注入）

ag_ui_langgraph.LangGraphAGUIAgent 的两个标准行为已经满足 99% 的需求：
- `clone()` 在每次请求重新调用 __init__，self.config 是请求私有副本，并发安全。
- `prepare_stream` 把 `config["configurable"]` 整体喂给 `get_stream_kwargs`，再传给
  `astream_events(context=...)`，最终 LangGraph 用 `context_schema(**dict)` 实例化为
  runtime.context（详见 `langgraph/pregel/main.py:_coerce_context`）。

本 wrapper 补三件 ag_ui_langgraph 没做对 / 没做的事：

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
"""
import inspect
import logging
from typing import Any, Dict, Literal, Optional

from copilotkit import LangGraphAGUIAgent
from ag_ui_langgraph.utils import camel_to_snake
from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)

# ag_ui_langgraph.utils.agui_messages_to_langchain 仅支持的 4 种标准 role
_AGUI_STANDARD_ROLES = frozenset({"user", "assistant", "system", "tool"})

# 业务字段白名单：仅这些键会被透传到 ContextV2
_BIZ_KEYS = frozenset({"pet_information", "user_id"})


class DataclassAwareLangGraphAGUIAgent(LangGraphAGUIAgent):
    """LangGraphAGUIAgent 的轻量 patch（保留原类名以兼容现有 import 与日志）。"""

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
            kwargs["config"] = config
        if fork:
            kwargs.update(fork)

        return kwargs
