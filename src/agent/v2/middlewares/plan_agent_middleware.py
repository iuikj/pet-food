from typing import Any

from langchain.agents.middleware import TodoListMiddleware, ModelRequest, ModelResponse, AgentMiddleware, \
    wrap_model_call
from deepagents.middleware._utils import append_to_system_message
from langchain.agents.middleware.types import ResponseT, ExtendedModelResponse, StateT,AgentState
from langchain.messages import SystemMessage,AIMessage
from langchain_core.messages import filter_messages, HumanMessage
from langgraph.runtime import Runtime
from typing_extensions import NotRequired

from langgraph.typing import ContextT

from src.agent.v1.models import WeekAssignment
from src.agent.v2.state import State, WeekAgentState
from src.agent.v2.utils.context import ContextV2
from collections.abc import Awaitable, Callable


class PlanAgentState(AgentState):
    call_account:NotRequired[int]

class PlanAgentMiddleware(AgentMiddleware):
    async def abefore_agent(
        self, state: StateT, runtime: Runtime[ContextT]
    ) -> dict[str, Any] | None:
        return {
            "call_account": 0
        }

    async def awrap_model_call(
        self,
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
    ) -> ModelResponse[ResponseT] | AIMessage | ExtendedModelResponse[ResponseT]:
        """
        动态组装system prompt
        :param request:
        :param handler:
        :return:
        """
        if request.state.get("call_account") == 0:
            ctx: ContextV2 = request.runtime.context
            new_content = ctx.research_planner_prompt.format(
                pet_information=ctx.pet_information,
            )
            state=request.state
            return await handler(
                request.override(
                    system_message=append_to_system_message(request.system_message, new_content),
                )
            )
        return await handler(request)

    async def aafter_model(
        self, state: StateT, runtime: Runtime[ContextT]
    ) -> dict[str, Any] | None:
        return {
            "call_account": state["call_account"] + 1
        }

    async def aafter_agent(
        self, state: StateT, runtime: Runtime[ContextT]
    ) -> dict[str, Any] | None:
        return {
            "call_account": 0
        }

