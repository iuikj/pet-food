"""
饮食计划服务
调用 LangGraph 多智能体系统生成宠物饮食计划
"""
import json
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
import uuid

from src.api.services.task_service import TaskService
from src.api.utils.errors import TaskException
from src.api.utils.stream import stream_langgraph_execution


class PlanService:
    """饮食计划服务类"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.task_service = TaskService(db)

    async def create_diet_plan(
        self,
        user_id: str,
        pet_info: Dict[str, Any],
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        创建饮食计划（同步模式）

        Args:
            user_id: 用户 ID
            pet_info: 宠物信息
            stream: 是否使用流式输出

        Returns:
            任务信息
        """
        # 创建任务
        task = await self.task_service.create_task(
            user_id=user_id,
            task_type="diet_plan",
            input_data=pet_info
        )

        # 在后台异步执行任务
        asyncio.create_task(
            self._execute_task_async(task.id, pet_info)
        )

        return {
            "task_id": task.id,
            "status": task.status,
            "message": "任务已创建，正在执行中"
        }

    async def execute_diet_plan_stream(
        self,
        user_id: str,
        pet_info: Dict[str, Any]
    ) -> AsyncGenerator[str, None]:
        """
        执行饮食计划生成（流式模式）

        Args:
            user_id: 用户 ID
            pet_info: 宠物信息

        Yields:
            SSE 格式的事件字符串
        """
        # 创建任务
        task = await self.task_service.create_task(
            user_id=user_id,
            task_type="diet_plan",
            input_data=pet_info
        )

        # 发送任务创建事件
        yield f"data: {json.dumps({'type': 'task_created', 'task_id': task.id})}\n\n"

        try:
            # 获取 LangGraph 图
            graph = await self._get_langgraph()

            # 配置（使用 thread_id 隔离会话）
            config = {
                "configurable": {
                    "thread_id": task.id,
                    "user_id": user_id
                }
            }

            # 更新任务状态为运行中
            await self.task_service.update_task_status(task.id, "running")

            # 构造输入
            inputs = {
                "pet_information": pet_info
            }

            # 流式执行
            async for event in stream_langgraph_execution(graph, inputs, config):
                # 更新任务进度
                await self._update_task_progress_from_event(task.id, event)

                # 发送事件到客户端
                yield event

            # 执行完成，获取最终状态
            final_state = await graph.ainvoke(inputs, config)

            # 保存结果
            await self.task_service.complete_task(task.id, final_state)

            # 保存到数据库
            await self._save_diet_plan(user_id, task.id, pet_info, final_state)

            # 发送完成事件
            yield f"data: {json.dumps({'type': 'task_completed', 'task_id': task.id})}\n\n"

        except Exception as e:
            # 任务失败
            await self.task_service.fail_task(task.id, str(e))

            # 发送错误事件
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    async def _execute_task_async(self, task_id: str, pet_info: Dict[str, Any]):
        """
        异步执行任务（后台任务）

        Args:
            task_id: 任务 ID
            pet_info: 宠物信息
        """
        try:
            # 获取 LangGraph 图
            graph = await self._get_langgraph()

            # 配置
            config = {
                "configurable": {
                    "thread_id": task_id
                }
            }

            # 更新任务状态
            await self.task_service.update_task_status(task_id, "running")

            # 构造输入
            inputs = {
                "pet_information": pet_info
            }

            # 执行图
            result = await graph.ainvoke(inputs, config)

            # 完成任务
            completed_task = await self.task_service.complete_task(task_id, result)

            # 保存到数据库
            await self._save_diet_plan(
                completed_task.user_id,
                task_id,
                pet_info,
                result
            )

        except Exception as e:
            # 失败任务
            await self.task_service.fail_task(task_id, str(e))

    async def _get_langgraph(self):
        """
        获取 LangGraph 图实例

        Returns:
            编译后的 LangGraph 图

        Raises:
            TaskException: 图加载失败
        """
        try:
            # 导入图构建函数
            from src.agent.graph import build_graph_with_langgraph_studio

            # 获取图
            graph = build_graph_with_langgraph_studio()

            return graph

        except ImportError as e:
            raise TaskException(f"LangGraph 图导入失败: {str(e)}")
        except Exception as e:
            raise TaskException(f"LangGraph 图加载失败: {str(e)}")

    async def _update_task_progress_from_event(
        self,
        task_id: str,
        event: str
    ):
        """
        从事件更新任务进度

        Args:
            task_id: 任务 ID
            event: SSE 事件字符串
        """
        import json

        try:
            # 解析事件
            if event.startswith("data: "):
                json_str = event[6:]  # 去掉 "data: " 前缀
                data = json.loads(json_str)

                event_type = data.get("type")
                node = data.get("node", "")

                # 根据事件类型更新进度
                if event_type == "node_started":
                    if node == "main_agent":
                        progress = 10
                    elif node == "subagent":
                        progress = 30
                    elif node == "writeagent":
                        progress = 70
                    elif node == "structureagent":
                        progress = 90

                    await self.task_service.update_task_progress(
                        task_id,
                        progress,
                        node
                    )

        except (json.JSONDecodeError, KeyError):
            # 忽略解析错误
            pass

    async def _save_diet_plan(
        self,
        user_id: str,
        task_id: str,
        pet_info: Dict[str, Any],
        result: Dict[str, Any]
    ):
        """
        保存饮食计划到数据库

        Args:
            user_id: 用户 ID
            task_id: 任务 ID
            pet_info: 宠物信息
            result: LangGraph 执行结果
        """
        from src.db.models import DietPlan

        # 提取报告数据
        report = result.get("report", {})

        # 创建饮食计划记录
        diet_plan = DietPlan(
            id=str(uuid.uuid4()),
            user_id=user_id,
            task_id=task_id,
            pet_type=pet_info.get("pet_type", "unknown"),
            pet_breed=pet_info.get("pet_breed"),
            pet_age=pet_info.get("pet_age_months", 0),
            pet_weight=pet_info.get("pet_weight", 0),
            health_status=pet_info.get("health_status"),
            plan_data=report,
            created_at=datetime.now(timezone.utc)
        )

        self.db.add(diet_plan)
        await self.db.commit()
