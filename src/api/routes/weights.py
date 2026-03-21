"""
体重记录路由
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.api.middleware.auth import get_current_user
from src.api.models.response import ApiResponse
from src.api.services.weight_service import WeightService

router = APIRouter()


class RecordWeightRequest(BaseModel):
    pet_id: str
    weight: float = Field(..., gt=0, le=500, description="体重 (kg)")
    recorded_date: Optional[date] = Field(None, description="记录日期，默认今天")
    notes: Optional[str] = Field(None, max_length=500, description="备注")


@router.post("/", response_model=ApiResponse[dict], summary="记录体重")
async def record_weight(
    request: RecordWeightRequest,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """记录宠物体重（同日覆盖），同时更新宠物当前体重"""
    try:
        service = WeightService(db)
        result = await service.record_weight(
            user_id=current_user_id,
            pet_id=request.pet_id,
            weight=request.weight,
            recorded_date=request.recorded_date,
            notes=request.notes,
        )
        return ApiResponse(code=0, message="记录成功", data=result)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 404, "message": str(exc), "detail": None},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": -1, "message": "记录体重失败", "detail": str(exc)},
        )


@router.get("/history", response_model=ApiResponse[list], summary="体重历史")
async def get_weight_history(
    pet_id: str = Query(..., description="宠物 ID"),
    days: int = Query(30, ge=1, le=365, description="最近天数"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """获取宠物体重历史记录"""
    try:
        service = WeightService(db)
        result = await service.get_weight_history(
            user_id=current_user_id,
            pet_id=pet_id,
            days=days,
        )
        return ApiResponse(code=0, message="获取成功", data=result)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 404, "message": str(exc), "detail": None},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": -1, "message": "获取体重历史失败", "detail": str(exc)},
        )


@router.get("/latest", response_model=ApiResponse[Optional[dict]], summary="最新体重")
async def get_latest_weight(
    pet_id: str = Query(..., description="宠物 ID"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """获取宠物最新体重记录"""
    try:
        service = WeightService(db)
        result = await service.get_latest_weight(
            user_id=current_user_id,
            pet_id=pet_id,
        )
        return ApiResponse(code=0, message="获取成功", data=result)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 404, "message": str(exc), "detail": None},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": -1, "message": "获取最新体重失败", "detail": str(exc)},
        )


@router.delete("/{record_id}", response_model=ApiResponse[dict], summary="删除体重记录")
async def delete_weight_record(
    record_id: str,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """删除体重记录"""
    try:
        service = WeightService(db)
        deleted_id = await service.delete_weight_record(
            user_id=current_user_id,
            record_id=record_id,
        )
        return ApiResponse(code=0, message="删除成功", data={"record_id": deleted_id})
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 404, "message": str(exc), "detail": None},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": -1, "message": "删除体重记录失败", "detail": str(exc)},
        )
