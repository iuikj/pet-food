from typing import Literal, cast

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_dev_utils import (
    has_tool_calling,
    load_chat_model,
    message_format,
    parse_tool_calling,
)
from langgraph.prebuilt import ToolNode
from langgraph.runtime import get_runtime
from langgraph.types import Command

from src.agent.v0.stream_events import ProgressEventType, emit_progress
from src.agent.v0.sub_agent.state import SubAgentState
from src.agent.v0.tools import get_weather, query_note, tavily_search
from src.agent.v0.utils.context import Context


async def subagent_call_model(
    state: SubAgentState,
) -> Command[Literal["sub_tools", "__end__"]]:
    run_time = get_runtime(Context)
    last_ai_message = cast(AIMessage, state["messages"][-1])

    _, args = parse_tool_calling(last_ai_message, first_tool_call_only=True)
    task_name = cast(dict, args).get("content", "")

    # 发送任务开始执行进度
    emit_progress(
        ProgressEventType.TASK_EXECUTING,
        f"子智能体开始执行任务: {task_name}",
        node="subagent",
        task_name=task_name,
    )

    # 预防模型多次调用网络搜索
    messages = state["temp_task_messages"] if "temp_task_messages" in state else []

    model = load_chat_model(
        model=run_time.context.sub_model,
        **{
            "max_retries": 3
        }
    ).bind_tools(
        [get_weather, tavily_search, query_note]
    )


    notes = state["note"] if "note" in state else {}

    user_requirement = state["messages"][0].content

    response = await model.ainvoke(
        [
            SystemMessage(
                content=run_time.context.sub_prompt.format(
                    task_name=task_name,
                    history_files=message_format(list(notes.keys()))
                    if notes
                    else "当前没有笔记",
                    user_requirement=user_requirement,
                )
            ),
            HumanMessage(content=f"我的任务是：{task_name}，请帮我完成,宠物的基础信息是{state["pet_information"]}"),
            *messages,
        ]
    )

    if has_tool_calling(cast(AIMessage, response)):
        tool_name, _ = parse_tool_calling(
            cast(AIMessage, response), first_tool_call_only=True
        )
        # 根据工具类型发送对应进度事件
        if tool_name == "tavily_search":
            emit_progress(
                ProgressEventType.TASK_SEARCHING,
                "正在搜索相关信息...",
                node="subagent",
                task_name=task_name,
            )
        elif tool_name == "query_note":
            emit_progress(
                ProgressEventType.TASK_QUERYING_NOTE,
                "正在查询历史笔记...",
                node="subagent",
                task_name=task_name,
            )
        return Command(
            goto="sub_tools",
            update={"temp_task_messages": [response]},
        )

    # 任务执行完成（无工具调用，返回最终结果）
    emit_progress(
        ProgressEventType.TASK_COMPLETED,
        f"任务执行完成: {task_name}",
        node="subagent",
        task_name=task_name,
    )
    return Command(
        goto="__end__",
        update={
            "task_messages": [*state["temp_task_messages"], response],
        },
    )


sub_tools = ToolNode(
    [get_weather, tavily_search, query_note], messages_key="temp_task_messages"
)
