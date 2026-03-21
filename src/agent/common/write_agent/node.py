from typing import cast

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_dev_utils.chat_models import load_chat_model
from langgraph.prebuilt import ToolNode

from src.agent.common.entity.note import create_write_note_tool
from src.agent.common.stream_events import ProgressEventType, emit_progress
from src.agent.common.write_agent.state import WriteState
from src.agent.common.context import resolve_subgraph_context

# 在模块级别创建工具实例
write_note = create_write_note_tool(
    name="write_note",
    description="""用于写入笔记的工具。

    参数：
    content: str, 笔记内容
    type: Annotated[Literal["research", "diet_plan"]
    如果是制定确切的某周的饮食计划（按照报告模版的）type为diet_plan，其余作为信息收集的部分皆为research
    """,
    message_key="temp_write_note_messages",
)


async def write(state: WriteState, config: RunnableConfig):
    emit_progress(
        ProgressEventType.NOTE_SAVING,
        "正在保存任务笔记...",
        node="write_note",
    )

    ctx = resolve_subgraph_context(config)
    task_messages = state["task_messages"] if "task_messages" in state else []

    write_model = load_chat_model(
        model=ctx.write_model,
    ).bind_tools([write_note], tool_choice="write_note")

    task_content = task_messages[-1].content

    response = cast(
        AIMessage,
        await write_model.ainvoke(
            ctx.write_prompt.format(task_result=task_content)
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


async def summary(state: WriteState, config: RunnableConfig):
    emit_progress(
        ProgressEventType.SUMMARY_GENERATING,
        "正在生成任务摘要...",
        node="write_note",
    )

    ctx = resolve_subgraph_context(config)
    task_messages = state["task_messages"] if "task_messages" in state else []
    summary_model = load_chat_model(
        model=ctx.summary_model,
        **{
            "max_retries": 3
        }
    )

    task_content = task_messages[-1].content
    response = cast(
        AIMessage,
        await summary_model.ainvoke(
            ctx.summary_prompt.format(task_result=task_content)
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
