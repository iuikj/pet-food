"""
V1 主图工具

复用 common 工厂函数创建笔记和计划管理工具，新增 finalize_research 工具。
"""
from typing import Annotated

from langchain_core.tools import tool

from src.agent.common.entity.note import (
    create_write_note_tool,
    create_ls_tool,
    create_query_note_tool,
)
from src.agent.common.tools import (
    transfor_task_to_subagent,
    tavily_search,
)
from src.agent.common.entity.plan import (
    create_write_plan_tool,
    create_read_plan_tool,
    create_finish_sub_plan_tool
)

# ── 复用 v0 工厂创建的工具实例 ──

write_plan = create_write_plan_tool(
    description="""用于写入计划的工具,只能使用一次，在最开始的时候使用，后续请使用finish_sub_plan更新。
参数：
plan: list[str], 待写入的计划列表，这是一个字符串列表，每个字符串都是一个计划内容content
""",
)

# update_plan 已弃用，改用 read_plan_tool 和 finish_sub_plan
read_plan_tool = create_read_plan_tool()
finish_sub_plan = create_finish_sub_plan_tool()

ls = create_ls_tool(
    name="ls",
    description="""用于列出所有已保存的笔记名称。
    返回：list[str]: 包含所有笔记文件名的列表
    """,
)

query_note = create_query_note_tool(
    name="query_note",
    description="""用于查询笔记。
    参数：file_name: 笔记名称
    返回：str, 查询的笔记内容
    """,
)

write_note = create_write_note_tool(
    name="write_note",
    description="""用于写入笔记的工具。
    参数：
    content: str, 笔记内容
    type: Annotated[Literal["research", "diet_plan"]
    如果是制定确切的某周的饮食计划（按照报告模版的）type为diet_plan，其余作为信息收集的部分皆为research
    """,
    message_key="temp_write_note_messages",
)


# ── 新增工具 ──

@tool
async def finalize_research():
    """结束研究阶段，标记所有调研工作已完成。

    调用此工具后，系统将基于调研笔记自动生成四周差异化的协调指南，
    并将任务分发给四个并行的周计划智能体。

    注意：仅在所有调研任务完成后调用此工具。
    """
    return "研究阶段已完成，正在生成协调指南..."
