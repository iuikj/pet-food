from langgraph.graph.state import StateGraph, START, END

from src.agent.v2.node import plan_agent_with_sub,generate_coordination_guide
from src.agent.v2.state import State
from src.agent.v2.utils.context import ContextV2

graph=(
    StateGraph(state_schema=State,context_schema=ContextV2)
    .add_node("plan_agent",plan_agent_with_sub)
    .add_node("generate_coordination_guide",generate_coordination_guide)
    .add_edge(START,"plan_agent")
    .add_edge("plan_agent","generate_coordination_guide")
    .add_edge("generate_coordination_guide",END)
    .compile()
)
