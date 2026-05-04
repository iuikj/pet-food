from types import SimpleNamespace

import pytest
from langchain.agents.middleware.types import ModelRequest, ModelResponse, ToolCallRequest
from langchain.messages import AIMessage
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolRuntime
from langgraph.runtime import Runtime
from langgraph.types import Command

from src.agent.common.stream_events import ProgressEventType
from src.agent.v2.middlewares import progress_middleware as progress_module


@pytest.fixture(autouse=True)
def reset_progress_events(monkeypatch):
    yield


def _week_state(week_number: int, **extra):
    return {
        "week_assignment": SimpleNamespace(week_number=week_number),
        **extra,
    }


@pytest.mark.asyncio
async def test_plan_progress_emits_research_lifecycle(monkeypatch):
    events = []
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
                            "name": "task",
                            "args": {"topic": "low-allergen protein"},
                        }
                    ],
                )
            ]
        )

    await middleware.awrap_model_call(request, handler)

    tool_runtime = ToolRuntime(
        state={"messages": []},
        context=None,
        config={},
        stream_writer=lambda _chunk: None,
        tools=[],
        tool_call_id="call-1",
        store=None,
    )
    tool_request = ToolCallRequest(
        tool_call={
            "id": "call-1",
            "name": "task",
            "args": {
                "description": "调研低敏蛋白",
                "subagent_type": "general-purpose",
            },
        },
        tool=None,
        state={"messages": []},
        runtime=tool_runtime,
    )

    async def tool_handler(inner_request):
        assert inner_request.state["is_subagent"] is True
        assert inner_request.state["subagent_info"].input_message == "调研低敏蛋白"
        return Command(
            update={
                "messages": [ToolMessage(content="ok", tool_call_id="call-1")],
                "is_subagent": True,
                "subagent_info": inner_request.state["subagent_info"],
            }
        )

    result = await middleware.awrap_tool_call(tool_request, tool_handler)
    assert "is_subagent" not in result.update
    assert "subagent_info" not in result.update

    middleware.after_agent({"messages": []}, runtime)

    event_types = [event["type"] for event in events]
    assert event_types == [
        ProgressEventType.Research.STARTING,
        ProgressEventType.Research.TASK_DELEGATING,
        ProgressEventType.Task.COMPLETED,
        ProgressEventType.Research.FINALIZING,
    ]
    dispatch_event = events[1]
    assert dispatch_event["detail"]["view_type"] == "subagent_dispatch"
    assert dispatch_event["detail"]["subagent_id"]
    assert all("progress" not in event for event in events)


@pytest.mark.asyncio
async def test_week_progress_emits_business_phase_events_without_progress(monkeypatch):
    events = []
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
        state=_week_state(1, messages=[ToolMessage(content="ok", tool_call_id="tool-1")]),
        runtime=runtime,
    )

    async def model_handler(_request):
        return ModelResponse(result=[AIMessage(content="final answer")])

    await middleware.awrap_model_call(model_request, model_handler)
    middleware.after_agent(_week_state(1, structured_response=object()), runtime)

    assert [event["type"] for event in events] == [
        ProgressEventType.Week.PLANNING,
        ProgressEventType.Week.SEARCHING,
        ProgressEventType.Week.PLANNING,
        ProgressEventType.Week.WRITING,
        ProgressEventType.Week.WRITING,
        ProgressEventType.Week.COMPLETED,
    ]
    assert all("progress" not in event for event in events)


def test_week_after_agent_skips_incomplete_iterations(monkeypatch):
    events = []
    monkeypatch.setattr(progress_module, "emit_progress", lambda event_type, message, **kwargs: events.append({
        "type": event_type,
        "message": message,
        **kwargs,
    }))

    middleware = progress_module.WeekProgressMiddleware()
    runtime = Runtime(context=None)
    middleware.after_agent(_week_state(3), runtime)

    assert events == []
