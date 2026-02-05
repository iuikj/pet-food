"""
任务管理路由
处理任务状态查询、取消等操作
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.api.middleware.auth import get_current_user
from src.api.models.request import TaskStatus, TaskType
from src.api.models.response import (
    ApiResponse,
    TaskResponse,
    TaskListResponse,
    TaskCancelResponse,
    TaskResultResponse
)
from src.api.services.task_service import TaskService
from src.api.utils.errors import to_http_exception, APIException

router = APIRouter()


@router.get("/{task_id}", response_model=ApiResponse[TaskResponse], summary="获取任务状态")
async def get_task_status(
    task_id: str,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取指定任务的详细状态

    - **task_id**: 任务 ID

    返回任务的当前状态、进度、错误信息等
    """
    try:
        task_service = TaskService(db)
        task = await task_service.get_task(task_id, current_user_id)

        return ApiResponse(
            code=0,
            message="获取成功",
            data=TaskResponse.model_validate(task)
        )

    except APIException as e:
        raise to_http_exception(e)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": -1,
                "message": "获取任务状态失败",
                "detail": str(e)
            }
        )


@router.get("/", response_model=ApiResponse[TaskListResponse], summary="获取任务列表")
async def list_tasks(
    status: TaskStatus | None = None,
    task_type: TaskType | None = None,
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页大小"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取当前用户的任务列表

    - **status**: 状态筛选（可选）：pending, running, completed, failed, cancelled
    - **task_type**: 任务类型筛选（可选）：create_plan, generate_report
    - **page**: 页码（默认 1）
    - **page_size**: 每页大小（默认 10，最大 100）
    """
    try:
        task_service = TaskService(db)
        result = await task_service.list_tasks(
            user_id=current_user_id,
            status=status.value if status else None,
            task_type=task_type.value if task_type else None,
            page=page,
            page_size=page_size
        )

        return ApiResponse(
            code=0,
            message="获取成功",
            data=TaskListResponse(
                total=result.total,
                page=result.page,
                page_size=result.page_size,
                items=[TaskResponse.model_validate(item) for item in result.items]
            )
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": -1,
                "message": "获取任务列表失败",
                "detail": str(e)
            }
        )


@router.delete("/{task_id}", response_model=ApiResponse[TaskCancelResponse], summary="取消任务")
async def cancel_task(
    task_id: str,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    取消指定的任务

    - **task_id**: 任务 ID

    注意：只能取消 pending 或 running 状态的任务
    """
    try:
        task_service = TaskService(db)
        task = await task_service.cancel_task(task_id, current_user_id)

        return ApiResponse(
            code=0,
            message="任务已取消",
            data=TaskCancelResponse(
                task_id=task.id,
                status=TaskStatus(task.status)
            )
        )

    except APIException as e:
        raise to_http_exception(e)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": -1,
                "message": "取消任务失败",
                "detail": str(e)
            }
        )


@router.get("/{task_id}/result", response_model=ApiResponse[TaskResultResponse], summary="获取任务结果")
async def get_task_result(
    task_id: str,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取已完成任务的执行结果

    - **task_id**: 任务 ID

    仅当任务状态为 completed 时可用
    """
    try:
        task_service = TaskService(db)
        task = await task_service.get_task(task_id, current_user_id)

        if task.status != "completed":
            raise HTTPException(
                status_code=400,
                detail={
                    "code": 400,
                    "message": f"任务未完成，当前状态: {task.status}",
                    "detail": None
                }
            )

        return ApiResponse(
            code=0,
            message="获取成功",
            data=TaskResultResponse(
                task_id=task.id,
                output=task.output_data or {}
            )
        )

    except HTTPException:
        raise
    except APIException as e:
        raise to_http_exception(e)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": -1,
                "message": "获取任务结果失败",
                "detail": str(e)
            }
        )
