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

from src.agent.sub_agent.state import SubAgentState
from src.agent.tools import get_weather, query_note, tavily_search
from src.agent.utils.context import Context


async def subagent_call_model(
    state: SubAgentState,
) -> Command[Literal["sub_tools", "__end__"]]:
    run_time = get_runtime(Context)
    last_ai_message = cast(AIMessage, state["messages"][-1])

    _, args = parse_tool_calling(last_ai_message, first_tool_call_only=True)
    task_name = cast(dict, args).get("content", "")

    model = load_chat_model(
        model=run_time.context.sub_model,
        **{
            "max_retries": 3
        }
    ).bind_tools(
        [get_weather, tavily_search, query_note]
    )

    messages = state["temp_task_messages"] if "temp_task_messages" in state else []

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
            HumanMessage(content=f"我的任务是：{task_name}，请帮我完成"),
            *messages,
        ]
    )

    if has_tool_calling(cast(AIMessage, response)):
        return Command(
            goto="sub_tools",
            update={"temp_task_messages": [response]},
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
