from typing import Annotated

from src.agent.common.entity.note import Note
from src.agent.common.state import CommonState


class StructState(CommonState):
    temp_note: Annotated[Note, "临时笔记"]
    failed_reason: Annotated[str, "失败原因"]
