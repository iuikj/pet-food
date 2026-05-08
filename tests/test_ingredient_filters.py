import pytest
from pydantic import ValidationError

from src.agent.v2.tools.ingredient_filters import (
    IngredientCategory,
    IngredientSearchInput,
    IngredientSubCategory,
)


def test_ingredient_search_input_accepts_valid_category_pair():
    data = IngredientSearchInput(category="谷薯果蔬", sub_category="蔬菜")

    assert data.category is IngredientCategory.GRAIN_TUBER_FRUIT_VEG
    assert data.sub_category is IngredientSubCategory.VEGETABLE


@pytest.mark.parametrize("category", ["蔬菜", "海鲜", "蛋类", "骨头"])
def test_ingredient_search_input_rejects_unknown_categories(category):
    with pytest.raises(ValidationError):
        IngredientSearchInput(category=category)


def test_ingredient_search_input_rejects_invalid_category_pair():
    with pytest.raises(ValidationError, match="白肉.*牛"):
        IngredientSearchInput(category="白肉", sub_category="牛")


def test_ingredient_search_input_requires_category_for_other_subcategory():
    with pytest.raises(ValidationError, match="其他"):
        IngredientSearchInput(sub_category="其他")

