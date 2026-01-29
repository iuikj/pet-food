from typing import Literal, cast

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_dev_utils import has_tool_calling, load_chat_model, parse_tool_calling
from langgraph.prebuilt import ToolNode
from langgraph.runtime import get_runtime
from langgraph.types import Command, Send

from src.agent.entity.note import Note
from src.agent.state import State
from src.agent.structrue_agent.state import StructState
from src.agent.tools import (
    ls,
    query_note,
    transfor_task_to_subagent,
    update_plan,
    write_plan,
)
from src.agent.utils.context import Context
from src.agent.utils.struct import WeeklyDietPlan, PetDietPlan, MonthlyDietPlan


async def structure_report(state: StructState)-> Command[Literal["__end__","structure_report"]]:
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
        structure_model = model.with_structured_output(WeeklyDietPlan, include_raw=True)
        if state.get("weekly_diet_plans"):
            return Command(
                goto="__end__"
            )
        if state.get("failed_reason"):
            response = await structure_model.ainvoke(
                [
                    SystemMessage(content=run_time.context.report_prompt),
                    HumanMessage(content=state["failed_reason"]),
                ]
            )
        else:
            response = await structure_model.ainvoke(
                [
                    SystemMessage(content=run_time.context.report_prompt),
                    HumanMessage(content=state["temp_note"].content),
                ]
            )
        if response.get("parsed"):
            return Command(
                goto="__end__",
                update={
                    "weekly_diet_plans": [response.get("parsed")],
                })
        else:
            return Command(
                goto="structure_report",
                update={
                    "failed_reason": f"raw:{response.get("raw")},error:{response.get("parsing_error")}"
                }
            )
    else:
        return Command(
                goto="__end__",
                update={
                    "weekly_diet_plans": [],
                })
