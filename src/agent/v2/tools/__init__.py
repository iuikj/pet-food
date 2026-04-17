"""
V2 Agent 工具集

提供营养计算、食材查询等工具。
"""
from src.agent.v2.tools.nutrition_tools import (
    daily_calorie_tool,
    nutrition_requirement_tool,
)
from src.agent.v2.tools.ingredient_tools import (
    ingredient_search_tool,
    ingredient_detail_tool,
    ingredient_categories_tool,
)

# week_agent 可用的全部工具
# 注意：
# - 已移除 rag_search_tool（占位实现，未接入 Milvus 前暂不暴露）
# - 已移除 write_week_plan（Phase 3 改为从 response_format=WeekLightPlan 直接拿结构化结果）
WEEK_AGENT_TOOLS = [
    daily_calorie_tool,
    nutrition_requirement_tool,
    ingredient_search_tool,
    ingredient_detail_tool,
    ingredient_categories_tool,
]

__all__ = [
    "daily_calorie_tool",
    "nutrition_requirement_tool",
    "ingredient_search_tool",
    "ingredient_detail_tool",
    "ingredient_categories_tool",
    "WEEK_AGENT_TOOLS",
]
