"""
营养计算子 Agent

供 plan_agent 在研究阶段使用，用于初步评估宠物营养需求。
基于 RER 公式和 AAFCO 标准计算热量与微量营养素目标。
"""
from deepagents import SubAgent

from src.agent.v2.tools.nutrition_tools import (
    daily_calorie_tool,
    nutrition_requirement_tool,
)

nutrition_calc_sub_agent = SubAgent(
    name="nutrition-calculator",
    tools=[daily_calorie_tool, nutrition_requirement_tool],
    system_prompt=(
        "你是一个宠物营养计算专家。根据用户提供的宠物信息，"
        "精确计算每日热量需求和各项营养素目标。"
        "先调用 daily_calorie_tool 计算热量，再用 nutrition_requirement_tool 获取微量营养素标准。"
    ),
    description=(
        "宠物营养计算子agent，基于 RER 公式和 AAFCO 标准计算："
        "(1) 每日热量需求和宏量营养素目标 (daily_calorie_tool) "
        "(2) 微量营养素最低需求量 (nutrition_requirement_tool)。"
        "适用于需要了解宠物精确营养目标的场景。"
    ),
)
