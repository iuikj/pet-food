"""
V2 Agent 节点定义

Phase 1: plan_agent (create_deep_agent) — 研究阶段
Phase 1→2: generate_coordination_guide (create_agent + response_format) — 协调指南
Phase 2: dispatch_weeks → week_agent (create_deep_agent) x4 — 并行周计划
Phase 3: gather_and_structure — 结构化汇总
"""
import asyncio

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend, CompositeBackend, StateBackend
from deepagents.backends.protocol import FileData
from langchain.agents import create_agent

from langchain_core.messages import HumanMessage
from langchain_dev_utils.chat_models import load_chat_model
from langgraph.runtime import get_runtime
from langgraph.types import Command, Send

from typing import Literal,Dict

from src.agent.common.stream_events import ProgressEventType, emit_progress
from src.agent.common.utils.struct import (
    PetDietPlan,
    MonthlyDietPlan,
    WeeklyDietPlan,
)
from src.agent.v1.models import CoordinationGuide
from src.agent.v2.middlewares.dynamic_prompt_middleware import (
    plan_agent_prompt,
    coordination_agent_prompt,
    week_agent_prompt,
    structure_report_prompt,
)
from src.agent.v2.middlewares.note_middleware import NoteMiddleware, Note
from src.agent.v2.middlewares.tirgger_middleware import trigger_plan_agent,trigger_week_agent

from src.agent.v2.state import State, WeekAgentState
from src.agent.v2.sub_agents.web_search_agent import websearch_sub_agent
from src.agent.v2.sub_agents.nutrition_calc_agent import nutrition_calc_sub_agent
from src.agent.v2.sub_agents.ingredient_query_agent import ingredient_query_sub_agent
from src.agent.v2.tools import WEEK_AGENT_TOOLS
from src.agent.v2.utils.context import ContextV2


# ── Phase 1: plan_agent ──

plan_agent_with_sub = create_deep_agent(
    name="plan_agent",
    model=load_chat_model(ContextV2.plan_model),
    subagents=[
        websearch_sub_agent,
        nutrition_calc_sub_agent,
        ingredient_query_sub_agent,
    ],
    backend=CompositeBackend(
        default=StateBackend(),
        routes={
            "/skills/": FilesystemBackend(
                root_dir=r"E:\Graduate\pet_food_backend\pet-food\src\agent\v2\files\skills",
                virtual_mode=True,
            ),
            "/memory_notes/": FilesystemBackend(
                root_dir=r"E:\Graduate\pet_food_backend\pet-food\src\agent\v2\files\notebooks",
                virtual_mode=True,
            ),
            "/temp_notes/":StateBackend()

        },
    ),
    skills=["/skills/"],
    middleware=[plan_agent_prompt,trigger_plan_agent],
    context_schema=ContextV2,
)


# ── Phase 1→2: 协调指南生成 ──




async def generate_coordination_guide(state: State):
    coordination_agent = create_agent(
        model=load_chat_model(ContextV2.plan_model),
        middleware=[coordination_agent_prompt],
        response_format=CoordinationGuide,
        context_schema=ContextV2,
        state_schema=State,
    )
    response = await coordination_agent.ainvoke(input=state)
    return {
        "coordination_guide": response["structured_response"],
    }


# ── Phase 2: dispatch_weeks ──

async def dispatch_weeks(state: State) -> Command[Literal["week_agent"]]:
    guide: CoordinationGuide = state["coordination_guide"]
    ctx: ContextV2 = get_runtime().context
    # 提取所有临时调研笔记

    sends = []
    for assignment in guide.weekly_assignments:

        sends.append(
            Send(
                node="week_agent",
                arg={
                    "pet_information": ctx.pet_information,
                    "week_assignment": assignment,
                    "shared_notes": {},
                    "shared_constraints": guide.shared_constraints,
                    "ingredient_rotation_strategy": guide.ingredient_rotation_strategy,
                    "age_adaptation_note": guide.age_adaptation_note,
                    "files": state['files']
                },
            )
        )

    return Command(goto=sends)


# ── Phase 2: week_agent ──

week_agent = create_deep_agent(
    name="week_agent",
    model=load_chat_model(ContextV2.week_model),
    tools=WEEK_AGENT_TOOLS,
    backend=CompositeBackend(
        default=StateBackend(),
        routes={
            "/skills/": FilesystemBackend(
                root_dir=r"E:\Graduate\pet_food_backend\pet-food\src\agent\v2\files\skills",
                virtual_mode=True,
            ),
            "/memory_notes/": FilesystemBackend(
                root_dir=r"E:\Graduate\pet_food_backend\pet-food\src\agent\v2\files\notebooks",
                virtual_mode=True,
            ),
            "/temp_notes/": StateBackend()

        },
    ),
    skills=["/skills/"],
    middleware=[week_agent_prompt,trigger_week_agent],
    context_schema=ContextV2,
    response_format=WeeklyDietPlan,
)


# ── Phase 3: gather_and_structure ──

async def gather_and_structure(state: State):
    """从 note 中提取周计划 Markdown，逐周解析为 WeeklyDietPlan，汇总为 PetDietPlan。"""
    ctx: ContextV2 = get_runtime().context
    notes: dict[str, Note] = state.get("note", {})

    # 1. 筛选周计划笔记 (type="diet_plan_for_week")
    week_notes = {
        k: v for k, v in notes.items()
        if hasattr(v, 'type') and v.type == "diet_plan_for_week"
    }

    emit_progress(
        ProgressEventType.STRUCTURING,
        f"正在结构化 {len(week_notes)} 个周计划",
        node="gather_and_structure",
        progress=80,
    )

    if not week_notes:
        # 如果没有周计划笔记，返回空报告
        return {
            "report": PetDietPlan(
                pet_information=ctx.pet_information,
                pet_diet_plan=MonthlyDietPlan(monthly_diet_plan=[]),
                ai_suggestions="未能生成周计划，请重新尝试。",
            ),
        }

    # 2. 逐周解析为 WeeklyDietPlan（并行执行）
    async def _structure_one(note_name: str, note: Note) -> WeeklyDietPlan:
        structure_agent = create_agent(
            model=load_chat_model(ctx.report_model),
            response_format=WeeklyDietPlan,
            middleware=[structure_report_prompt],
        )
        response = await structure_agent.ainvoke(
            input={"messages": [HumanMessage(content=note.content)]}
        )
        return response["structured_response"]

    tasks = [
        _structure_one(name, note)
        for name, note in sorted(week_notes.items())
    ]
    weekly_plans = await asyncio.gather(*tasks)

    emit_progress(
        ProgressEventType.STRUCTURED,
        f"已完成 {len(weekly_plans)} 个周计划的结构化",
        node="gather_and_structure",
        progress=95,
    )

    # 3. 汇总为 PetDietPlan
    report = PetDietPlan(
        pet_information=ctx.pet_information,
        pet_diet_plan=MonthlyDietPlan(
            monthly_diet_plan=list(weekly_plans),
        ),
        ai_suggestions="基于宠物个体信息和专业调研生成的个性化月度营养饮食计划。",
    )

    emit_progress(
        ProgressEventType.COMPLETED,
        "月度饮食计划全部生成完成",
        node="gather_and_structure",
        progress=100,
    )

    return {
        "weekly_diet_plans": list(weekly_plans),
        "report": report,
    }
