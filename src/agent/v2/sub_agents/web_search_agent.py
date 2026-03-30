from deepagents import SubAgent, CompiledSubAgent

from src.agent.common.sub_agent.graph import build_sub_agent
from src.agent.common.tools import tavily_search
from src.agent.v2.tools import get_state

websearch_sub_agent=SubAgent(
    name="websearch_sub_agent",
    tools=[tavily_search,get_state],
    system_prompt="你是一个网络搜索子agent",
    description="""
    这是一个网络搜索子agent，用于搜索网络信息。
    """,
)

websearch_sub_agent_complied=CompiledSubAgent(
    description="你是一个信息搜索子agent,当有网络搜索的时候作为补充,同时进行",
    name="websearch_sub_agent_complied",
    runnable=build_sub_agent()
)