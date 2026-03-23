"""
任务管理 API 测试
覆盖任务创建、状态查询、列表、取消、结果获取
"""
import uuid
from datetime import datetime, timezone

import pytest
from httpx import AsyncClient

from src.db.models import Task


@pytest.mark.asyncio
class TestTaskStatus:
    """任务状态查询测试"""

    async def test_get_task_status(
        self, client: AsyncClient, auth_headers: dict, test_task: Task
    ):
        """正常获取任务状态"""
        response = await client.get(
            f"/api/v1/tasks/{test_task.id}", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        task_data = data["data"]
        assert task_data["id"] == test_task.id
        assert task_data["status"] == "pending"
        assert task_data["progress"] == 0

    async def test_get_task_not_found(self, client: AsyncClient, auth_headers: dict):
        """查询不存在的任务"""
        response = await client.get(
            f"/api/v1/tasks/{uuid.uuid4()}", headers=auth_headers
        )
        assert response.status_code == 404

    async def test_get_task_no_auth(self, client: AsyncClient, test_task: Task):
        """未认证查询任务"""
        response = await client.get(f"/api/v1/tasks/{test_task.id}")
        assert response.status_code == 401

    async def test_get_task_other_user(
        self, client: AsyncClient, second_auth_headers: dict, test_task: Task
    ):
        """其他用户无法查看别人的任务"""
        response = await client.get(
            f"/api/v1/tasks/{test_task.id}", headers=second_auth_headers
        )
        assert response.status_code == 404


@pytest.mark.asyncio
class TestTaskList:
    """任务列表测试"""

    async def test_list_tasks_empty(self, client: AsyncClient, auth_headers: dict):
        """空任务列表"""
        response = await client.get("/api/v1/tasks/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["total"] == 0

    async def test_list_tasks_with_data(
        self, client: AsyncClient, auth_headers: dict, test_task: Task
    ):
        """有数据时查询任务列表"""
        response = await client.get("/api/v1/tasks/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["total"] >= 1

    async def test_list_tasks_filter_status(
        self, client: AsyncClient, auth_headers: dict, test_task: Task
    ):
        """按状态筛选任务列表"""
        response = await client.get(
            "/api/v1/tasks/?status=pending", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        for item in data["data"]["items"]:
            assert item["status"] == "pending"

    async def test_list_tasks_pagination(
        self, client: AsyncClient, auth_headers: dict, test_task: Task
    ):
        """分页参数测试"""
        response = await client.get(
            "/api/v1/tasks/?page=1&page_size=5", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["page"] == 1
        assert data["data"]["page_size"] == 5


@pytest.mark.asyncio
class TestTaskCancel:
    """任务取消测试"""

    async def test_cancel_pending_task(
        self, client: AsyncClient, auth_headers: dict, test_task: Task
    ):
        """取消 pending 状态的任务"""
        response = await client.delete(
            f"/api/v1/tasks/{test_task.id}", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["status"] == "cancelled"

    async def test_cancel_nonexistent_task(
        self, client: AsyncClient, auth_headers: dict
    ):
        """取消不存在的任务"""
        response = await client.delete(
            f"/api/v1/tasks/{uuid.uuid4()}", headers=auth_headers
        )
        assert response.status_code == 404


@pytest.mark.asyncio
class TestTaskResult:
    """任务结果测试"""

    async def test_get_result_not_completed(
        self, client: AsyncClient, auth_headers: dict, test_task: Task
    ):
        """获取未完成任务的结果应返回 400"""
        response = await client.get(
            f"/api/v1/tasks/{test_task.id}/result", headers=auth_headers
        )
        assert response.status_code == 400

    async def test_get_result_completed(
        self,
        client: AsyncClient,
        auth_headers: dict,
        test_session,
        test_user,
    ):
        """获取已完成任务的结果"""
        # 直接创建已完成任务
        task = Task(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            task_type="diet_plan",
            status="completed",
            progress=100,
            input_data={"pet_type": "cat"},
            output_data={"plan": "test plan data"},
            completed_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        test_session.add(task)
        await test_session.commit()

        response = await client.get(
            f"/api/v1/tasks/{task.id}/result", headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["task_id"] == task.id
        assert data["data"]["output"]["plan"] == "test plan data"


@pytest.mark.asyncio
class TestTaskService:
    """TaskService 业务逻辑测试"""

    async def test_create_task(self, test_session, test_user):
        """测试任务创建"""
        from src.api.services.task_service import TaskService

        service = TaskService(test_session)
        task = await service.create_task(
            user_id=test_user.id,
            task_type="diet_plan",
            input_data={"test": True},
        )
        assert task.id is not None
        assert task.status == "pending"
        assert task.progress == 0

    async def test_update_task_status(self, test_session, test_task):
        """测试任务状态更新"""
        from src.api.services.task_service import TaskService

        service = TaskService(test_session)
        updated = await service.update_task_status(
            test_task.id, status="running", progress=50, current_node="research"
        )
        assert updated.status == "running"
        assert updated.progress == 50
        assert updated.current_node == "research"
        assert updated.started_at is not None

    async def test_complete_task(self, test_session, test_task):
        """测试任务完成"""
        from src.api.services.task_service import TaskService

        service = TaskService(test_session)
        completed = await service.complete_task(
            test_task.id, output_data={"result": "success"}
        )
        assert completed.status == "completed"
        assert completed.progress == 100
        assert completed.output_data["result"] == "success"

    async def test_fail_task(self, test_session, test_task):
        """测试任务失败"""
        from src.api.services.task_service import TaskService

        service = TaskService(test_session)
        failed = await service.fail_task(test_task.id, "Agent 执行超时")
        assert failed.status == "failed"
        assert failed.error_message == "Agent 执行超时"

    async def test_cancel_completed_task_raises(self, test_session, test_user):
        """取消已完成的任务应抛出异常"""
        from src.api.services.task_service import TaskService
        from src.api.utils.errors import TaskException

        task = Task(
            id=str(uuid.uuid4()),
            user_id=test_user.id,
            task_type="diet_plan",
            status="completed",
            progress=100,
            input_data={},
            created_at=datetime.now(timezone.utc),
        )
        test_session.add(task)
        await test_session.commit()

        service = TaskService(test_session)
        with pytest.raises(TaskException):
            await service.cancel_task(task.id, test_user.id)
