from langchain.agents.middleware import before_agent, after_model, AgentState
from langchain.messages import AIMessage
from langchain_core.messages import HumanMessage
from langgraph.runtime import Runtime
from typing import Any


@before_agent
def trigger_plan_agent(state: AgentState, runtime: Runtime):
    """
    用来稳定的触发skill的,后续要做意图识别
    :param state:
    :param runtime:
    :return:
    """
    return{
        "messages": [HumanMessage(content="/research-memory 使用skill")]
    }


@before_agent
def trigger_week_agent(state: AgentState, runtime: Runtime):
    """
    用来稳定的触发skill的,后续要做意图识别
    :param state:
    :param runtime:
    :return:
    """
    return {
        "messages": [HumanMessage(content="/week-diet-planner 使用skill")]
    }


@before_agent
def trigger_sub_agent(state: AgentState, runtime: Runtime):
    """
    用来稳定的触发skill的,后续要做意图识别
    :param state:
    :param runtime:
    :return:
    """
    return {
        "messages": [HumanMessage(content="/research-memory 使用skill")]
    }
