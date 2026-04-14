"""
V2 Agent 工具集

提供营养计算、食材查询、RAG 检索、计划输出等工具。
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
from src.agent.v2.tools.rag_tools import rag_search_tool
from src.agent.v2.tools.plan_output_tools import write_week_plan

# week_agent 可用的全部工具
WEEK_AGENT_TOOLS = [
    daily_calorie_tool,
    nutrition_requirement_tool,
    ingredient_search_tool,
    ingredient_detail_tool,
    ingredient_categories_tool,
    rag_search_tool,
    write_week_plan,
]

__all__ = [
    "daily_calorie_tool",
    "nutrition_requirement_tool",
    "ingredient_search_tool",
    "ingredient_detail_tool",
    "ingredient_categories_tool",
    "rag_search_tool",
    "write_week_plan",
    "WEEK_AGENT_TOOLS",
]
