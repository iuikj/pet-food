"""
V1 周 Agent 节点实现

week_planner: 循环搜索/查询笔记 → 生成周计划
week_write: 将计划写入笔记
"""
from typing import Literal, cast

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_dev_utils import (
    has_tool_calling,
    load_chat_model,
    parse_tool_calling,
)
from langgraph.prebuilt import ToolNode
from langgraph.runtime import get_runtime
from langgraph.types import Command

from src.agent.v0.entity.note import Note
from src.agent.v0.stream_events import ProgressEventType, emit_progress
from src.agent.v0.tools import tavily_search
from src.agent.v1.models import WeekAssignment
from src.agent.v1.utils.context import ContextV1
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
) -> Command[Literal["week_tools", "week_write", "__end__"]]:
    """周计划核心节点：搜索 + 查询笔记 → 输出完整周计划"""
    run_time = get_runtime(ContextV1)
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

    prompt = run_time.context.week_planner_prompt.format(
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
        model=run_time.context.week_model,
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

    if has_tool_calling(cast(AIMessage, response)):
        tool_name, _ = parse_tool_calling(
            cast(AIMessage, response), first_tool_call_only=True
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


async def week_write(state: WeekAgentState) -> Command[Literal["week_write_tool"]]:
    """将周计划写入笔记"""
    run_time = get_runtime(ContextV1)
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
        model=run_time.context.write_model,
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
    """周 Agent 完成节点：将 week_note 合并到主图的 note 中"""
    assignment: WeekAssignment = state["week_assignment"]
    week_num = assignment.week_number
    week_note = state.get("week_note") or {}

    base_progress = 30 + week_num * 12
    emit_progress(
        ProgressEventType.WEEK_COMPLETED,
        f"第{week_num}周: 饮食计划完成",
        node=f"week_agent_{week_num}",
        task_name=f"第{week_num}周饮食计划",
        progress=min(base_progress, 78),
    )

    # 将 week_note 合并到主图的 note 空间
    return {
        "note": week_note,
    }


# ── 工具执行节点 ──
week_tools = ToolNode(
    [tavily_search, query_shared_note],
    messages_key="week_messages",
)

week_write_tool = ToolNode(
    [week_write_note],
    messages_key="week_write_messages",
)
