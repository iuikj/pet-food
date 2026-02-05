"""
日历路由

处理月度日历、周视图等请求
"""
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc

from src.api.dependencies import get_db_session
from src.api.middleware.auth import get_current_user
from src.api.models.response import ApiResponse, MonthlyCalendarResponse, CalendarDayResponse
from src.api.services.meal_service import MealService
from src.db.models import MealRecord, Pet


router = APIRouter()


@router.get("/monthly", response_model=ApiResponse[MonthlyCalendarResponse], summary="获取月度日历")
async def get_monthly_calendar(
    pet_id: str = Query(..., description="宠物 ID"),
    year: Optional[int] = Query(None, ge=2020, le=2100, description="年份，默认当前年"),
    month: Optional[int] = Query(None, ge=1, le=12, description="月份，默认当前月"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取月度日历数据

    - **pet_id**: 宠物 ID
    - **year**: 年份（可选，默认当前年）
    - **month**: 月份（可选，默认当前月）

    返回一个月中每天的计划和完成情况
    """
    try:
        # 验证宠物所有权
        result = await db.execute(
            select(Pet).where(
                and_(
                    Pet.id == pet_id,
                    Pet.user_id == current_user_id,
                    Pet.is_active == True
                )
            )
        )
        pet = result.scalar_one_or_none()

        if not pet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": 3001,
                    "message": "宠物不存在",
                    "detail": None
                }
            )

        # 设置默认年月
        today = date.today()
        year = year or today.year
        month = month or today.month

        # 获取当月天数
        from calendar import monthrange
        days_in_month = monthrange(year, month)[1]

        # 查询当月的所有餐食记录
        month_start = date(year, month, 1)
        month_end = date(year, month, days_in_month)

        meal_result = await db.execute(
            select(MealRecord).where(
                and_(
                    MealRecord.pet_id == pet_id,
                    MealRecord.meal_date >= month_start,
                    MealRecord.meal_date <= month_end
                )
            ).order_by(MealRecord.meal_date)
        )
        meals = meal_result.scalars().all()

        # 按日期分组
        meals_by_date = {}
        for meal in meals:
            d = meal.meal_date
            if d not in meals_by_date:
                meals_by_date[d] = []
            meals_by_date[d].append(meal)

        # 构造日历数据
        days_data = []
        for day in range(1, days_in_month + 1):
            current_date = date(year, month, day)
            day_meals = meals_by_date.get(current_date, [])

            if day_meals:
                total_meals = len(day_meals)
                completed_meals = sum(1 for m in day_meals if m.is_completed)
                completion_rate = (completed_meals / total_meals * 100) if total_meals > 0 else 0

                # 判断状态
                if completion_rate >= 80:
                    status = "excellent"
                elif completion_rate >= 60:
                    status = "good"
                elif completion_rate >= 40:
                    status = "normal"
                else:
                    status = "poor"
            else:
                total_meals = 0
                completed_meals = 0
                completion_rate = 0
                status = "none"

            days_data.append(
                CalendarDayResponse(
                    date=current_date.isoformat(),
                    has_plan=len(day_meals) > 0,
                    completion_rate=int(completion_rate),
                    total_meals=total_meals,
                    completed_meals=completed_meals,
                    status=status
                )
            )

        return ApiResponse(
            code=0,
            message="获取成功",
            data=MonthlyCalendarResponse(
                year=year,
                month=month,
                days=days_data
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": 5000,
                "message": "获取月度日历失败",
                "detail": str(e)
            }
        )


@router.get("/weekly", response_model=ApiResponse[dict], summary="获取周视图数据")
async def get_weekly_calendar(
    pet_id: str = Query(..., description="宠物 ID"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD，默认本周一"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取周视图数据

    - **pet_id**: 宠物 ID
    - **start_date**: 开始日期（可选，默认本周一）

    返回一周的详细餐食数据
    """
    try:
        # 验证宠物所有权
        result = await db.execute(
            select(Pet).where(
                and_(
                    Pet.id == pet_id,
                    Pet.user_id == current_user_id,
                    Pet.is_active == True
                )
            )
        )
        pet = result.scalar_one_or_none()

        if not pet:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": 3001,
                    "message": "宠物不存在",
                    "detail": None
                }
            )

        # 计算周范围
        today = date.today()
        if start_date:
            start = date.fromisoformat(start_date)
        else:
            # 获取本周一
            start = today - timedelta(days=today.weekday())

        end = start + timedelta(days=6)  # 周日

        # 查询一周的餐食记录
        meal_service = MealService(db)

        week_days = []
        for day_offset in range(7):
            current_date = start + timedelta(days=day_offset)

            try:
                result = await meal_service.get_meals_by_date(
                    user_id=current_user_id,
                    pet_id=pet_id,
                    target_date=current_date
                )
            except ValueError:
                # 如果某天没有数据，返回空数据
                result = {"date": current_date.isoformat(), "meals": [], "nutrition_summary": {}}

            # 计算完成率
            meals = result["meals"]
            if meals:
                total_meals = len(meals)
                completed_meals = sum(1 for m in meals if m["is_completed"])
                completion_rate = (completed_meals / total_meals * 100) if total_meals > 0 else 0
            else:
                total_meals = 0
                completed_meals = 0
                completion_rate = 0

            week_days.append({
                "date": current_date.isoformat(),
                "day_of_week": (current_date.weekday() + 1) % 7 or 7,  # 1-7, 周日为7
                "has_plan": len(meals) > 0,
                "completion_rate": int(completion_rate),
                "meals": [
                    {
                        "id": m["id"],
                        "type": m["type"],
                        "name": m["name"],
                        "time": m["time"],
                        "calories": m["calories"],
                        "is_completed": m["is_completed"],
                        "completed_at": m["completed_at"]
                    }
                    for m in meals
                ]
            })

        return ApiResponse(
            code=0,
            message="获取成功",
            data={
                "week_number": start.isocalendar()[1],
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "days": week_days
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": 5000,
                "message": "获取周视图失败",
                "detail": str(e)
            }
        )
