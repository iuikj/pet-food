"""
V2 Agent 轻量结构化输出模型

week_agent 最终 structured_response 输出 WeekLightPlan，
由 Phase 3 (gather_and_structure) 从 Ingredient 数据库拉取营养数据，
用纯 Python 组装出完整的 WeeklyDietPlan。

设计目标：
- 字段少、嵌套浅，降低 LLM 生成耗时与错误率
- 营养素数值与单位契约完全由 Python 代码保证
- week_agent 只负责"选哪些食材、每餐多少克、餐次时间/烹饪法、文字说明"
"""
from pydantic import BaseModel, Field


class IngredientAllocation(BaseModel):
    """一餐中一种食材的用量。ingredient_name 必须能在 Ingredient 表命中。"""

    ingredient_name: str = Field(
        ...,
        description="食材名称，必须与数据库中 Ingredient.name 完全一致（用 ingredient_search_tool / ingredient_detail_tool 取名）。",
    )
    weight_g: float = Field(..., gt=0, description="本餐中该食材的克数 (g)")
    recommend_reason: str = Field(
        "",
        description="选择该食材的简短理由，可留空",
    )


class MealLight(BaseModel):
    """一餐的轻量描述。周内 7 天此餐内容相同。"""

    oder: int = Field(..., ge=1, description="第几餐 (1-based)")
    time: str = Field(..., description="餐次时间，如 '08:00'")
    cook_method: str = Field(..., description="烹饪方法简述（如低温水煮、清蒸）")
    ingredients: list[IngredientAllocation] = Field(
        ...,
        min_length=1,
        description="本餐食材分配列表",
    )


class WeekLightPlan(BaseModel):
    """week_agent 的最终结构化输出（周内 7 天统一食谱）。"""

    week_number: int = Field(..., ge=1, le=4, description="第几周 (1-4)")
    diet_adjustment_principle: str = Field(
        ..., description="本周饮食调整原则（基于 CoordinationGuide 的 theme / focus_nutrients）"
    )
    meals: list[MealLight] = Field(
        ...,
        min_length=1,
        description="每日餐次列表（通常 2-3 餐），周内 7 天共用此食谱",
    )
    weekly_special_adjustment_note: str = Field(
        "",
        description="本周特殊调整说明（过敏、疾病、阶段变化等），可留空",
    )
    suggestions: list[str] = Field(
        default_factory=list,
        description="本周饮食建议清单（饮水、运动、补剂等），可为空",
    )
