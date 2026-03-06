"""
V1 架构数据模型

定义研究阶段到并行执行阶段的协调数据结构。
"""
from pydantic import BaseModel, Field


class WeekAssignment(BaseModel):
    """单周任务分配，由 CoordinationGuide 生成"""

    week_number: int = Field(description="第几周 (1-4)")
    theme: str = Field(description="本周饮食主题，如'高蛋白恢复期'、'均衡营养维持期'")
    focus_nutrients: list[str] = Field(description="本周重点关注的营养素列表")
    constraints: list[str] = Field(description="本周的饮食约束条件")
    differentiation_note: str = Field(
        description="与其他周的差异化说明，确保四周互不重复"
    )
    search_keywords: list[str] = Field(
        description="建议的搜索关键词，供 week_agent 使用 tavily_search"
    )


class CoordinationGuide(BaseModel):
    """协调指南 — 研究阶段完成后生成，指导 4 周并行计划"""

    overall_principle: str = Field(description="整体饮食规划原则")
    weekly_assignments: list[WeekAssignment] = Field(
        description="四周任务分配列表",
        min_length=4,
        max_length=4,
    )
    shared_constraints: list[str] = Field(
        description="所有周共享的约束条件（如过敏食材、禁忌等）"
    )
    ingredient_rotation_strategy: str = Field(
        description="食材轮换策略，确保四周食材多样性"
    )
    age_adaptation_note: str = Field(
        description="年龄适应说明，考虑宠物在一个月内的生长变化"
    )
