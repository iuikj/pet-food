"""营养分析路由

处理营养数据分析请求
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.api.middleware.auth import get_current_user
from src.api.models.response import (
    ApiResponse,
    NutritionAnalysisResponse,
    NutritionSummary,
    DailyNutritionData,
    TrendChart,
    AIInsight
)
from src.api.services.meal_service import MealService


router = APIRouter()


@router.get("/nutrition", response_model=ApiResponse[NutritionAnalysisResponse], summary="获取营养分析")
async def get_nutrition_analysis(
    pet_id: str = Query(..., description="宠物 ID"),
    period: str = Query("week", pattern=r'^(week|month|year)$', description="时间周期: week/month/year"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取营养分析数据

    - **pet_id**: 宠物 ID
    - **period**: 时间周期 week/month/year（默认 week）

    返回：
    - 营养统计摘要
    - 每日营养数据
    - 趋势图表数据
    - AI 洞察建议
    """
    try:
        meal_service = MealService(db)

        result = await meal_service.get_nutrition_analysis(
            user_id=current_user_id,
            pet_id=pet_id,
            period=period
        )

        # 构造响应数据
        return ApiResponse(
            code=0,
            message="获取成功",
            data=NutritionAnalysisResponse(
                period=result["period"],
                summary=NutritionSummary(**result["summary"]),
                daily_data=[
                    DailyNutritionData(**d) for d in result["daily_data"]
                ],
                trend_chart=TrendChart(**result["trend_chart"]),
                ai_insights=[
                    AIInsight(**insight) for insight in result["ai_insights"]
                ]
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
                "message": "获取营养分析失败",
                "detail": str(e)
            }
        )
