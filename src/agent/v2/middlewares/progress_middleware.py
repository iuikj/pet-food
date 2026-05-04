"""
LangChain v1.2+ 业务进度 middleware。

这个 middleware 只负责 AG-UI 标准协议无法直接表达的业务阶段提示：
- plan_agent 生命周期：研究启动、task subagent 委派、研究完成
- task subagent 生命周期：子任务启动、业务工具阶段、子任务完成
- week_agent 生命周期：周计划启动、业务工具阶段、撰写阶段、周计划完成

不在这里做的事：
- 不计算或发送百分比进度
- 不重复发送 AG-UI 标准 text / reasoning / TOOL_CALL_* 事件
"""
from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Any, Mapping, Sequence

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import (
    AgentState,
    ModelRequest,
    ModelResponse,
    ResponseT,
    ToolCallRequest,
)
from langchain.messages import AIMessage, HumanMessage
from langchain_core.messages import ToolMessage
from langgraph.runtime import Runtime
from langgraph.types import Command
from pydantic import BaseModel, Field
from typing_extensions import NotRequired

from src.agent.common.stream_events import ProgressEventType, emit_progress
from src.agent.common.view_types import ViewType


_SEARCH_TOOL_NAMES = {
    "ingredient_search_tool",
    "ingredient_detail_tool",
    "ingredient_categories_tool",
}
_CALC_TOOL_NAMES = {
    "daily_calorie_tool",
    "nutrition_requirement_tool",
}
_WEEK_TOOL_NAMES = _SEARCH_TOOL_NAMES | _CALC_TOOL_NAMES


class SubAgentInfo(BaseModel):
    input_message: str = Field(
        description="作为subagent被传入的第一条human message就是task 工具创建对应的description;用这个来区分不同的subagent"
    )
    subagent_id: str = Field(description="将input_message hash,使得前后端得以匹配")


class ProgressState(AgentState, total=False):
    is_subagent: NotRequired[bool]
    subagent_info: NotRequired[SubAgentInfo]
    parent_call_id: NotRequired[str]
    subagent_type: NotRequired[str]
    week_assignment: NotRequired[Any]
    structured_response: NotRequired[Any]
    week_light_plans: NotRequired[Any]


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


def _last_ai_message(messages: Sequence[Any]) -> AIMessage | None:
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            return message
    return None


def _extract_tool_call_names(messages: Sequence[Any]) -> list[str]:
    last_ai = _last_ai_message(messages)
    if last_ai is None:
        return []
    tool_calls = getattr(last_ai, "tool_calls", None) or []
    names: list[str] = []
    for call in tool_calls:
        if isinstance(call, Mapping):
            name = call.get("name")
            if name:
                names.append(str(name))
    return names


def _has_tool_messages(state: Any) -> bool:
    messages = _state_get(state, "messages", []) or []
    for message in messages:
        if isinstance(message, ToolMessage):
            return True
        if getattr(message, "type", None) == "tool" or getattr(message, "tool_call_id", None):
            return True
    return False


def _is_subagent_tool(tool_name: str) -> bool:
    lowered = tool_name.lower()
    return (
        tool_name == "task"
        or "subagent" in lowered
        or "transfer" in lowered
        or "transfor" in lowered
    )


def _stable_subagent_id(input_message: str) -> str:
    normalized = " ".join(str(input_message or "").split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _task_subagent_info(tool_args: Mapping[str, Any]) -> SubAgentInfo:
    input_message = str(
        tool_args.get("description")
        or tool_args.get("content")
        or tool_args.get("task_name")
        or tool_args.get("task")
        or "subagent task"
    )
    return SubAgentInfo(
        input_message=input_message,
        subagent_id=_stable_subagent_id(input_message),
    )


def _coerce_subagent_info(value: Any) -> SubAgentInfo | None:
    if isinstance(value, SubAgentInfo):
        return value
    if isinstance(value, Mapping):
        try:
            return SubAgentInfo(**value)
        except Exception:
            return None
    return None


def _first_human_message(state: Any) -> str | None:
    messages = _state_get(state, "messages", []) or []
    for message in messages:
        if isinstance(message, HumanMessage) or getattr(message, "type", None) == "human":
            content = getattr(message, "content", None)
            if content:
                return str(content)
    return None


def _subagent_info_from_state(state: Any) -> SubAgentInfo | None:
    info = _coerce_subagent_info(_state_get(state, "subagent_info"))
    if info is not None:
        return info

    input_message = _first_human_message(state)
    if not input_message:
        return None
    return SubAgentInfo(
        input_message=input_message,
        subagent_id=_stable_subagent_id(input_message),
    )


def _subagent_node(info: SubAgentInfo | None) -> str:
    return f"subagent_{info.subagent_id}" if info is not None else "subagent"


def _subagent_detail(
    info: SubAgentInfo | None,
    state: Any = None,
    **extra: Any,
) -> dict[str, Any]:
    detail: dict[str, Any] = {"agent_scope": "subagent"}
    if info is not None:
        detail.update(
            {
                "subagent_id": info.subagent_id,
                "input_message": info.input_message,
            }
        )
    parent_call_id = _state_get(state, "parent_call_id") if state is not None else None
    subagent_type = _state_get(state, "subagent_type") if state is not None else None
    if parent_call_id:
        detail["parent_call_id"] = parent_call_id
    if subagent_type:
        detail["target"] = subagent_type
    detail.update(extra)
    return detail


def _strip_progress_state_from_command(result: Any) -> Any:
    if not isinstance(result, Command) or not isinstance(result.update, dict):
        return result
    update = dict(result.update)
    update.pop("is_subagent", None)
    update.pop("subagent_info", None)
    update.pop("parent_call_id", None)
    update.pop("subagent_type", None)
    return Command(graph=result.graph, update=update, resume=result.resume, goto=result.goto)


class PlanProgressMiddleware(AgentMiddleware[ProgressState, Any, Any]):
    state_schema = ProgressState

    def before_agent(self, state: ProgressState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        emit_progress(
            ProgressEventType.Research.STARTING,
            "研究阶段启动：正在分析宠物信息并规划调研路径",
            node="plan_agent",
        )
        return None

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler,
    ) -> ModelResponse[ResponseT]:
        try:
            return await handler(request)
        except Exception as exc:
            emit_progress(
                ProgressEventType.Run.ERROR,
                f"[plan_agent] 调研阶段失败: {exc}",
                node="plan_agent",
            )
            raise

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler,
    ) -> Any:
        tool_call = request.tool_call or {}
        tool_name = str(tool_call.get("name") or "")
        tool_args = tool_call.get("args") or {}
        if not isinstance(tool_args, Mapping):
            tool_args = {}

        if not _is_subagent_tool(tool_name):
            return await handler(request)

        info = _task_subagent_info(tool_args)
        call_id = tool_call.get("id")
        subagent_type = str(tool_args.get("subagent_type") or tool_args.get("agent_name") or "subagent")
        detail = {
            "view_type": ViewType.SUBAGENT_DISPATCH.value,
            "target": subagent_type,
            "task_name": info.input_message,
            "subagent_id": info.subagent_id,
            "input_message": info.input_message,
            "tool_name": tool_name,
            "args": dict(tool_args),
            "status": "started",
            "call_id": call_id,
            "agent_scope": "subagent",
        }

        emit_progress(
            ProgressEventType.Research.TASK_DELEGATING,
            f"委派 -> {subagent_type}: {info.input_message}",
            node="plan_agent",
            task_name=info.input_message,
            detail=detail,
        )

        subagent_state = dict(request.state or {})
        subagent_state.update(
            {
                "is_subagent": True,
                "subagent_info": info,
                "parent_call_id": call_id,
                "subagent_type": subagent_type,
            }
        )
        request = replace(
            request,
            state=subagent_state,
            runtime=replace(request.runtime, state=subagent_state),
        )

        try:
            result = await handler(request)
        except Exception as exc:
            emit_progress(
                ProgressEventType.Run.ERROR,
                f"[subagent:{subagent_type}] 任务失败: {exc}",
                node="plan_agent",
                task_name=info.input_message,
                detail={**detail, "status": "error", "result": str(exc)},
            )
            raise

        emit_progress(
            ProgressEventType.Task.COMPLETED,
            f"SubAgent 已返回: {info.input_message}",
            node="plan_agent",
            task_name=info.input_message,
            detail={**detail, "status": "completed"},
        )
        return _strip_progress_state_from_command(result)

    def after_agent(self, state: ProgressState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        emit_progress(
            ProgressEventType.Research.FINALIZING,
            "研究阶段完成，调研笔记已经整理就绪",
            node="plan_agent",
        )
        return None


class SubAgentProgressMiddleware(AgentMiddleware[ProgressState, Any, Any]):
    state_schema = ProgressState

    def before_agent(self, state: ProgressState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        info = _subagent_info_from_state(state)
        emit_progress(
            ProgressEventType.Task.EXECUTING,
            f"SubAgent 开始执行: {info.input_message}" if info else "SubAgent 开始执行",
            node=_subagent_node(info),
            task_name=info.input_message if info else None,
            detail=_subagent_detail(info, state),
        )
        return None

    def _tool_event(self, tool_name: str) -> tuple[ProgressEventType, str]:
        if tool_name in _SEARCH_TOOL_NAMES or tool_name in {"tavily_search", "get_weather"}:
            return ProgressEventType.Task.SEARCHING, "SubAgent 正在检索信息"
        if tool_name in _CALC_TOOL_NAMES:
            return ProgressEventType.Task.EXECUTING, "SubAgent 正在计算营养目标"
        if tool_name == "query_note":
            return ProgressEventType.Task.QUERYING_NOTE, "SubAgent 正在查询笔记"
        return ProgressEventType.Task.EXECUTING, f"SubAgent 正在调用工具: {tool_name}"

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler,
    ) -> Any:
        info = _subagent_info_from_state(request.state)
        tool_call = request.tool_call or {}
        tool_name = str(tool_call.get("name") or "")
        tool_args = tool_call.get("args") or {}
        if not isinstance(tool_args, Mapping):
            tool_args = {}

        event_type, message = self._tool_event(tool_name)
        emit_progress(
            event_type,
            message,
            node=_subagent_node(info),
            task_name=info.input_message if info else None,
            detail=_subagent_detail(
                info,
                request.state,
                tool_name=tool_name,
                tool_args=dict(tool_args),
                call_id=tool_call.get("id"),
            ),
        )

        try:
            return await handler(request)
        except Exception as exc:
            emit_progress(
                ProgressEventType.Run.ERROR,
                f"[{_subagent_node(info)}] 工具调用失败({tool_name}): {exc}",
                node=_subagent_node(info),
                task_name=info.input_message if info else None,
                detail=_subagent_detail(
                    info,
                    request.state,
                    tool_name=tool_name,
                    call_id=tool_call.get("id"),
                ),
            )
            raise

    def after_agent(self, state: ProgressState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        info = _subagent_info_from_state(state)
        emit_progress(
            ProgressEventType.Task.COMPLETED,
            f"SubAgent 执行完成: {info.input_message}" if info else "SubAgent 执行完成",
            node=_subagent_node(info),
            task_name=info.input_message if info else None,
            detail=_subagent_detail(info, state),
        )
        return None


class WeekProgressMiddleware(AgentMiddleware[ProgressState, Any, Any]):
    state_schema = ProgressState

    def _node_name(self, week_number: int | None) -> str:
        return f"week_agent_{week_number}" if week_number is not None else "week_agent"

    def _task_name(self, week_number: int | None) -> str | None:
        return f"第{week_number}周饮食计划" if week_number is not None else None

    def _detail(self, week_number: int | None, **extra: Any) -> dict[str, Any]:
        detail: dict[str, Any] = {"agent_scope": "week"}
        if week_number is not None:
            detail["week"] = week_number
            detail["agent_id"] = f"week_agent_{week_number}"
        detail.update(extra)
        return detail

    def _emit_week_event(
        self,
        event_type: ProgressEventType,
        message: str,
        *,
        week_number: int | None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        emit_progress(
            event_type,
            message,
            node=self._node_name(week_number),
            task_name=self._task_name(week_number),
            detail=detail or self._detail(week_number),
        )

    def _tool_message(
        self,
        week_number: int | None,
        tool_name: str,
        tool_args: Mapping[str, Any],
    ) -> tuple[ProgressEventType, str]:
        prefix = f"第{week_number}周：" if week_number is not None else ""

        if tool_name == "daily_calorie_tool":
            return (
                ProgressEventType.Week.PLANNING,
                f"{prefix}正在计算每日热量与三大营养素目标",
            )
        if tool_name == "nutrition_requirement_tool":
            return (
                ProgressEventType.Week.PLANNING,
                f"{prefix}正在计算微量营养素需求",
            )
        if tool_name == "ingredient_categories_tool":
            return (
                ProgressEventType.Week.SEARCHING,
                f"{prefix}正在读取食材分类与库存范围",
            )
        if tool_name == "ingredient_detail_tool":
            ingredient_name = tool_args.get("name")
            suffix = f"：{ingredient_name}" if ingredient_name else ""
            return (
                ProgressEventType.Week.SEARCHING,
                f"{prefix}正在查询食材营养详情{suffix}",
            )

        keyword = tool_args.get("keyword")
        category = tool_args.get("category")
        sub_category = tool_args.get("sub_category")
        focus = keyword or sub_category or category
        suffix = f"（{focus}）" if focus else ""
        return (
            ProgressEventType.Week.SEARCHING,
            f"{prefix}正在检索可用食材{suffix}",
        )

    def _has_final_week_output(self, state: AgentState) -> bool:
        if _state_get(state, "structured_response") is not None:
            return True
        week_light_plans = _state_get(state, "week_light_plans")
        return bool(week_light_plans)

    def before_agent(self, state: ProgressState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        week_number = _extract_week_number(state)
        self._emit_week_event(
            ProgressEventType.Week.PLANNING,
            f"第{week_number}周：已接收约束，开始制定周计划" if week_number is not None else "周计划任务已启动",
            week_number=week_number,
        )
        return None

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler,
    ) -> ModelResponse[ResponseT]:
        week_number = _extract_week_number(request.state)

        if _has_tool_messages(request.state):
            self._emit_week_event(
                ProgressEventType.Week.WRITING,
                f"第{week_number}周：正在整合工具结果并撰写周计划"
                if week_number is not None
                else "正在整合工具结果并撰写周计划",
                week_number=week_number,
            )

        try:
            response = await handler(request)
        except Exception as exc:
            emit_progress(
                ProgressEventType.Run.ERROR,
                f"[{self._node_name(week_number)}] 周计划生成失败: {exc}",
                node=self._node_name(week_number),
                task_name=self._task_name(week_number),
                detail=self._detail(week_number),
            )
            raise

        tool_names = _extract_tool_call_names(response.result)
        if any(name in _WEEK_TOOL_NAMES for name in tool_names):
            return response

        self._emit_week_event(
            ProgressEventType.Week.WRITING,
            f"第{week_number}周：选材与配比完成，正在整理结构化输出"
            if week_number is not None
            else "周计划草案已完成，正在整理最终输出",
            week_number=week_number,
        )
        return response

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler,
    ) -> Any:
        week_number = _extract_week_number(request.state)
        tool_call = request.tool_call or {}
        tool_name = str(tool_call.get("name") or "")
        tool_args = tool_call.get("args") or {}
        if not isinstance(tool_args, Mapping):
            tool_args = {}

        if tool_name in _WEEK_TOOL_NAMES:
            event_type, message = self._tool_message(week_number, tool_name, tool_args)
            self._emit_week_event(
                event_type,
                message,
                week_number=week_number,
                detail=self._detail(week_number, tool_name=tool_name),
            )

        try:
            return await handler(request)
        except Exception as exc:
            emit_progress(
                ProgressEventType.Run.ERROR,
                f"[{self._node_name(week_number)}] 工具调用失败({tool_name}): {exc}",
                node=self._node_name(week_number),
                task_name=self._task_name(week_number),
                detail=self._detail(week_number, tool_name=tool_name),
            )
            raise

    def after_agent(self, state: ProgressState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        if not self._has_final_week_output(state):
            return None

        week_number = _extract_week_number(state)
        self._emit_week_event(
            ProgressEventType.Week.COMPLETED,
            f"第{week_number}周食谱已完成" if week_number is not None else "周计划已完成",
            week_number=week_number,
        )
        return None


plan_progress_middleware = PlanProgressMiddleware()
sub_agent_progress_middleware = SubAgentProgressMiddleware()
week_progress_middleware = WeekProgressMiddleware()
