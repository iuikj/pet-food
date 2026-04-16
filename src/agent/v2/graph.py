"""
V2 Agent 图拓扑

START → plan_agent → generate_coordination_guide → dispatch_weeks → week_agent → gather_and_structure → END
"""
from langgraph.graph.state import StateGraph, START, END

from src.agent.v2.node import (
    plan_agent_with_sub,
    generate_coordination_guide,
    dispatch_weeks,
    week_agent,
    # gather_and_structure,
)
from src.agent.v2.state import State, StateV2Input, StateV2Output
from src.agent.v2.utils.context import ContextV2

graph = (
    StateGraph(
        state_schema=State,
        context_schema=ContextV2,
    )
    .add_node("plan_agent", plan_agent_with_sub)
    .add_node("generate_coordination_guide", generate_coordination_guide)
    .add_node("dispatch_weeks", dispatch_weeks)
    .add_node("week_agent", week_agent)
    # .add_node("gather_and_structure", gather_and_structure)
    .add_edge(START, "plan_agent")
    .add_edge("plan_agent", "generate_coordination_guide")
    .add_edge("generate_coordination_guide", "dispatch_weeks")
    # .add_edge("week_agent", "gather_and_structure")
    # .add_edge("gather_and_structure", END)
    .add_edge("week_agent", END)
    .compile()
)
