from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend, CompositeBackend
from deepagents.middleware.skills import SkillsMiddleware
from langchain.agents import create_agent

from langchain_dev_utils.chat_models import load_chat_model
from langgraph.runtime import get_runtime
from langgraph.types import Command, Send

from typing import Literal
from src.agent.v1.models import CoordinationGuide
from src.agent.v2.middlewares.dynamic_prompt_middleware import (
    plan_agent_prompt,
    coordination_agent_prompt,
    week_agent_prompt,
)
from src.agent.v2.middlewares.note_middleware import NoteMiddleware

from src.agent.v1.tools import query_note
from src.agent.v2.state import State
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
        default=FilesystemBackend(root_dir=r"E:\Graduate\pet_food_backend\pet-food\src\agent\v2", virtual_mode=True),
        # 默认工作目录
        routes={
            "/skills/": FilesystemBackend(root_dir=r"E:\Graduate\pet_food_backend\pet-food\src\agent\v2\skills",
                                          virtual_mode=True),  # 技能目录
            "/notes/": FilesystemBackend(root_dir=r"E:\Graduate\pet_food_backend\pet-food\src\agent\v2\files",
                                         virtual_mode=True),  # 笔记目录
        }
    ),
    skills=[
        "/skills/",
    ],
    middleware=[
        NoteMiddleware(), plan_agent_prompt,
    ],
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

    sends = []
    for assignment in guide.weekly_assignments:
        sends.append(
            Send(
                node="week_agent",
                arg={
                    "pet_information": ctx.pet_information,
                    "week_assignment": assignment,
                    "shared_notes": [],
                    "shared_constraints": guide.shared_constraints,
                    "ingredient_rotation_strategy": guide.ingredient_rotation_strategy,
                    "age_adaptation_note": guide.age_adaptation_note,
                },
            )
        )

    return Command(goto=sends)


# ── Phase 2: week_agent（工具驱动，不再使用 skills/scripts） ──

week_agent = create_deep_agent(
    name="week_agent",
    model=load_chat_model(ContextV2.week_model),
    tools=WEEK_AGENT_TOOLS,
    backend = CompositeBackend(
        default=FilesystemBackend(root_dir=r"E:\Graduate\pet_food_backend\pet-food\src\agent\v2",virtual_mode=True),  # 默认工作目录
        routes={
            "/skills/": FilesystemBackend(root_dir=r"E:\Graduate\pet_food_backend\pet-food\src\agent\v2\skills",virtual_mode=True),  # 技能目录
            "/notes/": FilesystemBackend(root_dir=r"E:\Graduate\pet_food_backend\pet-food\src\agent\v2\files",virtual_mode=True),    # 笔记目录
        }
    ),
    skills=[
        "/skills/",
    ],
    middleware=[NoteMiddleware(), week_agent_prompt],
    context_schema=ContextV2,
)

