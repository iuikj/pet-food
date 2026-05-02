"""
V1 周 Agent 节点实现

week_planner: 循环搜索/查询笔记 → 生成周计划
week_write: 将计划写入笔记
week_finalize: 发送完成进度事件（note 已由 week_write_note 工具直接写入）
"""
from typing import Literal, cast

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_dev_utils.chat_models import load_chat_model
from langchain_dev_utils.tool_calling import has_tool_calling, parse_tool_calling
from langgraph.prebuilt import ToolNode
from langgraph.types import Command

from src.agent.common.stream_events import (
    ProgressEventType,
    emit_progress,
    emit_ai_message,
    emit_tool_call,
    extract_reasoning,
)
from src.agent.common.tools import tavily_search
from src.agent.v1.models import WeekAssignment
from src.agent.v1.utils.context import resolve_context
from src.agent.v1.week_agent.state import WeekAgentState
from src.agent.v1.week_agent.tools import (
    create_query_shared_note_tool,
    create_week_write_note_tool,
)

# 创建工具实例
query_shared_note = create_query_shared_note_tool()
week_write_note = create_week_write_note_tool()


def _emit_completed_tool_call_from_messages(
    messages_key_value: list,
    *,
    node: str,
    task_name: str,
) -> None:
    """若 messages 列表最后一条是 ToolMessage,补发 tool_call completed 事件。

    适用于:week_planner 从 week_tools 回来时检测 week_messages 末尾;
          week_finalize 入口检测 week_write_messages 末尾的 week_write_note 结果。
    """
    if not messages_key_value:
        return
    last = messages_key_value[-1]
    if not isinstance(last, ToolMessage):
        return

    tool_call_id = getattr(last, "tool_call_id", None)
    tool_name = getattr(last, "name", None)

    # name 字段可能在某些 LC 版本缺失,从上一条 AIMessage 反查
    if not tool_name and len(messages_key_value) >= 2 and isinstance(messages_key_value[-2], AIMessage):
        for tc in messages_key_value[-2].tool_calls or []:
            if tc.get("id") == tool_call_id:
                tool_name = tc.get("name")
                break

    if not tool_name:
        return

    emit_tool_call(
        node=node,
        tool_name=tool_name,
        status="completed",
        result=last.content,
        call_id=tool_call_id or f"{tool_name}_{node}",
        task_name=task_name,
    )


async def week_planner(
    state: WeekAgentState,
    config: RunnableConfig,
) -> Command[Literal["week_tools", "week_write", "__end__"]]:
    """周计划核心节点：搜索 + 查询笔记 → 输出完整周计划"""
    ctx = resolve_context(config)
    assignment: WeekAssignment = state["week_assignment"]
    week_num = assignment.week_number
    info = state["pet_information"]
    shared_notes = state.get("shared_notes") or {}
    week_node = f"week_agent_{week_num}"
    task_label = f"第{week_num}周饮食计划"

    # 首次进入时发送进度
    if not state.get("week_messages"):
        base_progress = 30 + (week_num - 1) * 12
        emit_progress(
            ProgressEventType.WEEK_PLANNING,
            f"第{week_num}周: 开始制定饮食计划...",
            node=week_node,
            task_name=task_label,
            progress=base_progress,
        )
    else:
        # 从 week_tools 循环回来 — 上一轮工具结果落在 week_messages 末尾
        _emit_completed_tool_call_from_messages(
            state.get("week_messages") or [],
            node=week_node,
            task_name=task_label,
        )

    # 构建提示词
    shared_notes_list = (
        "\n".join(f"- {name}" for name in shared_notes.keys())
        if shared_notes
        else "（暂无共享笔记）"
    )

    prompt = ctx.week_planner_prompt.format(
        week_number=week_num,
        pet_information=info,
        theme=assignment.theme,
        focus_nutrients=", ".join(assignment.focus_nutrients),
        constraints="\n".join(f"- {c}" for c in assignment.constraints),
        differentiation_note=assignment.differentiation_note,
        search_keywords=", ".join(assignment.search_keywords),
        shared_constraints="\n".join(
            f"- {c}" for c in (state.get("shared_constraints") or [])
        ),
        ingredient_rotation_strategy=state.get("ingredient_rotation_strategy", ""),
        age_adaptation_note=state.get("age_adaptation_note", ""),
        shared_notes_list=shared_notes_list,
    )

    # 加载模型
    model = load_chat_model(
        model=ctx.week_model,
        max_retries=3,
    )
    tools = [tavily_search, query_shared_note]
    bind_model = model.bind_tools(tools)

    # 组装消息
    existing_messages = state.get("week_messages") or []
    messages_to_send = [
        SystemMessage(content=prompt),
        HumanMessage(
            content=f"请为第{week_num}周制定饮食计划，宠物信息：{info}"
        ),
        *existing_messages,
    ]

    response = await bind_model.ainvoke(messages_to_send)

    # AI 输出事件 — 第N周 LLM 决策可见
    content, reasoning = extract_reasoning(response)
    emit_ai_message(
        node=week_node,
        content=content,
        reasoning=reasoning,
        task_name=task_label,
        message_id=getattr(response, "id", None),
    )

    if has_tool_calling(response):
        tool_name, tool_args = parse_tool_calling(
            response, first_tool_call_only=True
        )
        tool_call_id = None
        if response.tool_calls:
            tool_call_id = response.tool_calls[0].get("id")

        # 发 tool_call started 事件 — SearchToolWidget / NoteReadWidget 渲染
        emit_tool_call(
            node=week_node,
            tool_name=tool_name,
            args=cast(dict, tool_args) if isinstance(tool_args, dict) else {},
            status="started",
            call_id=tool_call_id,
            task_name=task_label,
        )

        if tool_name == "tavily_search":
            emit_progress(
                ProgressEventType.WEEK_SEARCHING,
                f"第{week_num}周: 正在搜索相关食材信息...",
                node=week_node,
                task_name=task_label,
            )

        return Command(
            goto="week_tools",
            update={"week_messages": [response]},
        )

    # 无工具调用 — 计划已完成，进入写入阶段
    base_progress = 30 + (week_num - 1) * 12 + 8
    emit_progress(
        ProgressEventType.WEEK_PLAN_READY,
        f"第{week_num}周: 饮食计划制定完成，正在保存...",
        node=week_node,
        task_name=task_label,
        progress=base_progress,
    )

    return Command(
        goto="week_write",
        update={
            "week_messages": [response],
            "week_task_messages": [response],
        },
    )


async def week_write(state: WeekAgentState, config: RunnableConfig) -> Command[Literal["week_write_tool"]]:
    """将周计划写入笔记"""
    ctx = resolve_context(config)
    assignment: WeekAssignment = state["week_assignment"]
    week_num = assignment.week_number
    week_node = f"week_agent_{week_num}"
    task_label = f"第{week_num}周饮食计划"

    emit_progress(
        ProgressEventType.WEEK_WRITING,
        f"第{week_num}周: 正在保存饮食计划笔记...",
        node=week_node,
        task_name=task_label,
    )

    # 获取最后的计划内容
    task_messages = state.get("week_task_messages") or []
    plan_content = task_messages[-1].content if task_messages else ""

    write_model = load_chat_model(
        model=ctx.write_model,
    ).bind_tools([week_write_note], tool_choice="week_write_note")

    write_prompt = f"""请调用 week_write_note 工具保存以下第{week_num}周饮食计划。
文件名使用 "week_{week_num}_diet_plan"，内容如下：

{plan_content}

请确保笔记内容是Markdown格式。"""

    response = cast(
        AIMessage,
        await write_model.ainvoke(write_prompt),
    )

    # tool_choice="week_write_note" 强制调用,response.tool_calls 必有一项
    tool_call_id = None
    tool_args = {}
    if response.tool_calls:
        tool_call_id = response.tool_calls[0].get("id")
        tool_args = response.tool_calls[0].get("args") or {}

    emit_tool_call(
        node=week_node,
        tool_name="week_write_note",
        args=tool_args,
        status="started",
        call_id=tool_call_id,
        task_name=task_label,
    )

    return Command(
        goto="week_write_tool",
        update={"week_write_messages": [response]},
    )


async def week_finalize(state: WeekAgentState):
    """周 Agent 完成节点

    note 已由 week_write_note 工具通过 Command 直接写入 state["note"]，
    此节点仅负责发送进度事件。
    """
    assignment: WeekAssignment = state["week_assignment"]
    week_num = assignment.week_number
    week_node = f"week_agent_{week_num}"
    task_label = f"第{week_num}周饮食计划"

    # 上一节点是 week_write_tool — 补发 week_write_note 的 completed 事件
    _emit_completed_tool_call_from_messages(
        state.get("week_write_messages") or [],
        node=week_node,
        task_name=task_label,
    )

    # 验证 note 已写入
    notes = state.get("note") or {}
    note_count = len(notes)

    base_progress = 30 + week_num * 12
    emit_progress(
        ProgressEventType.WEEK_COMPLETED,
        f"第{week_num}周: 饮食计划完成 (已保存 {note_count} 条笔记)",
        node=week_node,
        task_name=task_label,
        progress=min(base_progress, 78),
    )

    # 无需返回任何状态更新 — note 已在 week_write_note 工具中直接写入
    return {}


# ── 工具执行节点 ──
week_tools = ToolNode(
    [tavily_search, query_shared_note],
    messages_key="week_messages",
)

week_write_tool = ToolNode(
    [week_write_note],
    messages_key="week_write_messages",
)
