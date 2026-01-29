from dataclasses import dataclass
from typing import Annotated

from src.agent.prompts.prompt import (
    SUBAGENT_PROMPT,
    SUMMARY_PROMPT,
    PLAN_MODEL_PROMPT,
    WRITE_PROMPT,
)


@dataclass
class Context:
    # plan_model: Annotated[str, "用于执行任务规划的模型"] = (
    #     # "moonshot:kimi-k2-0905-preview"
    #     "dashscope:qwen3-max"
    # )
    # sub_model: Annotated[str, "用于执行每个任务的模型"] = "dashscope:qwen3-max"
    # write_model: Annotated[str, "用于执行记笔记任务的模型"] = "dashscope:qwen-flash"
    # summary_model: Annotated[str, "用于执行总结任务的模型"] = "dashscope:qwen-flash"
    # report_model: Annotated[str, "用于生成报告模型的模型"] = "dashscope:qwen3-max"
    plan_model: Annotated[str, "用于执行任务规划的模型"] = (
        # "moonshot:kimi-k2-0905-preview"
        "dashscope:qwen3-max"
    )
    sub_model: Annotated[str, "用于执行每个任务的模型"] = "zai:glm-4.7"
    write_model: Annotated[str, "用于执行记笔记任务的模型"] = "dashscope:qwen-flash"
    summary_model: Annotated[str, "用于执行总结任务的模型"] = "dashscope:qwen-flash"
    report_model: Annotated[str, "用于生成报告模型的模型"] = "zai:glm-4.7"

    report_prompt: Annotated[str, "用于生成报告的prompt"] = "请你根据我给出的内容生成结构化报告"
    plan_prompt: Annotated[str, "用于执行任务规划的prompt"] = PLAN_MODEL_PROMPT
    sub_prompt: Annotated[str, "用于执行每个任务的prompt"] = SUBAGENT_PROMPT
    write_prompt: Annotated[str, "用于执行记笔记任务的prompt"] = WRITE_PROMPT
    summary_prompt: Annotated[str, "用于执行总结任务的prompt"] = SUMMARY_PROMPT
