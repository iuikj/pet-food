from langchain.agents.middleware import ModelRequest, ModelResponse, wrap_model_call
from langchain.agents.middleware.types import ResponseT, ExtendedModelResponse
from langchain.messages import AIMessage
from langchain_core.messages import filter_messages, HumanMessage

from langgraph.typing import ContextT

from collections.abc import Awaitable, Callable


@wrap_model_call
async def ban_sub_agent(
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
) -> ModelResponse[ResponseT] | AIMessage | ExtendedModelResponse[ResponseT]:
    """
    ban subagent
    :param state:
    :param runtime:
    :return:

    """
    tools=[]
    if hasattr(request, 'tools') and request.tools:
        tools = [tool for tool in request.tools if tool.name != "task"]
    return await handler(
        request.override(
            tools=tools
        )
    )