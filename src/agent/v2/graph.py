from langgraph.graph.state import StateGraph, START, END

from src.agent.v2.node import node, plan_agent_with_sub, node_before
from src.agent.v2.state import StateV2
from src.agent.v2.utils.context import ContextV2

graph=(
    StateGraph(state_schema=StateV2,context_schema=ContextV2)
    .add_node("plan_agent",plan_agent_with_sub)
    .add_node("node",node)
    .add_node("node_before",node_before)
    .add_edge("plan_agent","node")
    .add_edge(START,"node_before")
    .add_edge("node_before","plan_agent")
    .add_edge("node",END)
    .compile()
)
