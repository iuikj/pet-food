"""
饮食记录服务

处理餐食记录的 CRUD 操作和营养统计
"""
import uuid
from typing import Optional
from datetime import datetime, date, timedelta
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import MealRecord, Pet, DietPlan


class MealService:
    """餐食记录服务类"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_meal_records_from_plan(
        self,
        user_id: str,
        pet_id: str,
        plan_id: str,
        plan_data: dict
    ) -> list[MealRecord]:
        """
        从饮食计划创建餐食记录（30天）

        Args:
            user_id: 用户 ID
            pet_id: 宠物 ID
            plan_id: 计划 ID
            plan_data: 计划数据 (PetDietPlan 结构）

        Returns:
            创建的餐食记录列表
        """
        records = []
        start_date = date.today()

        # 提取月度计划
        monthly_plan = plan_data.get("pet_diet_plan", {})
        monthly_diet_plan = monthly_plan.get("monthly_diet_plan", [])

        for day_offset in range(30):  # 30 天
            meal_date = start_date + timedelta(days=day_offset)

            # 选择对应的周计划（每 7 天换一周）
            week_index = min(day_offset // 7, len(monthly_diet_plan) - 1)
            week_plan = monthly_diet_plan[week_index] if monthly_diet_plan else None

            if week_plan:
                daily_plan = week_plan.get("weekly_diet_plan", {})
                daily_meals = daily_plan.get("daily_diet_plans", [])

                meal_order = 1
                for meal in daily_meals:
                    meal_type = self._meal_order_to_type(meal_order)

                    # 提取营养信息
                    food_items = meal.get("food_items", [])
                    total_calories = 0
                    macro_nutrients = {
                        "protein": 0,
                        "fat": 0,
                        "carbs": 0,
                        "fiber": 0
                    }
                    micro_nutrients = {
                        "vitamin_a": 0,
                        "vitamin_c": 0,
                        "vitamin_d": 0,
                        "calcium": 0,
                        "iron": 0,
                        "sodium": 0,
                        "potassium": 0,
                        "cholesterol": 0
                    }

                    for item in food_items:
                        weight = item.get("weight", 0)
                        macro = item.get("macro_nutrients", {})
                        micro = item.get("micro_nutrients", {})

                        total_calories += (macro.get("protein", 0) * 4 +
                                          macro.get("fat", 0) * 9 +
                                          macro.get("carbohydrates", 0) * 4)

                        macro_nutrients["protein"] += macro.get("protein", 0)
                        macro_nutrients["fat"] += macro.get("fat", 0)
                        macro_nutrients["carbs"] += macro.get("carbohydrates", 0)
                        macro_nutrients["fiber"] += macro.get("dietary_fiber", 0)

                        micro_nutrients["vitamin_a"] += micro.get("vitamin_a", 0)
                        micro_nutrients["vitamin_c"] += micro.get("vitamin_c", 0)
                        micro_nutrients["vitamin_d"] += micro.get("vitamin_d", 0)
                        micro_nutrients["calcium"] += micro.get("calcium", 0)
                        micro_nutrients["iron"] += micro.get("iron", 0)
                        micro_nutrients["sodium"] += micro.get("sodium", 0)
                        micro_nutrients["potassium"] += micro.get("potassium", 0)
                        micro_nutrients["cholesterol"] += micro.get("cholesterol", 0)

                    # 构造营养数据
                    nutrition_data = {
                        "macro_nutrients": macro_nutrients,
                        "micro_nutrients": micro_nutrients,
                        "food_items": food_items,
                        "cook_method": meal.get("cook_method", ""),
                        "recommend_reason": meal.get("recommend_reason", "")
                    }

                    record = MealRecord(
                        id=str(uuid.uuid4()),
                        pet_id=pet_id,
                        plan_id=plan_id,
                        meal_date=meal_date,
                        meal_type=meal_type,
                        meal_order=meal_order,
                        food_name=f"第 {week_index + 1} 周 - {meal.get('name', '')}",
                        description=meal.get("description", ""),
                        calories=total_calories,
                        nutrition_data=nutrition_data,
                        is_completed=False
                    )
                    self.db.add(record)
                    records.append(record)
                    meal_order += 1

        await self.db.commit()
        return records

    def _meal_order_to_type(self, order: int) -> str:
        """将餐序号转换为类型"""
        mapping = {1: "breakfast", 2: "lunch", 3: "dinner", 4: "snack"}
        return mapping.get(order, "snack")

    async def get_today_meals(
        self,
        user_id: str,
        pet_id: str
    ) -> dict:
        """
        获取今日餐食

        Args:
            user_id: 用户 ID
            pet_id: 宠物 ID

        Returns:
            今日餐食数据，包含餐食列表和营养摘要
        """
        # 验证宠物所有权
        pet = await self._verify_pet_ownership(user_id, pet_id)
        if not pet:
            raise ValueError("宠物不存在")

        today = date.today()

        # 查询今日餐食
        result = await self.db.execute(
            select(MealRecord).where(
                and_(
                    MealRecord.pet_id == pet_id,
                    MealRecord.meal_date == today
                )
            ).order_by(MealRecord.meal_order)
        )
        meals = result.scalars().all()

        # 计算营养摘要
        nutrition_summary = await self._calculate_nutrition_summary(meals)

        return {
            "date": today.isoformat(),
            "meals": [
                {
                    "id": meal.id,
                    "type": meal.meal_type,
                    "name": meal.food_name,
                    "time": self._get_meal_time(meal.meal_type),
                    "description": meal.description,
                    "calories": meal.calories,
                    "is_completed": meal.is_completed,
                    "completed_at": meal.completed_at.isoformat() if meal.completed_at else None,
                    "notes": meal.notes,
                    "details": meal.nutrition_data or {}
                }
                for meal in meals
            ],
            "nutrition_summary": nutrition_summary
        }

    async def get_meals_by_date(
        self,
        user_id: str,
        pet_id: str,
        target_date: date
    ) -> dict:
        """
        获取指定日期的餐食

        Args:
            user_id: 用户 ID
            pet_id: 宠物 ID
            target_date: 目标日期

        Returns:
            指定日期的餐食数据
        """
        # 验证宠物所有权
        pet = await self._verify_pet_ownership(user_id, pet_id)
        if not pet:
            raise ValueError("宠物不存在")

        result = await self.db.execute(
            select(MealRecord).where(
                and_(
                    MealRecord.pet_id == pet_id,
                    MealRecord.meal_date == target_date
                )
            ).order_by(MealRecord.meal_order)
        )
        meals = result.scalars().all()

        nutrition_summary = await self._calculate_nutrition_summary(meals)

        return {
            "date": target_date.isoformat(),
            "meals": [
                {
                    "id": meal.id,
                    "type": meal.meal_type,
                    "name": meal.food_name,
                    "time": self._get_meal_time(meal.meal_type),
                    "description": meal.description,
                    "calories": meal.calories,
                    "is_completed": meal.is_completed,
                    "completed_at": meal.completed_at.isoformat() if meal.completed_at else None,
                    "notes": meal.notes,
                    "details": meal.nutrition_data or {}
                }
                for meal in meals
            ],
            "nutrition_summary": nutrition_summary
        }

    async def complete_meal(
        self,
        user_id: str,
        meal_id: str,
        notes: Optional[str] = None
    ) -> Optional[MealRecord]:
        """
        标记餐食完成

        Args:
            user_id: 用户 ID
            meal_id: 餐食 ID
            notes: 备注

        Returns:
            更新后的餐食记录，不存在返回 None
        """
        meal = await self._verify_meal_ownership(user_id, meal_id)
        if not meal:
            return None

        meal.is_completed = True
        meal.completed_at = datetime.utcnow()
        if notes is not None:
            meal.notes = notes

        await self.db.commit()
        await self.db.refresh(meal)
        return meal

    async def uncomplete_meal(
        self,
        user_id: str,
        meal_id: str
    ) -> Optional[MealRecord]:
        """
        取消餐食完成标记

        Args:
            user_id: 用户 ID
            meal_id: 餐食 ID

        Returns:
            更新后的餐食记录，不存在返回 None
        """
        meal = await self._verify_meal_ownership(user_id, meal_id)
        if not meal:
            return None

        meal.is_completed = False
        meal.completed_at = None

        await self.db.commit()
        await self.db.refresh(meal)
        return meal

    async def get_meal_history(
        self,
        user_id: str,
        pet_id: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        page: int = 1,
        page_size: int = 10
    ) -> dict:
        """
        获取餐食历史记录

        Args:
            user_id: 用户 ID
            pet_id: 宠物 ID
            start_date: 开始日期
            end_date: 结束日期
            page: 页码
            page_size: 每页大小

        Returns:
            餐食历史记录
        """
        # 验证宠物所有权
        pet = await self._verify_pet_ownership(user_id, pet_id)
        if not pet:
            raise ValueError("宠物不存在")

        # 构建查询
        query = select(MealRecord).where(MealRecord.pet_id == pet_id)

        if start_date:
            query = query.where(MealRecord.meal_date >= start_date)
        if end_date:
            query = query.where(MealRecord.meal_date <= end_date)

        # 获取总数
        count_result = await self.db.execute(
            select(func.count()).select_from(query.alias())
        )
        total = count_result.scalar()

        # 分页查询
        offset = (page - 1) * page_size
        query = query.order_by(desc(MealRecord.meal_date), desc(MealRecord.meal_order))
        query = query.offset(offset).limit(page_size)

        result = await self.db.execute(query)
        meals = result.scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": meal.id,
                    "pet_id": meal.pet_id,
                    "meal_date": meal.meal_date.isoformat(),
                    "meal_type": meal.meal_type,
                    "calories": meal.calories,
                    "is_completed": meal.is_completed,
                    "completed_at": meal.completed_at.isoformat() if meal.completed_at else None,
                    "food_name": meal.food_name
                }
                for meal in meals
            ]
        }

    async def get_nutrition_analysis(
        self,
        user_id: str,
        pet_id: str,
        period: str = "week"
    ) -> dict:
        """
        获取营养分析数据

        Args:
            user_id: 用户 ID
            pet_id: 宠物 ID
            period: 时间周期 week/month/year

        Returns:
            营养分析数据
        """
        # 验证宠物所有权
        pet = await self._verify_pet_ownership(user_id, pet_id)
        if not pet:
            raise ValueError("宠物不存在")

        # 计算日期范围
        end_date = date.today()
        if period == "week":
            start_date = end_date - timedelta(days=7)
            days_range = 7
        elif period == "month":
            start_date = end_date - timedelta(days=30)
            days_range = 30
        else:  # year
            start_date = end_date - timedelta(days=365)
            days_range = 365

        # 查询时间段内的餐食记录
        result = await self.db.execute(
            select(MealRecord).where(
                and_(
                    MealRecord.pet_id == pet_id,
                    MealRecord.meal_date >= start_date,
                    MealRecord.meal_date <= end_date
                )
            ).order_by(MealRecord.meal_date)
        )
        meals = result.scalars().all()

        # 计算每日数据
        daily_data = []
        for i in range(days_range):
            d = start_date + timedelta(days=i)
            day_meals = [m for m in meals if m.meal_date == d]

            if day_meals:
                total_calories = sum(m.calories or 0 for m in day_meals)
                completed_count = sum(1 for m in day_meals if m.is_completed)
                total_meals = len(day_meals)
                completion_rate = (completed_count / total_meals * 100) if total_meals > 0 else 0

                # 聚合营养素
                protein = 0
                fat = 0
                carbs = 0
                for m in day_meals:
                    nutr = m.nutrition_data or {}
                    macro = nutr.get("macro_nutrients", {})
                    protein += macro.get("protein", 0)
                    fat += macro.get("fat", 0)
                    carbs += macro.get("carbohydrates", 0)

                daily_data.append({
                    "date": d.isoformat(),
                    "calories": total_calories,
                    "protein": protein,
                    "fat": fat,
                    "carbs": carbs,
                    "completion_rate": round(completion_rate, 1)
                })

        # 计算摘要
        total_days = len(daily_data)
        avg_calories = sum(d["calories"] for d in daily_data) / total_days if total_days > 0 else 0
        avg_completion = sum(d["completion_rate"] for d in daily_data) / total_days if total_days > 0 else 0

        total_protein = sum(d["protein"] for d in daily_data)
        total_fat = sum(d["fat"] for d in daily_data)
        total_carbs = sum(d["carbs"] for d in daily_data)

        # 趋势判断
        if total_days >= 2:
            first_half = daily_data[:total_days // 2]
            second_half = daily_data[total_days // 2:]
            first_avg = sum(d["calories"] for d in first_half) / len(first_half)
            second_avg = sum(d["calories"] for d in second_half) / len(second_half)
            if second_avg > first_avg * 1.1:
                calorie_trend = "increasing"
            elif second_avg < first_avg * 0.9:
                calorie_trend = "decreasing"
            else:
                calorie_trend = "stable"
        else:
            calorie_trend = "stable"

        # 生成 AI 洞察
        ai_insights = self._generate_ai_insights(avg_completion, total_protein, total_fat, total_carbs, total_days)

        # 构造趋势图表数据
        trend_chart = self._build_trend_chart(daily_data)

        return {
            "period": period,
            "summary": {
                "avg_calories": round(avg_calories, 1),
                "avg_completion_rate": round(avg_completion, 1),
                "calorie_trend": calorie_trend,
                "protein_target": round(total_protein * 1.1, 1),
                "protein_consumed": round(total_protein, 1),
                "fat_target": round(total_fat * 1.1, 1),
                "fat_consumed": round(total_fat, 1),
                "carbs_target": round(total_carbs * 1.1, 1),
                "carbs_consumed": round(total_carbs, 1)
            },
            "daily_data": daily_data,
            "trend_chart": trend_chart,
            "ai_insights": ai_insights
        }

    def _verify_pet_ownership(self, user_id: str, pet_id: str) -> Optional[Pet]:
        """验证宠物所有权"""
        result = self.db.execute(
            select(Pet).where(
                and_(
                    Pet.id == pet_id,
                    Pet.user_id == user_id,
                    Pet.is_active == True
                )
            )
        )
        return result.scalar_one_or_none()

    def _verify_meal_ownership(self, user_id: str, meal_id: str) -> Optional[MealRecord]:
        """验证餐食所有权"""
        result = self.db.execute(
            select(MealRecord).join(Pet).where(
                and_(
                    MealRecord.id == meal_id,
                    Pet.user_id == user_id
                )
            )
        )
        return result.scalar_one_or_none()

    async def _calculate_nutrition_summary(self, meals: list) -> dict:
        """计算营养摘要"""
        total_calories = sum(m.calories or 0 for m in meals)
        consumed_calories = sum(m.calories or 0 for m in meals if m.is_completed)

        total_protein = 0
        consumed_protein = 0
        total_fat = 0
        consumed_fat = 0
        total_carbs = 0
        consumed_carbs = 0
        total_fiber = 0
        consumed_fiber = 0

        for meal in meals:
            nutr = meal.nutrition_data or {}
            macro = nutr.get("macro_nutrients", {})

            protein = macro.get("protein", 0)
            fat = macro.get("fat", 0)
            carbs = macro.get("carbohydrates", 0)
            fiber = macro.get("dietary_fiber", 0)

            total_protein += protein
            total_fat += fat
            total_carbs += carbs
            total_fiber += fiber

            if meal.is_completed:
                consumed_protein += protein
                consumed_fat += fat
                consumed_carbs += carbs
                consumed_fiber += fiber

        return {
            "total_calories": total_calories,
            "consumed_calories": consumed_calories,
            "protein": {"target": round(total_protein, 1), "consumed": round(consumed_protein, 1)},
            "fat": {"target": round(total_fat, 1), "consumed": round(consumed_fat, 1)},
            "carbs": {"target": round(total_carbs, 1), "consumed": round(consumed_carbs, 1)},
            "fiber": {"target": round(total_fiber, 1), "consumed": round(consumed_fiber, 1)}
        }

    def _get_meal_time(self, meal_type: str) -> str:
        """根据餐食类型返回建议时间"""
        time_map = {
            "breakfast": "08:00",
            "lunch": "12:00",
            "dinner": "18:00",
            "snack": "15:00"
        }
        return time_map.get(meal_type, "")

    def _generate_ai_insights(self, completion_rate: float, protein: float, fat: float, carbs: float, days: int) -> list:
        """生成 AI 洞察建议"""
        insights = []

        if completion_rate >= 90:
            insights.append({
                "type": "positive",
                "content": f"用餐完成率 {completion_rate:.0f}%，表现优秀！继续保持！"
            })
        elif completion_rate >= 70:
            insights.append({
                "type": "suggestion",
                "content": f"用餐完成率 {completion_rate:.0f}%，可以尝试设定用餐提醒来提高完成率。"
            })
        else:
            insights.append({
                "type": "warning",
                "content": f"用餐完成率较低（{completion_rate:.0f}%），建议检查饮食安排是否合理。"
            })

        # 营养分析
        avg_protein = protein / days if days > 0 else 0
        avg_fat = fat / days if days > 0 else 0
        avg_carbs = carbs / days if days > 0 else 0

        if avg_protein < 50:
            insights.append({
                "type": "suggestion",
                "content": "蛋白质摄入偏低，建议增加鸡肉、鱼肉等高蛋白食材。"
            })

        if avg_fat > 80:
            insights.append({
                "type": "warning",
                "content": "脂肪摄入偏高，建议减少油腻食材，增加蔬菜比例。"
            })

        if avg_carbs < 80:
            insights.append({
                "type": "suggestion",
                "content": "碳水摄入偏低，建议适量增加谷物类主食。"
            })

        return insights

    def _build_trend_chart(self, daily_data: list) -> dict:
        """构造趋势图表数据"""
        labels = []
        calories_data = []
        protein_data = []
        fat_data = []
        carbs_data = []

        for d in daily_data:
            labels.append(d["date"][5:10])  # 只取 MM-DD
            calories_data.append(d["calories"])
            protein_data.append(d["protein"])
            fat_data.append(d["fat"])
            carbs_data.append(d["carbs"])

        return {
            "labels": labels,
            "calories": calories_data,
            "protein": protein_data,
            "fat": fat_data,
            "carbs": carbs_data
        }
