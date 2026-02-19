"""
饮食计划服务
调用 LangGraph 多智能体系统生成宠物饮食计划
"""
import json
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator

from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.session import AsyncSessionLocal
from datetime import datetime, timezone
import uuid

from src.api.services.task_service import TaskService
from src.api.services.pet_service import PetService
from src.api.utils.errors import TaskException
from src.api.utils.stream import stream_langgraph_execution
from src.agent.v0.graph import build_graph_with_langgraph_studio


class PlanService:
    """饮食计划服务类"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.task_service = TaskService(db)
        self.pet_service = PetService(db)

    async def _get_langgraph(self)->CompiledStateGraph:
        return await build_graph_with_langgraph_studio()

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

        通过 astream(stream_mode=["custom", "updates"]) 一次性执行图，
        同时通过 final_output 收集最终状态用于持久化，避免二次调用 ainvoke。

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

            # 流式执行 —— 通过 final_output 收集累积状态
            final_output: Dict[str, Any] = {}
            async for event in stream_langgraph_execution(graph, inputs, config, final_output):
                # 更新任务进度
                await self._update_task_progress_from_event(task.id, event)

                # 发送事件到客户端
                yield event

            # 流式执行完毕，final_output 中已累积最终状态（无需再调用 ainvoke）
            # 保存结果
            await self.task_service.complete_task(task.id, final_output)

            # 保存到数据库
            await self._save_diet_plan(user_id, task.id, pet_info, final_output)

            # 发送完成事件
            yield f"data: {json.dumps({'type': 'task_completed', 'task_id': task.id})}\n\n"

        except Exception as e:
            # 任务失败
            await self.task_service.fail_task(task.id, str(e))

            # 发送错误事件
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    async def resume_diet_plan_stream(
        self,
        user_id: str,
        task_id: str
    ) -> AsyncGenerator[str, None]:
        pass
        # """
        # 恢复流式连接（断线重连）
        #
        # 混合架构核心：支持断线后通过 task_id 重连，继续接收执行事件
        #
        # Args:
        #     user_id: 用户 ID
        #     task_id: 任务 ID
        #
        # Yields:
        #     SSE 格式的事件字符串
        # """
        # try:
        #     # 查询任务状态
        #     task = await self.task_service.get_task(task_id, user_id)
        #
        #     # 检查任务所有权
        #     if task.user_id != user_id:
        #         yield f"data: {json.dumps({'type': 'error', 'error': '无权访问此任务'})}\n\n"
        #         return
        #
        #     # 根据任务状态处理
        #     if task.status == "completed":
        #         # 任务已完成，返回结果
        #         yield f"data: {json.dumps({{\n"
        #         yield f'"type": "task_completed",\n'
        #         yield f'"task_id": "{task.id}",\n'
        #         yield f'"result": {json.dumps(task.output_data or {}, ensure_ascii=False)}\n'
        #         yield f'}})}}\n\n'
        #         return
        #
        #     elif task.status == "failed":
        #         # 任务失败
        #         yield f"data: {json.dumps({{\n"
        #         yield f'"type": "error",\n'
        #         yield f'"task_id": "{task.id}",\n'
        #         yield f'"error": "{task.error_message or "任务执行失败"}"\n'
        #         yield f'}})}}\n\n'
        #         return
        #
        #     elif task.status == "cancelled":
        #         # 任务已取消
        #         yield f"data: {json.dumps({{\n"
        #         yield f'"type": "error",\n'
        #         yield f'"task_id": "{task.id}",\n'
        #         yield f'"error": "任务已取消"\n'
        #         yield f'}})}}\n\n"
        #         return
        #
        #     elif task.status == "pending":
        #         # 任务等待开始，发送状态后继续
        #         yield f"data: {json.dumps({{\n"
        #         yield f'"type": "resumed",\n'
        #         yield f'"task_id": "{task.id}",\n'
        #         yield f'"status": "pending",\n'
        #         yield f'"progress": {task.progress},\n'
        #         yield f'"current_node": "{task.current_node or ""}"\n'
        #         yield f'}})}}\n\n"
        #         # 等待任务开始，轮询状态
        #         await self._wait_for_task_start(task_id, user_id)
        #
        #     elif task.status == "running":
        #         # 任务正在运行，发送当前状态
        #         yield f"data: {json.dumps({{\n"
        #         yield f'"type": "resumed",\n'
        #         yield f'"task_id": "{task.id}",\n'
        #         yield f'"status": "running",\n'
        #         yield f'"progress": {task.progress},\n'
        #         yield f'"current_node": "{task.current_node or ""}"\n'
        #         yield f'}})}}\n\n"
        #
        #         # 继续接收后续事件
        #         # 注意：由于 LangGraph 已经在运行，这里我们只能轮询获取更新
        #         async for event in self._stream_task_progress(task_id, user_id):
        #             yield event
        #
        # except Exception as e:
        #     yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

    async def _wait_for_task_start(
        self,
        task_id: str,
        user_id: str,
        timeout: int = 60
    ):
        """
        等待任务开始执行

        Args:
            task_id: 任务 ID
            user_id: 用户 ID
            timeout: 超时时间（秒）
        """
        import asyncio

        start_time = asyncio.get_event_loop().time()
        check_interval = 0.5  # 检查间隔（秒）

        while True:
            # 检查超时
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TaskException(f"等待任务开始超时（{timeout}秒）")

            # 查询任务状态
            task = await self.task_service.get_task(task_id, user_id)

            if task.status == "running":
                return
            elif task.status in ["failed", "cancelled"]:
                raise TaskException(f"任务已{task.status}")

            # 等待下一次检查
            await asyncio.sleep(check_interval)

    async def _stream_task_progress(
        self,
        task_id: str,
        user_id: str
    ) -> AsyncGenerator[str, None]:
        """
        流式推送任务进度（用于重连后的进度更新）

        Args:
            task_id: 任务 ID
            user_id: 用户 ID

        Yields:
            SSE 格式的事件字符串
        """
        # import asyncio
        # from datetime import datetime, timezone
        #
        # last_status = None
        # last_progress = None
        # last_node = None
        #
        # while True:
        #     # 查询最新任务状态
        #     task = await self.task_service.get_task(task_id, user_id)
        #
        #     # 检查任务是否完成
        #     if task.status == "completed":
        #         yield f"data: {json.dumps({{\n"
        #         yield f'"type": "task_completed",\n'
        #         yield f'"task_id": "{task.id}",\n'
        #         yield f'"result": {json.dumps(task.output_data or {}, ensure_ascii=False)}\n'
        #         yield f'}})}}\n\n'
        #         return
        #
        #     elif task.status == "failed":
        #         yield f"data: {json.dumps({{\n"
        #         yield f'"type": "error",\n'
        #         yield f'"task_id": "{task.id}",\n'
        #         yield f'"error": "{task.error_message or "任务执行失败"}"\n'
        #         yield f'}})}}\n\n"
        #         return
        #
        #     elif task.status == "cancelled":
        #         yield f"data: {json.dumps({{\n"
        #         yield f'"type": "error",\n'
        #         yield f'"task_id": "{task.id}",\n'
        #         yield f'"error": "任务已取消"\n'
        #         yield f'}})}}\n\n"
        #         return
        #
        #     # 检查是否有状态变化
        #     status_changed = task.status != last_status
        #     progress_changed = task.progress != last_progress
        #     node_changed = task.current_node != last_node
        #
        #     if status_changed or progress_changed or node_changed:
        #         yield f"data: {json.dumps({{\n"
        #         yield f'"type": "progress_update",\n'
        #         yield f'"task_id": "{task.id}",\n'
        #         yield f'"status": "{task.status}",\n'
        #         yield f'"progress": {task.progress},\n'
        #         yield f'"current_node": "{task.current_node or ""}",\n'
        #         yield f'"timestamp": "{datetime.now(timezone.utc).isoformat()}Z"\n'
        #         yield f'}})}}\n\n"
        #
        #         last_status = task.status
        #         last_progress = task.progress
        #         last_node = task.current_node
        #
        #     # 等待下一次检查
        #     await asyncio.sleep(0.5)  # 每 0.5 秒检查一次
        pass

    async def _execute_task_async(self, task_id: str, pet_info: Dict[str, Any]):
        """
        异步执行任务（后台任务）

        注意：此方法在后台运行，需要使用独立的 database session，
        不能与请求的 session 共享（请求完成后 session 会被关闭）。

        Args:
            task_id: 任务 ID
            pet_info: 宠物信息
        """
        # 为后台任务创建独立的 session（避免与请求的 session 冲突）
        async with AsyncSessionLocal() as db:
            task_service = TaskService(db)

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
                await task_service.update_task_status(task_id, "running")

                # 构造输入
                inputs = {
                    "pet_information": pet_info
                }

                # 执行图
                result = await graph.ainvoke(inputs, config)

                # 完成任务
                completed_task = await task_service.complete_task(task_id, result)

                # 保存到数据库（使用独立的 session）
                await self._save_diet_plan(
                    db,
                    completed_task.user_id,
                    task_id,
                    pet_info,
                    result
                )

            except Exception as e:
                # 失败任务
                await task_service.fail_task(task_id, str(e))

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
            from src.agent.v0.graph import build_graph_with_langgraph_studio

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
        从 ProgressEvent SSE 事件更新任务进度

        支持两种事件来源：
        - custom 模式的 ProgressEvent（含 progress 字段）
        - updates 模式的 node_completed 事件

        Args:
            task_id: 任务 ID
            event: SSE 事件字符串
        """
        import json

        try:
            # 解析事件
            if event.startswith("data: "):
                json_str = event[6:].strip()
                data = json.loads(json_str)

                event_type = data.get("type", "")
                node = data.get("node", "")
                progress = data.get("progress")

                # 优先使用 ProgressEvent 中的 progress 字段
                if progress is not None:
                    await self.task_service.update_task_progress(
                        task_id,
                        progress,
                        node or event_type
                    )

        except (json.JSONDecodeError, KeyError):
            # 忽略解析错误
            pass

    async def _save_diet_plan(
        self,
        db: Optional[AsyncSession] = None,
        user_id: str = None,
        task_id: str = None,
        pet_info: Dict[str, Any] = None,
        result: Dict[str, Any] = None
    ):
        """
        保存饮食计划到数据库

        Args:
            db: 数据库 session（可选，用于后台任务的独立 session）
            user_id: 用户 ID
            task_id: 任务 ID
            pet_info: 宠物信息
            result: LangGraph 执行结果
        """
        from src.db.models import DietPlan

        # 使用传入的 db 或默认的 self.db
        session = db or self.db

        # 提取报告数据
        report = result.get("report", {})

        # 提取 pet_id（如果存在）
        pet_id = pet_info.get("pet_id")

        # 创建饮食计划记录
        diet_plan = DietPlan(
            id=str(uuid.uuid4()),
            user_id=user_id,
            task_id=task_id,
            pet_id=pet_id,  # 新增：关联宠物
            pet_type=pet_info.get("pet_type", "unknown"),
            pet_breed=pet_info.get("pet_breed"),
            pet_age=pet_info.get("pet_age_months", 0),
            pet_weight=pet_info.get("pet_weight", 0),
            health_status=pet_info.get("health_status"),
            plan_data=report,
            created_at=datetime.now(timezone.utc)
        )

        session.add(diet_plan)
        await session.commit()

