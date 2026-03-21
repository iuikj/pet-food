"""
common 共享状态定义

提供 V0 和 V1 共用的基础状态类。
"""
import operator
from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph.message import MessagesState, add_messages

from src.agent.common.entity.plan import PlanStateMixin
from src.agent.common.entity.note import NoteStateMixin
from src.agent.common.utils.struct import PetDietPlan, WeeklyDietPlan
from src.utils.strtuct import PetInformation


class CommonStateInput(MessagesState):
    pet_information: Annotated[PetInformation, "宠物信息"]


class CommonState(MessagesState, PlanStateMixin, NoteStateMixin, total=False):
    pet_information: Annotated[PetInformation, "宠物信息"]
    task_messages: Annotated[list[AnyMessage], add_messages]
    report: Annotated[PetDietPlan, "报告"]
    weekly_diet_plans: Annotated[list[WeeklyDietPlan], operator.add]
