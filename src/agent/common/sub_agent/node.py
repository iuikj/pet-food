from typing import Literal, cast

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_dev_utils.chat_models import load_chat_model
from langchain_dev_utils.tool_calling import has_tool_calling, parse_tool_calling
from langgraph.prebuilt import ToolNode
from langgraph.types import Command

from src.agent.common.context import resolve_subgraph_context
from src.agent.common.entity.note import create_query_note_tool
from src.agent.common.stream_events import (
    ProgressEventType,
    aemit_progress,
)
from src.agent.common.sub_agent.state import SubAgentState
from src.agent.common.tools import get_weather, tavily_search
from src.agent.common.utils.format import message_format

# 在模块级别创建工具实例
query_note = create_query_note_tool(
    name="query_note",
    description="""用于查询笔记。

    参数：
    file_name:笔记名称

    返回：
    str, 查询的笔记内容

    """,
)


async def subagent_call_model(
    state: SubAgentState,
    config: RunnableConfig,
) -> Command[Literal["sub_tools", "__end__"]]:
    ctx = resolve_subgraph_context(config)
    last_ai_message = cast(AIMessage, state["messages"][-1])

    _, args = parse_tool_calling(last_ai_message, first_tool_call_only=True)
    task_name = cast(dict, args).get("content", "")

    # 发送任务开始执行进度
    await aemit_progress(
        ProgressEventType.Task.EXECUTING,
        f"子智能体开始执行任务: {task_name}",
        node="subagent",
        task_name=task_name,
    )

    # 预防模型多次调用网络搜索
    messages = state["temp_task_messages"] if "temp_task_messages" in state else []

    model = load_chat_model(
        model=ctx.sub_model,
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
                content=ctx.sub_prompt.format(
                    task_name=task_name,
                    history_files=message_format(list(notes.keys()))
                    if notes
                    else "当前没有笔记",
                    user_requirement=user_requirement,
                )
            ),
            HumanMessage(content=f"请帮我完成：{task_name}，宠物的基础信息是{state['pet_information']}"),
            *messages,
        ]
    )

    if has_tool_calling(response):
        tool_name, tool_args = parse_tool_calling(
            response, first_tool_call_only=True
        )

        # 根据工具类型发送对应 phase 进度事件(保留旧行为,plan_service SSE 仍消费)
        if tool_name == "tavily_search":
            await aemit_progress(
                ProgressEventType.Task.SEARCHING,
                "正在搜索相关信息...",
                node="subagent",
                task_name=task_name,
            )
        elif tool_name == "query_note":
            await aemit_progress(
                ProgressEventType.Task.QUERYING_NOTE,
                "正在查询历史笔记...",
                node="subagent",
                task_name=task_name,
            )
        return Command(
            goto="sub_tools",
            update={"temp_task_messages": [response]},
        )

    # 任务执行完成（无工具调用，返回最终结果）
    await aemit_progress(
        ProgressEventType.Task.COMPLETED,
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
