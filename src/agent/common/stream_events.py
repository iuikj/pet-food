"""
流式进度事件定义

提供结构化的 ProgressEvent 消息，供各 agent 节点通过双通道发送业务级进度信息：

通道 ❶ get_stream_writer()
    LangGraph 原生 custom 通道，被 graph.astream(stream_mode="custom") 消费。
    供 src/api/utils/stream.py 的 SSE 路径使用（plan_service /api/v1/plans/stream）。

通道 ❷ adispatch_custom_event(event_name, payload)
    LangChain callback 通道，被 graph.astream_events(version="v2") 消费。
    供 ag_ui_langgraph 路径使用（/langgraph 端点 → AG-UI CUSTOM 事件 → CopilotKit）。

ag_ui_langgraph.agent.py 写死调用 astream_events，不传 stream_mode，因此业务进度想被
AG-UI 协议层看到，**必须**走通道 ❷。但 plan_service 已上线消费通道 ❶，所以同时双发
是最低成本方案（每个调用点零改动）。

详细决策见 AGUI_INTEGRATION.md 与 v2 GenUI 方案文档。
"""
import asyncio
import logging
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def _deep_serialize(obj: Any) -> Any:
    """递归序列化嵌套的 Pydantic 模型 / dataclass / 列表 / 字典为原生类型"""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return {k: _deep_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_deep_serialize(item) for item in obj]
    return obj


class ProgressEventType(str, Enum):
    """业务级流式进度事件类型。

    事件 payload 的字符串值保持稳定，避免前端和历史 SSE 回放大规模迁移。
    新代码优先用下方挂载的二级枚举入口，例如:
    ``ProgressEventType.Research.STARTING``、``ProgressEventType.Week.PLANNING``。

    AG-UI 标准 text / reasoning / tool events 不在这里重复定义。
    """

    # ── 主智能体 / 研究阶段 ──
    PLAN_CREATING = "plan_creating"
    PLAN_CREATED = "plan_created"
    PLAN_UPDATED = "plan_updated"
    TASK_DELEGATING = "task_delegating"
    RESEARCH_STARTING = "research_starting"
    RESEARCH_TASK_DELEGATING = "research_task_delegating"
    RESEARCH_FINALIZING = "research_finalizing"

    # ── 子智能体 ──
    TASK_EXECUTING = "task_executing"
    TASK_SEARCHING = "task_searching"
    TASK_QUERYING_NOTE = "task_querying_note"
    TASK_COMPLETED = "task_completed"

    # ── 写入 / 摘要 ──
    NOTE_SAVING = "note_saving"
    NOTE_SAVED = "note_saved"
    SUMMARY_GENERATING = "summary_generating"
    SUMMARY_GENERATED = "summary_generated"

    # ── 分发 / 周计划并行阶段 ──
    DISPATCHING = "dispatching"
    WEEK_PLANNING = "week_planning"
    WEEK_SEARCHING = "week_searching"
    WEEK_WRITING = "week_writing"
    WEEK_COMPLETED = "week_completed"

    # 保留兼容值，不再从 v2 middleware 主动发送，避免 week_writing 重叠。
    WEEK_PLAN_READY = "week_plan_ready"

    # ── 汇总 / 结构化 ──
    GATHERING = "gathering"
    STRUCTURING = "structuring"
    STRUCTURING_RETRY = "structuring_retry"
    STRUCTURED = "structured"
    COMPLETED = "completed"

    # ── 通用 ──
    ERROR = "error"
    INFO = "info"


class _ResearchProgressEventType(str, Enum):
    STARTING = ProgressEventType.RESEARCH_STARTING.value
    TASK_DELEGATING = ProgressEventType.RESEARCH_TASK_DELEGATING.value
    FINALIZING = ProgressEventType.RESEARCH_FINALIZING.value


class _PlanProgressEventType(str, Enum):
    CREATING = ProgressEventType.PLAN_CREATING.value
    CREATED = ProgressEventType.PLAN_CREATED.value
    UPDATED = ProgressEventType.PLAN_UPDATED.value


class _AgentProgressEventType(str, Enum):
    DELEGATING = ProgressEventType.TASK_DELEGATING.value


class _TaskProgressEventType(str, Enum):
    DELEGATING = ProgressEventType.TASK_DELEGATING.value
    EXECUTING = ProgressEventType.TASK_EXECUTING.value
    SEARCHING = ProgressEventType.TASK_SEARCHING.value
    QUERYING_NOTE = ProgressEventType.TASK_QUERYING_NOTE.value
    COMPLETED = ProgressEventType.TASK_COMPLETED.value


class _NoteProgressEventType(str, Enum):
    SAVING = ProgressEventType.NOTE_SAVING.value
    SAVED = ProgressEventType.NOTE_SAVED.value


class _SummaryProgressEventType(str, Enum):
    GENERATING = ProgressEventType.SUMMARY_GENERATING.value
    GENERATED = ProgressEventType.SUMMARY_GENERATED.value


class _DispatchProgressEventType(str, Enum):
    STARTING = ProgressEventType.DISPATCHING.value


class _WeekProgressEventType(str, Enum):
    PLANNING = ProgressEventType.WEEK_PLANNING.value
    SEARCHING = ProgressEventType.WEEK_SEARCHING.value
    WRITING = ProgressEventType.WEEK_WRITING.value
    COMPLETED = ProgressEventType.WEEK_COMPLETED.value
    PLAN_READY = ProgressEventType.WEEK_PLAN_READY.value


class _ResultProgressEventType(str, Enum):
    GATHERING = ProgressEventType.GATHERING.value
    STRUCTURING = ProgressEventType.STRUCTURING.value
    RETRYING = ProgressEventType.STRUCTURING_RETRY.value
    STRUCTURED = ProgressEventType.STRUCTURED.value
    COMPLETED = ProgressEventType.COMPLETED.value


class _RunProgressEventType(str, Enum):
    ERROR = ProgressEventType.ERROR.value
    INFO = ProgressEventType.INFO.value


# Python Enum 不能在类体内直接声明子 Enum；否则子类本身会变成一个枚举成员。
# 这里在类创建后挂载，提供 ProgressEventType.Research.STARTING 这类二级调用入口。
ProgressEventType.Research = _ResearchProgressEventType  # type: ignore[attr-defined]
ProgressEventType.Plan = _PlanProgressEventType  # type: ignore[attr-defined]
ProgressEventType.Agent = _AgentProgressEventType  # type: ignore[attr-defined]
ProgressEventType.Task = _TaskProgressEventType  # type: ignore[attr-defined]
ProgressEventType.Note = _NoteProgressEventType  # type: ignore[attr-defined]
ProgressEventType.Summary = _SummaryProgressEventType  # type: ignore[attr-defined]
ProgressEventType.Dispatch = _DispatchProgressEventType  # type: ignore[attr-defined]
ProgressEventType.Week = _WeekProgressEventType  # type: ignore[attr-defined]
ProgressEventType.Result = _ResultProgressEventType  # type: ignore[attr-defined]
ProgressEventType.Run = _RunProgressEventType  # type: ignore[attr-defined]


class ProgressEvent(BaseModel):
    """流式进度消息"""

    type: ProgressEventType
    message: str
    node: Optional[str] = None
    task_name: Optional[str] = None
    detail: Optional[Any] = None
    progress: Optional[int] = Field(None, ge=0, le=100)
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat() + "Z"
    )

    def to_dict(self) -> dict:
        """序列化为 dict，剔除 None 值以减少传输体积。

        对 detail 字段中可能包含的 Pydantic 模型进行递归序列化，
        确保最终输出全部为 JSON 可序列化的原生类型。
        """
        data = self.model_dump(mode="json")
        if data.get("detail") is not None:
            data["detail"] = _deep_serialize(self.detail)
        return {k: v for k, v in data.items() if v is not None}


# ────────────────────────────────────────────────────────
# 核心：双发 emit_progress（sync + async 两套）
# ────────────────────────────────────────────────────────
#
# 设计要点：
#   - sync emit_*：用 `dispatch_custom_event` 同步发送，给 LangChain AgentMiddleware
#     的 sync hook（before_agent / after_agent / wrap_model_call 的 sync 实现）使用
#   - async aemit_*：`await adispatch_custom_event` 同步等待，给 async graph node 使用
#   - 两套都不再走 `loop.create_task` fire-and-forget，彻底消除事件丢失风险
#   - `emit_progress` 名字保留，向后兼容；新代码（async node）应优先用 `aemit_progress`


def _build_payload(event_type: ProgressEventType, message: str, **kwargs: Any) -> dict:
    return ProgressEvent(type=event_type, message=message, **kwargs).to_dict()


def _emit_to_stream_writer(payload: dict) -> None:
    """通道 ❶：写入 LangGraph custom stream（plan_service.py SSE 链路消费）。"""
    try:
        from langgraph.config import get_stream_writer
        get_stream_writer()(payload)
    except Exception:
        # ainvoke 非流式 / 运行环境无 writer，静默跳过
        pass


def emit_progress(
    event_type: ProgressEventType,
    message: str,
    **kwargs: Any,
) -> None:
    """SYNC：从 sync 函数（如 LangChain middleware 的 sync hook）发送进度事件。"""
    payload = _build_payload(event_type, message, **kwargs)
    _emit_to_stream_writer(payload)
    # 通道 ❷ AG-UI custom event（同步路径）
    try:
        from langchain_core.callbacks.manager import dispatch_custom_event
        dispatch_custom_event(event_type.value, payload)
    except Exception:
        # callback manager 未配置（单元测试 / 非 graph 环境），静默
        pass


async def aemit_progress(
    event_type: ProgressEventType,
    message: str,
    **kwargs: Any,
) -> None:
    """ASYNC：从 async graph node 发送进度事件，同步 await，避免 fire-and-forget。"""
    payload = _build_payload(event_type, message, **kwargs)
    _emit_to_stream_writer(payload)
    try:
        from langchain_core.callbacks.manager import adispatch_custom_event
        await adispatch_custom_event(event_type.value, payload)
    except Exception:
        pass


# ────────────────────────────────────────────────────────
# 工具：从 AIMessage 抽出 reasoning（thinking）
# ────────────────────────────────────────────────────────

_THINK_PATTERN = re.compile(r"<think>(.*?)</think>", re.DOTALL)


def extract_reasoning(response: AIMessage) -> tuple[str, str | None]:
    """从 AIMessage 拆出 (clean_content, reasoning)。

    支持两种主流 LLM 推理输出格式：
    1. DashScope qwen3 / DeepSeek-R1：reasoning 在 `additional_kwargs.reasoning_content`
    2. 部分模型直接在 content 里夹 `<think>...</think>` 块

    Returns:
        (清理后的 content, 抽出来的 reasoning 或 None)
    """
    reasoning: str | None = None
    if hasattr(response, "additional_kwargs"):
        reasoning = response.additional_kwargs.get("reasoning_content")

    content = response.content if response and response.content is not None else ""
    if not isinstance(content, str):
        # 多模态 content (list of parts)，跳过 think 抽取
        return str(content), reasoning

    if not reasoning:
        match = _THINK_PATTERN.search(content)
        if match:
            reasoning = match.group(1).strip()
            content = _THINK_PATTERN.sub("", content).strip()

    return content, reasoning
