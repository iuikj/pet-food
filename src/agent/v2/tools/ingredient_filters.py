"""Ingredient search enums and input validation for v2 agent tools."""
from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, Field, model_validator


class IngredientCategory(str, Enum):
    """Available values in Ingredient.category."""

    ORGAN = "内脏"
    COMMON = "常用"
    WHITE_MEAT = "白肉"
    RED_MEAT = "红肉"
    CUSTOM = "自定义"
    GRAIN_TUBER_FRUIT_VEG = "谷薯果蔬"
    FISH = "鱼类"


class IngredientSubCategory(str, Enum):
    """Available values in Ingredient.sub_category."""

    LIVER = "肝脏"
    INGREDIENT = "食材"
    RABBIT = "兔"
    OTHER = "其他"
    TURKEY = "火鸡"
    EGG = "蛋"
    CHICKEN = "鸡"
    DUCK = "鸭"
    OSTRICH = "鸵鸟"
    GOOSE = "鹅"
    BEEF = "牛"
    PORK = "猪"
    LAMB = "羊"
    VENISON = "鹿"
    DAIRY = "奶制品"
    FRUIT = "水果"
    SEED = "籽"
    MUSHROOM = "菌菇"
    VEGETABLE = "蔬菜"
    TUBER = "薯类"
    GRAIN = "谷物"
    BEAN = "豆类"
    SPANISH_MACKEREL = "马鲛"
    SALMON = "鲑鱼"
    MACKEREL = "鲭鱼"
    HERRING = "鲱鱼"


INGREDIENT_SUB_CATEGORIES_BY_CATEGORY: dict[
    IngredientCategory, tuple[IngredientSubCategory, ...]
] = {
    IngredientCategory.ORGAN: (IngredientSubCategory.LIVER,),
    IngredientCategory.COMMON: (IngredientSubCategory.INGREDIENT,),
    IngredientCategory.WHITE_MEAT: (
        IngredientSubCategory.RABBIT,
        IngredientSubCategory.OTHER,
        IngredientSubCategory.TURKEY,
        IngredientSubCategory.EGG,
        IngredientSubCategory.CHICKEN,
        IngredientSubCategory.DUCK,
        IngredientSubCategory.OSTRICH,
        IngredientSubCategory.GOOSE,
    ),
    IngredientCategory.RED_MEAT: (
        IngredientSubCategory.OTHER,
        IngredientSubCategory.BEEF,
        IngredientSubCategory.PORK,
        IngredientSubCategory.LAMB,
        IngredientSubCategory.VENISON,
    ),
    IngredientCategory.CUSTOM: (
        IngredientSubCategory.OTHER,
        IngredientSubCategory.DAIRY,
    ),
    IngredientCategory.GRAIN_TUBER_FRUIT_VEG: (
        IngredientSubCategory.FRUIT,
        IngredientSubCategory.SEED,
        IngredientSubCategory.MUSHROOM,
        IngredientSubCategory.VEGETABLE,
        IngredientSubCategory.TUBER,
        IngredientSubCategory.GRAIN,
        IngredientSubCategory.BEAN,
    ),
    IngredientCategory.FISH: (
        IngredientSubCategory.OTHER,
        IngredientSubCategory.SPANISH_MACKEREL,
        IngredientSubCategory.SALMON,
        IngredientSubCategory.MACKEREL,
        IngredientSubCategory.HERRING,
    ),
}


class IngredientSearchInput(BaseModel):
    """Validated input schema for ingredient_search_tool."""

    allowed_sub_categories: ClassVar[
        dict[IngredientCategory, tuple[IngredientSubCategory, ...]]
    ] = INGREDIENT_SUB_CATEGORIES_BY_CATEGORY

    keyword: str | None = Field(
        default=None,
        description="食材名称关键词(模糊匹配)，如'鸡''三文鱼'",
    )
    category: IngredientCategory | None = Field(
        default=None,
        description="大类别，只能从数据库现有大类选择。",
    )
    sub_category: IngredientSubCategory | None = Field(
        default=None,
        description="子类别，只能从数据库现有子类选择；使用'其他'时必须同时指定大类别。",
    )
    protein_min: float | None = Field(
        default=None,
        ge=0,
        description="蛋白质最小值(g/100g)",
    )
    protein_max: float | None = Field(
        default=None,
        ge=0,
        description="蛋白质最大值(g/100g)",
    )
    fat_min: float | None = Field(
        default=None,
        ge=0,
        description="脂肪最小值(g/100g)",
    )
    fat_max: float | None = Field(
        default=None,
        ge=0,
        description="脂肪最大值(g/100g)",
    )
    calcium_min: float | None = Field(
        default=None,
        ge=0,
        description="钙最低值(mg/100g)",
    )
    taurine_min: float | None = Field(
        default=None,
        ge=0,
        description="牛磺酸最低值(mg/100g)，猫粮选材常用",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=50,
        description="返回条数上限",
    )

    @model_validator(mode="after")
    def validate_category_pair(self) -> "IngredientSearchInput":
        """Reject invalid category/sub_category combinations before querying."""
        if self.sub_category is IngredientSubCategory.OTHER and self.category is None:
            raise ValueError("子类别为'其他'时必须同时指定大类别。")

        if self.category is None or self.sub_category is None:
            return self

        allowed = self.allowed_sub_categories[self.category]
        if self.sub_category not in allowed:
            allowed_text = "、".join(item.value for item in allowed)
            raise ValueError(
                f"'{self.category.value}' 下没有子类别 '{self.sub_category.value}'；"
                f"可用子类别：{allowed_text}。"
            )
        return self

