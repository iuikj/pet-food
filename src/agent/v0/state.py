import operator
from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph.message import MessagesState, add_messages
from langchain_dev_utils import PlanStateMixin
from src.agent.v0.entity.note import NoteStateMixin
from src.agent.v0.utils.struct import PetDietPlan, WeeklyDietPlan
from src.utils.strtuct import PetInformation


class StateInput(MessagesState):
    pet_information: Annotated[PetInformation, "宠物信息"]


class StateOutput(StateInput):
    report: Annotated[PetDietPlan, "报告"]


class State(MessagesState, PlanStateMixin, NoteStateMixin, total=False):
    pet_information: Annotated[PetInformation, "宠物信息"]
    task_messages: Annotated[list[AnyMessage], add_messages]
    report: Annotated[PetDietPlan, "报告"]
    weekly_diet_plans: Annotated[list[WeeklyDietPlan], "每周计划", operator.add]
