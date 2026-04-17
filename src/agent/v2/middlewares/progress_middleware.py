"""
Agent 级流式进度 middleware 工厂

在 create_deep_agent 的 middleware 列表里使用 wrap_model_call 发送
LLM 调用的开始/完成事件，避免在每个节点里重复 emit_progress 调用。

用法：
    plan_progress = make_progress_middleware(
        node_name="plan_agent",
        enter_event=ProgressEventType.PLAN_CREATING,
        exit_event=ProgressEventType.PLAN_CREATED,
    )
    create_deep_agent(middleware=[plan_progress, ...], ...)
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable

from langchain.agents.middleware import wrap_model_call

from src.agent.common.stream_events import ProgressEventType, emit_progress


def make_progress_middleware(
    node_name: str,
    enter_event: ProgressEventType,
    exit_event: ProgressEventType,
    enter_message: str | None = None,
    exit_message: str | None = None,
):
    """构造一个 wrap_model_call middleware，在 LLM 调用前后发送进度事件。

    非流式（ainvoke）模式下 emit_progress 静默跳过，不会报错。
    """
    enter_msg = enter_message or f"[{node_name}] AI 推理中"
    exit_msg = exit_message or f"[{node_name}] AI 推理完成"

    @wrap_model_call
    async def _progress_middleware(
        request,
        handler: Callable[[object], Awaitable[object]],
    ):
        emit_progress(enter_event, enter_msg, node=node_name)
        try:
            response = await handler(request)
        except Exception as exc:
            emit_progress(
                ProgressEventType.ERROR,
                f"[{node_name}] 推理失败: {exc}",
                node=node_name,
            )
            raise
        emit_progress(exit_event, exit_msg, node=node_name)
        return response

    return _progress_middleware


# 预构造常用实例
plan_progress_middleware = make_progress_middleware(
    node_name="plan_agent",
    enter_event=ProgressEventType.PLAN_CREATING,
    exit_event=ProgressEventType.PLAN_CREATED,
    enter_message="规划研究阶段：正在分析宠物信息并委派调研任务",
    exit_message="规划阶段一轮推理完成",
)

week_progress_middleware = make_progress_middleware(
    node_name="week_agent",
    enter_event=ProgressEventType.WEEK_PLANNING,
    exit_event=ProgressEventType.WEEK_PLAN_READY,
    enter_message="周计划：正在选择食材与组装餐次",
    exit_message="周计划一轮推理完成",
)
