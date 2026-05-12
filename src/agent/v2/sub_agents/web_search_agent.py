from deepagents import SubAgent, CompiledSubAgent
from src.agent.common.tools import tavily_search
from src.agent.v2.middlewares.dynamic_prompt_middleware import sub_agent_prompt
from src.agent.v2.middlewares.progress_middleware import sub_agent_progress_middleware
# from src.agent.v2.node import _make_backend


websearch_sub_agent=SubAgent(
    name="general-purpose",
    tools=[tavily_search],
    system_prompt="你是一个网络搜索子agent,是一个通用功能的agent",
    description="""
    这是一个网络搜索子agent，用于搜索网络信息。
    """,
    middleware=[
        sub_agent_progress_middleware,
        sub_agent_prompt
    ]
)


# CompiledSubAgent(
#     name="general-purpose",
#     description="""
#     这是一个网络搜索子agent，用于搜索网络信息。
#     """,
#     runnable=create_agent(
#         tools=[tavily_search]
#     ),
#     middleware=[
#         sub_agent_prompt
#     ]
# )
