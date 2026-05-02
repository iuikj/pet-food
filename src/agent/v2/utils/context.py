"""V2 运行时上下文配置。

ContextV2 是 V2 graph 的 `context_schema`，由 LangGraph runtime 在每次 `astream_events`
时实例化，并通过 `request.runtime.context` 暴露给 middleware / 节点。

为什么用 Pydantic 而不是 dataclass：
- ag_ui_langgraph 把 `RunnableConfig.configurable` 整个 dict（含 thread_id）作为
  `context_schema(**dict)` 的入参。dataclass 不接受额外字段会抛 TypeError，导致
  context 实例化静默失败 → runtime.context 变 None → 下游崩溃。
- Pydantic + `model_config = ConfigDict(extra='ignore')` 自动吞掉 thread_id 等
  系统字段，不需要 wrapper 层做过滤。
- Pydantic 还会自动把前端传来的 dict 验证成 PetInformation 实例，免去手动 coerce。

模块级 DEFAULT_* 常量：
    Pydantic v2 类级访问 `ContextV2.plan_model` 返回 `FieldInfo` 对象而不是默认值，
    破坏了 dataclass 时代 `load_chat_model(ContextV2.plan_model)` 的写法。提取常量
    给 node.py 使用，字段默认值也用同一常量保持一致。
"""
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict

from src.agent.v2.prompts.sub_agent_prompt import (
    SUBAGENT_PROMPT,
    SUMMARY_PROMPT,
    WRITE_PROMPT,
)
from src.agent.v2.prompts.agent_prompt import (
    RESEARCH_PLANNER_PROMPT,
    COORDINATION_GUIDE_PROMPT,
    WEEK_PLANNER_PROMPT,
    STRUCTURE_REPORT_PROMPT,
)
from src.utils.strtuct import PetInformation

# ── 模型配置默认常量（供 node.py 模块加载时直接读取，避免 Pydantic 字段 FieldInfo 包装）──
DEFAULT_PLAN_MODEL = "dashscope:qwen3.5-plus"
DEFAULT_SUB_MODEL = "dashscope:qwen3.6-plus"
DEFAULT_WRITE_MODEL = "dashscope:qwen-flash"
DEFAULT_SUMMARY_MODEL = "dashscope:qwen-flash"
DEFAULT_REPORT_MODEL = "dashscope:qwen3.5-plus"
DEFAULT_WEEK_MODEL = "dashscope:qwen3.6-plus"


class ContextV2(BaseModel):
    """V2 运行时配置。`extra='ignore'` 让 ag_ui_langgraph 注入的 thread_id 等系统字段
    被自动忽略。`arbitrary_types_allowed=True` 让 PetInformation 这类自定义模型可作字段类型。
    """

    model_config = ConfigDict(extra="ignore", arbitrary_types_allowed=True)

    user_id: Annotated[str, "用户ID"] = "Test"
    pet_information: Annotated[Optional[PetInformation], "宠物信息"] = None

    # ── 模型配置 ──
    plan_model: Annotated[str, "研究规划器模型"] = DEFAULT_PLAN_MODEL
    sub_model: Annotated[str, "子智能体模型"] = DEFAULT_SUB_MODEL
    write_model: Annotated[str, "笔记写入模型"] = DEFAULT_WRITE_MODEL
    summary_model: Annotated[str, "摘要模型"] = DEFAULT_SUMMARY_MODEL
    report_model: Annotated[str, "结构化报告模型"] = DEFAULT_REPORT_MODEL
    week_model: Annotated[str, "周规划器模型"] = DEFAULT_WEEK_MODEL

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
    structure_report_prompt: Annotated[str, "结构化解析提示词"] = STRUCTURE_REPORT_PROMPT
