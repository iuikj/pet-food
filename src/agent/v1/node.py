"""
V1 主图节点实现

research_planner: Phase 1 核心，循环执行调研任务
dispatch_weeks: Phase 1→2 转折，生成 4 个 Send 并行任务
collect_and_structure: Phase 2→3 转折，收集笔记并 Send 到结构化智能体
gather: 汇总所有周计划生成最终报告
"""
from typing import Literal, cast

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_dev_utils import has_tool_calling, load_chat_model, parse_tool_calling, message_format
from langgraph.prebuilt import ToolNode
from langgraph.runtime import get_runtime
from langgraph.types import Command, Send

from src.agent.v0.entity.note import Note
from src.agent.v0.stream_events import ProgressEventType, emit_progress
from src.agent.v0.utils.struct import PetDietPlan, MonthlyDietPlan
from src.agent.v1.models import CoordinationGuide
from src.agent.v1.state import StateV1
from src.agent.v1.tools import (
    write_plan,
    update_plan,
    transfor_task_to_subagent,
    ls,
    query_note,
    finalize_research,
)
from src.agent.v1.utils.context import ContextV1


# ────────────────────────────────────────────────────────
# Phase 1: 研究规划器
# ────────────────────────────────────────────────────────

async def research_planner(
    state: StateV1,
) -> Command[Literal["research_tools", "research_subagent", "dispatch_weeks"]]:
    """研究阶段核心节点：调研循环 + finalize 触发协调指南生成"""
    run_time = get_runtime(ContextV1)
    has_plan = bool(state.get("plan"))

    if not has_plan:
        emit_progress(
            ProgressEventType.RESEARCH_STARTING,
            "正在分析宠物信息，制定研究计划...",
            node="research_planner",
            progress=2,
        )

    # 加载模型
    model = load_chat_model(
        model=run_time.context.plan_model,
        max_retries=3,
    )

    tools = [
        write_plan,
        update_plan,
        transfor_task_to_subagent,
        ls,
        query_note,
        finalize_research,
    ]
    bind_model = model.bind_tools(tools, parallel_tool_calls=False)

    info = state["pet_information"]
    messages = state["messages"]

    response = await bind_model.ainvoke(
        [
            SystemMessage(
                content=run_time.context.research_planner_prompt.format(
                    pet_information=info,
                )
            ),
            *messages,
        ]
    )

    if has_tool_calling(cast(AIMessage, response)):
        name, args = parse_tool_calling(
            cast(AIMessage, response), first_tool_call_only=True
        )

        # ── finalize_research: 结束研究，生成协调指南 ──
        if name == "finalize_research":
            emit_progress(
                ProgressEventType.RESEARCH_FINALIZING,
                "研究完成，正在生成四周差异化协调指南...",
                node="research_planner",
                progress=25,
            )

            # 先执行 finalize_research 工具以获取 ToolMessage
            tool_node_temp = ToolNode([finalize_research])
            tool_result = await tool_node_temp.ainvoke(
                {"messages": [response]}
            )

            # 生成 CoordinationGuide
            coordination_guide = await _generate_coordination_guide(state, run_time)

            return Command(
                goto="dispatch_weeks",
                update={
                    "messages": [response, *tool_result["messages"]],
                    "coordination_guide": coordination_guide,
                },
            )

        # ── transfor_task_to_subagent: 委派研究任务 ──
        if name == "transfor_task_to_subagent":
            task_name = (
                cast(dict, args).get("content", "") if isinstance(args, dict) else ""
            )
            progress = _estimate_research_progress(state)
            emit_progress(
                ProgressEventType.RESEARCH_TASK_DELEGATING,
                f"正在委派研究任务: {task_name}",
                node="research_planner",
                task_name=task_name,
                progress=progress,
            )
            return Command(
                goto="research_subagent",
                update={
                    "messages": [response],
                    "now_task_message_index": len(
                        state["task_messages"] if "task_messages" in state else []
                    ),
                },
            )

        # ── 其他工具（write_plan, update_plan, ls, query_note）──
        if name == "write_plan":
            emit_progress(
                ProgressEventType.PLAN_CREATED,
                "研究任务计划已创建",
                node="research_planner",
                progress=5,
            )
        elif name == "update_plan":
            emit_progress(
                ProgressEventType.PLAN_UPDATED,
                "研究任务进度已更新",
                node="research_planner",
                progress=_estimate_research_progress(state),
            )

        return Command(goto="research_tools", update={"messages": [response]})

    # 无工具调用 — 研究阶段自然结束，直接 dispatch
    emit_progress(
        ProgressEventType.RESEARCH_FINALIZING,
        "研究完成，正在生成四周差异化协调指南...",
        node="research_planner",
        progress=25,
    )
    coordination_guide = await _generate_coordination_guide(state, run_time)
    return Command(
        goto="dispatch_weeks",
        update={
            "messages": [response],
            "coordination_guide": coordination_guide,
        },
    )


async def _generate_coordination_guide(state: StateV1, run_time) -> CoordinationGuide:
    """基于研究笔记生成 CoordinationGuide"""
    notes: dict[str, Note] = state.get("note") or {}

    # 汇总所有研究笔记
    research_notes_text = ""
    for name, note in notes.items():
        research_notes_text += f"\n### {name}\n{note.content}\n"

    if not research_notes_text:
        research_notes_text = "（暂无调研笔记）"

    info = state["pet_information"]

    model = load_chat_model(
        model=run_time.context.plan_model,
        max_retries=3,
    )
    guide_model = model.with_structured_output(CoordinationGuide)

    guide = await guide_model.ainvoke(
        [
            SystemMessage(
                content=run_time.context.coordination_guide_prompt.format(
                    pet_information=info,
                    research_notes=research_notes_text,
                )
            ),
            HumanMessage(content="请根据以上调研结果，生成四周差异化的饮食计划协调指南。"),
        ]
    )
    return guide


def _estimate_research_progress(state: StateV1) -> int:
    """研究阶段进度估算 (5-25%)"""
    plan = state.get("plan")
    if not plan:
        return 5
    total = len(plan)
    if total == 0:
        return 5
    done = sum(1 for item in plan if getattr(item, "status", None) == "done")
    return 5 + int((done / total) * 20)


# ────────────────────────────────────────────────────────
# Phase 1→2: 分发周任务
# ────────────────────────────────────────────────────────

async def dispatch_weeks(state: StateV1) -> Command[Literal["week_agent"]]:
    """纯逻辑节点：从 coordination_guide 生成 4 个 Send 并行任务"""
    guide: CoordinationGuide = state["coordination_guide"]
    notes: dict[str, Note] = state.get("note") or {}
    info = state["pet_information"]

    emit_progress(
        ProgressEventType.DISPATCHING,
        "正在分发四周饮食计划任务（并行执行）...",
        node="dispatch_weeks",
        progress=30,
    )

    sends = []
    for assignment in guide.weekly_assignments:
        sends.append(
            Send(
                node="week_agent",
                arg={
                    "pet_information": info,
                    "week_assignment": assignment,
                    "shared_notes": notes,
                    "shared_constraints": guide.shared_constraints,
                    "ingredient_rotation_strategy": guide.ingredient_rotation_strategy,
                    "age_adaptation_note": guide.age_adaptation_note,
                },
            )
        )

    return Command(goto=sends)


# ────────────────────────────────────────────────────────
# Phase 2→3: 收集并结构化
# ────────────────────────────────────────────────────────

async def collect_and_structure(state: StateV1) -> Command[Literal["structure_report"]]:
    """收集所有 week_agent 产出的 diet_plan 笔记，Send 到结构化智能体"""
    notes: dict[str, Note] = state.get("note") or {}

    emit_progress(
        ProgressEventType.GATHERING,
        "所有周计划已完成，正在进入结构化解析阶段...",
        node="collect_and_structure",
        progress=80,
    )

    sends = [
        Send(
            node="structure_report",
            arg={"temp_note": note},
        )
        for _, note in notes.items()
    ]

    return Command(goto=sends)


# ────────────────────────────────────────────────────────
# Phase 3: 汇总
# ────────────────────────────────────────────────────────

async def gather(state: StateV1):
    """汇总所有 WeeklyDietPlan 生成最终报告"""
    weekly_plans = state.get("weekly_diet_plans", [])

    emit_progress(
        ProgressEventType.COMPLETED,
        f"月度饮食计划生成完成！共 {len(weekly_plans)} 周计划",
        node="gather",
        detail={"total_weeks": len(weekly_plans)},
        progress=100,
    )

    # 生成 AI 建议摘要
    messages = state.get("messages", [])
    ai_suggestions = messages[-1].content if messages else "饮食计划已生成，请查看详细报告。"

    return {
        "report": PetDietPlan(
            pet_information=state["pet_information"],
            pet_diet_plan=MonthlyDietPlan(monthly_diet_plan=weekly_plans),
            ai_suggestions=ai_suggestions,
        )
    }


# ── 工具执行节点 ──
research_tools = ToolNode([write_plan, update_plan, ls, query_note])
