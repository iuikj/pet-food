
from langchain.agents.middleware import ModelRequest, ModelResponse, wrap_model_call
from deepagents.middleware._utils import append_to_system_message
from langchain.agents.middleware.types import ResponseT, ExtendedModelResponse
from langchain.messages import AIMessage
from langchain_core.messages import filter_messages, HumanMessage

from langgraph.typing import ContextT

from src.agent.v1.models import WeekAssignment
from src.agent.v2.state import State, WeekAgentState
from src.agent.v2.middlewares.note_middleware import Note
from src.agent.v2.utils.context import ContextV2
from collections.abc import Awaitable, Callable
from typing import Dict
from deepagents.backends.protocol import FileData



@wrap_model_call
async def sub_agent_prompt(
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
) -> ModelResponse[ResponseT] | AIMessage | ExtendedModelResponse[ResponseT]:
    request.runtime.execution_info
    ctx:ContextV2=request.runtime.context
    notes:dict|None=request.state.get("note")
    new_content=ctx.sub_prompt.format(
        user_requirement=f"下面是用户的宠物情况:{ctx.pet_information}",
        task_name=request.messages[-1].content,
        history_files=notes.keys() if notes else "当前没有笔记",
    )
    return await handler(
        request.override(
            system_message=append_to_system_message(request.system_message, new_content),
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
    # messages=request.state['messages']
    # if messages[-1].role == "human":
    #     messages[-1]=HumanMessage(
    #         content="/research-memory"+messages[-1].content,
    #     )


    return await handler(
        request.override(
            system_message=append_to_system_message(request.system_message, new_content),
        )
    )



def _extract_temp_notes(state) -> Dict[str,FileData]|None:
    """从 state['files'] 中提取 /temp_notes/ 下的临时笔记内容。

    state['files'] 是 DeepAgents FileData 字典：
    键为相对路径（如 "/temp_notes/调研_软便饮食方案.md"），
    值为 FileData TypedDict（含 content, encoding 等字段）。
    """
    files: Dict[str,FileData]|None = state.get("files", {})
    temp_notes = {}
    if files:
        for file_name,file_data in files.items():
            temp_notes[file_name]=file_data["content"]
        return temp_notes
    return None


@wrap_model_call(state_schema=State)
async def coordination_agent_prompt(
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
) -> ModelResponse[ResponseT] | AIMessage | ExtendedModelResponse[ResponseT]:
    ctx: ContextV2 = request.runtime.context
    state: State = request.state


    temp_notes: Dict[str,FileData]|None = _extract_temp_notes(request.state)


    # 构建调研笔记文本
    if temp_notes:
        notes_parts = []
        for name, content in temp_notes.items():
            notes_parts.append(f"### file name: {name}\n{content}")
        notes_text = "\n\n".join(notes_parts)
    else:
        notes_text = "（暂无调研笔记）"

    new_content = ctx.coordination_guide_prompt.format(
        pet_information=ctx.pet_information,
        research_notes=notes_text,
    )
    return await handler(
        request.override(
            system_message=append_to_system_message(request.system_message, new_content)
        )
    )


@wrap_model_call
async def structure_report_prompt(
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
) -> ModelResponse[ResponseT] | AIMessage | ExtendedModelResponse[ResponseT]:
    ctx: ContextV2 = request.runtime.context
    new_content = ctx.structure_report_prompt
    return await handler(
        request.override(
            system_message=append_to_system_message(request.system_message, new_content)
        )
    )


@wrap_model_call(
    state_schema=WeekAgentState
)
async def week_agent_prompt(
        request: ModelRequest[ContextT],
        handler: Callable[[ModelRequest[ContextT]], Awaitable[ModelResponse[ResponseT]]],
) -> ModelResponse[ResponseT] | AIMessage | ExtendedModelResponse[ResponseT]:
    ctx:ContextV2 = request.runtime.context
    state:WeekAgentState=request.state
    assignment: WeekAssignment = state["week_assignment"]
    week_num = assignment.week_number
    info = ctx.pet_information

    # # 构建调研笔记内容（来自 dispatch_weeks 分配的 research_note_contents）
    # research_notes: dict[str, str] = state.get("research_note_contents") or {}
    # if research_notes:
    #     research_notes_text = "\n\n".join(
    #         f"### {name}\n{content}" for name, content in research_notes.items()
    #     )
    # else:
    #     research_notes_text = "（暂无调研笔记）"

    new_content = ctx.week_planner_prompt.format(
        week_number=week_num,
        pet_information=info,
        theme=assignment.theme,
        focus_nutrients=", ".join(assignment.focus_nutrients),
        constraints="\n".join(f"- {c}" for c in assignment.constraints),
        differentiation_note=assignment.differentiation_note,
        search_keywords=", ".join(assignment.search_keywords),
        shared_constraints="\n".join(
            f"- {c}" for c in (state.get("shared_constraints") or [])
        ),
        ingredient_rotation_strategy=state.get("ingredient_rotation_strategy", ""),
        age_adaptation_note=state.get("age_adaptation_note", ""),
        research_notes=assignment.relevant_research_notes,
    )
    return await handler(
        request.override(
            system_message=append_to_system_message(request.system_message, new_content),
        )
    )