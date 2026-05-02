from typing import Literal, cast

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_dev_utils.chat_models import load_chat_model
from langchain_dev_utils.tool_calling import has_tool_calling, parse_tool_calling
from langgraph.prebuilt import ToolNode
from langgraph.types import Command, Send

from src.agent.common.entity.note import Note
from src.agent.common.stream_events import ProgressEventType, aemit_progress
from src.agent.common.utils.struct import PetDietPlan, MonthlyDietPlan
from src.agent.v0.state import State
from src.agent.v0.tools import (
    ls,
    query_note,
    transfor_task_to_subagent,
    finish_sub_plan,
    read_plan_tool,
    write_plan,
)
from src.agent.v0.utils.context import resolve_v0_context


async def call_model(state: State, config: RunnableConfig) -> Command[Literal["tools", "subagent", "structure_report"]]:
    ctx = resolve_v0_context(config)
    has_plan = bool(state.get("plan"))

    # 首次调用（无 plan）时发送"正在创建计划"进度
    if not has_plan:
        await aemit_progress(
            ProgressEventType.PLAN_CREATING,
            "正在分析宠物信息，制定任务计划...",
            node="call_model",
            progress=5,
        )

    model = load_chat_model(
        model=ctx.plan_model,
        **{
            "max_retries": 3,
            # "enable_thinking" : True,  # 在使用智谱的时候不用这个配置项
        }
    )
    if has_plan:
        # 如果已经制定了计划了，就不使用thinking
        model = load_chat_model(
            model=ctx.plan_model,
            **{
                "max_retries": 3
            }
        )

    tools = [
        write_plan,
        read_plan_tool,
        finish_sub_plan,
        transfor_task_to_subagent,
        ls,
        query_note,
    ]
    bind_model = model.bind_tools(tools, parallel_tool_calls=False)
    messages = state["messages"]
    info = state["pet_information"]
    response = await bind_model.ainvoke(
        [SystemMessage(content=ctx.plan_prompt.format(
            pet_information=info,
        )), *messages]
    )

    if has_tool_calling(response):
        name, args = parse_tool_calling(
            response, first_tool_call_only=True
        )

        # 根据工具调用类型发送对应进度事件
        if name == "write_plan":
            await aemit_progress(
                ProgressEventType.PLAN_CREATED,
                "任务计划已创建",
                node="call_model",
                progress=10,
            )
        elif name == "finish_sub_plan":
            progress = _estimate_progress(state)
            await aemit_progress(
                ProgressEventType.PLAN_UPDATED,
                "任务计划已更新",
                node="call_model",
                progress=progress,
            )
        elif name == "transfor_task_to_subagent":
            task_name = cast(dict, args).get("content", "") if isinstance(args, dict) else ""
            progress = _estimate_progress(state)
            await aemit_progress(
                ProgressEventType.TASK_DELEGATING,
                f"正在委派任务: {task_name}",
                node="call_model",
                task_name=task_name,
                progress=progress,
            )
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

    # 所有任务完成，进入结构化阶段
    notes: dict[str, Note] = state["note"]
    await aemit_progress(
        ProgressEventType.GATHERING,
        "所有任务已完成，正在进入结构化解析阶段...",
        node="call_model",
        progress=80,
    )
    return Command(
        goto=[Send(
            node="structure_report",
            arg={
                "temp_note": v
            }
        ) for k, v in notes.items()
        ]
    )


def _estimate_progress(state: State) -> int:
    """根据 plan 完成情况估算当前进度 (10-80%)"""
    plan = state.get("plan")
    if not plan:
        return 10
    total = len(plan)
    if total == 0:
        return 10
    done = sum(1 for item in plan if getattr(item, "status", None) == "done")
    # 映射到 10-80 区间
    return 10 + int((done / total) * 70)


async def gather(state: State):
    weekly_plans = state.get("weekly_diet_plans", [])
    await aemit_progress(
        ProgressEventType.COMPLETED,
        f"月度饮食计划生成完成！共 {len(weekly_plans)} 周计划",
        node="gather",
        detail={"total_weeks": len(weekly_plans)},
        progress=100,
    )
    return {
        "report": PetDietPlan(
            pet_information=state["pet_information"],
            pet_diet_plan=MonthlyDietPlan(
                monthly_diet_plan=weekly_plans
            ),
            ai_suggestions=state["messages"][-1].content,
        )
    }


tool_node = ToolNode([write_plan, read_plan_tool, finish_sub_plan, ls, query_note])
