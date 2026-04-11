"""
待办事项路由

处理待办事项的创建、查询、完成、删除等请求
"""
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db_session
from src.api.middleware.auth import get_current_user
from src.api.models.response import (
    ApiResponse,
    CreateTodoRequest,
    UpdateTodoRequest,
    TodoItemResponse,
    TodoListResponse,
)
from src.db.models import Pet, TodoItem

router = APIRouter()


def _todo_to_response(todo: TodoItem, pet_name: Optional[str] = None) -> TodoItemResponse:
    """将 ORM 对象转换为响应模型"""
    return TodoItemResponse(
        id=todo.id,
        user_id=todo.user_id,
        pet_id=todo.pet_id,
        pet_name=pet_name,
        title=todo.title,
        description=todo.description,
        due_date=todo.due_date.isoformat(),
        due_time=todo.due_time,
        is_all_day=todo.is_all_day,
        is_completed=todo.is_completed,
        completed_at=todo.completed_at,
        priority=todo.priority,
        category=todo.category,
        created_at=todo.created_at,
        updated_at=todo.updated_at,
    )


async def _get_todo_owned_by_user(
    db: AsyncSession, *, todo_id: str, user_id: str
) -> TodoItem | None:
    result = await db.execute(
        select(TodoItem).where(
            and_(TodoItem.id == todo_id, TodoItem.user_id == user_id)
        )
    )
    return result.scalar_one_or_none()


async def _validate_pet_ownership(
    db: AsyncSession, *, pet_id: str, user_id: str
) -> None:
    """校验宠物归属，不通过时抛 404"""
    result = await db.execute(
        select(Pet).where(
            and_(Pet.id == pet_id, Pet.user_id == user_id, Pet.is_active == True)
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 3001, "message": "Pet not found", "detail": None},
        )


async def _enrich_with_pet_names(
    db: AsyncSession, todos: list[TodoItem]
) -> list[TodoItemResponse]:
    """批量查询关联宠物名称"""
    pet_ids = {t.pet_id for t in todos if t.pet_id}
    pet_name_map: dict[str, str] = {}
    if pet_ids:
        result = await db.execute(
            select(Pet.id, Pet.name).where(Pet.id.in_(pet_ids))
        )
        pet_name_map = {row.id: row.name for row in result.all()}

    return [
        _todo_to_response(t, pet_name_map.get(t.pet_id) if t.pet_id else None)
        for t in todos
    ]


@router.get("/", response_model=ApiResponse[TodoListResponse], summary="获取待办列表")
async def list_todos(
    date_start: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    date_end: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    pet_id: Optional[str] = Query(None, description="宠物 ID 筛选"),
    is_completed: Optional[bool] = Query(None, description="完成状态筛选"),
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        conditions = [TodoItem.user_id == current_user_id]

        if date_start:
            conditions.append(TodoItem.due_date >= date.fromisoformat(date_start))
        if date_end:
            conditions.append(TodoItem.due_date <= date.fromisoformat(date_end))
        if pet_id is not None:
            conditions.append(TodoItem.pet_id == pet_id)
        if is_completed is not None:
            conditions.append(TodoItem.is_completed == is_completed)

        # 总数
        count_result = await db.execute(
            select(sa_func.count(TodoItem.id)).where(and_(*conditions))
        )
        total = count_result.scalar() or 0

        # 列表
        result = await db.execute(
            select(TodoItem)
            .where(and_(*conditions))
            .order_by(TodoItem.due_date, TodoItem.is_completed, TodoItem.created_at)
        )
        todos = result.scalars().all()
        items = await _enrich_with_pet_names(db, list(todos))

        return ApiResponse(
            code=0,
            message="获取成功",
            data=TodoListResponse(total=total, items=items),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 4000, "message": f"日期格式错误: {e}", "detail": None},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 5000, "message": "获取待办列表失败", "detail": str(e)},
        )


@router.post("/", response_model=ApiResponse[TodoItemResponse], summary="创建待办")
async def create_todo(
    body: CreateTodoRequest,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        # 校验日期格式
        parsed_date = date.fromisoformat(body.due_date)

        # 校验宠物归属
        if body.pet_id:
            await _validate_pet_ownership(db, pet_id=body.pet_id, user_id=current_user_id)

        todo = TodoItem(
            id=str(uuid.uuid4()),
            user_id=current_user_id,
            pet_id=body.pet_id,
            title=body.title,
            description=body.description,
            due_date=parsed_date,
            due_time=body.due_time,
            is_all_day=body.is_all_day,
            priority=body.priority.value,
            category=body.category.value,
        )
        db.add(todo)
        await db.commit()
        await db.refresh(todo)

        # 查宠物名
        pet_name = None
        if todo.pet_id:
            pet_result = await db.execute(select(Pet.name).where(Pet.id == todo.pet_id))
            row = pet_result.first()
            pet_name = row.name if row else None

        return ApiResponse(
            code=0,
            message="创建成功",
            data=_todo_to_response(todo, pet_name),
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 4000, "message": f"参数错误: {e}", "detail": None},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 5000, "message": "创建待办失败", "detail": str(e)},
        )


@router.put("/{todo_id}", response_model=ApiResponse[TodoItemResponse], summary="更新待办")
async def update_todo(
    todo_id: str,
    body: UpdateTodoRequest,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        todo = await _get_todo_owned_by_user(db, todo_id=todo_id, user_id=current_user_id)
        if not todo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": 4001, "message": "待办不存在", "detail": None},
            )

        update_data = body.model_dump(exclude_unset=True)

        # 校验宠物归属
        if "pet_id" in update_data and update_data["pet_id"]:
            await _validate_pet_ownership(
                db, pet_id=update_data["pet_id"], user_id=current_user_id
            )

        # 解析日期
        if "due_date" in update_data and update_data["due_date"]:
            update_data["due_date"] = date.fromisoformat(update_data["due_date"])

        # 枚举值转字符串
        if "priority" in update_data and update_data["priority"]:
            update_data["priority"] = update_data["priority"].value
        if "category" in update_data and update_data["category"]:
            update_data["category"] = update_data["category"].value

        for key, value in update_data.items():
            setattr(todo, key, value)

        await db.commit()
        await db.refresh(todo)

        pet_name = None
        if todo.pet_id:
            pet_result = await db.execute(select(Pet.name).where(Pet.id == todo.pet_id))
            row = pet_result.first()
            pet_name = row.name if row else None

        return ApiResponse(
            code=0,
            message="更新成功",
            data=_todo_to_response(todo, pet_name),
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 4000, "message": f"参数错误: {e}", "detail": None},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 5000, "message": "更新待办失败", "detail": str(e)},
        )


@router.delete("/{todo_id}", response_model=ApiResponse[dict], summary="删除待办")
async def delete_todo(
    todo_id: str,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        todo = await _get_todo_owned_by_user(db, todo_id=todo_id, user_id=current_user_id)
        if not todo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": 4001, "message": "待办不存在", "detail": None},
            )

        await db.delete(todo)
        await db.commit()

        return ApiResponse(code=0, message="删除成功", data={"todo_id": todo_id})
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 5000, "message": "删除待办失败", "detail": str(e)},
        )


@router.post("/{todo_id}/complete", response_model=ApiResponse[dict], summary="标记完成")
async def complete_todo(
    todo_id: str,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        todo = await _get_todo_owned_by_user(db, todo_id=todo_id, user_id=current_user_id)
        if not todo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": 4001, "message": "待办不存在", "detail": None},
            )

        todo.is_completed = True
        todo.completed_at = datetime.now(timezone.utc)
        await db.commit()

        return ApiResponse(
            code=0,
            message="标记成功",
            data={
                "todo_id": todo_id,
                "is_completed": True,
                "completed_at": todo.completed_at.isoformat(),
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 5000, "message": "标记完成失败", "detail": str(e)},
        )


@router.delete("/{todo_id}/complete", response_model=ApiResponse[dict], summary="取消完成")
async def uncomplete_todo(
    todo_id: str,
    current_user_id: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    try:
        todo = await _get_todo_owned_by_user(db, todo_id=todo_id, user_id=current_user_id)
        if not todo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": 4001, "message": "待办不存在", "detail": None},
            )

        todo.is_completed = False
        todo.completed_at = None
        await db.commit()

        return ApiResponse(
            code=0,
            message="取消成功",
            data={"todo_id": todo_id, "is_completed": False},
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 5000, "message": "取消标记失败", "detail": str(e)},
        )
