from langgraph.graph import StateGraph

from src.agent.v0.structrue_agent.node import structure_report
from src.agent.v0.structrue_agent.state import StructState


def build_structure_agent():
    struct_graph = StateGraph(StructState)
    struct_graph.add_node("structure_report", structure_report)
    struct_graph.add_edge("__start__", "structure_report")
    return struct_graph.compile()
