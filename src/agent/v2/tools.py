from langchain.tools import tool,ToolRuntime


@tool(
    name_or_callable="get_langgraph_state",
    description="用于获取当前运行时的langgraph state",
)
def get_state(runtime:ToolRuntime)->str:
    return f"目前的运行时状态为：{runtime.state},且运行时状态的schema为：{runtime.context}"


@tool(
    description="""
    结束研究阶段，标记所有调研工作已完成。

    调用此工具后，系统将基于调研笔记自动生成四周差异化的协调指南，
    并将任务分发给四个并行的周计划智能体。

    注意：仅在所有调研任务完成后调用此工具。"""
)
async def finalize_research():
    """结束研究阶段，标记所有调研工作已完成。

    调用此工具后，系统将基于调研笔记自动生成四周差异化的协调指南，
    并将任务分发给四个并行的周计划智能体。

    注意：仅在所有调研任务完成后调用此工具。
    """
    return "研究阶段已完成，正在生成协调指南..."