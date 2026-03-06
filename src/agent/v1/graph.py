"""
V1 主图构建

Phase 1 (串行): research_planner ←→ subagent/write (调研循环)
Phase 2 (并行): dispatch_weeks → Send ×4 → week_agent[1..4]
Phase 3 (并行): collect_and_structure → Send ×N → structure_report → gather
"""
import os

from dotenv import load_dotenv
from langgraph.graph.state import StateGraph

from src.agent.v0.sub_agent.graph import build_sub_agent
from src.agent.v0.write_agent.graph import build_write_agent
from src.agent.v0.structrue_agent.graph import build_structure_agent
from src.agent.v1.node import (
    research_planner,
    research_tools,
    dispatch_weeks,
    collect_and_structure,
    gather,
)
from src.agent.v1.state import StateV1, StateV1Input, StateV1Output
from src.agent.v1.utils.context import ContextV1
from src.agent.v1.week_agent.graph import build_week_agent

load_dotenv(dotenv_path=".env", override=True)


async def build_v1_graph():
    """构建 V1 并行架构主图"""
    graph = StateGraph(
        StateV1,
        input_schema=StateV1Input,
        output_schema=StateV1Output,
        context_schema=ContextV1,
    )

    # ── Phase 1: 研究阶段节点 ──
    graph.add_node("research_planner", research_planner)
    graph.add_node("research_tools", research_tools)
    graph.add_node("research_subagent", build_sub_agent())      # 复用 v0 子智能体
    graph.add_node("research_write", build_write_agent())        # 复用 v0 写入智能体

    # ── Phase 1→2: 分发节点 ──
    graph.add_node("dispatch_weeks", dispatch_weeks)

    # ── Phase 2: 周 Agent（子图，由 Send 并行触发）──
    graph.add_node("week_agent", build_week_agent())

    # ── Phase 2→3: 收集并结构化 ──
    graph.add_node("collect_and_structure", collect_and_structure)

    # ── Phase 3: 结构化 + 汇总（复用 v0）──
    graph.add_node("structure_report", build_structure_agent())
    graph.add_node("gather", gather)

    # ── 边定义 ──

    # Phase 1: 研究循环
    graph.add_edge("__start__", "research_planner")
    graph.add_edge("research_tools", "research_planner")
    graph.add_edge("research_subagent", "research_write")
    graph.add_edge("research_write", "research_planner")
    # research_planner 通过 Command 路由到:
    #   - research_tools (计划管理工具)
    #   - research_subagent (委派研究任务)
    #   - dispatch_weeks (研究完成)

    # Phase 1→2: dispatch_weeks 通过 Send 路由到 week_agent
    # (Command goto=sends 实现)

    # Phase 2→3: 所有 week_agent 完成后进入 collect
    graph.add_edge("week_agent", "collect_and_structure")
    # collect_and_structure 通过 Send 路由到 structure_report

    # Phase 3: 结构化 → 汇总
    graph.add_edge("structure_report", "gather")

    return graph.compile()
