"""
V1 主图节点实现

research_planner: Phase 1 核心，循环执行调研任务
dispatch_weeks: Phase 1→2 转折，生成 4 个 Send 并行任务
collect_and_structure: Phase 2→3 转折，收集笔记并 Send 到结构化智能体
gather: 汇总所有周计划生成最终报告
"""
import logging
from typing import Literal, cast

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_dev_utils.chat_models import load_chat_model
from langchain_dev_utils.tool_calling import has_tool_calling, parse_tool_calling
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, Send

from src.agent.common.entity.note import Note
from src.agent.common.stream_events import (
    ProgressEventType,
    aemit_progress,
    aemit_ai_message,
    aemit_plan_snapshot,
    aemit_subagent_spawn,
    extract_reasoning,
)
from src.agent.common.utils.struct import PetDietPlan, MonthlyDietPlan
from src.agent.v1.models import CoordinationGuide
from src.agent.v1.state import StateV1
from src.agent.v1.tools import (
    ls,
    query_note,
    transfor_task_to_subagent,
    finish_sub_plan,
    read_plan_tool,
    write_plan,
)
from src.agent.v1.utils.context import resolve_context
from src.utils.strtuct import PetInformation

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────
# Phase 1: 研究规划器
# ────────────────────────────────────────────────────────

async def research_planner(
    state: StateV1,
    config: RunnableConfig,
) -> Command[Literal["research_tools", "research_subagent", "dispatch_weeks"]]:
    """研究阶段核心节点：调研循环 + finalize 触发协调指南生成"""
    ctx = resolve_context(config)
    has_plan = bool(state.get("plan"))

    if not has_plan:
        await aemit_progress(
            ProgressEventType.RESEARCH_STARTING,
            "正在分析宠物信息，制定研究计划...",
            node="research_planner",
            progress=2,
        )
    else:
        # 已有计划 — 进入时发一次 plan_snapshot,前端 PlanBoardWidget 直接看到当前 todo 状态
        await aemit_plan_snapshot(
            node="research_planner",
            plan=state["plan"],
            action="snapshot",
            progress=_estimate_research_progress(state),
        )

    # 加载模型
    model = load_chat_model(
        model=ctx.plan_model,
        max_retries=3,
    )

    tools = [
        write_plan,
        read_plan_tool,
        finish_sub_plan,
        transfor_task_to_subagent,
        ls,
        query_note,
    ]
    bind_model = model.bind_tools(tools, parallel_tool_calls=False)

    info = state["pet_information"]
    messages = state["messages"]

    response = await bind_model.ainvoke(
        [
            SystemMessage(
                content=ctx.research_planner_prompt.format(
                    pet_information=info,
                )
            ),
            *messages,
        ]
    )

    # AI 输出事件:抽出 reasoning 单独标识(qwen3 thinking / DeepSeek-R1 reasoning_content)
    content, reasoning = extract_reasoning(response)
    await aemit_ai_message(
        node="research_planner",
        content=content,
        reasoning=reasoning,
        message_id=getattr(response, "id", None),
    )

    if has_tool_calling(response):
        name, args = parse_tool_calling(
            response, first_tool_call_only=True
        )

        # ── finish_sub_plan 后仍需检查是否所有任务完成 ──
        plan = state.get("plan", [])
        all_done = len(plan) > 0 and all(getattr(item, "status", None) == "done" for item in plan)

        if all_done:
            # 所有研究任务完成，生成协调指南
            await aemit_progress(
                ProgressEventType.RESEARCH_FINALIZING,
                "研究完成，正在生成四周差异化协调指南...",
                node="research_planner",
                progress=25,
            )
            coordination_guide = await _generate_coordination_guide(state, ctx)
            return Command(
                goto="dispatch_weeks",
                update={
                    "messages": [response],
                    "coordination_guide": coordination_guide,
                },
            )

        # ── transfor_task_to_subagent: 委派研究任务 ──
        if name == "transfor_task_to_subagent":
            task_name = (
                cast(dict, args).get("content", "") if isinstance(args, dict) else ""
            )
            progress = _estimate_research_progress(state)
            await aemit_progress(
                ProgressEventType.RESEARCH_TASK_DELEGATING,
                f"正在委派研究任务: {task_name}",
                node="research_planner",
                task_name=task_name,
                progress=progress,
            )
            # 同时发 subagent_spawn 给 SubagentDispatchWidget 渲染
            await aemit_subagent_spawn(
                node="research_planner",
                target="research_subagent",
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

        # ── 其他工具（write_plan, finish_sub_plan, ls, query_note）──
        if name == "write_plan":
            await aemit_progress(
                ProgressEventType.PLAN_CREATED,
                "研究任务计划已创建",
                node="research_planner",
                progress=5,
            )
            # write_plan 的 args 含完整 plan 列表,前端立刻能看到 todo
            plan_arg = cast(dict, args).get("plan") if isinstance(args, dict) else None
            if plan_arg:
                await aemit_plan_snapshot(
                    node="research_planner",
                    plan=[{"content": p, "status": "pending"} for p in plan_arg],
                    action="created",
                    progress=5,
                )
        elif name == "finish_sub_plan":
            await aemit_progress(
                ProgressEventType.PLAN_UPDATED,
                "研究任务进度已更新",
                node="research_planner",
                progress=_estimate_research_progress(state),
            )

        return Command(goto="research_tools", update={"messages": [response]})

    # 无工具调用 — 研究阶段自然结束，直接 dispatch
    await aemit_progress(
        ProgressEventType.RESEARCH_FINALIZING,
        "研究完成，正在生成四周差异化协调指南...",
        node="research_planner",
        progress=25,
    )
    coordination_guide = await _generate_coordination_guide(state, ctx)
    return Command(
        goto="dispatch_weeks",
        update={
            "messages": [response],
            "coordination_guide": coordination_guide,
        },
    )


async def _generate_coordination_guide(state: StateV1, ctx) -> CoordinationGuide:
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
        model=ctx.plan_model,
        max_retries=3,
    )
    guide_model = model.with_structured_output(CoordinationGuide)

    guide = await guide_model.ainvoke(
        [
            SystemMessage(
                content=ctx.coordination_guide_prompt.format(
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

    await aemit_progress(
        ProgressEventType.DISPATCHING,
        "正在分发四周饮食计划任务（并行执行）...",
        node="dispatch_weeks",
        progress=30,
    )

    sends = []
    for assignment in guide.weekly_assignments:
        # 每个 Send 之前发一个 week_dispatch 事件,前端 SubagentDispatchWidget 渲染
        # "分发到第N周 Agent" 的扇出动效。
        await aemit_subagent_spawn(
            node="dispatch_weeks",
            target="week_agent",
            task_name=assignment.theme or f"第{assignment.week_number}周饮食计划",
            week_number=assignment.week_number,
            progress=30,
        )
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

    await aemit_progress(
        ProgressEventType.GATHERING,
        "所有周计划已完成，正在进入结构化解析阶段...",
        node="collect_and_structure",
        progress=80,
    )
    logger.debug("Gathering notes: %s", list(notes.keys()))
    sends = [
        Send(
            node="structure_report",
            arg={"temp_note": note},
        )
        for _, note in notes.items() if note.type == "diet_plan_for_week"
    ]

    return Command(goto=sends)


# ────────────────────────────────────────────────────────
# Phase 3: 汇总
# ────────────────────────────────────────────────────────

async def gather(state: StateV1):
    """汇总所有 WeeklyDietPlan 生成最终报告"""
    weekly_plans = state.get("weekly_diet_plans", [])

    # 生成 AI 建议摘要（在 emit_progress 之前计算，以便加入 detail）
    messages = state.get("messages", [])
    ai_suggestions = messages[-1].content if messages else "饮食计划已生成，请查看详细报告。"

    # 预序列化 Pydantic 模型，避免 json.dumps 遇到模型实例抛 TypeError 导致流中断
    serialized_plans = [
        p.model_dump() if hasattr(p, "model_dump") else p
        for p in weekly_plans
    ]

    await aemit_progress(
        ProgressEventType.COMPLETED,
        f"月度饮食计划生成完成！共 {len(weekly_plans)} 周计划",
        node="gather",
        detail={
            "plans": serialized_plans,
            "ai_suggestions": ai_suggestions,
        },
        progress=100,
    )

    # pet_information 可能在图执行过程中被序列化为 JSON 字符串，需要反序列化
    pet_info = state["pet_information"]
    if isinstance(pet_info, str):
        import json
        pet_info = PetInformation(**json.loads(pet_info))


    return {
        "report": PetDietPlan(
            pet_information=pet_info,
            pet_diet_plan=MonthlyDietPlan(monthly_diet_plan=weekly_plans),
            ai_suggestions=ai_suggestions,
        )
    }


# ── 工具执行节点 ──
research_tools = ToolNode([write_plan, read_plan_tool, finish_sub_plan, ls, query_note])
