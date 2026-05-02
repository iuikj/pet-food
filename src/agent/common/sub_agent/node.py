from typing import Literal, cast

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
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
    aemit_ai_message,
    aemit_tool_call,
    extract_reasoning,
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


async def _emit_completed_tool_call_if_any(state: SubAgentState, node: str, task_name: str) -> None:
    """
    入口检测：若上一条 temp_task_messages 是 ToolMessage,补发 tool_call completed 事件。

    LangGraph 的 ToolNode 执行完毕后,把 ToolMessage 追加到 temp_task_messages,
    再回到 subagent_call_model。此处把它"翻译"成 tool_call (status=completed),
    与之前 LLM 决定调用时发的 started 事件用同一 call_id 合并到前端同一张卡。
    """
    msgs = state.get("temp_task_messages") or []
    if not msgs or not isinstance(msgs[-1], ToolMessage):
        return

    tool_msg: ToolMessage = msgs[-1]
    tool_call_id = getattr(tool_msg, "tool_call_id", None)
    tool_name = getattr(tool_msg, "name", None)

    # name 字段在 LC 0.3+ 一般有;若缺失则从上一条 AIMessage 的 tool_calls 反查。
    if not tool_name and len(msgs) >= 2 and isinstance(msgs[-2], AIMessage):
        for tc in msgs[-2].tool_calls or []:
            if tc.get("id") == tool_call_id:
                tool_name = tc.get("name")
                break

    if not tool_name:
        return

    await aemit_tool_call(
        node=node,
        tool_name=tool_name,
        status="completed",
        result=tool_msg.content,
        call_id=tool_call_id or f"{tool_name}_{node}",
        task_name=task_name,
    )


async def subagent_call_model(
    state: SubAgentState,
    config: RunnableConfig,
) -> Command[Literal["sub_tools", "__end__"]]:
    ctx = resolve_subgraph_context(config)
    last_ai_message = cast(AIMessage, state["messages"][-1])

    _, args = parse_tool_calling(last_ai_message, first_tool_call_only=True)
    task_name = cast(dict, args).get("content", "")

    # 检测上一轮工具是否刚执行完,补发 completed 事件供前端合并 widget
    await _emit_completed_tool_call_if_any(state, node="subagent", task_name=task_name)

    # 发送任务开始执行进度
    await aemit_progress(
        ProgressEventType.TASK_EXECUTING,
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

    # AI 输出事件 — 子智能体 LLM 决策可见(reasoning 自动抽出)
    content, reasoning = extract_reasoning(response)
    await aemit_ai_message(
        node="subagent",
        content=content,
        reasoning=reasoning,
        task_name=task_name,
        message_id=getattr(response, "id", None),
    )

    if has_tool_calling(response):
        tool_name, tool_args = parse_tool_calling(
            response, first_tool_call_only=True
        )
        # 取真实的 tool_call_id 作为 call_id,前端用它把 started + completed 两条合并
        tool_call_id = None
        if response.tool_calls:
            tool_call_id = response.tool_calls[0].get("id")

        # 发 tool_call started 事件 — 前端按 tool_name 路由到 SearchToolWidget / NoteReadWidget 等
        await aemit_tool_call(
            node="subagent",
            tool_name=tool_name,
            args=cast(dict, tool_args) if isinstance(tool_args, dict) else {},
            status="started",
            call_id=tool_call_id,
            task_name=task_name,
        )

        # 根据工具类型发送对应 phase 进度事件(保留旧行为,plan_service SSE 仍消费)
        if tool_name == "tavily_search":
            await aemit_progress(
                ProgressEventType.TASK_SEARCHING,
                "正在搜索相关信息...",
                node="subagent",
                task_name=task_name,
            )
        elif tool_name == "query_note":
            await aemit_progress(
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
    await aemit_progress(
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
