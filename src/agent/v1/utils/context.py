"""
V1 运行时上下文配置

提供 ContextV1 数据类和 resolve_context 双层配置解析函数。
- 优先使用 LangGraph context_schema（直接调用/LangGraph Studio）
- 回退到 RunnableConfig.configurable（CopilotKit LangGraphAGUIAgent）
"""
import logging
from dataclasses import dataclass, fields
from typing import Annotated, Optional

from langchain_core.runnables import RunnableConfig

from src.agent.common.prompts.prompt import (
    SUBAGENT_PROMPT,
    SUMMARY_PROMPT,
    WRITE_PROMPT,
)
from src.agent.v1.prompts.prompt import (
    RESEARCH_PLANNER_PROMPT,
    COORDINATION_GUIDE_PROMPT,
    WEEK_PLANNER_PROMPT,
)

logger = logging.getLogger(__name__)


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

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "ContextV1":
        """从 RunnableConfig.configurable 中提取配置，缺省使用默认值"""
        configurable = (
            config["configurable"] if config and "configurable" in config else {}
        )
        values = {
            f.name: configurable[f.name]
            for f in fields(cls)
            if f.init and f.name in configurable
        }
        return cls(**values)


def resolve_context(config: Optional[RunnableConfig] = None) -> ContextV1:
    """双层配置解析：优先 context_schema，回退 RunnableConfig

    Layer 1: get_runtime(ContextV1).context — LangGraph 原生 context_schema 注入
    Layer 2: ContextV1.from_runnable_config(config) — CopilotKit / 旧版 config 方式
    """
    try:
        from langgraph.runtime import get_runtime
        runtime = get_runtime(ContextV1)
        if runtime and runtime.context is not None:
            return runtime.context
    except (ImportError, AttributeError, RuntimeError) as e:
        logger.debug("context_schema 不可用 (%s: %s)，回退到 RunnableConfig", type(e).__name__, e)

    return ContextV1.from_runnable_config(config)
