"""
common 子图上下文解析

提供通用的 resolve_subgraph_context，兼容 V0 Context 和 V1 ContextV1。
"""
import logging
from dataclasses import dataclass
from typing import Annotated

logger = logging.getLogger(__name__)


@dataclass
class _DefaultContext:
    """当 context_schema 不可用时的默认兜底配置"""
    sub_model: Annotated[str, "子智能体模型"] = "dashscope:qwen3.5-plus"
    write_model: Annotated[str, "写入模型"] = "dashscope:qwen-flash"
    summary_model: Annotated[str, "摘要模型"] = "dashscope:qwen-flash"
    report_model: Annotated[str, "报告模型"] = "dashscope:qwen3.5-plus"

    @property
    def sub_prompt(self):
        from src.agent.common.prompts.prompt import SUBAGENT_PROMPT
        return SUBAGENT_PROMPT

    @property
    def write_prompt(self):
        from src.agent.common.prompts.prompt import WRITE_PROMPT
        return WRITE_PROMPT

    @property
    def summary_prompt(self):
        from src.agent.common.prompts.prompt import SUMMARY_PROMPT
        return SUMMARY_PROMPT

    @property
    def report_prompt(self):
        return "请你根据我给出的内容生成结构化报告"


def resolve_subgraph_context(config=None):
    """子图通用 context 获取，兼容 V0 Context 和 V1 ContextV1。

    优先使用 LangGraph context_schema（直接调用/LangGraph Studio），
    回退到 _DefaultContext（默认模型和提示词配置）。
    """
    # 先尝试用 V0 Context 类型解析
    try:
        from src.agent.v0.utils.context import Context
        from langgraph.runtime import get_runtime
        runtime = get_runtime(Context)
        if runtime and runtime.context is not None:
            return runtime.context
    except Exception:
        pass

    # 再尝试用 V1 ContextV1 类型解析
    try:
        from src.agent.v1.utils.context import ContextV1
        from langgraph.runtime import get_runtime
        runtime = get_runtime(ContextV1)
        if runtime and runtime.context is not None:
            return runtime.context
    except Exception:
        pass

    logger.debug("context_schema 不可用，使用默认 _DefaultContext")
    return _DefaultContext()
