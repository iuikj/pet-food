from typing import Annotated

from langchain_core.tools import tool


@tool
async def transfor_task_to_subagent(
    content: Annotated[
        str,
        "当前待执行的todo任务内容，必须与todo列表中待办事项的content字段完全一致，但是当子智能体执行的任务有误时，重试的时候可以适当改写",
    ],
):
    """用于执行todo任务的工具。

    参数：
    content: str, 待执行的todo任务内容，必须与todo列表中待办事项的content字段完全一致，但是当子智能体执行的任务有误时，重试的时候可以适当改写

    例如当前的todo list是
    [
        {"content":"待办1"，"status":"done"}
        {"content":"待办2"，"status":"in_progress"}
        {"content":"待办3"，"status":"pending"}

    ]
    则可以知道当前执行的是待办2，则输入的content应该为"待办2"。
    """

    return "transfor success!"


@tool
def get_weather(city: str):
    """查询天气。

    参数：
    city:城市名称

    返回：
    str, 天气信息

    """
    return f"{city}的天气是晴天，温度是25度。"


async def tavily_search(query: Annotated[str, "要搜索的内容"]):
    """互联网搜索工具，用于获取最新的网络信息和资料。注意：为控制上下文长度和降低调用成本，每个任务执行过程中仅可调用一次此工具。"""
    # 延迟导入：只在首次实际搜索时引入 langchain_tavily，避免 agent 模块
    # import 期就拉入该重量级依赖。
    from langchain_tavily.tavily_search import TavilySearch

    search = TavilySearch(
        max_results=3,
    )
    result = await search.ainvoke({"query": query})
    return result
