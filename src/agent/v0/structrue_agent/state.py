from typing import Annotated

from src.agent.v0.entity.note import Note
from src.agent.v0.state import State


class StructState(State):
    temp_note: Annotated[Note, "临时笔记"]
    failed_reason: Annotated[str, "失败原因"]