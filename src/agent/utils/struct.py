from typing import Dict

from pydantic import BaseModel, Field


class Macronutrients(BaseModel):
    """
    宏观营养素
    """
    protein: float = Field(description="蛋白质 (克)")
    fat: float = Field(description="脂肪 (克)")
    carbohydrates: float = Field(description="碳水化合物 (克)")
    dietary_fiber: float = Field(description="膳食纤维(g)")


class Micronutrients(BaseModel):
    """
    微量营养素
    """
    vitamin_a: float = Field(description="维生素A含量(mg)")
    vitamin_c: float = Field(description="维生素C含量(mg)")
    vitamin_d: float = Field(description="维生素D含量(mg)")
    calcium: float = Field(description="钙含量(mg)")
    iron: float = Field(description="铁含量(mg)")
    sodium: float = Field(description="钠(mg)")
    potassium: float = Field(description="钾(mg)")
    cholesterol: float = Field(description="胆固醇(mg)")
    additional_nutrients: Dict[str, float] = Field(description="其他营养素")
    # 可继续添加其它字段...


class FoodItem(BaseModel):
    name: str
    weight: float = Field(description="重量(g)")
    macro_nutrients: Macronutrients = Field(description="macro nutrients")
    micro_nutrients: Micronutrients = Field(description="micro nutrients")
    recommend_reason: str = Field(description="推荐理由")


class SingleMealPlan(BaseModel):
    """
    每餐计划
    """
    oder: int = Field(description="第几餐")
    time: str = Field(description="时间")
    food_items: list[FoodItem] = Field(description="食物列表")
    cook_method: str = Field(description="烹饪方式")


class DailyDietPlan(BaseModel):
    """
    每天计划
    """
    daily_diet_plans: list[SingleMealPlan] = Field(description="每天宠物饮食计划")


class WeeklyDietPlan(BaseModel):
    """
    每周计划
    """
    oder: int = Field(description="第几周")
    diet_adjustment_principle: str = Field(description="本周饮食调整建议")
    weekly_diet_plan: DailyDietPlan = Field(description="周宠物饮食计划,一周的饮食保持一致")
    weekly_special_adjustment_note: str = Field(description="本周周特殊调整说明")
    suggestions: list = Field(description="配套建议")


class MonthlyDietPlan(BaseModel):
    """
    月度计划
    """
    monthly_diet_plan: list[WeeklyDietPlan] = Field(description="每月宠物饮食计划,分为多周，各周之间计划可能不同",
                                                    max_length=4)


class PetInformation(BaseModel):
    """
    宠物信息
    """
    pet_type: str = Field(description="宠物类型，如猫、狗等")
    pet_breed: str = Field(description="宠物品种,如马尔济斯")
    age: str = Field(description="宠物年龄")
    pet_weight: float = Field(description="宠物体重")
    pet_health_status: str = Field(description="宠物健康状态")


class PetDietPlan(BaseModel):
    pet_information: PetInformation = Field(description="宠物信息")
    ai_suggestions: str = Field(description="AI建议")  # 使用最后的总结，即最新的message信息
    pet_diet_plan: MonthlyDietPlan = Field(description="宠物饮食计划")