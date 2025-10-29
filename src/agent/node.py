from typing import Literal, cast

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_dev_utils import has_tool_calling, load_chat_model, parse_tool_calling
from langgraph.prebuilt import ToolNode
from langgraph.runtime import get_runtime
from langgraph.types import Command, Send

from src.agent.entity.note import Note
from src.agent.state import State
from src.agent.tools import (
    ls,
    query_note,
    transfor_task_to_subagent,
    update_plan,
    write_plan,
)
from src.agent.utils.context import Context
from src.agent.utils.struct import WeeklyDietPlan, PetDietPlan, MonthlyDietPlan


async def call_model(state: State) -> Command[Literal["tools", "subagent", "structure_report"]]:
    run_time = get_runtime(Context)
    model = load_chat_model(
        model=run_time.context.plan_model,
        **{
            "max_retries": 3
        }
    )

    tools = [
        write_plan,
        update_plan,
        transfor_task_to_subagent,
        ls,
        query_note,
    ]
    bind_model = model.bind_tools(tools, parallel_tool_calls=False)
    messages = state["messages"]
    info = state["pet_information"]
    response = await bind_model.ainvoke(
        [SystemMessage(content=run_time.context.plan_prompt.format(
            pet_information=info,
        )), *messages]
    )

    if has_tool_calling(cast(AIMessage, response)):
        name, _ = parse_tool_calling(
            cast(AIMessage, response), first_tool_call_only=True
        )
        if name == "transfor_task_to_subagent":
            return Command(
                goto="subagent",
                update={
                    "messages": [response],
                    "now_task_message_index": len(
                        state["task_messages"] if "task_messages" in state else []
                    ),
                },
            )

        return Command(goto="tools", update={"messages": [response]})

    notes: dict[str, Note] = state["note"]
    # return Command(goto="__end__", update={"messages": [response]})
    return Command(
        goto=[Send(
            node="structure_report",
            arg={
                "temp_note": v
            }
        ) for k, v in notes.items()
        ]
    )


async def structure_report(state: State):
    """
    将deep agent所产出的结果（note），转换成结构化的信息来解析
    :param state:
    :return:
    """
    run_time = get_runtime(Context)
    model = load_chat_model(
        model=run_time.context.report_model,
        **{
            "max_retries": 3
        }
    )

    if state["temp_note"].type == "diet_plan":
        structure_model = model.with_structured_output(WeeklyDietPlan)
        response = await structure_model.ainvoke(
            [
                SystemMessage(content=run_time.context.plan_prompt),
                HumanMessage(content=state["temp_note"].content),
            ]
        )

        return {
            "weekly_diet_plans": [response],
        }
    else:
        return {
            "weekly_diet_plans": [],
        }


async def gather(state: State):
    return {
        "report": PetDietPlan(
            pet_information=state["pet_information"],
            pet_diet_plan=MonthlyDietPlan(
                monthly_diet_plan=state["weekly_diet_plans"]
            ),
            ai_suggestions=state["messages"][-1].content,
        )
    }


tool_node = ToolNode([write_plan, update_plan, ls, query_note])
