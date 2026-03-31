from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain.agents import create_agent

from langchain_dev_utils.chat_models import load_chat_model

from src.agent.v1.models import CoordinationGuide
from src.agent.v2.middlewares.dynamic_prompt_middleware import plan_agent_prompt,coordination_agent_prompt
from src.agent.v2.middlewares.note_middleware import NoteMiddleware
from src.agent.v2.middlewares.sub_dynamic_prompt_middleware import SubDynamicPromptMiddleware

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


