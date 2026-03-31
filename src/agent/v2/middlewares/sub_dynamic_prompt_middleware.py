from typing import Callable

from deepagents.middleware.memory import MemoryMiddleware, MemoryState, MemoryStateUpdate
from langchain.agents.middleware import TodoListMiddleware, ModelRequest, ModelResponse,AgentMiddleware
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from deepagents.middleware import SubAgentMiddleware
from langchain.agents.middleware.types import ResponseT, ExtendedModelResponse
from langchain.messages import SystemMessage
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.runtime import Runtime
from langgraph.typing import ContextT

from src.agent.v2.utils.context import ContextV2
from collections.abc import Awaitable, Callable, Sequence

class SubDynamicPromptMiddleware(AgentMiddleware):

    async def awrap_model_call(
            self,
            request: ModelRequest[ContextT],
            handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
    ) -> ModelResponse[ResponseT] | AIMessage | ExtendedModelResponse[ResponseT]:
        ctx:ContextV2=request.runtime.context
        notes:dict|None=request.state.get("note")
        new_content=ctx.sub_prompt.format(
            user_requirement=f"下面是用户的宠物情况:{ctx.pet_information}",
            task_name=request.messages[-1].content,
            history_files=notes.keys() if notes else "当前没有笔记",
        )
        return await handler(
            request.override(
                system_message=SystemMessage(
                    content=new_content
                )
            )
        )