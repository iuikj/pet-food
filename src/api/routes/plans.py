"""
Diet plan routes.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.api.middleware.auth import get_current_user
from src.api.models.request import CreatePlanRequest
from src.api.models.response import (
    ApiResponse,
    CreateTaskResponse,
    DietPlanDetailResponse,
    DietPlanListResponse,
    PetType,
)
from src.api.services.plan_service import PlanService
from src.api.utils.errors import APIException, to_http_exception
from src.utils.strtuct import PetInformation

router = APIRouter()


async def _resolve_pet_info(
    plan_service: PlanService,
    request: CreatePlanRequest,
    user_id: str,
) -> dict[str, Any]:
    if request.pet_id:
        pet_info = await plan_service.pet_service.get_pet_for_plan(
            user_id=user_id,
            pet_id=request.pet_id,
        )
        if not pet_info:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": 3001, "message": "宠物不存在", "detail": None},
            )
        return pet_info

    return PetInformation(
        pet_type=request.pet_type or "dog",
        pet_breed=request.pet_breed,
        pet_age=request.pet_age or 12,
        pet_weight=request.pet_weight or 10,
        health_status=request.health_status or "健康",
    ).model_dump()


@router.post("/", response_model=ApiResponse[CreateTaskResponse], summary="创建饮食计划")
async def create_diet_plan(
    request: CreatePlanRequest,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        plan_service = PlanService(db)
        pet_info = await _resolve_pet_info(plan_service, request, current_user_id)
        result = await plan_service.create_diet_plan(
            user_id=current_user_id,
            pet_info=pet_info,
        )

        return ApiResponse(
            code=0,
            message="饮食计划任务已创建",
            data=CreateTaskResponse(
                task_id=result["task_id"],
                status=result["status"],
                message="任务创建成功，请使用任务 ID 查询进度",
            ),
        )
    except APIException as exc:
        raise to_http_exception(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": -1, "message": "创建任务失败", "detail": str(exc)},
        )


@router.post("/stream", summary="创建饮食计划（流式）")
async def create_diet_plan_stream(
    request: CreatePlanRequest,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        plan_service = PlanService(db)
        pet_info = await _resolve_pet_info(plan_service, request, current_user_id)

        return StreamingResponse(
            plan_service.execute_diet_plan_stream(
                user_id=current_user_id,
                pet_info=pet_info,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except APIException as exc:
        raise to_http_exception(exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": -1, "message": "流式执行失败", "detail": str(exc)},
        )


@router.get("/stream", summary="恢复流式连接")
async def resume_diet_plan_stream(
    task_id: str = Query(..., description="任务 ID"),
    current_user_id: str = Depends(get_current_user),
):
    try:
        plan_service = PlanService(None)
        return StreamingResponse(
            plan_service.resume_diet_plan_stream(
                user_id=current_user_id,
                task_id=task_id,
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": -1, "message": "恢复连接失败", "detail": str(exc)},
        )


@router.post("/{plan_id}/confirm", response_model=ApiResponse[dict], summary="确认保存饮食计划")
async def confirm_diet_plan(
    plan_id: str,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        service = PlanService(db)
        saved_id = await service.confirm_diet_plan(plan_id, current_user_id)
        return ApiResponse(
            code=0,
            message="保存成功",
            data={"plan_id": saved_id},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": -1, "message": "确认保存失败", "detail": str(exc)},
        )


@router.post("/{plan_id}/apply", response_model=ApiResponse[dict], summary="应用饮食计划")
async def apply_diet_plan(
    plan_id: str,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """应用饮食计划：停用旧计划 → 激活新计划 → 从今天起生成 MealRecords"""
    try:
        service = PlanService(db)
        result = await service.apply_diet_plan(
            plan_id=plan_id,
            user_id=current_user_id,
        )
        return ApiResponse(
            code=0,
            message="应用成功",
            data=result,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": -1, "message": "应用计划失败", "detail": str(exc)},
        )


@router.get("/", response_model=ApiResponse[DietPlanListResponse], summary="获取饮食计划列表")
async def list_diet_plans(
    pet_type: PetType | None = Query(None, description="宠物类型筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页大小"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        plan_service = PlanService(db)
        result = await plan_service.list_diet_plans(
            user_id=current_user_id,
            pet_type=pet_type.value if pet_type else None,
            page=page,
            page_size=page_size,
        )
        return ApiResponse(
            code=0,
            message="获取成功",
            data=result,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": -1, "message": "获取列表失败", "detail": str(exc)},
        )


@router.get("/{plan_id}", response_model=ApiResponse[DietPlanDetailResponse], summary="获取饮食计划详情")
async def get_diet_plan(
    plan_id: str,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        plan_service = PlanService(db)
        result = await plan_service.get_diet_plan_detail(
            plan_id=plan_id,
            user_id=current_user_id,
        )
        return ApiResponse(
            code=0,
            message="获取成功",
            data=result,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": -1, "message": "获取详情失败", "detail": str(exc)},
        )


@router.delete("/{plan_id}", response_model=ApiResponse[dict], summary="删除饮食计划")
async def delete_diet_plan(
    plan_id: str,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        plan_service = PlanService(db)
        deleted_plan_id = await plan_service.delete_diet_plan(
            plan_id=plan_id,
            user_id=current_user_id,
        )
        return ApiResponse(
            code=0,
            message="删除成功",
            data={"plan_id": deleted_plan_id},
        )
    except HTTPException:
        raise
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": -1, "message": "删除失败", "detail": str(exc)},
        )
