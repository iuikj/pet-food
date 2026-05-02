"""
V2 Agent 节点定义

Phase 1: plan_agent (create_deep_agent) — 研究阶段
Phase 1→2: generate_coordination_guide (create_agent + response_format) — 协调指南
Phase 2: dispatch_weeks → week_agent (create_deep_agent, response_format=WeekLightPlan) x4 — 并行周计划
Phase 3: gather_and_structure — 纯 Python 组装 + 可选 1 次 LLM 生成 ai_suggestions
"""
import asyncio
import logging
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend, CompositeBackend, StateBackend, StoreBackend
from langchain.agents import create_agent
from langchain.agents.middleware import after_agent
from langchain.agents.structured_output import ToolStrategy
from langchain.messages import HumanMessage
from langchain_dev_utils.chat_models import load_chat_model
from langgraph.runtime import Runtime, get_runtime
from langgraph.types import Command, Send

from typing import Any, Literal

from src.agent.common.stream_events import (
    ProgressEventType,
    emit_progress,
    emit_subagent_spawn,
)
from src.agent.common.utils.struct import (
    MonthlyDietPlan,
    PetDietPlan,
    WeeklyDietPlan,
)
from src.agent.v1.models import CoordinationGuide
from src.agent.v2.middlewares.ban_subagent_middleware import ban_sub_agent
from src.agent.v2.middlewares.dynamic_prompt_middleware import (
    plan_agent_prompt,
    coordination_agent_prompt,
    week_agent_prompt,
)
from src.agent.v2.middlewares.progress_middleware import (
    plan_progress_middleware,
    week_progress_middleware,
)
from src.agent.v2.middlewares.trigger_middleware import (
    trigger_plan_agent,
    trigger_week_agent,
)
from src.agent.v2.middlewares.response_format_middleware import collect_week_light_plan
from src.agent.v2.models import WeekLightPlan
from src.agent.v2.state import State, WeekAgentState
from src.agent.v2.sub_agents.web_search_agent import websearch_sub_agent
from src.agent.v2.sub_agents.nutrition_calc_agent import nutrition_calc_sub_agent
from src.agent.v2.sub_agents.ingredient_query_agent import ingredient_query_sub_agent
from src.agent.v2.tools import WEEK_AGENT_TOOLS
from src.agent.v2.utils.assemble import (
    assemble_weekly_plan,
    collect_ingredient_names,
    fetch_ingredients_by_names,
)
from src.agent.v2.utils.context import ContextV2
from langchain.agents import create_agent
from deepagents.middleware.filesystem import FilesystemMiddleware
from deepagents.middleware.skills import SkillsMiddleware

logger = logging.getLogger(__name__)


# v2 在模块顶层即调用 load_chat_model 构造 plan_agent_with_sub / week_agent，
# 因此必须在第一次 load_chat_model 之前完成厂商注册。
# 通过独立模块的幂等函数执行一次即可。
from src.models_registry import ensure_dotenv_loaded, ensure_providers_registered

ensure_dotenv_loaded()
ensure_providers_registered()


# ──────────────────────────── 路径常量（可移植） ────────────────────────────

_V2_DIR = Path(__file__).resolve().parent
_SKILLS_DIR = _V2_DIR / "files" / "skills"
_NOTEBOOKS_DIR = _V2_DIR / "files" / "notebooks"

from langgraph.store.postgres import AsyncPostgresStore
from deepagents.backends.store import StoreBackend

def _make_backend() -> CompositeBackend:
    """构建 CompositeBackend：skills / memory_notes 走文件系统，temp_notes 走 State。"""
    return CompositeBackend(
        default=StateBackend(),
        routes={
            "/skills/": FilesystemBackend(
                root_dir=str(_SKILLS_DIR),
                virtual_mode=True,
            ),
            "/memory_notes/": FilesystemBackend(
                root_dir=str(_NOTEBOOKS_DIR),
                virtual_mode=True,
            ),
            # "/memory_notes_store/":StoreBackend(
            #     namespace=lambda ctx: (ctx.runtime.context.user_id,),
            # ),
            "/temp_notes/": StateBackend(),
        },
    )


# ──────────────────────────── Phase 1: plan_agent ────────────────────────────

plan_agent_with_sub = create_deep_agent(
    name="plan_agent",
    model=load_chat_model(ContextV2.plan_model),
    subagents=[
        websearch_sub_agent,
        nutrition_calc_sub_agent,
        ingredient_query_sub_agent,
    ],
    backend=_make_backend(),
    skills=["/skills/"],
    middleware=[plan_agent_prompt, trigger_plan_agent, plan_progress_middleware],
    context_schema=ContextV2,
    # store=AsyncPostgresStore()
)


# ──────────────────────────── Phase 1→2: 协调指南生成 ────────────────────────────

async def generate_coordination_guide(state: State):
    emit_progress(
        ProgressEventType.RESEARCH_FINALIZING,
        "根据调研笔记生成四周差异化协调指南",
        node="generate_coordination_guide",
        progress=30,
    )
    coordination_agent = create_agent(
        model=load_chat_model(ContextV2.plan_model),
        middleware=[coordination_agent_prompt],
        response_format=CoordinationGuide,
        context_schema=ContextV2,
        state_schema=State,
    )
    # 用精简的 seed message 触发，避免 plan_agent 阶段累积的大量工具消息污染
    response = await coordination_agent.ainvoke(
        input={
            **state,
            "messages": [
                HumanMessage(content="请根据 system prompt 中提供的调研笔记，生成 CoordinationGuide。")
            ],
        }
    )
    return {
        "coordination_guide": response["structured_response"],
    }


# ──────────────────────────── Phase 2: dispatch_weeks ────────────────────────────

async def dispatch_weeks(state: State) -> Command[Literal["week_agent"]]:
    guide: CoordinationGuide = state["coordination_guide"]
    ctx: ContextV2 = get_runtime().context

    emit_progress(
        ProgressEventType.DISPATCHING,
        f"向 {len(guide.weekly_assignments)} 个并行 week_agent 分发任务",
        node="dispatch_weeks",
        progress=40,
    )

    sends: list[Send] = []
    for assignment in guide.weekly_assignments:
        # v2 GenUI: 触发前端 WeekParallelBlock inline 嵌入 (target=week_agent → view_type=week_dispatch)
        emit_subagent_spawn(
            node="dispatch_weeks",
            target="week_agent",
            task_name=getattr(assignment, "theme", None) or f"第{assignment.week_number}周",
            week_number=assignment.week_number,
            progress=40,
        )
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
                    "files": state.get("files") or {},
                },
            )
        )
    return Command(goto=sends)


# ──────────────────────────── Phase 2: week_agent ────────────────────────────


# week_agent = create_deep_agent(
#     name="week_agent",
#     model=load_chat_model(
#         ContextV2.week_model,
#         extra_body={
#             "thinking": {"type": "disabled"}
#         }),
#     tools=WEEK_AGENT_TOOLS,
#     backend=_make_backend(),
#     skills=["/skills/"],
#     middleware=[
#         week_agent_prompt,
#         trigger_week_agent,
#         week_progress_middleware,
#         collect_week_light_plan,
#         ban_sub_agent
#     ],
#     subagents=[],
#     context_schema=ContextV2,
#     response_format=ToolStrategy(WeekLightPlan),
# )
week_agent = create_agent(
    name="week_agent",
    model=load_chat_model(
        ContextV2.week_model,
        extra_body={
            "thinking": {"type": "disabled"}
        }),
    tools=WEEK_AGENT_TOOLS,
    middleware=[
        FilesystemMiddleware(backend=_make_backend()),
        SkillsMiddleware(backend=_make_backend(),sources=["/skills/"]),
        week_agent_prompt,
        trigger_week_agent,
        week_progress_middleware,
        collect_week_light_plan,
        ban_sub_agent
    ],
    context_schema=ContextV2,
    response_format=ToolStrategy(WeekLightPlan),
)

# ──────────────────────────── Phase 3: 纯 Python 组装 + 可选 ai_suggestions ────────────────────────────

_AI_SUGGESTIONS_PROMPT = (
    "你是一个宠物营养师。以下是为一只宠物制定好的月度（4 周）饮食计划原则与每周餐次。"
    "请用 1-2 段话、面向宠物主人，给出整体执行建议，强调饮水、过渡、禁忌与监测。不要重复罗列食材清单。\n\n"
)


async def _generate_ai_suggestions(
    weekly_plans: list[WeeklyDietPlan], model_name: str
) -> str:
    """可选的 1 次 LLM 调用，生成 PetDietPlan.ai_suggestions。失败时返回兜底文案。"""
    try:
        summary_lines: list[str] = []
        for w in weekly_plans:
            meal_names = []
            for m in w.weekly_diet_plan.daily_diet_plans:
                names = ",".join(f.name for f in m.food_items)
                meal_names.append(f"第{m.oder}餐({m.time}){names}")
            summary_lines.append(
                f"第{w.oder}周 原则: {w.diet_adjustment_principle} | 菜单: {'; '.join(meal_names)}"
            )
        prompt = _AI_SUGGESTIONS_PROMPT + "\n".join(summary_lines)
        model = load_chat_model(model_name, max_retries=2)
        resp = await model.ainvoke(prompt)
        content = getattr(resp, "content", "")
        if isinstance(content, list):
            content = "".join(str(x) for x in content)
        return (content or "").strip() or "请保证每日饮水充足，并循序渐进切换饮食。"
    except Exception as exc:
        logger.warning("ai_suggestions 生成失败，使用兜底文案: %s", exc)
        return "请保证每日饮水充足，循序渐进切换饮食，留意过敏与消化反应。"


async def gather_and_structure(state: State):
    """从 week_light_plans 批量拉 Ingredient 行，纯 Python 组装 PetDietPlan。"""
    ctx: ContextV2 = get_runtime().context
    light_plans: list[WeekLightPlan] = list(state.get("week_light_plans") or [])

    emit_progress(
        ProgressEventType.GATHERING,
        f"汇总 {len(light_plans)} 个轻量周计划，开始批量查询食材数据",
        node="gather_and_structure",
        progress=80,
    )

    if not light_plans:
        logger.warning("gather_and_structure: 未收到任何 week_light_plans")
        return {
            "report": PetDietPlan(
                pet_information=ctx.pet_information,
                pet_diet_plan=MonthlyDietPlan(monthly_diet_plan=[]),
                ai_suggestions="未能生成周计划，请重试。",
            ),
            "weekly_diet_plans": [],
        }

    # 1) 一次性批量查询所有用到的食材
    names = collect_ingredient_names(light_plans)
    rows_by_name = await fetch_ingredients_by_names(names)
    logger.info(
        "gather_and_structure: 食材批量查询完成，命中 %s/%s",
        len(rows_by_name), len(names),
    )

    emit_progress(
        ProgressEventType.STRUCTURING,
        f"组装 4 周 WeeklyDietPlan（命中食材 {len(rows_by_name)}/{len(names)}）",
        node="gather_and_structure",
        progress=88,
    )

    # 2) 并行组装每一周（纯 CPU，to_thread 不必要；直接在事件循环中同步调用即可）
    weekly_plans: list[WeeklyDietPlan] = [
        assemble_weekly_plan(light=lp, rows_by_name=rows_by_name)
        for lp in sorted(light_plans, key=lambda p: p.week_number)
    ]

    # 3) 可选 1 次 LLM 生成 ai_suggestions
    ai_suggestions = await _generate_ai_suggestions(weekly_plans, ctx.summary_model)

    emit_progress(
        ProgressEventType.STRUCTURED,
        "周计划结构化完成",
        node="gather_and_structure",
        progress=95,
    )

    report = PetDietPlan(
        pet_information=ctx.pet_information,
        pet_diet_plan=MonthlyDietPlan(monthly_diet_plan=weekly_plans),
        ai_suggestions=ai_suggestions,
    )

    serialized_plans = [
        plan.model_dump() if hasattr(plan, "model_dump") else plan
        for plan in weekly_plans
    ]

    emit_progress(
        ProgressEventType.COMPLETED,
        "月度饮食计划全部生成完成",
        node="gather_and_structure",
        detail={
            "plans": serialized_plans,
            "ai_suggestions": ai_suggestions,
        },
        progress=100,
    )

    return {
        "weekly_diet_plans": weekly_plans,
        "report": report,
    }
