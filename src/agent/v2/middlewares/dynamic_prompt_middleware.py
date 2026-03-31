
from langchain.agents.middleware import TodoListMiddleware, ModelRequest, ModelResponse, AgentMiddleware, \
    wrap_model_call

from langchain.agents.middleware.types import ResponseT, ExtendedModelResponse
from langchain.messages import SystemMessage,AIMessage
from langchain_core.messages import filter_messages



from langgraph.typing import ContextT

from src.agent.v2.utils.context import ContextV2
from collections.abc import Awaitable, Callable


# class DynamicPromptMiddleware(AgentMiddleware):
#     """动态提示中间件"""
#
#     async def awrap_model_call(
#         self,
#         request: ModelRequest[ContextT],
#         handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
#     ) -> ModelResponse[ResponseT] | AIMessage | ExtendedModelResponse[ResponseT]:
#         ctx:ContextV2=request.runtime.context
#         new_content=ctx.research_planner_prompt.format(
#             pet_information=ctx.pet_information,
#         )
#         return await handler(
#             request.override(
#                 system_message=SystemMessage(content=new_content)
#             )
#         )


@wrap_model_call
async def sub_agent_prompt(
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


@wrap_model_call
async def plan_agent_prompt(
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
)-> ModelResponse[ResponseT] | AIMessage | ExtendedModelResponse[ResponseT]:
    ctx: ContextV2 = request.runtime.context
    new_content = ctx.research_planner_prompt.format(
        pet_information=ctx.pet_information,
    )
    return await handler(
        request.override(
            system_message=SystemMessage(content=new_content)
        )
    )

@wrap_model_call
async def coordination_agent_prompt(
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
)-> ModelResponse[ResponseT] | AIMessage | ExtendedModelResponse[ResponseT]:
    ctx: ContextV2 = request.runtime.context
    messages=request.messages
    print(len(messages))
    messages = filter_messages(
        messages=messages,
        include_types=["tool"],
        include_names=["task"]
    )
    notes=[s.content for s in messages]
    new_content = ctx.coordination_guide_prompt.format(
        pet_information=ctx.pet_information,
        research_notes=notes
    )
    return await handler(
        request.override(
            system_message=SystemMessage(content=new_content)
        )
    )