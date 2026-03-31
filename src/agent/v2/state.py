import operator
from typing import Annotated

from langchain.agents import AgentState
from typing_extensions import NotRequired

from src.agent.common.entity.note import NoteStateMixin
from src.agent.common.utils.struct import PetDietPlan, WeeklyDietPlan
from src.agent.v1.models import CoordinationGuide
from src.agent.v2.middlewares.note_middleware import Note, note_reducer
from src.utils.strtuct import PetInformation


class StateV2Input(AgentState):
    pet_information: Annotated[PetInformation, "宠物信息"]


class StateV2Output(AgentState):
    report: Annotated[PetDietPlan, "报告"]


class State(AgentState, total=False):
    # 研究阶段完成后生成的协调指南
    coordination_guide: CoordinationGuide
    # 结构化周计划（由 structure_report 写入，operator.add 支持并行合并）
    weekly_diet_plans: Annotated[list[WeeklyDietPlan], operator.add]
    # 最终报告
    report: Annotated[PetDietPlan, "报告"]
    note: NotRequired[Annotated[dict[str, Note], note_reducer]]