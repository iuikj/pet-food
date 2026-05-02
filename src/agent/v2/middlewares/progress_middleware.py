"""
LangChain v1.2+ 进度 middleware。

基于最新的 class-based AgentMiddleware 写法，同时接入：
- before_agent：阶段启动
- wrap_model_call：感知模型轮次与“开始写作/准备完成”信号
- wrap_tool_call：感知工具执行中的检索/计算信号
- after_agent：只在真正完成时发出 completed 类事件

核心目标：
1. 不再把每一次 model call 都误报成“阶段完成”
2. 为并行 4 周 week_agent 计算单调递增的总进度，避免前端进度条倒退
3. 保留现有 ProgressEventType，兼容前端事件消费逻辑
"""
from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from time import monotonic
from typing import Any, Mapping, Sequence

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import (
    AgentState,
    ModelRequest,
    ModelResponse,
    ResponseT,
    ToolCallRequest,
)
from langchain.messages import AIMessage
from langchain_core.messages import ToolMessage
from langgraph.config import get_config
from langgraph.runtime import Runtime
from langgraph.types import Command

from src.agent.common.stream_events import (
    ProgressEventType,
    emit_progress,
    emit_ai_message,
    emit_tool_call,
    emit_plan_snapshot,
    emit_subagent_spawn,
    extract_reasoning,
)

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

_TRACKERS_TTL_SECONDS = 1800.0
_TRACKERS_LOCK = Lock()


@dataclass(frozen=True)
class _ProgressWindow:
    start: int
    end: int

    def to_absolute(self, fraction: float) -> int:
        bounded = max(0.0, min(1.0, fraction))
        return self.start + round((self.end - self.start) * bounded)


@dataclass
class _UnitProgress:
    stage: float = 0.0
    model_calls: int = 0
    tool_calls: int = 0
    ready_emitted: bool = False


@dataclass
class _PhaseTracker:
    expected_units: int
    window: _ProgressWindow
    units: dict[str, _UnitProgress] = field(default_factory=dict)
    last_progress: int = -1
    updated_at: float = field(default_factory=monotonic)

    def current_progress(self) -> int:
        total_stage = sum(unit.stage for unit in self.units.values())
        ratio = total_stage / max(self.expected_units, 1)
        return self.window.to_absolute(ratio)

    def is_complete(self) -> bool:
        if len(self.units) < self.expected_units:
            return False
        return all(unit.stage >= 1.0 for unit in self.units.values())


_TRACKERS: dict[tuple[str, str], _PhaseTracker] = {}


def _purge_stale_trackers_locked(now: float) -> None:
    stale_keys = [
        key for key, tracker in _TRACKERS.items()
        if now - tracker.updated_at >= _TRACKERS_TTL_SECONDS
    ]
    for key in stale_keys:
        _TRACKERS.pop(key, None)


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


def _extract_result_content(result: Any) -> Any:
    """从 ToolMessage / Command / 原始返回值抽 result content,供 emit_tool_call 使用。"""
    if isinstance(result, ToolMessage):
        return result.content
    if hasattr(result, "content"):
        return result.content
    return result


def _emit_genui_after_model_call(
    response: ModelResponse[Any],
    *,
    node: str,
    task_name: str | None = None,
) -> None:
    """v2 GenUI 适配:在 awrap_model_call 拿到 response 后发 ai_message/plan/subagent 三类事件。"""
    last_ai = _last_ai_message(response.result)
    if last_ai is None:
        return

    content, reasoning = extract_reasoning(last_ai)
    if content or reasoning:
        emit_ai_message(
            node=node,
            content=content or "",
            reasoning=reasoning,
            message_id=getattr(last_ai, "id", None),
            task_name=task_name,
        )

    tool_calls = getattr(last_ai, "tool_calls", None) or []
    for call in tool_calls:
        if not isinstance(call, Mapping):
            continue
        call_name = str(call.get("name") or "")
        call_args = call.get("args") or {}
        if not isinstance(call_args, Mapping):
            call_args = {}

        # plan/todos 工具调用 → plan_snapshot
        if call_name in ("write_todos", "update_todos", "TodoWrite"):
            todos = call_args.get("todos") or call_args.get("plan") or []
            if todos:
                emit_plan_snapshot(
                    node=node,
                    plan=list(todos),
                    action="updated" if call_name == "update_todos" else "created",
                )
            continue

        # subagent 调用 → subagent_spawn (deepagents task 工具 / 业务 transfor_task_to_subagent)
        lname = call_name.lower()
        if call_name == "task" or "subagent" in lname or "transfor" in lname:
            sub_name = (
                call_args.get("subagent_type")
                or call_args.get("agent_name")
                or call_name
            )
            task_desc = (
                call_args.get("description")
                or call_args.get("content")
                or call_args.get("task_name")
                or ""
            )
            emit_subagent_spawn(
                node=node,
                target=str(sub_name),
                task_name=str(task_desc),
            )


def _safe_run_key() -> str:
    try:
        config = get_config()
    except Exception:
        return "unknown-run"

    configurable = {}
    if isinstance(config, Mapping):
        configurable = config.get("configurable", {}) or {}

    for key in ("thread_id", "task_id", "run_id"):
        value = configurable.get(key)
        if value:
            return str(value)
    return "unknown-run"


class _TrackedProgressMiddleware(AgentMiddleware[AgentState, Any, Any]):
    """共享的 tracker 辅助层。"""

    phase_name: str
    expected_units: int
    progress_window: _ProgressWindow

    def _tracker_key(self) -> tuple[str, str]:
        return (_safe_run_key(), self.phase_name)

    def _update_unit(
        self,
        unit_key: str,
        *,
        stage: float | None = None,
        model_delta: int = 0,
        tool_delta: int = 0,
        ready_emitted: bool | None = None,
    ) -> tuple[_UnitProgress, int, bool]:
        tracker_key = self._tracker_key()
        now = monotonic()

        with _TRACKERS_LOCK:
            _purge_stale_trackers_locked(now)
            tracker = _TRACKERS.get(tracker_key)
            if tracker is None:
                tracker = _PhaseTracker(
                    expected_units=self.expected_units,
                    window=self.progress_window,
                )
                _TRACKERS[tracker_key] = tracker

            unit = tracker.units.setdefault(unit_key, _UnitProgress())
            unit.model_calls += model_delta
            unit.tool_calls += tool_delta
            if ready_emitted is not None:
                unit.ready_emitted = ready_emitted

            stage_changed = False
            if stage is not None:
                bounded_stage = max(0.0, min(1.0, stage))
                if bounded_stage > unit.stage:
                    unit.stage = bounded_stage
                    stage_changed = True

            tracker.updated_at = now
            progress = tracker.current_progress()
            if progress < tracker.last_progress:
                progress = tracker.last_progress
            else:
                tracker.last_progress = progress

            snapshot = _UnitProgress(
                stage=unit.stage,
                model_calls=unit.model_calls,
                tool_calls=unit.tool_calls,
                ready_emitted=unit.ready_emitted,
            )
            return snapshot, progress, stage_changed

    def _get_unit(self, unit_key: str) -> _UnitProgress:
        tracker_key = self._tracker_key()
        now = monotonic()

        with _TRACKERS_LOCK:
            _purge_stale_trackers_locked(now)
            tracker = _TRACKERS.get(tracker_key)
            if tracker is None:
                return _UnitProgress()
            unit = tracker.units.get(unit_key)
            if unit is None:
                return _UnitProgress()
            tracker.updated_at = now
            return _UnitProgress(
                stage=unit.stage,
                model_calls=unit.model_calls,
                tool_calls=unit.tool_calls,
                ready_emitted=unit.ready_emitted,
            )

    def _cleanup_if_complete(self) -> None:
        tracker_key = self._tracker_key()
        with _TRACKERS_LOCK:
            tracker = _TRACKERS.get(tracker_key)
            if tracker and tracker.is_complete():
                _TRACKERS.pop(tracker_key, None)


class PlanProgressMiddleware(_TrackedProgressMiddleware):
    phase_name = "plan_phase"
    expected_units = 1
    progress_window = _ProgressWindow(start=5, end=28)

    def before_agent(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        _, progress, changed = self._update_unit("plan", stage=0.08)
        if changed:
            emit_progress(
                ProgressEventType.RESEARCH_STARTING,
                "研究阶段启动：正在分析宠物信息并规划调研路径",
                node="plan_agent",
                progress=progress,
            )
        return None

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler,
    ) -> ModelResponse[ResponseT]:
        unit, _, _ = self._update_unit("plan", model_delta=1)
        enter_stage = min(0.42, 0.18 + 0.09 * unit.model_calls)
        unit, progress, changed = self._update_unit("plan", stage=enter_stage)
        if changed:
            emit_progress(
                ProgressEventType.PLAN_CREATING if unit.model_calls == 1 else ProgressEventType.PLAN_UPDATED,
                "规划研究阶段：正在整理宠物信息并决定下一步调研动作",
                node="plan_agent",
                progress=progress,
            )

        try:
            response = await handler(request)
        except Exception as exc:
            emit_progress(
                ProgressEventType.ERROR,
                f"[plan_agent] 调研阶段失败: {exc}",
                node="plan_agent",
            )
            raise

        tool_names = _extract_tool_call_names(response.result)
        if tool_names:
            delegation_stage = min(0.82, 0.48 + 0.06 * len(tool_names))
            _, progress, changed = self._update_unit("plan", stage=delegation_stage)
            if changed:
                emit_progress(
                    ProgressEventType.RESEARCH_TASK_DELEGATING,
                    f"正在委派 {len(tool_names)} 个调研动作:{', '.join(tool_names)}",
                    node="plan_agent",
                    detail={"tool_names": tool_names},
                    progress=progress,
                )
        else:
            update_stage = min(0.9, 0.50 + 0.08 * unit.model_calls)
            _, progress, changed = self._update_unit("plan", stage=update_stage)
            if changed:
                emit_progress(
                    ProgressEventType.PLAN_UPDATED,
                    "研究结果正在收束,准备生成协调指南",
                    node="plan_agent",
                    progress=progress,
                )

        # v2 GenUI: ai_message + plan_snapshot + subagent_spawn 细粒度事件
        _emit_genui_after_model_call(
            response,
            node="plan_agent",
            task_name=None,
        )

        return response

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler,
    ) -> ToolMessage | Command[Any]:
        tool_call = request.tool_call or {}
        tool_name = str(tool_call.get("name") or "")
        tool_args = tool_call.get("args") or {}
        if not isinstance(tool_args, Mapping):
            tool_args = {}
        call_id = tool_call.get("id") or f"{tool_name}_plan_agent"

        emit_tool_call(
            node="plan_agent",
            tool_name=tool_name,
            args=dict(tool_args),
            status="started",
            call_id=call_id,
        )

        try:
            result = await handler(request)
        except Exception as exc:
            emit_tool_call(
                node="plan_agent",
                tool_name=tool_name,
                args=dict(tool_args),
                status="error",
                result=str(exc),
                call_id=call_id,
            )
            raise

        emit_tool_call(
            node="plan_agent",
            tool_name=tool_name,
            args=dict(tool_args),
            status="completed",
            result=_extract_result_content(result),
            call_id=call_id,
        )
        return result

    def after_agent(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        _, progress, changed = self._update_unit("plan", stage=1.0)
        if changed:
            emit_progress(
                ProgressEventType.PLAN_CREATED,
                "研究阶段完成，调研笔记已经整理就绪",
                node="plan_agent",
                progress=progress,
            )
        self._cleanup_if_complete()
        return None


class WeekProgressMiddleware(_TrackedProgressMiddleware):
    phase_name = "week_phase"
    expected_units = 4
    progress_window = _ProgressWindow(start=40, end=78)

    def _unit_key(self, state: Any) -> str:
        week_number = _extract_week_number(state)
        return str(week_number) if week_number is not None else "unknown-week"

    def _node_name(self, week_number: int | None) -> str:
        return f"week_agent_{week_number}" if week_number is not None else "week_agent"

    def _task_name(self, week_number: int | None) -> str | None:
        return f"第{week_number}周饮食计划" if week_number is not None else None

    def _detail(self, week_number: int | None, **extra: Any) -> dict[str, Any]:
        detail: dict[str, Any] = {}
        if week_number is not None:
            detail["week"] = week_number
        detail.update(extra)
        return detail

    def _emit_week_event(
        self,
        event_type: ProgressEventType,
        message: str,
        *,
        week_number: int | None,
        progress: int | None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        emit_progress(
            event_type,
            message,
            node=self._node_name(week_number),
            task_name=self._task_name(week_number),
            detail=detail or self._detail(week_number),
            progress=progress,
        )

    def _tool_message(self, week_number: int | None, tool_name: str, tool_args: Mapping[str, Any]) -> tuple[ProgressEventType, str]:
        prefix = f"第{week_number}周：" if week_number is not None else ""

        if tool_name == "daily_calorie_tool":
            return (
                ProgressEventType.WEEK_PLANNING,
                f"{prefix}正在计算每日热量与三大营养素目标",
            )
        if tool_name == "nutrition_requirement_tool":
            return (
                ProgressEventType.WEEK_PLANNING,
                f"{prefix}正在计算微量营养素需求",
            )
        if tool_name == "ingredient_categories_tool":
            return (
                ProgressEventType.WEEK_SEARCHING,
                f"{prefix}正在读取食材分类与库存范围",
            )
        if tool_name == "ingredient_detail_tool":
            ingredient_name = tool_args.get("name")
            suffix = f"：{ingredient_name}" if ingredient_name else ""
            return (
                ProgressEventType.WEEK_SEARCHING,
                f"{prefix}正在查询食材营养详情{suffix}",
            )

        keyword = tool_args.get("keyword")
        category = tool_args.get("category")
        sub_category = tool_args.get("sub_category")
        focus = keyword or sub_category or category
        suffix = f"（{focus}）" if focus else ""
        return (
            ProgressEventType.WEEK_SEARCHING,
            f"{prefix}正在检索可用食材{suffix}",
        )

    def _has_final_week_output(self, state: AgentState) -> bool:
        if _state_get(state, "structured_response") is not None:
            return True
        week_light_plans = _state_get(state, "week_light_plans")
        return bool(week_light_plans)

    def before_agent(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        week_number = _extract_week_number(state)
        _, progress, changed = self._update_unit(self._unit_key(state), stage=0.15)
        if changed:
            self._emit_week_event(
                ProgressEventType.WEEK_PLANNING,
                f"第{week_number}周：已接收约束，开始制定周计划" if week_number is not None else "周计划任务已启动",
                week_number=week_number,
                progress=progress,
            )
        return None

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler,
    ) -> ModelResponse[ResponseT]:
        week_number = _extract_week_number(request.state)
        unit_key = self._unit_key(request.state)
        current = self._get_unit(unit_key)

        enter_stage = None
        enter_event = None
        enter_message = None
        if current.tool_calls > 0 and not current.ready_emitted:
            enter_stage = min(0.78, 0.60 + 0.04 * min(current.model_calls + 1, 3))
            enter_event = ProgressEventType.WEEK_WRITING
            enter_message = (
                f"第{week_number}周：正在整合工具结果并撰写周计划"
                if week_number is not None
                else "正在整合工具结果并撰写周计划"
            )

        _, progress, changed = self._update_unit(
            unit_key,
            model_delta=1,
            stage=enter_stage,
        )
        if enter_event and changed:
            self._emit_week_event(
                enter_event,
                enter_message or "正在撰写周计划",
                week_number=week_number,
                progress=progress,
            )

        try:
            response = await handler(request)
        except Exception as exc:
            emit_progress(
                ProgressEventType.ERROR,
                f"[{self._node_name(week_number)}] 周计划生成失败: {exc}",
                node=self._node_name(week_number),
                task_name=self._task_name(week_number),
            )
            raise

        # v2 GenUI: ai_message + plan_snapshot + subagent_spawn 细粒度事件
        _emit_genui_after_model_call(
            response,
            node=self._node_name(week_number),
            task_name=self._task_name(week_number),
        )

        tool_names = _extract_tool_call_names(response.result)
        business_tool_names = [name for name in tool_names if name in _WEEK_TOOL_NAMES]
        if business_tool_names:
            return response

        _, progress, changed = self._update_unit(
            unit_key,
            stage=0.85,
            ready_emitted=True,
        )
        if changed:
            self._emit_week_event(
                ProgressEventType.WEEK_PLAN_READY,
                f"第{week_number}周：选材与配比完成，正在整理结构化输出"
                if week_number is not None
                else "周计划草案已完成，正在整理最终输出",
                week_number=week_number,
                progress=progress,
            )
        return response

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler,
    ) -> ToolMessage | Command[Any]:
        week_number = _extract_week_number(request.state)
        unit_key = self._unit_key(request.state)
        tool_call = request.tool_call or {}
        tool_name = str(tool_call.get("name") or "")
        tool_args = tool_call.get("args") or {}
        if not isinstance(tool_args, Mapping):
            tool_args = {}
        call_id = tool_call.get("id") or f"{tool_name}_{self._node_name(week_number)}"

        if tool_name in _WEEK_TOOL_NAMES:
            _, _, _ = self._update_unit(unit_key, tool_delta=1)
            current = self._get_unit(unit_key)
            if tool_name in _SEARCH_TOOL_NAMES:
                stage = min(0.68, 0.34 + 0.07 * min(current.tool_calls, 5))
            else:
                stage = min(0.54, 0.24 + 0.06 * min(current.tool_calls, 4))

            event_type, message = self._tool_message(week_number, tool_name, tool_args)
            _, progress, changed = self._update_unit(unit_key, stage=stage)
            if changed:
                self._emit_week_event(
                    event_type,
                    message,
                    week_number=week_number,
                    progress=progress,
                    detail=self._detail(week_number, tool_name=tool_name, tool_args=dict(tool_args)),
                )

        # v2 GenUI: emit_tool_call started
        emit_tool_call(
            node=self._node_name(week_number),
            tool_name=tool_name,
            args=dict(tool_args),
            status="started",
            call_id=call_id,
            task_name=self._task_name(week_number),
        )

        try:
            result = await handler(request)
        except Exception as exc:
            emit_tool_call(
                node=self._node_name(week_number),
                tool_name=tool_name,
                args=dict(tool_args),
                status="error",
                result=str(exc),
                call_id=call_id,
                task_name=self._task_name(week_number),
            )
            emit_progress(
                ProgressEventType.ERROR,
                f"[{self._node_name(week_number)}] 工具调用失败({tool_name}): {exc}",
                node=self._node_name(week_number),
                task_name=self._task_name(week_number),
                detail=self._detail(week_number, tool_name=tool_name),
            )
            raise

        # v2 GenUI: emit_tool_call completed
        emit_tool_call(
            node=self._node_name(week_number),
            tool_name=tool_name,
            args=dict(tool_args),
            status="completed",
            result=_extract_result_content(result),
            call_id=call_id,
            task_name=self._task_name(week_number),
        )
        return result

    def after_agent(self, state: AgentState, runtime: Runtime[Any]) -> dict[str, Any] | None:
        if not self._has_final_week_output(state):
            return None

        week_number = _extract_week_number(state)
        _, progress, changed = self._update_unit(self._unit_key(state), stage=1.0)
        if changed:
            self._emit_week_event(
                ProgressEventType.WEEK_COMPLETED,
                f"第{week_number}周食谱已完成" if week_number is not None else "周计划已完成",
                week_number=week_number,
                progress=progress,
            )
        self._cleanup_if_complete()
        return None


plan_progress_middleware = PlanProgressMiddleware()
week_progress_middleware = WeekProgressMiddleware()

