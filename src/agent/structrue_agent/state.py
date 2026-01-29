import operator
from typing import Annotated

from src.agent.entity.note import Note
from src.agent.state import State
from src.agent.utils.struct import PetDietPlan, WeeklyDietPlan


class StructState(State):
    temp_note: Annotated[Note, "临时笔记"]
    failed_reason: Annotated[str, "失败原因"]