"""
流式进度事件定义

提供结构化的 ProgressEvent 消息，供各 agent 节点通过 get_stream_writer() 发送业务级进度信息。
前端通过 SSE 直接消费这些事件，展示任务执行进度。
"""
from enum import Enum
from typing import Optional, Any
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class ProgressEventType(str, Enum):
    """流式进度事件类型"""

    # 主智能体
    PLAN_CREATING = "plan_creating"
    PLAN_CREATED = "plan_created"
    PLAN_UPDATED = "plan_updated"
    TASK_DELEGATING = "task_delegating"

    # 子智能体
    TASK_EXECUTING = "task_executing"
    TASK_SEARCHING = "task_searching"
    TASK_QUERYING_NOTE = "task_querying_note"
    TASK_COMPLETED = "task_completed"

    # 写入智能体
    NOTE_SAVING = "note_saving"
    NOTE_SAVED = "note_saved"
    SUMMARY_GENERATING = "summary_generating"
    SUMMARY_GENERATED = "summary_generated"

    # 结构化智能体
    STRUCTURING = "structuring"
    STRUCTURING_RETRY = "structuring_retry"
    STRUCTURED = "structured"

    # 汇总
    GATHERING = "gathering"
    COMPLETED = "completed"

    # 通用
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
        """序列化为 dict，剔除 None 值以减少传输体积"""
        return {k: v for k, v in self.model_dump().items() if v is not None}


def emit_progress(
    event_type: ProgressEventType,
    message: str,
    **kwargs: Any,
) -> None:
    """
    发送进度消息到 stream writer。

    在非流式模式（ainvoke）下会静默忽略，确保节点代码在两种调用方式下都能正常工作。
    """
    try:
        from langgraph.config import get_stream_writer

        writer = get_stream_writer()
        event = ProgressEvent(type=event_type, message=message, **kwargs)
        writer(event.to_dict())
    except Exception:
        # ainvoke 模式下无 writer，或其他异常均静默跳过
        pass
