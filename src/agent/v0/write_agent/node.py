from typing import cast

from langchain_core.messages import AIMessage, ToolMessage
from langchain_dev_utils import load_chat_model
from langgraph.prebuilt import ToolNode
from langgraph.runtime import get_runtime

from src.agent.v0.stream_events import ProgressEventType, emit_progress
from src.agent.v0.write_agent.state import WriteState
from src.agent.v0.tools import write_note
from src.agent.v0.utils.context import Context


async def write(state: WriteState):
    emit_progress(
        ProgressEventType.NOTE_SAVING,
        "正在保存任务笔记...",
        node="write_note",
    )

    run_time = get_runtime(Context)
    task_messages = state["task_messages"] if "task_messages" in state else []

    write_model = load_chat_model(
        model=run_time.context.write_model,
    ).bind_tools([write_note], tool_choice="write_note")

    task_content = task_messages[-1].content

    response = cast(
        AIMessage,
        await write_model.ainvoke(
            run_time.context.write_prompt.format(task_result=task_content)
        ),
    )

    emit_progress(
        ProgressEventType.NOTE_SAVED,
        "笔记保存完成",
        node="write_note",
    )

    return {
        "temp_write_note_messages": [response],
    }


async def summary(state: WriteState):
    emit_progress(
        ProgressEventType.SUMMARY_GENERATING,
        "正在生成任务摘要...",
        node="write_note",
    )

    run_time = get_runtime(Context)
    task_messages = state["task_messages"] if "task_messages" in state else []
    summary_model = load_chat_model(
        model=run_time.context.summary_model,
        **{
            "max_retries": 3
        }
    )

    task_content = task_messages[-1].content
    response = cast(
        AIMessage,
        await summary_model.ainvoke(
            run_time.context.summary_prompt.format(task_result=task_content)
        ),
    )

    emit_progress(
        ProgressEventType.SUMMARY_GENERATED,
        "任务摘要生成完成",
        node="write_note",
    )

    tool_call_id = cast(AIMessage, state["messages"][-1]).tool_calls[0]["id"]
    return {
        "messages": [
            ToolMessage(
                content=f"任务执行完成！此任务结果摘要：{response.content}",
                tool_call_id=tool_call_id,
            ),
        ],
    }


write_tool = ToolNode([write_note], messages_key="temp_write_note_messages")
