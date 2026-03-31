from deepagents import SubAgent, CompiledSubAgent

from src.agent.common.sub_agent.graph import build_sub_agent
from src.agent.common.tools import tavily_search
from src.agent.v2.middlewares.note_middleware import NoteMiddleware
from src.agent.v2.middlewares.dynamic_prompt_middleware import sub_agent_prompt

websearch_sub_agent=SubAgent(
    name="general-purpose",
    tools=[tavily_search],
    system_prompt="你是一个网络搜索子agent,是一个通用功能的agent",
    description="""
    这是一个网络搜索子agent，用于搜索网络信息。
    """,
    middleware=[NoteMiddleware(),sub_agent_prompt]
)

websearch_sub_agent_complied=CompiledSubAgent(
    description="你是一个信息搜索子agent,当有网络搜索的时候作为补充,同时进行",
    name="websearch_sub_agent_complied",
    runnable=build_sub_agent()
)