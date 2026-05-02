"""
AG-UI 适配层：让 ag_ui_langgraph 兼容 LangGraph 1.x 的 dataclass context_schema，
并修复中断恢复时遗留 reasoning message 引发的崩溃。

## 问题 1：context_schema 不兼容

ag_ui_langgraph 的 `LangGraphAgent.get_stream_kwargs` 会把 `config['configurable']`
（含 `thread_id`）整个塞进 LangGraph 1.x 的 `context` 参数。
LangGraph 用 `context_schema(**ctx_dict)` 实例化 dataclass，多余字段（如 `thread_id`）
触发 TypeError，于是 `runtime.context` 变成 None，下游 middleware 抛 AttributeError。

→ 重写 `get_stream_kwargs`，按 dataclass fields 过滤后实例化。

## 问题 2：用户中断后 thread 历史含 reasoning role

用户在 agent 流式输出（含 reasoning chunk）时中断，CopilotKit 把残留的
reasoning message 保留在 thread state。下一轮请求把历史 messages 发回，
其中含 `role="reasoning"`，`agui_messages_to_langchain` 不识别四种标准 role
之外的 role，抛 `ValueError: Unsupported message role: reasoning`。

→ 重写 `run`，在调用 super 前过滤掉非标准 role 的历史消息。

## 问题 3：业务上下文（宠物信息等）需通过 forwardedProps 透传

ag_ui_langgraph 的 prepare_stream 不消费 forwarded_props.config（见 AGUI_INTEGRATION.md Pit 2），
但 `input.forwarded_props` 本身可读。我们用 contextvars 在 `run()` 入口暂存当前请求的
forwarded_props，再在 `get_stream_kwargs` 中按 schema 字段挑出业务键合并进 raw_ctx，
对 dict 形式的 pet_information 自动实例化为 PetInformation Pydantic 模型，与现有
SSE 食谱制定流程（plan_service._prepare_inputs）的 ContextV2 形态保持一致。

## 问题 4：每次请求 introspection warning 刷屏

ag_ui_langgraph 的 `get_schema_keys` 用 `graph.context_schema().schema()` 这种 Pydantic v1
风格反射，LangGraph 1.x 的 dataclass `context_schema` 没有 `.schema()` 方法，
每个请求都打 warning：
  `context_schema introspection failed (AttributeError: 'ContextV2' object has no attribute 'schema')`

实际上 `schema_keys["context"]` 在 ag_ui_langgraph 整个代码库里只被 `get_schema_keys` 自己赋值，
下游所有 `filter_object_by_schema_keys` 都只用 input/output —— 这条 warning 完全无害但很吵。

→ 重写 `get_schema_keys`，dataclass schema 时直接用 `dataclasses.fields()` 短路，
   既给出准确的 context 字段列表（万一未来有人用），又彻底消除 warning。

完全不动 v2 graph 源码，只在协议适配层修复。
"""
import contextvars
import logging
from dataclasses import fields, is_dataclass
from typing import Any

from copilotkit import LangGraphAGUIAgent
from ag_ui_langgraph.utils import camel_to_snake

from src.utils.strtuct import PetInformation

logger = logging.getLogger(__name__)

# ag_ui_langgraph.utils.agui_messages_to_langchain 支持的 4 种标准 role
_AGUI_STANDARD_ROLES = frozenset({"user", "assistant", "system", "tool"})

# 当前请求 scope 的 forwarded_props（已 camel→snake 规范化）。
# 用 ContextVar 而非实例属性以避免并发请求互相覆盖。
_current_forwarded_props: contextvars.ContextVar[dict] = contextvars.ContextVar(
    "agui_current_forwarded_props", default={}
)


def _coerce_pet_information(value: Any) -> Any:
    """把前端传来的 dict 实例化为 PetInformation；其它情况原样返回。"""
    if isinstance(value, PetInformation) or value is None:
        return value
    if isinstance(value, dict):
        try:
            return PetInformation(**value)
        except Exception as exc:  # ValidationError / TypeError 等
            logger.warning(
                "forwardedProps.pet_information 构造 PetInformation 失败 (%s)，"
                "原始值=%s，将忽略此字段",
                exc, value,
            )
            return None
    return value


class DataclassAwareLangGraphAGUIAgent(LangGraphAGUIAgent):
    """补丁版 LangGraphAGUIAgent：
    1. 兼容 dataclass context_schema（注入 + introspection）
    2. 过滤掉中断遗留的非标准 role 消息（reasoning / thinking 等）
    3. 把前端 forwardedProps 中的业务字段（pet_information / user_id 等）注入 ContextV2
    """

    def get_schema_keys(self, config) -> dict[str, Any]:
        """重写父类的 schema introspection，避免 dataclass context_schema 触发
        `'ContextV2' object has no attribute 'schema'` warning。

        父类对 input/output/config 用 `get_input_jsonschema` / `config_schema().schema()`，
        对 context 用 `context_schema().schema()`。前者在 LangGraph 1.x 仍可用，后者
        在 dataclass schema 上不可用（dataclass 没有 .schema() 方法）。

        我们这里复刻父类的 input/output/config 计算路径，对 context 改用 `fields()`
        直接读 dataclass 字段名 —— 更准确（不依赖 Pydantic 反射），也消除 warning。
        """
        schema = getattr(self.graph, "context_schema", None)
        if schema is None or not is_dataclass(schema):
            # 非 dataclass（None / Pydantic / TypedDict）走父类原逻辑
            return super().get_schema_keys(config)

        try:
            input_schema = self.graph.get_input_jsonschema(config)
            output_schema = self.graph.get_output_jsonschema(config)
            config_schema_dict = self.graph.config_schema().schema()

            input_keys = list(input_schema.get("properties", {}).keys())
            output_keys = list(output_schema.get("properties", {}).keys())
            config_keys = list(config_schema_dict.get("properties", {}).keys())
            context_keys = [f.name for f in fields(schema)]

            return {
                "input": [*input_keys, *self.constant_schema_keys],
                "output": [*output_keys, *self.constant_schema_keys],
                "config": config_keys,
                "context": context_keys,
            }
        except (AttributeError, TypeError, KeyError, ValueError, NotImplementedError) as exc:
            logger.debug(
                "DataclassAwareLangGraphAGUIAgent.get_schema_keys: 短路路径失败 (%s: %s)，"
                "fallback 到父类",
                type(exc).__name__, exc,
            )
            return super().get_schema_keys(config)

    async def run(self, input):
        # 1) 把当前请求的 forwarded_props 暂存到 ContextVar，供 get_stream_kwargs 注入业务字段。
        #    父类 run 第一行也会做 camel_to_snake，我们这里同步做一次保证语义一致。
        raw_fwd = getattr(input, "forwarded_props", None)
        normalized_fwd: dict = {}
        if isinstance(raw_fwd, dict):
            for k, v in raw_fwd.items():
                key = camel_to_snake(k) if isinstance(k, str) else k
                normalized_fwd[key] = v

        # 调试日志：观察前端真正传过来的字段（含 keys 与 pet_information 摘要）
        logger.info(
            "[AGUI Adapter.run] thread_id=%s | forwarded_props keys=%s | pet_information=%s | user_id=%s",
            getattr(input, "thread_id", None),
            list(normalized_fwd.keys()) or "(empty)",
            normalized_fwd.get("pet_information"),
            normalized_fwd.get("user_id"),
        )

        token = _current_forwarded_props.set(normalized_fwd)
        try:
            # 2) 中断恢复时前端可能携带 role="reasoning" 等非标准消息，会让
            #    ag_ui_langgraph 的 agui_messages_to_langchain 抛 ValueError。
            #    这里在 super().run 之前主动过滤。
            if getattr(input, "messages", None):
                original_count = len(input.messages)
                filtered_messages = [
                    m for m in input.messages
                    if getattr(m, "role", None) in _AGUI_STANDARD_ROLES
                ]
                if len(filtered_messages) < original_count:
                    dropped = original_count - len(filtered_messages)
                    logger.info(
                        "DataclassAwareLangGraphAGUIAgent: 过滤掉 %d 条非标准 role 消息（中断遗留）",
                        dropped,
                    )
                    input = input.copy(update={"messages": filtered_messages})

            async for event in super().run(input):
                yield event
        finally:
            _current_forwarded_props.reset(token)

    def get_stream_kwargs(self, *args, **kwargs) -> dict[str, Any]:
        result = super().get_stream_kwargs(*args, **kwargs)

        schema = getattr(self.graph, "context_schema", None)
        if schema is None or not is_dataclass(schema):
            return result

        valid_field_names = {f.name for f in fields(schema)}

        # 收集 raw_ctx：超类返回的 context（来自 config.configurable，含 thread_id）
        raw_ctx = result.get("context") or {}
        if not isinstance(raw_ctx, dict):
            raw_ctx = {}
        else:
            raw_ctx = dict(raw_ctx)  # 拷贝，避免修改原对象

        # 把前端 forwardedProps 中的业务字段合并进来（仅当 raw_ctx 没有同名 key）
        biz = _current_forwarded_props.get() or {}
        for key in valid_field_names:
            if key in biz and biz[key] is not None and key not in raw_ctx:
                raw_ctx[key] = biz[key]

        # pet_information 特殊处理：dict → PetInformation 实例
        if "pet_information" in raw_ctx:
            raw_ctx["pet_information"] = _coerce_pet_information(raw_ctx["pet_information"])

        # 按 schema 字段过滤多余键（thread_id 等），再实例化 ContextV2
        filtered = {k: v for k, v in raw_ctx.items() if k in valid_field_names}
        try:
            # dataclass 所有字段都有默认值时可零参实例化；
            # 过滤后的字段覆盖默认值，未传字段保留默认。
            ctx_instance = schema(**filtered)
            result["context"] = ctx_instance

            # 调试日志：观察最终注入到 graph 的 ContextV2 关键字段
            pet_info = getattr(ctx_instance, "pet_information", None)
            logger.info(
                "[AGUI Adapter.get_stream_kwargs] %s 注入完成 | filtered_keys=%s | "
                "user_id=%s | pet_information=%s",
                schema.__name__,
                list(filtered.keys()),
                getattr(ctx_instance, "user_id", None),
                pet_info,
            )
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
