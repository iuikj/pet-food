import pytest
from langchain.messages import AIMessageChunk

from ag_ui.core import EventType
from src.api.agui_agent import DataclassAwareLangGraphAGUIAgent


class _StubGraph:
    nodes = {}


@pytest.mark.asyncio
async def test_reasoning_events_keep_langgraph_raw_metadata():
    agent = DataclassAwareLangGraphAGUIAgent(name="test", graph=_StubGraph())
    agent.active_run = {
        "id": "run-1",
        "thread_id": "thread-1",
        "reasoning_process": None,
    }

    raw_event = {
        "event": "on_chat_model_stream",
        "metadata": {"subagent_id": "subagent-1"},
        "data": {
            "chunk": AIMessageChunk(
                content="",
                additional_kwargs={"reasoning_content": "创建总结报告"},
            )
        },
    }

    events = [event async for event in agent._handle_single_event(raw_event, {})]

    reasoning_content = next(
        event for event in events if event.type == EventType.REASONING_MESSAGE_CONTENT
    )
    assert reasoning_content.delta == "创建总结报告"
    assert reasoning_content.raw_event["metadata"]["subagent_id"] == "subagent-1"
    assert all(
        event.raw_event["metadata"]["subagent_id"] == "subagent-1"
        for event in events
        if event.type in {
            EventType.REASONING_START,
            EventType.REASONING_MESSAGE_START,
            EventType.REASONING_MESSAGE_CONTENT,
        }
    )
