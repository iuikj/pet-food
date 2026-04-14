"""
食材查询子 Agent

供 plan_agent 在研究阶段使用，用于探索可用食材和营养数据。
所有数据来自真实 PostgreSQL 数据库，基于每 100g 可食部分。
"""
from deepagents import SubAgent

from src.agent.v2.tools.ingredient_tools import (
    ingredient_search_tool,
    ingredient_detail_tool,
    ingredient_categories_tool,
)

ingredient_query_sub_agent = SubAgent(
    name="ingredient-query",
    tools=[ingredient_search_tool, ingredient_detail_tool, ingredient_categories_tool],
    system_prompt=(
        "你是一个食材营养数据库查询专家。根据用户需求，"
        "高效检索食材营养数据。所有数据基于每 100g 可食部分。"
        "先用 ingredient_categories_tool 了解可用分类，"
        "再用 ingredient_search_tool 按条件搜索，"
        "最后用 ingredient_detail_tool 获取关键食材的完整营养数据。"
    ),
    description=(
        "食材数据库查询子agent，可以："
        "(1) 按类别/关键词/营养素范围搜索食材 (ingredient_search_tool) "
        "(2) 获取食材完整营养数据 (ingredient_detail_tool) "
        "(3) 查看所有可用食材分类 (ingredient_categories_tool)。"
        "所有数据来自真实数据库。"
    ),
)
