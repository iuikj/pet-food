"""
日历相关接口。

周历接口已经改成单次批量查询，避免按天逐次查库。
"""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.api.middleware.auth import get_current_user
from src.api.models.response import (
    ApiResponse,
    CalendarDayResponse,
    MonthlyCalendarResponse,
)
from src.db.models import MealRecord, Pet


router = APIRouter()

MEAL_TIME_MAP = {
    "breakfast": "08:00",
    "lunch": "12:00",
    "dinner": "18:00",
    "snack": "15:00",
}


async def _get_owned_active_pet(
    db: AsyncSession,
    *,
    pet_id: str,
    user_id: str,
) -> Pet | None:
    """统一校验宠物归属，避免各接口重复拼接校验查询。"""
    result = await db.execute(
        select(Pet).where(
            and_(
                Pet.id == pet_id,
                Pet.user_id == user_id,
                Pet.is_active == True,
            )
        )
    )
    return result.scalar_one_or_none()


@router.get("/monthly", response_model=ApiResponse[MonthlyCalendarResponse], summary="Get monthly calendar")
async def get_monthly_calendar(
    pet_id: str = Query(..., description="Pet ID"),
    year: Optional[int] = Query(None, ge=2020, le=2100, description="Calendar year"),
    month: Optional[int] = Query(None, ge=1, le=12, description="Calendar month"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        # 先做一次宠物归属校验，后续查询只面向当前宠物。
        pet = await _get_owned_active_pet(db, pet_id=pet_id, user_id=current_user_id)
        if not pet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": 3001, "message": "Pet not found", "detail": None},
            )

        today = date.today()
        year = year or today.year
        month = month or today.month

        from calendar import monthrange

        days_in_month = monthrange(year, month)[1]
        month_start = date(year, month, 1)
        month_end = date(year, month, days_in_month)

        # 月历场景一次性拉取当月餐食，再按日期分组。
        meal_result = await db.execute(
            select(MealRecord).where(
                and_(
                    MealRecord.pet_id == pet_id,
                    MealRecord.meal_date >= month_start,
                    MealRecord.meal_date <= month_end,
                )
            ).order_by(MealRecord.meal_date)
        )
        meals = meal_result.scalars().all()

        meals_by_date: dict[date, list[MealRecord]] = {}
        for meal in meals:
            meals_by_date.setdefault(meal.meal_date, []).append(meal)

        days_data = []
        for day in range(1, days_in_month + 1):
            current_date = date(year, month, day)
            day_meals = meals_by_date.get(current_date, [])

            if day_meals:
                total_meals = len(day_meals)
                completed_meals = sum(1 for meal in day_meals if meal.is_completed)
                completion_rate = (completed_meals / total_meals * 100) if total_meals > 0 else 0

                if completion_rate >= 80:
                    day_status = "excellent"
                elif completion_rate >= 60:
                    day_status = "good"
                elif completion_rate >= 40:
                    day_status = "normal"
                else:
                    day_status = "poor"
            else:
                total_meals = 0
                completed_meals = 0
                completion_rate = 0
                day_status = "none"

            days_data.append(
                CalendarDayResponse(
                    date=current_date.isoformat(),
                    has_plan=len(day_meals) > 0,
                    completion_rate=int(completion_rate),
                    total_meals=total_meals,
                    completed_meals=completed_meals,
                    status=day_status,
                )
            )

        return ApiResponse(
            code=0,
            message="Monthly calendar retrieved successfully",
            data=MonthlyCalendarResponse(year=year, month=month, days=days_data),
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 5000, "message": "Failed to load monthly calendar", "detail": str(exc)},
        )


@router.get("/weekly", response_model=ApiResponse[dict], summary="Get weekly calendar")
async def get_weekly_calendar(
    pet_id: str = Query(..., description="Pet ID"),
    start_date: Optional[str] = Query(None, description="Week start date in YYYY-MM-DD"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        # 周历同样先做一次宠物归属校验。
        pet = await _get_owned_active_pet(db, pet_id=pet_id, user_id=current_user_id)
        if not pet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": 3001, "message": "Pet not found", "detail": None},
            )

        today = date.today()
        start = date.fromisoformat(start_date) if start_date else today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)

        # 一次性查询整周餐食，替代原来的按天 N+1 查询。
        meal_result = await db.execute(
            select(MealRecord).where(
                and_(
                    MealRecord.pet_id == pet_id,
                    MealRecord.meal_date >= start,
                    MealRecord.meal_date <= end,
                )
            ).order_by(MealRecord.meal_date, MealRecord.meal_order)
        )
        week_meals = meal_result.scalars().all()

        # 将结果按日期分桶，后续循环只做内存读取。
        meals_by_date: dict[date, list[MealRecord]] = {}
        for meal in week_meals:
            meals_by_date.setdefault(meal.meal_date, []).append(meal)

        week_days = []
        for day_offset in range(7):
            current_date = start + timedelta(days=day_offset)
            day_meals = meals_by_date.get(current_date, [])
            total_meals = len(day_meals)
            completed_meals = sum(1 for meal in day_meals if meal.is_completed)
            completion_rate = (completed_meals / total_meals * 100) if total_meals > 0 else 0

            week_days.append(
                {
                    "date": current_date.isoformat(),
                    "day_of_week": (current_date.weekday() + 1) % 7 or 7,
                    "has_plan": total_meals > 0,
                    "completion_rate": int(completion_rate),
                    "meals": [
                        {
                            "id": meal.id,
                            "type": meal.meal_type,
                            "name": meal.food_name,
                            "time": MEAL_TIME_MAP.get(meal.meal_type, ""),
                            "calories": meal.calories,
                            "is_completed": meal.is_completed,
                            "completed_at": meal.completed_at.isoformat() if meal.completed_at else None,
                        }
                        for meal in day_meals
                    ],
                }
            )

        return ApiResponse(
            code=0,
            message="Weekly calendar retrieved successfully",
            data={
                "week_number": start.isocalendar()[1],
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "days": week_days,
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 5000, "message": "Failed to load weekly calendar", "detail": str(exc)},
        )
