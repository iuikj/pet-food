"""
V1 周 Agent 节点实现

week_planner: 循环搜索/查询笔记 → 生成周计划
week_write: 将计划写入笔记
week_finalize: 发送完成进度事件（note 已由 week_write_note 工具直接写入）
"""
from typing import Literal, cast

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_dev_utils.chat_models import load_chat_model
from langchain_dev_utils.tool_calling import has_tool_calling, parse_tool_calling
from langgraph.prebuilt import ToolNode
from langgraph.types import Command

from src.agent.common.stream_events import ProgressEventType, emit_progress
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

    # 首次进入时发送进度
    if not state.get("week_messages"):
        base_progress = 30 + (week_num - 1) * 12
        emit_progress(
            ProgressEventType.WEEK_PLANNING,
            f"第{week_num}周: 开始制定饮食计划...",
            node=f"week_agent_{week_num}",
            task_name=f"第{week_num}周饮食计划",
            progress=base_progress,
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

    if has_tool_calling(response):
        tool_name, _ = parse_tool_calling(
            response, first_tool_call_only=True
        )

        if tool_name == "tavily_search":
            emit_progress(
                ProgressEventType.WEEK_SEARCHING,
                f"第{week_num}周: 正在搜索相关食材信息...",
                node=f"week_agent_{week_num}",
                task_name=f"第{week_num}周饮食计划",
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
        node=f"week_agent_{week_num}",
        task_name=f"第{week_num}周饮食计划",
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

    emit_progress(
        ProgressEventType.WEEK_WRITING,
        f"第{week_num}周: 正在保存饮食计划笔记...",
        node=f"week_agent_{week_num}",
        task_name=f"第{week_num}周饮食计划",
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

    # 验证 note 已写入
    notes = state.get("note") or {}
    note_count = len(notes)

    base_progress = 30 + week_num * 12
    emit_progress(
        ProgressEventType.WEEK_COMPLETED,
        f"第{week_num}周: 饮食计划完成 (已保存 {note_count} 条笔记)",
        node=f"week_agent_{week_num}",
        task_name=f"第{week_num}周饮食计划",
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
