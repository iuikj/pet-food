from typing import Literal

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_dev_utils.chat_models import load_chat_model
from langgraph.types import Command

from src.agent.common.context import resolve_subgraph_context
from src.agent.common.stream_events import ProgressEventType, emit_progress
from src.agent.common.structrue_agent.state import StructState
from src.agent.common.utils.struct import WeeklyDietPlan


async def structure_report(state: StructState, config: RunnableConfig) -> Command[Literal["__end__", "structure_report"]]:
    """
    将deep agent所产出的结果（note），转换成结构化的信息来解析
    :param state:
    :param config:
    :return:
    """
    ctx = resolve_subgraph_context(config)
    model = load_chat_model(
        model=ctx.report_model,
        **{
            "max_retries": 3
        }
    )

    # 兼容 v0 (`diet_plan`) 与 v1 (`diet_plan_for_week`)：
    # 两种类型都对应"单周饮食计划"笔记，需要解析为 WeeklyDietPlan
    if state["temp_note"].type in ("diet_plan", "diet_plan_for_week"):
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
                    SystemMessage(content=ctx.report_prompt),
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
                    SystemMessage(content=ctx.report_prompt),
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
                    "failed_reason": f"raw:{response.get('raw')},error:{response.get('parsing_error')}"
                }
            )
    else:
        return Command(
                goto="__end__",
                update={
                    "weekly_diet_plans": [],
                })
