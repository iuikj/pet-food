from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from src.agent.common.state import CommonState


class WriteState(CommonState):
    temp_write_note_messages: Annotated[list[AnyMessage], add_messages]
