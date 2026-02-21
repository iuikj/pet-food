"""
V1 周 Agent 状态定义

每个 week_agent 实例拥有完全独立的状态空间，通过 Send 接收只读输入。
"""
from typing import Annotated

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from src.agent.v0.entity.note import Note, note_reducer
from src.agent.v0.utils.struct import WeeklyDietPlan
from src.agent.v1.models import WeekAssignment
from src.utils.strtuct import PetInformation


class WeekAgentState(TypedDict, total=False):
    # ── 只读输入（由 dispatch_weeks 通过 Send 传入）──
    pet_information: PetInformation
    week_assignment: WeekAssignment
    shared_notes: Annotated[dict[str, Note], "研究阶段的共享笔记（只读）"]
    shared_constraints: list[str]
    ingredient_rotation_strategy: str
    age_adaptation_note: str

    # ── 独立消息空间 ──
    week_messages: Annotated[list[AnyMessage], add_messages]
    week_task_messages: Annotated[list[AnyMessage], add_messages]
    week_write_messages: Annotated[list[AnyMessage], add_messages]

    # ── 独立笔记空间 ──
    week_note: Annotated[dict[str, Note], note_reducer]

    # ── 输出（回写到主图）──
    # note 用 note_reducer 合并到主图
    note: Annotated[dict[str, Note], note_reducer]
    weekly_diet_plans: list[WeeklyDietPlan]
