"""
LangChain v1.2+ 业务进度 middleware。

这个 middleware 只负责 AG-UI 标准协议无法直接表达的业务阶段提示：
- task subagent 生命周期：子任务启动、子任务完成；内部消息/推理/工具调用走 AG-UI 标准事件
- week_agent 生命周期：周计划启动、周计划完成；内部消息/推理/工具调用走 AG-UI 标准事件

不在这里做的事：
- 不计算或发送百分比进度
- 不重复发送 AG-UI 标准 text / reasoning / TOOL_CALL_* 事件
"""
from __future__ import annotations

import hashlib
from typing import Any, Mapping, Callable, Awaitable

from langchain.agents.middleware import AgentMiddleware, ExtendedModelResponse
from langchain.agents.middleware.types import (
    AgentState,
    ModelRequest,
    ModelResponse,
    ResponseT,
    ToolCallRequest,
)
from langchain.messages import AIMessage
from langgraph.runtime import Runtime
from langgraph.typing import ContextT
from pydantic import BaseModel, Field
from typing_extensions import NotRequired

from src.agent.common.stream_events import ProgressEventType, emit_progress
from src.agent.common.view_types import ViewType


class SubAgentInfo(BaseModel):
    input_message: str = Field(
        description="作为subagent被传入的第一条human message就是task 工具创建对应的description;用这个来区分不同的subagent"
    )
    subagent_id: str = Field(description="将input_message hash,使得前后端得以匹配", default="")


class ProgressState(AgentState, total=False):
    subagent_info: NotRequired[SubAgentInfo]


def _state_get(state: Any, key: str, default: Any = None) -> Any:
    if isinstance(state, Mapping):
        return state.get(key, default)
    return getattr(state, key, default)


def _extract_week_number(state: Any) -> int | None:
    assignment = _state_get(state, "week_assignment")
    if assignment is None:
        return None
    week_number = getattr(assignment, "week_number", None)
    if week_number is None and isinstance(assignment, Mapping):
        week_number = assignment.get("week_number")
    try:
        return int(week_number)
    except (TypeError, ValueError):
        return None


def _stable_subagent_id(input_message: str) -> str:
    normalized = " ".join(str(input_message or "").split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


class SubAgentProgressMiddleware(AgentMiddleware[ProgressState, Any, Any]):
    state_schema = ProgressState

    def before_agent(self, state: ProgressState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        first_message = state["messages"][0]
        input_message: str = str(first_message.content)
        sub_info: SubAgentInfo = SubAgentInfo(
            input_message=input_message
        )
        sub_info.subagent_id = _stable_subagent_id(input_message)
        emit_progress(
            ProgressEventType.Task.EXECUTING,
            f"SubAgent 开始执行: {input_message}",
            node=f"subagent_{sub_info.subagent_id}",
            task_name=input_message,
            detail={
                "view_type": ViewType.SUBAGENT_DISPATCH.value,
                "agent_scope": "subagent",
                "subagent_id": sub_info.subagent_id,
                "input_message": input_message,
                "task_name": input_message,
                "status": "started",
            },
        )
        return {
            "subagent_info": sub_info,
        }

    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
    ) -> ModelResponse[ResponseT] | AIMessage | ExtendedModelResponse[ResponseT]:
        model = request.model
        info: SubAgentInfo = request.state["subagent_info"]
        model.metadata = {
            "subagent_id": info.subagent_id
        }
        return await handler(request.override(model=model))

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler,
    ) -> Any:
        tool = request.tool
        info: SubAgentInfo = request.state["subagent_info"]
        tool.metadata = {
            "subagent_id": info.subagent_id
        }
        return await handler(request.override(tool=tool))

    def after_agent(self, state: ProgressState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        sub_info: SubAgentInfo = state["subagent_info"]
        emit_progress(
            ProgressEventType.Task.COMPLETED,
            f"SubAgent 执行完成: {sub_info.input_message}",
            node=f"subagent_{sub_info.subagent_id}",
            task_name=sub_info.input_message,
            detail={
                "view_type": ViewType.SUBAGENT_DISPATCH.value,
                "agent_scope": "subagent",
                "subagent_id": sub_info.subagent_id,
                "input_message": sub_info.input_message,
                "task_name": sub_info.input_message,
                "status": "completed",
            },
        )
        return None


class WeekProgressMiddleware(AgentMiddleware[ProgressState, Any, Any]):
    state_schema = ProgressState

    def before_agent(self, state: ProgressState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        week_number = _extract_week_number(state)
        node = f"week_agent_{week_number}" if week_number is not None else "week_agent"
        task_name = f"第{week_number}周饮食计划" if week_number is not None else None
        detail: dict[str, Any] = {
            "view_type": ViewType.PHASE_MARKER.value,
            "agent_scope": "week",
            "status": "started",
        }
        if week_number is not None:
            detail.update({
                "week": week_number,
                "week_number": week_number,
                "agent_id": node,
            })
        emit_progress(
            ProgressEventType.Week.PLANNING,
            f"第{week_number}周：已接收约束，开始制定周计划" if week_number is not None else "周计划任务已启动",
            node=node,
            task_name=task_name,
            detail=detail,
        )
        return None

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler,
    ) -> ModelResponse[ResponseT]:
        week_number = _extract_week_number(request.state)
        model = request.model
        model.metadata = {
            "week_number": week_number,
        }
        return await handler(request.override(model=model))

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler,
    ) -> Any:
        week_number = _extract_week_number(request.state)
        tool = request.tool
        tool.metadata = {
            "week_number": week_number,
        }
        return await handler(request.override(tool=tool))

    def after_agent(self, state: ProgressState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        week_number = _extract_week_number(state)
        node = f"week_agent_{week_number}" if week_number is not None else "week_agent"
        task_name = f"第{week_number}周饮食计划" if week_number is not None else None
        detail: dict[str, Any] = {
            "view_type": ViewType.PHASE_MARKER.value,
            "agent_scope": "week",
            "status": "completed",
        }
        if week_number is not None:
            detail.update({
                "week": week_number,
                "week_number": week_number,
                "agent_id": node,
            })
        emit_progress(
            ProgressEventType.Week.COMPLETED,
            f"第{week_number}周食谱已完成" if week_number is not None else "周计划已完成",
            node=node,
            task_name=task_name,
            detail=detail,
        )
        return None


sub_agent_progress_middleware = SubAgentProgressMiddleware()
week_progress_middleware = WeekProgressMiddleware()
