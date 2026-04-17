import operator
from typing import Annotated, Any

from deepagents.middleware.filesystem import _file_data_reducer
from deepagents.backends.protocol import FileData
from langchain.agents import AgentState
from typing_extensions import NotRequired

from src.agent.common.entity.note import NoteStateMixin
from src.agent.common.utils.struct import PetDietPlan, WeeklyDietPlan
from src.agent.v1.models import CoordinationGuide, WeekAssignment
from src.agent.v2.middlewares.note_middleware import Note, note_reducer
from src.agent.v2.models import WeekLightPlan
from src.utils.strtuct import PetInformation


def _structured_response_reducer(left: Any, right: Any) -> Any:
    """允许 4 个并行 week_agent 同一 super-step 写入 `structured_response`，
    避免 LangGraph `InvalidUpdateError: Can receive only one value per step`。

    实际聚合由 `week_light_plans` 承担，此字段仅为兼容子图输出冒泡。
    语义：last non-None wins — 任意非 None 值会覆盖先前的，None 不会覆盖非 None。
    """
    return right if right is not None else left


class StateV2Input(AgentState):
    pet_information: Annotated[PetInformation, "宠物信息"]


class StateV2Output(AgentState):
    report: Annotated[PetDietPlan, "报告"]


class State(AgentState, total=False):
    # 研究阶段完成后生成的协调指南
    coordination_guide: CoordinationGuide
    # 兼容并行 week_agent 子图向父图冒泡的 structured_response（见 reducer 注释）
    structured_response: Annotated[Any, _structured_response_reducer]
    # 各并行 week_agent 产出的轻量周计划（Phase 3 的输入）
    week_light_plans: Annotated[list[WeekLightPlan], operator.add]
    # 结构化周计划（保留旧字段兼容 v1 下游消费者；Phase 3 仍会写入）
    weekly_diet_plans: Annotated[list[WeeklyDietPlan], operator.add]
    # 最终报告
    report: Annotated[PetDietPlan, "报告"]
    files: Annotated[NotRequired[dict[str, FileData]], _file_data_reducer]
    note: NotRequired[Annotated[dict[str, Note], note_reducer]]


class WeekAgentState(AgentState, total=False):
    """周 Agent 内部完整状态"""
    # ── 只读输入（由 dispatch_weeks 通过 Send 传入）──
    pet_information: PetInformation
    week_assignment: WeekAssignment
    shared_notes: dict[str, Note]
    files: Annotated[NotRequired[dict[str, FileData]], _file_data_reducer]
    shared_constraints: list[str]
    ingredient_rotation_strategy: str
    age_adaptation_note: str
    week_light_plans: Annotated[list[WeekLightPlan], operator.add]