
from langchain.agents.middleware import ModelRequest, ModelResponse, wrap_model_call, after_agent
from deepagents.middleware._utils import append_to_system_message
from langchain.agents.middleware.types import ResponseT, ExtendedModelResponse, AgentState
from langchain.messages import AIMessage
from langchain_core.messages import HumanMessage
from langgraph.runtime import Runtime

from src.agent.v2.models import WeekLightPlan


@after_agent(can_jump_to="model")
def collect_week_light_plan(state: AgentState, runtime: Runtime) -> dict | None:
    """把 week_agent 的 structured_response 归集到父图的 week_light_plans。

    父 State 的 `week_light_plans` 用 operator.add 合并，4 个并行 week_agent
    各返回一个长度 1 的列表即可正确汇总为 4 条。
    """
    sr = None
    if isinstance(state, dict):
        sr = state.get("structured_response")
        if not sr:
            return {
                "messages":[HumanMessage("请结构化结构化输出")],
                "jump_to":"model"
            }
    else:
        sr = getattr(state, "structured_response", None)
    if isinstance(sr, WeekLightPlan):
        return {
            "week_light_plans": [sr],
            "structured_response":None
        }
    return None

