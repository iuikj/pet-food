"""
饮食记录路由

处理餐食记录的创建、查询、打卡等请求
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.api.middleware.auth import get_current_user
from src.api.models.response import (
    ApiResponse,
    TodayMealsResponse,
    MealDetail,
    NutritionSummary,
    MealHistoryResponse,
    NutritionAnalysisResponse,
    AIInsight
)
from src.api.services.meal_service import MealService


router = APIRouter()


@router.get("/today", response_model=ApiResponse[TodayMealsResponse], summary="获取今日餐食")
async def get_today_meals(
    pet_id: str = Query(..., description="宠物 ID"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取今日餐食列表

    - **pet_id**: 宠物 ID

    返回今日的所有餐食，包括完成状态和营养摘要
    """
    try:
        meal_service = MealService(db)

        result = await meal_service.get_today_meals(current_user_id, pet_id)

        # 转换餐食详情
        meals = [
            MealDetail(
                id=m["id"],
                type=m["type"],
                name=m.get("details", {}).get("food_items", [{}])[0].get("name", "") if m.get("details", {}).get("food_items") else m["name"],
                time=m["time"],
                description=m["description"],
                calories=m["calories"],
                is_completed=m["is_completed"],
                completed_at=m["completed_at"],
                notes=m.get("notes"),
                food_items=m.get("details", {}).get("food_items"),
                nutrition_data=m.get("details"),
                ai_tip=m.get("details", {}).get("cook_method", "")
            )
            for m in result["meals"]
        ]

        return ApiResponse(
            code=0,
            message="获取成功",
            data=TodayMealsResponse(
                date=result["date"],
                meals=meals,
                nutrition_summary=NutritionSummary(**result["nutrition_summary"])
            )
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": 4001,
                "message": str(e),
                "detail": None
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": 5000,
                "message": "获取今日餐食失败",
                "detail": str(e)
            }
        )


@router.get("/date", response_model=ApiResponse[TodayMealsResponse], summary="获取指定日期餐食")
async def get_meals_by_date(
    pet_id: str = Query(..., description="宠物 ID"),
    target_date: str = Query(..., description="目标日期 YYYY-MM-DD"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取指定日期的餐食列表

    - **pet_id**: 宠物 ID
    - **target_date**: 目标日期 YYYY-MM-DD
    """
    try:
        meal_service = MealService(db)

        # 解析日期
        try:
            parsed_date = date.fromisoformat(target_date)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": 4000,
                    "message": "日期格式错误，请使用 YYYY-MM-DD",
                    "detail": None
                }
            )

        result = await meal_service.get_meals_by_date(current_user_id, pet_id, parsed_date)

        meals = [
            MealDetail(
                id=m["id"],
                type=m["type"],
                name=m.get("details", {}).get("food_items", [{}])[0].get("name", "") if m.get("details", {}).get("food_items") else m["name"],
                time=m["time"],
                description=m["description"],
                calories=m["calories"],
                is_completed=m["is_completed"],
                completed_at=m["completed_at"],
                notes=m.get("notes"),
                food_items=m.get("details", {}).get("food_items"),
                nutrition_data=m.get("details"),
                ai_tip=m.get("details", {}).get("cook_method", "")
            )
            for m in result["meals"]
        ]

        return ApiResponse(
            code=0,
            message="获取成功",
            data=TodayMealsResponse(
                date=result["date"],
                meals=meals,
                nutrition_summary=NutritionSummary(**result["nutrition_summary"])
            )
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": 4001,
                "message": str(e),
                "detail": None
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": 5000,
                "message": "获取餐食失败",
                "detail": str(e)
            }
        )


@router.post("/{meal_id}/complete", response_model=ApiResponse[dict], summary="标记餐食完成")
async def complete_meal(
    meal_id: str,
    notes: Optional[str] = None,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    标记餐食为已完成

    - **meal_id**: 餐食 ID
    - **notes**: 备注（可选）
    """
    try:
        meal_service = MealService(db)

        meal = await meal_service.complete_meal(current_user_id, meal_id, notes)

        if not meal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": 4001,
                    "message": "餐食记录不存在",
                    "detail": None
                }
            )

        return ApiResponse(
            code=0,
            message="标记成功",
            data={
                "meal_id": meal_id,
                "is_completed": True,
                "completed_at": meal.completed_at.isoformat() if meal.completed_at else None
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": 5000,
                "message": "标记餐食失败",
                "detail": str(e)
            }
        )


@router.delete("/{meal_id}/complete", response_model=ApiResponse[dict], summary="取消餐食完成标记")
async def uncomplete_meal(
    meal_id: str,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    取消餐食完成标记

    - **meal_id**: 餐食 ID
    """
    try:
        meal_service = MealService(db)

        meal = await meal_service.uncomplete_meal(current_user_id, meal_id)

        if not meal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": 4001,
                    "message": "餐食记录不存在",
                    "detail": None
                }
            )

        return ApiResponse(
            code=0,
            message="取消成功",
            data={
                "meal_id": meal_id,
                "is_completed": False
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": 5000,
                "message": "取消标记失败",
                "detail": str(e)
            }
        )


@router.get("/history", response_model=ApiResponse[MealHistoryResponse], summary="获取餐食历史")
async def get_meal_history(
    pet_id: str = Query(..., description="宠物 ID"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页大小"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取餐食历史记录

    - **pet_id**: 宠物 ID
    - **start_date**: 开始日期（可选）
    - **end_date**: 结束日期（可选）
    - **page**: 页码（默认 1）
    - **page_size**: 每页大小（默认 10，最大 100）
    """
    try:
        meal_service = MealService(db)

        # 解析日期参数
        parsed_start = None
        parsed_end = None

        if start_date:
            try:
                parsed_start = date.fromisoformat(start_date)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"code": 4000, "message": "开始日期格式错误"}
                )

        if end_date:
            try:
                parsed_end = date.fromisoformat(end_date)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={"code": 4000, "message": "结束日期格式错误"}
                )

        result = await meal_service.get_meal_history(
            user_id=current_user_id,
            pet_id=pet_id,
            start_date=parsed_start,
            end_date=parsed_end,
            page=page,
            page_size=page_size
        )

        return ApiResponse(
            code=0,
            message="获取成功",
            data=MealHistoryResponse(
                total=result["total"],
                page=result["page"],
                page_size=result["page_size"],
                items=result["items"]
            )
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": 4001,
                "message": str(e),
                "detail": None
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": 5000,
                "message": "获取历史记录失败",
                "detail": str(e)
            }
        )
