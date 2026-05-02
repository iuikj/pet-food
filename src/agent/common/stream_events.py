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

from src.agent.common.view_types import ViewType

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
    """流式进度事件类型"""

    # ── 主智能体 ──
    PLAN_CREATING = "plan_creating"
    PLAN_CREATED = "plan_created"
    PLAN_UPDATED = "plan_updated"
    TASK_DELEGATING = "task_delegating"

    # ── 子智能体 ──
    TASK_EXECUTING = "task_executing"
    TASK_SEARCHING = "task_searching"
    TASK_QUERYING_NOTE = "task_querying_note"
    TASK_COMPLETED = "task_completed"

    # ── 写入智能体 ──
    NOTE_SAVING = "note_saving"
    NOTE_SAVED = "note_saved"
    SUMMARY_GENERATING = "summary_generating"
    SUMMARY_GENERATED = "summary_generated"

    # ── 结构化智能体 ──
    STRUCTURING = "structuring"
    STRUCTURING_RETRY = "structuring_retry"
    STRUCTURED = "structured"

    # ── 汇总 ──
    GATHERING = "gathering"
    COMPLETED = "completed"

    # ── V1 架构: 研究阶段 ──
    RESEARCH_STARTING = "research_starting"
    RESEARCH_TASK_DELEGATING = "research_task_delegating"
    RESEARCH_FINALIZING = "research_finalizing"

    # ── V1 架构: 分发阶段 ──
    DISPATCHING = "dispatching"

    # ── V1 架构: 周计划并行阶段 ──
    WEEK_PLANNING = "week_planning"
    WEEK_SEARCHING = "week_searching"
    WEEK_PLAN_READY = "week_plan_ready"
    WEEK_WRITING = "week_writing"
    WEEK_COMPLETED = "week_completed"

    # ── 聊天式事件流（v2 GenUI 新增） ──
    AI_MESSAGE = "ai_message"          # AI 文本输出（含可选 reasoning）
    REASONING = "reasoning"            # 单独的思考流
    TOOL_CALL = "tool_call"            # 工具调用 started/completed/error 三态合一
    PLAN_SNAPSHOT = "plan_snapshot"    # deepagent 风格 todo 列表快照
    SUBAGENT_SPAWN = "subagent_spawn"  # 任务委派给 subagent / week_agent
    NOTE_OPERATION = "note_operation"  # 阅读 / 写入 / 更新笔记的统一入口（暂未单独使用，预留）

    # ── 通用 ──
    ERROR = "error"
    INFO = "info"


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
        data = self.model_dump()
        if data.get("detail") is not None:
            data["detail"] = _deep_serialize(self.detail)
        return {k: v for k, v in data.items() if v is not None}


# ────────────────────────────────────────────────────────
# 核心：双发 emit_progress
# ────────────────────────────────────────────────────────

def emit_progress(
    event_type: ProgressEventType,
    message: str,
    **kwargs: Any,
) -> None:
    """
    双通道发送进度消息。

    通道 ❶ stream_writer：plan_service.py SSE 链路（已上线，保持不变）。
    通道 ❷ dispatch_custom_event：ag_ui_langgraph → AG-UI CUSTOM 事件 → CopilotKit。

    在非流式模式（ainvoke）下两条通道都会静默忽略，确保节点代码在所有调用方式下都能正常工作。
    """
    event = ProgressEvent(type=event_type, message=message, **kwargs)
    payload = event.to_dict()

    # 通道 ❶ stream_writer（plan_service.py 走这条；保持不变）
    try:
        from langgraph.config import get_stream_writer
        writer = get_stream_writer()
        writer(payload)
    except Exception:
        # ainvoke 模式下无 writer，或运行环境不支持，静默跳过
        pass

    # 通道 ❷ adispatch_custom_event（ag_ui_langgraph 走这条；新增）
    # adispatch_custom_event 是 async；在 sync 函数里只能用 ensure_future 异步触发，不阻塞节点。
    # event_type.value 作为 on_custom_event 的 name 字段，前端按 name 路由。
    try:
        from langchain_core.callbacks.manager import adispatch_custom_event
        loop = asyncio.get_running_loop()
        loop.create_task(adispatch_custom_event(event_type.value, payload))
    except RuntimeError:
        # 当前线程没有 running loop（如单元测试 / 同步代码），降级到 sync dispatch
        try:
            from langchain_core.callbacks.manager import dispatch_custom_event
            dispatch_custom_event(event_type.value, payload)
        except Exception:
            pass
    except Exception:
        # callback manager 未配置或其他异常，静默跳过
        pass


# ────────────────────────────────────────────────────────
# 帮助函数：let 业务节点零认知负担发送高级别事件
# ────────────────────────────────────────────────────────

# message 字段的最大长度（聊天列表预览用，详情入 detail.content）
_MESSAGE_PREVIEW_MAX = 120

# tool_call result 字段的最大长度（移动端 SSE 帧体积保护）
_TOOL_RESULT_MAX = 4000
_TOOL_RESULT_MAX_LIST = 5


def _truncate_preview(text: str | None, limit: int = _MESSAGE_PREVIEW_MAX) -> str:
    if not text:
        return ""
    text = str(text).strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _truncate_tool_result(result: Any) -> Any:
    """避免 tavily_search 等工具结果撑爆 SSE 帧（移动端 webview 4-8KB 容易丢包）。"""
    if result is None:
        return None
    if isinstance(result, str) and len(result) > _TOOL_RESULT_MAX:
        return result[:_TOOL_RESULT_MAX] + "\n...(truncated)"
    if isinstance(result, dict):
        out = dict(result)
        if isinstance(out.get("results"), list) and len(out["results"]) > _TOOL_RESULT_MAX_LIST:
            out["results"] = out["results"][:_TOOL_RESULT_MAX_LIST]
            out["_truncated"] = True
        return out
    if isinstance(result, list) and len(result) > _TOOL_RESULT_MAX_LIST:
        return [*result[:_TOOL_RESULT_MAX_LIST], {"_truncated": True}]
    return result


# tool_name → ViewType 路由表（emit_tool_call 内部用）
_TOOL_VIEW_MAP: dict[str, ViewType] = {
    "tavily_search": ViewType.TOOL_SEARCH,
    "query_note": ViewType.TOOL_NOTE_READ,
    "ls": ViewType.TOOL_NOTE_READ,
    "query_shared_note": ViewType.TOOL_NOTE_READ,
    "write_note": ViewType.TOOL_NOTE_WRITE,
    "week_write_note": ViewType.TOOL_NOTE_WRITE,
    "update_note": ViewType.TOOL_NOTE_WRITE,
}


def emit_ai_message(
    *,
    node: str,
    content: str,
    reasoning: str | None = None,
    message_id: str | None = None,
    progress: int | None = None,
    task_name: str | None = None,
) -> None:
    """发送 AI 文本输出事件（前端用 AIMessageWidget 渲染，下沉折叠）。

    Args:
        node: graph 节点名（如 "research_planner"、"week_agent_2"）
        content: AI 完整输出
        reasoning: 思考过程（qwen3 thinking / DeepSeek-R1 reasoning_content 抽出来的部分）
        message_id: 可选，用于前端去重 / 引用
    """
    if not content and not reasoning:
        return  # 空消息不发
    emit_progress(
        ProgressEventType.AI_MESSAGE,
        _truncate_preview(content or reasoning or ""),
        node=node,
        task_name=task_name,
        progress=progress,
        detail={
            "view_type": ViewType.AI_MESSAGE.value,
            "content": content or "",
            "reasoning": reasoning,
            "message_id": message_id,
        },
    )


def emit_tool_call(
    *,
    node: str,
    tool_name: str,
    args: dict | None = None,
    status: str = "started",
    result: Any = None,
    call_id: str | None = None,
    task_name: str | None = None,
) -> None:
    """发送工具调用事件（前端按 tool_name 路由到定制 Widget）。

    Args:
        node: graph 节点名
        tool_name: 工具名（tavily_search / query_note / write_note 等）
        args: 工具入参 dict
        status: started / completed / error
        result: 工具返回值（completed 时传，会自动截断）
        call_id: 唯一调用 ID。前端按 call_id 合并 started + completed 两条事件为同一卡片。
                 若不传，会按 tool_name + node 生成；同节点同工具多次调用应显式传不同 call_id。
        task_name: 可选，关联的任务名
    """
    view_type = _TOOL_VIEW_MAP.get(tool_name, ViewType.TOOL_CALL_GENERIC).value
    safe_args = args or {}

    detail: dict[str, Any] = {
        "view_type": view_type,
        "tool_name": tool_name,
        "args": safe_args,
        "status": status,
        "call_id": call_id or f"{tool_name}_{node}",
    }
    if result is not None:
        detail["result"] = _truncate_tool_result(result)

    emit_progress(
        ProgressEventType.TOOL_CALL,
        f"{tool_name}: {status}",
        node=node,
        task_name=task_name,
        detail=detail,
    )


def emit_plan_snapshot(
    *,
    node: str,
    plan: list,
    action: str = "snapshot",
    progress: int | None = None,
) -> None:
    """发送 deepagent 风格 todo 列表快照（前端用 PlanBoardWidget 渲染）。

    Args:
        node: graph 节点名
        plan: list[Todo]，每项需有 .content 和 .status 属性（langchain_dev_utils Todo）
        action: created / updated / completed_item / snapshot
    """
    items = []
    for it in plan or []:
        if isinstance(it, dict):
            items.append({
                "content": it.get("content", str(it)),
                "status": it.get("status", "pending"),
            })
        else:
            items.append({
                "content": getattr(it, "content", str(it)),
                "status": getattr(it, "status", "pending"),
            })

    emit_progress(
        ProgressEventType.PLAN_SNAPSHOT,
        f"任务列表 {action}",
        node=node,
        progress=progress,
        detail={
            "view_type": ViewType.PLAN_BOARD.value,
            "items": items,
            "action": action,
        },
    )


def emit_subagent_spawn(
    *,
    node: str,
    target: str,
    task_name: str,
    week_number: int | None = None,
    progress: int | None = None,
) -> None:
    """发送任务委派事件（前端用 SubagentDispatchWidget 渲染）。

    Args:
        node: 发起委派的节点名（如 "research_planner"、"dispatch_weeks"）
        target: 目标子图名（"research_subagent" / "week_agent" / "structure_report"）
        task_name: 任务描述
        week_number: 仅 target=week_agent 时填写
    """
    view_type = (
        ViewType.WEEK_DISPATCH if target == "week_agent" else ViewType.SUBAGENT_DISPATCH
    ).value
    emit_progress(
        ProgressEventType.SUBAGENT_SPAWN,
        f"委派 → {target}: {task_name}",
        node=node,
        task_name=task_name,
        progress=progress,
        detail={
            "view_type": view_type,
            "target": target,
            "task_name": task_name,
            "week_number": week_number,
        },
    )


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
