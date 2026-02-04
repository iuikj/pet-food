"""
任务管理服务
处理任务的创建、查询、取消等操作
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
import uuid

from src.db.models import Task, User
from src.api.utils.errors import NotFoundException, TaskException
from src.api.models.response import TaskResponse, TaskListResponse
from src.api.config import settings


class TaskService:
    """任务管理服务类"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_task(
        self,
        user_id: str,
        task_type: str,
        input_data: dict
    ) -> Task:
        """
        创建新任务

        Args:
            user_id: 用户 ID
            task_type: 任务类型（diet_plan, research 等）
            input_data: 任务输入数据

        Returns:
            创建的任务对象
        """
        task = Task(
            id=str(uuid.uuid4()),
            user_id=user_id,
            task_type=task_type,
            status="pending",
            progress=0,
            input_data=input_data,
            created_at=datetime.now(timezone.utc)
        )

        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)

        return task

    async def get_task(self, task_id: str, user_id: str) -> Task:
        """
        获取任务信息

        Args:
            task_id: 任务 ID
            user_id: 用户 ID

        Returns:
            任务对象

        Raises:
            NotFoundException: 任务不存在
        """
        result = await self.db.execute(
            select(Task).where(
                Task.id == task_id,
                Task.user_id == user_id
            )
        )
        task = result.scalars().first()

        if not task:
            raise NotFoundException("任务不存在")

        return task

    async def update_task_status(
        self,
        task_id: str,
        status: str,
        progress: Optional[int] = None,
        current_node: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Task:
        """
        更新任务状态

        Args:
            task_id: 任务 ID
            status: 新状态
            progress: 进度（0-100）
            current_node: 当前执行节点
            error_message: 错误信息

        Returns:
            更新后的任务对象

        Raises:
            NotFoundException: 任务不存在
        """
        result = await self.db.execute(
            select(Task).where(Task.id == task_id)
        )
        task = result.scalars().first()

        if not task:
            raise NotFoundException("任务不存在")

        # 更新状态
        task.status = status

        if progress is not None:
            task.progress = progress

        if current_node is not None:
            task.current_node = current_node

        if error_message is not None:
            task.error_message = error_message

        # 更新时间戳
        if status == "running" and not task.started_at:
            task.started_at = datetime.now(timezone.utc)
        elif status in ["completed", "failed", "cancelled"]:
            task.completed_at = datetime.now(timezone.utc)

        task.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(task)

        return task

    async def update_task_progress(
        self,
        task_id: str,
        progress: int,
        current_node: str
    ) -> Task:
        """
        更新任务进度

        Args:
            task_id: 任务 ID
            progress: 进度（0-100）
            current_node: 当前执行节点

        Returns:
            更新后的任务对象
        """
        return await self.update_task_status(
            task_id,
            status="running",
            progress=progress,
            current_node=current_node
        )

    async def complete_task(
        self,
        task_id: str,
        output_data: dict
    ) -> Task:
        """
        标记任务完成

        Args:
            task_id: 任务 ID
            output_data: 输出数据

        Returns:
            更新后的任务对象
        """
        task = await self.update_task_status(
            task_id,
            status="completed",
            progress=100
        )

        task.output_data = output_data
        await self.db.commit()
        await self.db.refresh(task)

        return task

    async def fail_task(
        self,
        task_id: str,
        error_message: str
    ) -> Task:
        """
        标记任务失败

        Args:
            task_id: 任务 ID
            error_message: 错误信息

        Returns:
            更新后的任务对象
        """
        return await self.update_task_status(
            task_id,
            status="failed",
            error_message=error_message
        )

    async def cancel_task(self, task_id: str, user_id: str) -> Task:
        """
        取消任务

        Args:
            task_id: 任务 ID
            user_id: 用户 ID

        Returns:
            更新后的任务对象

        Raises:
            NotFoundException: 任务不存在
            TaskException: 任务无法取消
        """
        task = await self.get_task(task_id, user_id)

        if task.status in ["completed", "failed", "cancelled"]:
            raise TaskException(f"任务已{task.status}，无法取消")

        if task.status == "running":
            # TODO: 实际取消正在运行的任务（例如设置取消标志）
            pass

        task.status = "cancelled"
        task.completed_at = datetime.now(timezone.utc)
        task.updated_at = datetime.now(timezone.utc)

        await self.db.commit()
        await self.db.refresh(task)

        return task

    async def list_tasks(
        self,
        user_id: str,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 10
    ) -> TaskListResponse:
        """
        获取任务列表

        Args:
            user_id: 用户 ID
            status: 状态筛选
            page: 页码
            page_size: 每页大小

        Returns:
            任务列表响应
        """
        # 构建查询
        query = select(Task).where(Task.user_id == user_id)

        if status:
            query = query.where(Task.status == status)

        # 获取总数
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar()

        # 分页查询
        query = query.order_by(Task.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await self.db.execute(query)
        tasks = result.scalars().all()

        # 转换为响应模型
        items = [TaskResponse.model_validate(task) for task in tasks]

        return TaskListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items
        )

    async def cleanup_old_tasks(self, days: int = 7) -> int:
        """
        清理旧任务（定期清理任务）

        Args:
            days: 保留天数

        Returns:
            删除的任务数量
        """
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        # 删除超过指定天数且已完成/失败/取消的任务
        result = await self.db.execute(
            select(Task).where(
                Task.created_at < cutoff_date,
                Task.status.in_(["completed", "failed", "cancelled"])
            )
        )
        old_tasks = result.scalars().all()

        count = len(old_tasks)

        for task in old_tasks:
            await self.db.delete(task)

        await self.db.commit()

        return count
