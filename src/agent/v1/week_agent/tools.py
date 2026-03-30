"""
V1 周 Agent 工具

每个 week_agent 实例拥有独立的搜索和笔记写入工具。
"""
from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, InjectedToolCallId, tool
from langgraph.types import Command

from src.agent.common.entity.note import Note


def create_query_shared_note_tool() -> BaseTool:
    """创建只读查询共享笔记工具（从研究阶段的 shared_notes 查询）"""
    try:
        from langchain.agents.tool_node import InjectedState  # type: ignore
    except ImportError:
        from langgraph.prebuilt.tool_node import InjectedState

    from src.agent.v1.week_agent.state import WeekAgentState

    @tool(
        name_or_callable="query_shared_note",
        description="""查询研究阶段保存的共享笔记内容。

        参数：
        file_name: str, 笔记名称

        返回：
        str, 笔记内容
        """,
    )
    def query_shared_note(
        file_name: str,
        state: Annotated[WeekAgentState, InjectedState],
    ):
        shared_notes = state.get("shared_notes") or {}
        note = shared_notes.get(file_name)
        if note is None:
            return f"笔记 '{file_name}' 不存在"
        return note.content if hasattr(note, "content") else str(note)

    return query_shared_note


def create_week_write_note_tool() -> BaseTool:
    """创建周 Agent 专用的笔记写入工具

    关键设计：直接写入 `note`（输出 channel），而非中间的 `week_note`。
    这确保了 note 一定会通过 WeekAgentOutput 回传到父图。
    """
    try:
        from langchain.agents.tool_node import InjectedState  # type: ignore
    except ImportError:
        from langgraph.prebuilt.tool_node import InjectedState

    @tool(
        name_or_callable="week_write_note",
        description="""写入本周饮食计划笔记。

        参数：
        file_name: str, 笔记名称
        content: str, 笔记内容（Markdown 格式的饮食计划）
        """,
    )
    def week_write_note(
        file_name: Annotated[str, "笔记名称"],
        content: Annotated[str, "笔记内容"],
        tool_call_id: Annotated[str, InjectedToolCallId],
        # state: Annotated[WeekAgentState, InjectedState],
    ):
        # 周计划笔记固定为 diet_plan 类型
        note = Note(content=content, type="diet_plan_for_week")
        # 直接写入 `note`（WeekAgentOutput 的输出 key），
        # 而非中间的 `week_note`，确保输出链路不断
        return Command(
            update={
                "note": {file_name: note},
                "week_write_messages": [
                    ToolMessage(
                        content=f"笔记 '{file_name}' 写入成功",
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )

    return week_write_note
