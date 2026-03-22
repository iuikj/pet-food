"""
V1 LangGraph builder with process-level caching.
"""
import asyncio

from dotenv import load_dotenv
from langgraph.graph.state import StateGraph

from src.agent.common.structrue_agent.graph import build_structure_agent
from src.agent.common.sub_agent.graph import build_sub_agent
from src.agent.common.write_agent.graph import build_write_agent
from src.agent.v1.node import (
    collect_and_structure,
    dispatch_weeks,
    gather,
    research_planner,
    research_tools,
)
from src.agent.v1.state import StateV1, StateV1Input, StateV1Output
from src.agent.v1.utils.context import ContextV1
from src.agent.v1.week_agent.graph import build_week_agent

load_dotenv(dotenv_path=".env", override=True)


_compiled_v1_graph = None
_compiled_v1_graph_lock = asyncio.Lock()


async def build_v1_graph(force_rebuild: bool = False):
    """Build and cache the compiled V1 graph for reuse across requests."""
    global _compiled_v1_graph

    if _compiled_v1_graph is not None and not force_rebuild:
        return _compiled_v1_graph

    async with _compiled_v1_graph_lock:
        if _compiled_v1_graph is not None and not force_rebuild:
            return _compiled_v1_graph

        graph = StateGraph(
            StateV1,
            input_schema=StateV1Input,
            output_schema=StateV1Output,
            context_schema=ContextV1,
        )

        graph.add_node("research_planner", research_planner)
        graph.add_node("research_tools", research_tools)
        graph.add_node("research_subagent", build_sub_agent())
        graph.add_node("research_write", build_write_agent())
        graph.add_node("dispatch_weeks", dispatch_weeks)
        graph.add_node("week_agent", build_week_agent())
        graph.add_node("collect_and_structure", collect_and_structure)
        graph.add_node("structure_report", build_structure_agent())
        graph.add_node("gather", gather)

        graph.add_edge("__start__", "research_planner")
        graph.add_edge("research_tools", "research_planner")
        graph.add_edge("research_subagent", "research_write")
        graph.add_edge("research_write", "research_planner")
        graph.add_edge("week_agent", "collect_and_structure")
        graph.add_edge("structure_report", "gather")

        compiled_graph = graph.compile()
        if not force_rebuild:
            _compiled_v1_graph = compiled_graph
        return compiled_graph
