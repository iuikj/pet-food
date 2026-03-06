"""
V1 主图工具

复用 v0 工厂函数创建笔记和计划管理工具，新增 finalize_research 工具。
"""
from typing import Annotated

from langchain_core.tools import tool

from src.agent.v0.entity.note import (
    create_write_note_tool,
    create_ls_tool,
    create_query_note_tool,
)
from src.agent.v0.tools import (
    transfor_task_to_subagent,
    tavily_search,
)
from langchain_dev_utils import (
    create_write_plan_tool,
    create_update_plan_tool,
)

# ── 复用 v0 工厂创建的工具实例 ──

write_plan = create_write_plan_tool(
    name="write_plan",
    description="""用于写入计划的工具,只能使用一次，在最开始的时候使用，后续请使用update_plan更新。
参数：
plan: list[str], 待写入的计划列表，这是一个字符串列表，每个字符串都是一个计划内容content
""",
)

update_plan = create_update_plan_tool(
    name="update_plan",
    description="""用于更新计划的工具，可以多次使用来更新计划进度。
    参数：
    update_plans: list[Todo] - 需要更新的计划列表，每个元素是一个包含以下字段的字典：
        - content: str, 计划内容，必须与现有计划内容完全一致
        - status: str, 计划状态，只能是"in_progress"（进行中）或"done"（已完成）

    使用说明：
    1. 每次调用只需传入需要更新状态的计划，无需传入所有计划
    2. 必须同时包含至少一个"done"状态的计划和至少一个"in_progress"状态的计划
        - 将已完成的计划设置为"done"
        - 将接下来要执行的计划设置为"in_progress"
    3. content字段必须与现有计划内容精确匹配
    """,
)

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
