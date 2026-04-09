from deepagents import create_deep_agent, FilesystemMiddleware
from deepagents.backends import FilesystemBackend
from langchain.agents import create_agent

from langchain_dev_utils.chat_models import load_chat_model
from langgraph.runtime import get_runtime

from langgraph.types import Command, Send
from langgraph.checkpoint.memory import MemorySaver

from typing import Literal, cast
from src.agent.v1.models import CoordinationGuide
from src.agent.v2.middlewares.dynamic_prompt_middleware import plan_agent_prompt, coordination_agent_prompt

from src.agent.v2.middlewares.note_middleware import NoteMiddleware


from deepagents.backends.local_shell import LocalShellBackend
from deepagents.backends.composite import CompositeBackend

from src.agent.v1.tools import (
    query_note,
    transfor_task_to_subagent,
)

from src.agent.v2.state import State
from src.agent.v2.sub_agents.web_search_agent import websearch_sub_agent
from src.agent.v2.tools import get_state
from src.agent.v2.utils.context import ContextV2

plan_agent_with_sub = create_deep_agent(
    model=load_chat_model(ContextV2.plan_model),  # 使用默认模型
    tools=[
        get_state,
        query_note,
    ],
    subagents=[
        websearch_sub_agent,
    ],
    backend=FilesystemBackend(
        root_dir=r"E:\Graduate\pet_food_backend\pet-food\src\agent\v2\files",
        virtual_mode=True
    ),
    middleware=[
        NoteMiddleware(), plan_agent_prompt
    ],
    context_schema=ContextV2,
)


async def generate_coordination_guide(state: State):
    coordination_agent = create_agent(
        model=load_chat_model(ContextV2.plan_model),
        middleware=[coordination_agent_prompt],
        response_format=CoordinationGuide,
        context_schema=ContextV2,
        state_schema=State,
    )
    response=await coordination_agent.ainvoke(
        input=state
    )
    return {
        "coordination_guide":response["structured_response"]
    }


async def dispatch_weeks(state:State)-> Command[Literal["week_agent"]]:
    guide: CoordinationGuide = state["coordination_guide"]
    ctx :ContextV2= get_runtime().context

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

checkpoint=MemorySaver()

week_agent=create_deep_agent(
    name="week_agent",
    model=load_chat_model(ContextV2.week_model),
    # backend=FilesystemBackend(
    #     root_dir=r"E:\Graduate\pet_food_backend\pet-food\src\agent\v2",
    #     virtual_mode=True,
    # ),
    backend=LocalShellBackend(
        root_dir=r"E:\Graduate\pet_food_backend\pet-food\src\agent\v2",
        virtual_mode=True,
        inherit_env=True,
    ),
    skills=[
        "/skills/",
    ],
    # middleware=[week_agent_prompt],
    interrupt_on={
        "write_file": True,  # Default: approve, edit, reject
        "read_file": False,  # No interrupts needed
        "edit_file": True  # Default: approve, edit, reject
    },
    context_schema=ContextV2,
)

