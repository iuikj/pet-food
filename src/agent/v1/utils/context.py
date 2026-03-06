"""
V1 运行时上下文配置
"""
from dataclasses import dataclass
from typing import Annotated

from src.agent.v0.prompts.prompt import (
    SUBAGENT_PROMPT,
    SUMMARY_PROMPT,
    WRITE_PROMPT,
)
from src.agent.v1.prompts.prompt import (
    RESEARCH_PLANNER_PROMPT,
    COORDINATION_GUIDE_PROMPT,
    WEEK_PLANNER_PROMPT,
)


@dataclass
class ContextV1:
    # ── 模型配置 ──
    plan_model: Annotated[str, "研究规划器模型"] = "dashscope:qwen3.5-plus"
    sub_model: Annotated[str, "子智能体模型"] = "dashscope:qwen3.5-plus"
    write_model: Annotated[str, "笔记写入模型"] = "dashscope:qwen-flash"
    summary_model: Annotated[str, "摘要模型"] = "dashscope:qwen-flash"
    report_model: Annotated[str, "结构化报告模型"] = "dashscope:qwen3.5-plus"
    week_model: Annotated[str, "周规划器模型"] = "dashscope:qwen3.5-plus"

    # ── 提示词配置 ──
    # Phase 1: 研究阶段
    research_planner_prompt: Annotated[str, "研究规划器提示词"] = RESEARCH_PLANNER_PROMPT
    sub_prompt: Annotated[str, "子智能体提示词"] = SUBAGENT_PROMPT
    write_prompt: Annotated[str, "笔记写入提示词"] = WRITE_PROMPT
    summary_prompt: Annotated[str, "摘要提示词"] = SUMMARY_PROMPT

    # Phase 1→2: 协调指南生成
    coordination_guide_prompt: Annotated[str, "协调指南提示词"] = COORDINATION_GUIDE_PROMPT

    # Phase 2: 周计划
    week_planner_prompt: Annotated[str, "周规划器提示词"] = WEEK_PLANNER_PROMPT

    # Phase 3: 结构化
    report_prompt: Annotated[str, "结构化报告提示词"] = "请你根据我给出的内容生成结构化报告"
