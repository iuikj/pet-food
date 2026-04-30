"""
AG-UI 适配层：让 ag_ui_langgraph 兼容 LangGraph 1.x 的 dataclass context_schema。

## 问题背景

ag_ui_langgraph 的 `LangGraphAgent.get_stream_kwargs` 会把 `config['configurable']`
（含 `thread_id`）整个塞进 LangGraph 1.x 的 `context` 参数。
LangGraph 用 `context_schema(**ctx_dict)` 实例化 dataclass，多余字段（如 `thread_id`）
触发 TypeError，于是 `runtime.context` 变成 None，下游 middleware 抛 AttributeError。

## 修复

子类化 `LangGraphAGUIAgent`，重写 `get_stream_kwargs`：
1. 过滤 context dict，只保留 dataclass 字段
2. 用过滤后的 dict 实例化 dataclass，作为 `context` 传给 graph
3. 这样 dataclass 默认值生效，graph 拿到完整的 ContextV2 实例

完全不动 v2 graph 源码，只在协议适配层修复。
"""
import logging
from dataclasses import fields, is_dataclass
from typing import Any

from copilotkit import LangGraphAGUIAgent

logger = logging.getLogger(__name__)


class DataclassAwareLangGraphAGUIAgent(LangGraphAGUIAgent):
    """补丁版 LangGraphAGUIAgent：兼容 dataclass context_schema。"""

    def get_stream_kwargs(self, *args, **kwargs) -> dict[str, Any]:
        result = super().get_stream_kwargs(*args, **kwargs)

        schema = getattr(self.graph, "context_schema", None)
        if schema is None or not is_dataclass(schema):
            return result

        valid_field_names = {f.name for f in fields(schema)}
        raw_ctx = result.get("context") or {}

        filtered = {k: v for k, v in raw_ctx.items() if k in valid_field_names}
        try:
            # dataclass 所有字段都有默认值时可零参实例化；
            # 过滤后的字段覆盖默认值，未传字段保留默认。
            result["context"] = schema(**filtered)
        except TypeError as exc:
            # 兜底：实例化失败仍打印诊断信息，让 graph 收到 None 时能定位
            logger.warning(
                "DataclassAwareLangGraphAGUIAgent: 无法用过滤后的字段 %s 实例化 %s (%s)，"
                "fallback 为不传 context",
                list(filtered.keys()),
                schema.__name__,
                exc,
            )
            result.pop("context", None)

        return result
