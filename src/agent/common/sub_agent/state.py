from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from src.agent.common.state import CommonState


class SubAgentState(CommonState):
    temp_task_messages: Annotated[list[AnyMessage], add_messages]
    # 网络搜索的使用记录标签
    search_count: int
