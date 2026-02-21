"""
V1 架构状态定义

Phase 1 (研究) → Phase 2 (并行周计划) → Phase 3 (结构化汇总)
"""
import operator
from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph.message import MessagesState, add_messages
from langchain_dev_utils import PlanStateMixin

from src.agent.v0.entity.note import NoteStateMixin
from src.agent.v0.utils.struct import PetDietPlan, WeeklyDietPlan
from src.agent.v1.models import CoordinationGuide
from src.utils.strtuct import PetInformation


class StateV1Input(MessagesState):
    pet_information: Annotated[PetInformation, "宠物信息"]


class StateV1Output(StateV1Input):
    report: Annotated[PetDietPlan, "报告"]


class StateV1(MessagesState, PlanStateMixin, NoteStateMixin, total=False):
    pet_information: Annotated[PetInformation, "宠物信息"]
    # 研究阶段子智能体交互消息
    task_messages: Annotated[list[AnyMessage], add_messages]
    # 研究阶段完成后生成的协调指南
    coordination_guide: CoordinationGuide
    # 结构化周计划（由 structure_report 写入，operator.add 支持并行合并）
    weekly_diet_plans: Annotated[list[WeeklyDietPlan], operator.add]
    # 最终报告
    report: Annotated[PetDietPlan, "报告"]
