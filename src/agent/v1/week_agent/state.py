"""
V1 周 Agent 状态定义

每个 week_agent 实例拥有完全独立的状态空间，通过 Send 接收只读输入。
通过 WeekAgentOutput 严格控制回写到父图的 key，避免并行 Send 的 LastValue 冲突。

关键设计：`note` 既是内部 channel 也是输出 channel，
week_write_note 工具直接写入 `note`，无需中间 `week_note` 转发。
"""
from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from src.agent.v0.entity.note import Note, note_reducer, NoteStateMixin
from src.agent.v1.models import WeekAssignment
from src.utils.strtuct import PetInformation


class WeekAgentInput(TypedDict, total=False):
    """周 Agent 输入 schema — 由 dispatch_weeks Send 传入"""
    pet_information: PetInformation
    week_assignment: WeekAssignment
    shared_notes: dict[str, Note]
    shared_constraints: list[str]
    ingredient_rotation_strategy: str
    age_adaptation_note: str


class WeekAgentOutput(TypedDict, total=False):
    """周 Agent 输出 schema — 仅包含需要回写到父图的 key

    关键设计：不包含 pet_information 等只读输入字段，
    避免 4 个并行实例同时写入 LastValue channel 引发 InvalidUpdateError。
    """
    note: Annotated[dict[str, Note], note_reducer]


class WeekAgentState(NoteStateMixin, total=False):
    """周 Agent 内部完整状态"""
    # ── 只读输入（由 dispatch_weeks 通过 Send 传入）──
    pet_information: PetInformation
    week_assignment: WeekAssignment
    shared_notes: dict[str, Note]
    shared_constraints: list[str]
    ingredient_rotation_strategy: str
    age_adaptation_note: str

    # ── 独立消息空间 ──
    week_messages: Annotated[list[AnyMessage], add_messages]
    week_task_messages: Annotated[list[AnyMessage], add_messages]
    week_write_messages: Annotated[list[AnyMessage], add_messages]
