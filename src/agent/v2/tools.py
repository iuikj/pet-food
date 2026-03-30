from langchain.tools import tool,ToolRuntime


@tool(
    name_or_callable="get_langgraph_state",
    description="用于获取当前运行时的langgraph state",
)
def get_state(runtime:ToolRuntime)->str:
    return f"目前的运行时状态为：{runtime.state},且运行时状态的schema为：{runtime.context}"