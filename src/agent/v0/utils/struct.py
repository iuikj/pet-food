from typing import Dict, Literal

from pydantic import BaseModel, Field

from src.utils.strtuct import PetInformation


class Macronutrients(BaseModel):
    protein: float = Field(description="Protein in grams (g)")
    fat: float = Field(description="Fat in grams (g)")
    carbohydrates: float = Field(description="Carbohydrates in grams (g)")
    dietary_fiber: float = Field(description="Dietary fiber in grams (g)")


class NutrientAmount(BaseModel):
    value: float = Field(description="Nutrient amount")
    unit: str = Field(description="Unit for the nutrient amount")


class Micronutrients(BaseModel):
    vitamin_a: NutrientAmount = Field(
        description="Vitamin A amount. Use unit IU."
    )
    vitamin_c: NutrientAmount = Field(
        description="Vitamin C amount. Use unit mg."
    )
    vitamin_d: NutrientAmount = Field(
        description="Vitamin D amount. Use unit IU."
    )
    calcium: NutrientAmount = Field(
        description="Calcium amount. Use unit mg."
    )
    iron: NutrientAmount = Field(
        description="Iron amount. Use unit mg."
    )
    sodium: NutrientAmount = Field(
        description="Sodium amount. Use unit mg."
    )
    potassium: NutrientAmount = Field(
        description="Potassium amount. Use unit mg."
    )
    cholesterol: NutrientAmount = Field(
        description="Cholesterol amount. Use unit mg."
    )
    additional_nutrients: Dict[str, NutrientAmount] = Field(
        default_factory=dict,
        description=(
            "Additional nutrients keyed by display name. "
            "Each item must include both value and unit, for example Omega-3 (g), "
            "selenium (ug), vitamin E (mg), zinc (mg), probiotics (CFU)."
        ),
    )


class FoodItem(BaseModel):
    name: str
    weight: float = Field(description="Food weight in grams (g)")
    macro_nutrients: Macronutrients = Field(description="Macro nutrients")
    micro_nutrients: Micronutrients = Field(description="Micro nutrients")
    recommend_reason: str = Field(description="Why this food is recommended")


class SingleMealPlan(BaseModel):
    oder: int = Field(description="Meal order in the day")
    time: str = Field(description="Meal time")
    food_items: list[FoodItem] = Field(description="Food items for the meal")
    cook_method: str = Field(description="Cooking method")


class DailyDietPlan(BaseModel):
    daily_diet_plans: list[SingleMealPlan] = Field(
        description="Daily meal plan for the pet"
    )


class WeeklyDietPlan(BaseModel):
    oder: int = Field(description="Week order")
    diet_adjustment_principle: str = Field(
        description="Adjustment principle for the week"
    )
    weekly_diet_plan: DailyDietPlan = Field(description="Weekly diet plan")
    weekly_special_adjustment_note: str = Field(
        description="Special adjustment notes for the week"
    )
    suggestions: list[str] = Field(description="Supporting suggestions")


class MonthlyDietPlan(BaseModel):
    monthly_diet_plan: list[WeeklyDietPlan] = Field(
        description="Monthly diet plan grouped by week",
        max_length=4,
    )


class PetDietPlan(BaseModel):
    pet_information: PetInformation = Field(description="Pet information")
    ai_suggestions: str = Field(description="AI suggestions")
    pet_diet_plan: MonthlyDietPlan = Field(description="Pet diet plan")
