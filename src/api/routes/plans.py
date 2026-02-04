"""
饮食计划路由
处理饮食计划的创建、查询等请求
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session, get_redis_client
from src.api.middleware.auth import get_current_user
from src.api.models.request import CreatePlanRequest
from src.api.models.response import ApiResponse
from src.api.services.plan_service import PlanService
from src.api.utils.errors import to_http_exception, APIException
import redis.asyncio as redis

router = APIRouter()


@router.post("/", response_model=ApiResponse[dict], summary="创建饮食计划")
async def create_diet_plan(
    request: CreatePlanRequest,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    创建饮食计划（异步模式）

    创建任务后立即返回任务 ID，可以通过轮询查询进度

    - **pet_info**: 宠物信息
    - **stream**: 是否使用流式输出（false = 异步模式）
    """
    try:
        plan_service = PlanService(db)

        # 转换宠物信息
        pet_info = request.pet_info.model_dump()

        # 创建任务（异步执行）
        result = await plan_service.create_diet_plan(
            user_id=current_user_id,
            pet_info=pet_info,
            stream=False
        )

        return ApiResponse(
            code=0,
            message="饮食计划任务已创建",
            data=result
        )

    except APIException as e:
        raise to_http_exception(e)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": -1,
                "message": "创建任务失败",
                "detail": str(e)
            }
        )


@router.post("/stream", summary="创建饮食计划（流式）")
async def create_diet_plan_stream(
    request: CreatePlanRequest,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    创建饮食计划（流式模式）

    使用 SSE (Server-Sent Events) 实时推送执行过程

    - **pet_info**: 宠物信息
    - **stream**: 必须设置为 true

    返回 SSE 事件流，包含：
    - task_created: 任务创建
    - node_started: 节点开始执行
    - node_completed: 节点执行完成
    - llm_token: LLM 生成的内容
    - tool_started: 工具开始调用
    - tool_completed: 工具调用完成
    - task_completed: 任务完成
    - error: 错误
    """
    try:
        plan_service = PlanService(db)

        # 转换宠物信息
        pet_info = request.pet_info.model_dump()

        # 创建流式响应
        return StreamingResponse(
            plan_service.execute_diet_plan_stream(
                user_id=current_user_id,
                pet_info=pet_info
            ),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # 禁用 Nginx 缓冲
            }
        )

    except APIException as e:
        raise to_http_exception(e)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": -1,
                "message": "流式执行失败",
                "detail": str(e)
            }
        )


@router.get("/", response_model=ApiResponse[list], summary="获取饮食计划列表")
async def list_diet_plans(
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取当前用户的所有饮食计划

    返回计划摘要列表
    """
    try:
        from src.db.models import DietPlan
        from sqlalchemy import select

        result = await db.execute(
            select(DietPlan)
            .where(DietPlan.user_id == current_user_id)
            .order_by(DietPlan.created_at.desc())
            .limit(50)
        )
        plans = result.scalars().all()

        # 转换为摘要列表
        items = []
        for plan in plans:
            items.append({
                "id": plan.id,
                "task_id": plan.task_id,
                "pet_type": plan.pet_type,
                "pet_breed": plan.pet_breed,
                "pet_age": plan.pet_age,
                "pet_weight": plan.pet_weight,
                "created_at": plan.created_at.isoformat(),
            })

        return ApiResponse(
            code=0,
            message="获取成功",
            data=items
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": -1,
                "message": "获取列表失败",
                "detail": str(e)
            }
        )


@router.get("/{plan_id}", response_model=ApiResponse[dict], summary="获取饮食计划详情")
async def get_diet_plan(
    plan_id: str,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取指定饮食计划的详细信息

    - **plan_id**: 计划 ID
    """
    try:
        from src.db.models import DietPlan
        from sqlalchemy import select

        result = await db.execute(
            select(DietPlan).where(
                DietPlan.id == plan_id,
                DietPlan.user_id == current_user_id
            )
        )
        plan = result.scalars().first()

        if not plan:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": 404,
                    "message": "饮食计划不存在",
                    "detail": None
                }
            )

        return ApiResponse(
            code=0,
            message="获取成功",
            data={
                "id": plan.id,
                "task_id": plan.task_id,
                "pet_type": plan.pet_type,
                "pet_breed": plan.pet_breed,
                "pet_age": plan.pet_age,
                "pet_weight": plan.pet_weight,
                "health_status": plan.health_status,
                "plan_data": plan.plan_data,
                "created_at": plan.created_at.isoformat(),
                "updated_at": plan.updated_at.isoformat(),
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": -1,
                "message": "获取详情失败",
                "detail": str(e)
            }
        )
