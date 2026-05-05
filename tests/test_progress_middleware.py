from types import SimpleNamespace

import pytest
from langchain.agents.middleware.types import ModelRequest, ModelResponse, ToolCallRequest
from langchain.messages import AIMessage, HumanMessage
from langchain_core.messages import ToolMessage
from langgraph.runtime import Runtime

from src.agent.common.stream_events import ProgressEventType
from src.agent.common.view_types import ViewType
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
async def test_subagent_progress_emits_lifecycle_and_metadata(monkeypatch):
    events = []
    monkeypatch.setattr(progress_module, "emit_progress", lambda event_type, message, **kwargs: events.append({
        "type": event_type,
        "message": message,
        **kwargs,
    }))

    middleware = progress_module.SubAgentProgressMiddleware()
    runtime = Runtime(context=None)
    state = {
        "messages": [HumanMessage(content="调研低敏蛋白")],
    }

    update = middleware.before_agent(state, runtime)
    state.update(update or {})
    subagent_id = state["subagent_info"].subagent_id

    model = SimpleNamespace()
    model_request = ModelRequest(
        model=model,
        messages=[],
        state=state,
        runtime=runtime,
    )

    async def model_handler(inner_request):
        assert inner_request.model.metadata["subagent_id"] == subagent_id
        return ModelResponse(result=[AIMessage(content="ok")])

    await middleware.awrap_model_call(model_request, model_handler)

    tool = SimpleNamespace()
    tool_request = ToolCallRequest(
        tool_call={"id": "tool-1", "name": "tavily_search", "args": {}},
        tool=tool,
        state=state,
        runtime=runtime,
    )

    async def tool_handler(inner_request):
        assert inner_request.tool.metadata["subagent_id"] == subagent_id
        return ToolMessage(content="ok", tool_call_id="tool-1")

    await middleware.awrap_tool_call(tool_request, tool_handler)
    middleware.after_agent(state, runtime)

    event_types = [event["type"] for event in events]
    assert event_types == [
        ProgressEventType.Task.EXECUTING,
        ProgressEventType.Task.COMPLETED,
    ]
    start_event = events[0]
    assert start_event["detail"]["view_type"] == ViewType.SUBAGENT_DISPATCH.value
    assert start_event["detail"]["subagent_id"] == subagent_id
    assert events[1]["detail"]["status"] == "completed"
    assert all("progress" not in event for event in events)


@pytest.mark.asyncio
async def test_week_progress_emits_lifecycle_and_metadata_without_progress(monkeypatch):
    events = []
    monkeypatch.setattr(progress_module, "emit_progress", lambda event_type, message, **kwargs: events.append({
        "type": event_type,
        "message": message,
        **kwargs,
    }))

    middleware = progress_module.WeekProgressMiddleware()
    runtime = Runtime(context=None)
    state = _week_state(1)

    middleware.before_agent(state, runtime)

    tool = SimpleNamespace()
    tool_request = ToolCallRequest(
        tool_call={
            "id": "tool-1",
            "name": "ingredient_search_tool",
            "args": {"category": "白肉"},
        },
        tool=tool,
        state=state,
        runtime=runtime,
    )

    async def tool_handler(inner_request):
        assert inner_request.tool.metadata["week_number"] == 1
        return ToolMessage(content="ok", tool_call_id="tool-1")

    await middleware.awrap_tool_call(tool_request, tool_handler)

    model = SimpleNamespace()
    model_request = ModelRequest(
        model=model,
        messages=[],
        state=state,
        runtime=runtime,
    )

    async def model_handler(inner_request):
        assert inner_request.model.metadata["week_number"] == 1
        return ModelResponse(result=[AIMessage(content="final answer")])

    await middleware.awrap_model_call(model_request, model_handler)
    middleware.after_agent(_week_state(1), runtime)

    assert [event["type"] for event in events] == [
        ProgressEventType.Week.PLANNING,
        ProgressEventType.Week.COMPLETED,
    ]
    assert events[0]["detail"]["week_number"] == 1
    assert events[0]["detail"]["status"] == "started"
    assert events[1]["detail"]["status"] == "completed"
    assert all("progress" not in event for event in events)


def test_week_after_agent_emits_completed_lifecycle_without_output_gate(monkeypatch):
    events = []
    monkeypatch.setattr(progress_module, "emit_progress", lambda event_type, message, **kwargs: events.append({
        "type": event_type,
        "message": message,
        **kwargs,
    }))

    middleware = progress_module.WeekProgressMiddleware()
    runtime = Runtime(context=None)
    middleware.after_agent(_week_state(3), runtime)

    assert [event["type"] for event in events] == [ProgressEventType.Week.COMPLETED]
    assert events[0]["node"] == "week_agent_3"
    assert events[0]["detail"]["week_number"] == 3
    assert events[0]["detail"]["status"] == "completed"
