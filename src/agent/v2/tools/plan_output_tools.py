"""
周计划输出工具

week_agent 完成规划后，调用此工具将周饮食计划写入笔记状态。
保留 Markdown 格式，后续由 structure_report 节点解析为 Pydantic 模型。
"""
from typing import Annotated

from langchain.tools import tool, ToolRuntime
from langchain_core.messages import ToolMessage
from langgraph.types import Command

from src.agent.v2.middlewares.note_middleware import Note


@tool
def write_week_plan(
    week_number: Annotated[int, "第几周 (1-4)"],
    content: Annotated[str, "完整的周饮食计划 Markdown 内容，包含所有餐食、食材、份量和营养素数据"],
    runtime: ToolRuntime,
) -> Command:
    """将本周饮食计划写入笔记状态。

    week_agent 在完成热量计算、食材选择、餐食组装后，
    必须调用此工具输出最终的周计划。内容应为完整的 Markdown 格式，
    包含每日每餐的食材、份量和营养素详情。
    """
    file_name = f"week_{week_number}_diet_plan"
    note = Note(content=content, type="diet_plan_for_week")

    return Command(
        update={
            "note": {file_name: note},
            "messages": [
                ToolMessage(
                    content=f"第{week_number}周饮食计划已成功写入笔记 '{file_name}'。",
                    tool_call_id=runtime.tool_call_id,
                )
            ],
        }
    )
