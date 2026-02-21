"""
V1 周 Agent 子图构建

__start__ → week_planner ←→ week_tools (循环搜索/查询)
                 ↓ 计划完成
           week_write → week_write_tool → week_finalize → __end__
"""
from langgraph.graph.state import StateGraph

from src.agent.v1.week_agent.state import WeekAgentState
from src.agent.v1.week_agent.node import (
    week_planner,
    week_write,
    week_finalize,
    week_tools,
    week_write_tool,
)


def build_week_agent():
    """构建周 Agent 子图"""
    graph = StateGraph(WeekAgentState)

    # 添加节点
    graph.add_node("week_planner", week_planner)
    graph.add_node("week_tools", week_tools)
    graph.add_node("week_write", week_write)
    graph.add_node("week_write_tool", week_write_tool)
    graph.add_node("week_finalize", week_finalize)

    # 定义边
    graph.add_edge("__start__", "week_planner")
    graph.add_edge("week_tools", "week_planner")
    # week_planner 通过 Command 路由到 week_tools 或 week_write
    graph.add_edge("week_write", "week_write_tool")
    graph.add_edge("week_write_tool", "week_finalize")
    graph.add_edge("week_finalize", "__end__")

    return graph.compile()
