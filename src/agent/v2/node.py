from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain.agents import create_agent
from langchain_dev_utils.agents.middleware import PlanMiddleware
from langchain_dev_utils.chat_models import load_chat_model

from src.agent.v1.tools import (
    query_note,
    transfor_task_to_subagent,
)
from src.agent.v2.middlewares.inject_state_middleware import InjectStateMiddleware
from src.agent.v2.state import StateV2
from src.agent.v2.sub_agents.web_search_agent import websearch_sub_agent
from src.agent.v2.tools import get_state
from src.agent.v2.utils.context import ContextV2
from src.api.models.response import PetType
from src.utils.strtuct import PetInformation

plan_agent=create_agent(
    model=load_chat_model(ContextV2().plan_model),
    tools=[
        get_state,
        query_note,
    ],
    middleware=[
        PlanMiddleware(
        )
    ]
)


plan_agent_with_sub=create_deep_agent(
    model=load_chat_model(ContextV2.plan_model),# 使用默认模型
    tools=[
        get_state,
        query_note,
    ],
    subagents=[
        websearch_sub_agent,
        # websearch_sub_agent_complied
    ],
    backend=FilesystemBackend(
        root_dir=r"E:\Graduate\pet_food_backend\pet-food\src\agent\v2\files",
        virtual_mode=True
    ),
    middleware=[
        InjectStateMiddleware()
    ],
    context_schema=ContextV2,

)




async def node(state:StateV2):
    return state


async def node_before(state:StateV2):
    state["pet_information"]=PetInformation(
        pet_age=3,
        pet_breed="breed",
        pet_type=PetType.CAT,
        pet_weight=10,
        health_status="good"
    )
    return state
