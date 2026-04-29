from types import SimpleNamespace

import pytest
from langchain.agents.middleware.types import ModelRequest, ModelResponse, ToolCallRequest
from langchain.messages import AIMessage
from langchain_core.messages import ToolMessage
from langgraph.runtime import Runtime

from src.agent.common.stream_events import ProgressEventType
from src.agent.v2.middlewares import progress_middleware as progress_module


@pytest.fixture(autouse=True)
def reset_progress_trackers(monkeypatch):
    progress_module._TRACKERS.clear()
    yield
    progress_module._TRACKERS.clear()


def _week_state(week_number: int, **extra):
    return {
        "week_assignment": SimpleNamespace(week_number=week_number),
        **extra,
    }


@pytest.mark.asyncio
async def test_plan_progress_emits_research_lifecycle(monkeypatch):
    events = []
    monkeypatch.setattr(progress_module, "_safe_run_key", lambda: "plan-run")
    monkeypatch.setattr(progress_module, "emit_progress", lambda event_type, message, **kwargs: events.append({
        "type": event_type,
        "message": message,
        **kwargs,
    }))

    middleware = progress_module.PlanProgressMiddleware()
    runtime = Runtime(context=None)
    middleware.before_agent({"messages": []}, runtime)

    request = ModelRequest(
        model=object(),
        messages=[],
        state={"messages": []},
        runtime=runtime,
    )

    async def handler(_request):
        return ModelResponse(
            result=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "call-1",
                            "name": "general-purpose",
                            "args": {"topic": "low-allergen protein"},
                        }
                    ],
                )
            ]
        )

    await middleware.awrap_model_call(request, handler)
    middleware.after_agent({"messages": []}, runtime)

    event_types = [event["type"] for event in events]
    assert event_types == [
        ProgressEventType.RESEARCH_STARTING,
        ProgressEventType.PLAN_CREATING,
        ProgressEventType.RESEARCH_TASK_DELEGATING,
        ProgressEventType.PLAN_CREATED,
    ]
    progress_values = [event["progress"] for event in events]
    assert progress_values == sorted(progress_values)


@pytest.mark.asyncio
async def test_week_progress_stays_monotonic_across_parallel_events(monkeypatch):
    events = []
    monkeypatch.setattr(progress_module, "_safe_run_key", lambda: "week-run")
    monkeypatch.setattr(progress_module, "emit_progress", lambda event_type, message, **kwargs: events.append({
        "type": event_type,
        "message": message,
        **kwargs,
    }))

    middleware = progress_module.WeekProgressMiddleware()
    runtime = Runtime(context=None)

    middleware.before_agent(_week_state(1), runtime)

    tool_request = ToolCallRequest(
        tool_call={
            "id": "tool-1",
            "name": "ingredient_search_tool",
            "args": {"category": "白肉"},
        },
        tool=None,
        state=_week_state(1),
        runtime=runtime,
    )

    async def tool_handler(_request):
        return ToolMessage(content="ok", tool_call_id="tool-1")

    await middleware.awrap_tool_call(tool_request, tool_handler)

    middleware.before_agent(_week_state(2), runtime)

    model_request = ModelRequest(
        model=object(),
        messages=[],
        state=_week_state(1),
        runtime=runtime,
    )

    async def model_handler(_request):
        return ModelResponse(result=[AIMessage(content="final answer")])

    await middleware.awrap_model_call(model_request, model_handler)
    middleware.after_agent(_week_state(1, structured_response=object()), runtime)

    progress_values = [event["progress"] for event in events if event.get("progress") is not None]
    assert progress_values == sorted(progress_values)
    assert [event["type"] for event in events] == [
        ProgressEventType.WEEK_PLANNING,
        ProgressEventType.WEEK_SEARCHING,
        ProgressEventType.WEEK_PLANNING,
        ProgressEventType.WEEK_WRITING,
        ProgressEventType.WEEK_PLAN_READY,
        ProgressEventType.WEEK_COMPLETED,
    ]


def test_week_after_agent_skips_incomplete_iterations(monkeypatch):
    events = []
    monkeypatch.setattr(progress_module, "_safe_run_key", lambda: "week-incomplete-run")
    monkeypatch.setattr(progress_module, "emit_progress", lambda event_type, message, **kwargs: events.append({
        "type": event_type,
        "message": message,
        **kwargs,
    }))

    middleware = progress_module.WeekProgressMiddleware()
    runtime = Runtime(context=None)
    middleware.after_agent(_week_state(3), runtime)

    assert events == []

