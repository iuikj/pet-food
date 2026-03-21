"""
V0 运行时上下文配置

提供 Context 数据类和 resolve_v0_context 双层配置解析函数。
- 优先使用 LangGraph context_schema（直接调用/LangGraph Studio）
- 回退到 RunnableConfig.configurable（CopilotKit LangGraphAGUIAgent）

注意：V0 子图被嵌入 V1 主图时，get_runtime 返回的可能是 ContextV1 实例，
由于 ContextV1 包含 Context 所有同名字段，鸭子类型兼容。
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
from src.agent.v0.prompts.prompt import PLAN_MODEL_PROMPT

logger = logging.getLogger(__name__)


@dataclass
class Context:
    plan_model: Annotated[str, "用于执行任务规划的模型"] = (
        "dashscope:qwen3.5-plus"
    )
    sub_model: Annotated[str, "用于执行每个任务的模型"] = "dashscope:qwen3.5-plus"
    write_model: Annotated[str, "用于执行记笔记任务的模型"] = "dashscope:qwen-flash"
    summary_model: Annotated[str, "用于执行总结任务的模型"] = "dashscope:qwen-flash"
    report_model: Annotated[str, "用于生成报告模型的模型"] = "dashscope:qwen3.5-plus"

    report_prompt: Annotated[str, "用于生成报告的prompt"] = "请你根据我给出的内容生成结构化报告"
    plan_prompt: Annotated[str, "用于执行任务规划的prompt"] = PLAN_MODEL_PROMPT
    sub_prompt: Annotated[str, "用于执行每个任务的prompt"] = SUBAGENT_PROMPT
    write_prompt: Annotated[str, "用于执行记笔记任务的prompt"] = WRITE_PROMPT
    summary_prompt: Annotated[str, "用于执行总结任务的prompt"] = SUMMARY_PROMPT

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "Context":
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


def resolve_v0_context(config: Optional[RunnableConfig] = None):
    """双层配置解析：优先 context_schema，回退 RunnableConfig

    返回值可能是 Context 或 ContextV1（嵌入 V1 主图时），
    两者共享同名字段，鸭子类型兼容。
    """
    try:
        from langgraph.runtime import get_runtime
        runtime = get_runtime(Context)
        if runtime and runtime.context is not None:
            return runtime.context
    except Exception:
        pass

    logger.debug("context_schema 不可用，回退到 RunnableConfig 默认值")
    return Context.from_runnable_config(config)
