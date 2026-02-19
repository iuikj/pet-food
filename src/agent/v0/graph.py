import os

from dotenv import load_dotenv
from langgraph.graph.state import StateGraph

from src.agent.v0.node import call_model, tool_node,gather
from src.agent.v0.structrue_agent.graph import build_structure_agent
from src.agent.v0.state import State, StateInput,StateOutput
from src.agent.v0.sub_agent.graph import build_sub_agent
from src.agent.v0.utils.context import Context
from src.agent.v0.write_agent.graph import build_write_agent

load_dotenv(dotenv_path=".env", override=True)
print(os.getenv("ZAI_API_KEY"))


async def build_graph_with_langgraph_studio():
    graph = StateGraph(State, input_schema=StateInput,output_schema=StateOutput, context_schema=Context)
    graph.add_node("call_model", call_model)
    graph.add_node("tools", tool_node)
    graph.add_node("subagent", build_sub_agent())
    graph.add_node("write_note", build_write_agent())
    graph.add_node("structure_report", build_structure_agent())
    graph.add_node("gather", gather)

    graph.add_edge("__start__", "call_model")
    graph.add_edge("tools", "call_model")
    graph.add_edge("subagent", "write_note")
    graph.add_edge("write_note", "call_model")
    graph.add_edge("structure_report", "gather")

    return graph.compile()
