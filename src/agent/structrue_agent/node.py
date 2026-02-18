from typing import Literal, cast

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_dev_utils import has_tool_calling, load_chat_model, parse_tool_calling
from langgraph.prebuilt import ToolNode
from langgraph.runtime import get_runtime
from langgraph.types import Command, Send

from src.agent.entity.note import Note
from src.agent.state import State
from src.agent.stream_events import ProgressEventType, emit_progress
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

        is_retry = bool(state.get("failed_reason"))
        if is_retry:
            emit_progress(
                ProgressEventType.STRUCTURING_RETRY,
                "结构化解析失败，正在重试...",
                node="structure_report",
            )
            response = await structure_model.ainvoke(
                [
                    SystemMessage(content=run_time.context.report_prompt),
                    HumanMessage(content=state["failed_reason"]),
                ]
            )
        else:
            emit_progress(
                ProgressEventType.STRUCTURING,
                "正在解析饮食计划为结构化数据...",
                node="structure_report",
            )
            response = await structure_model.ainvoke(
                [
                    SystemMessage(content=run_time.context.report_prompt),
                    HumanMessage(content=state["temp_note"].content),
                ]
            )
        if response.get("parsed"):
            parsed_plan: WeeklyDietPlan = response.get("parsed")
            week_num = getattr(parsed_plan, "oder", None)
            emit_progress(
                ProgressEventType.STRUCTURED,
                f"第{week_num}周饮食计划解析完成" if week_num else "饮食计划解析完成",
                node="structure_report",
                detail={"week": week_num},
                progress=85,
            )
            return Command(
                goto="__end__",
                update={
                    "weekly_diet_plans": [parsed_plan],
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
