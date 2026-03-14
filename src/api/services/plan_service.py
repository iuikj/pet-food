"""
饮食计划服务
调用 LangGraph V1 多智能体系统生成宠物饮食计划
"""
import json
import asyncio
import logging
from typing import Dict, Any, AsyncGenerator
from datetime import datetime, timezone
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from langgraph.graph.state import CompiledStateGraph

from src.db.session import AsyncSessionLocal
from src.api.services.task_service import TaskService
from src.api.services.pet_service import PetService
from src.api.utils.stream import stream_langgraph_execution, create_sse_event, stream_with_heartbeat
from src.agent.v1.graph import build_v1_graph
from src.agent.v1.utils.context import ContextV1
from src.utils.strtuct import PetInformation

logger = logging.getLogger(__name__)


class PlanService:
    """饮食计划服务类"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.task_service = TaskService(db)
        self.pet_service = PetService(db)

    # ──────────── 公共接口 ────────────

    async def create_diet_plan(
        self,
        user_id: str,
        pet_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        创建饮食计划（异步后台模式）

        创建任务后在后台执行，立即返回任务 ID 供轮询查询进度。

        Args:
            user_id: 用户 ID
            pet_info: 宠物信息

        Returns:
            包含 task_id 和 status 的字典
        """
        task = await self.task_service.create_task(
            user_id=user_id,
            task_type="diet_plan",
            input_data=pet_info,
        )

        asyncio.create_task(
            self._execute_task_async(task.id, pet_info)
        )

        return {
            "task_id": task.id,
            "status": task.status,
            "message": "任务已创建，正在执行中",
        }

    async def execute_diet_plan_stream(
        self,
        user_id: str,
        pet_info: Dict[str, Any],
    ) -> AsyncGenerator[str, None]:
        """
        执行饮食计划生成（流式模式）

        通过 astream(stream_mode=["custom"]) 执行图，
        使用 completed_data 截获 completed 事件中的计划数据，
        流结束后存入 Redis 临时存储（24h TTL），用户确认后再持久化到 PostgreSQL。

        Args:
            user_id: 用户 ID
            pet_info: 宠物信息字典

        Yields:
            SSE 格式事件字符串
        """
        task = await self.task_service.create_task(
            user_id=user_id,
            task_type="diet_plan",
            input_data=pet_info,
        )

        # 提前缓存 task_id，避免 session 异常后无法访问 ORM 属性
        task_id = task.id

        yield create_sse_event({"type": "task_created", "task_id": task_id})

        try:
            graph = await self._build_graph()
            config = {
                "configurable": {
                    "thread_id": task_id,
                    "user_id": user_id,
                }
            }

            await self.task_service.update_task_status(task_id, "running")

            inputs, context = self._prepare_inputs(pet_info)

            # 流式执行 —— 通过 completed_data 截获 completed 事件
            # 使用心跳包裹器防止长时间无事件导致连接断开
            completed_data: Dict[str, Any] = {}
            raw_events = stream_langgraph_execution(
                graph, inputs, config, completed_data=completed_data, context=context
            )
            async for event in stream_with_heartbeat(raw_events):
                # 心跳注释行（以 : 开头）不含业务数据，直接转发即可
                if event.startswith(":"):
                    yield event
                    continue
                await self._update_task_progress_from_event(task_id, event)
                logger.debug("SSE event: %s", event)
                yield event

            # 流式结束后 → 存 Redis 临时存储（24h TTL）
            await self.task_service.complete_task(task_id, completed_data)
            plan_id = str(uuid.uuid4())
            await self._save_temp_plan(plan_id, user_id, task_id, pet_info, completed_data)

            yield create_sse_event({"type": "task_completed", "task_id": task_id, "plan_id": plan_id})

        except Exception as e:
            logger.error("流式饮食计划执行失败: %s", e, exc_info=True)
            # 先回滚脏事务，再标记任务失败
            try:
                await self.db.rollback()
            except Exception:
                pass
            try:
                await self.task_service.fail_task(task_id, str(e))
            except Exception as fail_err:
                logger.error("标记任务失败时出错: %s", fail_err)
            yield create_sse_event({"type": "error", "error": str(e)})

    async def resume_diet_plan_stream(
        self,
        user_id: str,
        task_id: str,
    ) -> AsyncGenerator[str, None]:
        """
        恢复流式连接（断线重连）

        查询任务当前状态：
        - 已完成/失败/取消：直接返回结果
        - 运行中/等待中：推送当前进度并轮询至终态

        注意：当前架构下图执行与 SSE 生成器绑定，SSE 断开后图也会被取消。
        因此 resume 主要用于客户端检查任务最终状态。

        Args:
            user_id: 用户 ID
            task_id: 任务 ID

        Yields:
            SSE 格式事件字符串
        """
        try:
            task = await self.task_service.get_task(task_id, user_id)

            if task.status == "completed":
                yield create_sse_event({
                    "type": "task_completed",
                    "task_id": task.id,
                    "result": task.output_data or {},
                })
                return

            if task.status == "failed":
                yield create_sse_event({
                    "type": "error",
                    "task_id": task.id,
                    "error": task.error_message or "任务执行失败",
                })
                return

            if task.status == "cancelled":
                yield create_sse_event({
                    "type": "error",
                    "task_id": task.id,
                    "error": "任务已取消",
                })
                return

            # running 或 pending：推送当前进度并轮询至终态
            yield create_sse_event({
                "type": "resumed",
                "task_id": task.id,
                "status": task.status,
                "progress": task.progress,
                "current_node": task.current_node or "",
            })

            # 轮询也使用心跳保活
            async for event in stream_with_heartbeat(
                self._poll_task_progress(task_id, user_id)
            ):
                yield event

        except Exception as e:
            yield create_sse_event({"type": "error", "error": str(e)})

    # ──────────── 内部方法 ────────────

    @staticmethod
    async def _build_graph() -> CompiledStateGraph:
        """构建 V1 LangGraph 图"""
        return await build_v1_graph()

    @staticmethod
    def _prepare_inputs(pet_info: Dict[str, Any]) -> tuple:
        """
        准备 V1 图的输入数据和上下文

        Args:
            pet_info: 宠物信息字典

        Returns:
            (inputs, context) 元组
        """
        pet_info_filtered = {
            k: v for k, v in pet_info.items()
            if k in PetInformation.model_fields
        }
        pet_information = PetInformation(**pet_info_filtered)
        return {"pet_information": pet_information}, ContextV1()

    async def _execute_task_async(self, task_id: str, pet_info: Dict[str, Any]):
        """
        后台异步执行任务

        使用独立 db session，避免与请求 session 冲突（请求完成后 session 会被关闭）。

        Args:
            task_id: 任务 ID
            pet_info: 宠物信息
        """
        async with AsyncSessionLocal() as db:
            task_service = TaskService(db)

            try:
                graph = await self._build_graph()
                config = {"configurable": {"thread_id": task_id}}

                await task_service.update_task_status(task_id, "running")

                inputs, context = self._prepare_inputs(pet_info)
                result = await graph.ainvoke(inputs, config, context=context)

                completed_task = await task_service.complete_task(task_id, result)
                await self._save_diet_plan(
                    db=db,
                    user_id=completed_task.user_id,
                    task_id=task_id,
                    pet_info=pet_info,
                    result=result,
                )

            except Exception as e:
                logger.error("后台任务执行失败 [%s]: %s", task_id, e, exc_info=True)
                try:
                    await db.rollback()
                except Exception:
                    pass
                try:
                    await task_service.fail_task(task_id, str(e))
                except Exception as fail_err:
                    logger.error("标记任务失败时出错 [%s]: %s", task_id, fail_err)

    async def _poll_task_progress(
        self,
        task_id: str,
        user_id: str,
        poll_interval: float = 1.0,
        timeout: int = 600,
    ) -> AsyncGenerator[str, None]:
        """
        轮询任务进度直到终态

        Args:
            task_id: 任务 ID
            user_id: 用户 ID
            poll_interval: 轮询间隔（秒）
            timeout: 超时时间（秒）

        Yields:
            SSE 格式事件字符串
        """
        start = asyncio.get_event_loop().time()
        last_progress = -1
        last_node = ""

        while True:
            if asyncio.get_event_loop().time() - start > timeout:
                yield create_sse_event({
                    "type": "error",
                    "error": f"轮询超时（{timeout}秒）",
                })
                return

            task = await self.task_service.get_task(task_id, user_id)

            if task.status == "completed":
                yield create_sse_event({
                    "type": "task_completed",
                    "task_id": task.id,
                    "result": task.output_data or {},
                })
                return

            if task.status in ("failed", "cancelled"):
                yield create_sse_event({
                    "type": "error",
                    "task_id": task.id,
                    "error": task.error_message or f"任务已{task.status}",
                })
                return

            # 有进度变化时推送
            current_node = task.current_node or ""
            if task.progress != last_progress or current_node != last_node:
                yield create_sse_event({
                    "type": "progress_update",
                    "task_id": task.id,
                    "status": task.status,
                    "progress": task.progress,
                    "current_node": current_node,
                })
                last_progress = task.progress
                last_node = current_node

            await asyncio.sleep(poll_interval)

    async def _update_task_progress_from_event(self, task_id: str, event: str):
        """
        从 SSE 事件中提取进度并更新任务

        支持 custom 模式的 ProgressEvent（含 progress 字段）。

        Args:
            task_id: 任务 ID
            event: SSE 事件字符串
        """
        try:
            if event.startswith("data: "):
                data = json.loads(event[6:].strip())
                progress = data.get("progress")
                if progress is not None:
                    node = data.get("node", "") or data.get("type", "")
                    await self.task_service.update_task_progress(
                        task_id, progress, node
                    )
        except (json.JSONDecodeError, KeyError):
            pass

    async def _save_temp_plan(
        self,
        plan_id: str,
        user_id: str,
        task_id: str,
        pet_info: Dict[str, Any],
        completed_data: Dict[str, Any],
    ) -> None:
        """
        将计划数据存入 Redis 临时存储（24h TTL）

        从 completed_data 中提取 plans 和 ai_suggestions，
        构造 plan_data 结构后序列化存储。

        Args:
            plan_id: 计划 ID
            user_id: 用户 ID
            task_id: 任务 ID
            pet_info: 宠物信息
            completed_data: completed 事件数据（含 detail.plans + detail.ai_suggestions）
        """
        from src.db.redis import set_json

        detail = completed_data.get("detail", {})
        plans = detail.get("plans", [])
        ai_suggestions = detail.get("ai_suggestions", "")

        # 序列化 Pydantic 模型
        serialized_plans = [
            p.model_dump() if hasattr(p, "model_dump") else p for p in plans
        ]

        # 构造与 PetDietPlan 结构一致的 plan_data
        pet_info_filtered = {
            k: v for k, v in pet_info.items()
            if k in PetInformation.model_fields
        }

        temp_data = {
            "plan_id": plan_id,
            "user_id": user_id,
            "task_id": task_id,
            "pet_info": pet_info,
            "plan_data": {
                "pet_information": pet_info_filtered,
                "ai_suggestions": ai_suggestions,
                "pet_diet_plan": {"monthly_diet_plan": serialized_plans},
            },
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        success = await set_json(f"temp_plan:{plan_id}", temp_data, expire=86400)
        if success:
            logger.info("临时计划已存入 Redis: temp_plan:%s (TTL 24h)", plan_id)
        else:
            logger.error("临时计划存入 Redis 失败: temp_plan:%s", plan_id)

    async def confirm_diet_plan(self, plan_id: str, user_id: str) -> str:
        """
        确认保存饮食计划：从 Redis 读取临时数据 → 写入 PostgreSQL → 删除 Redis 键

        Args:
            plan_id: 临时计划 ID
            user_id: 当前用户 ID

        Returns:
            已保存的饮食计划 ID

        Raises:
            HTTPException: 计划不存在/已过期 或 无权限
        """
        from fastapi import HTTPException
        from src.db.redis import get_json, get_redis

        temp = await get_json(f"temp_plan:{plan_id}")
        if not temp:
            raise HTTPException(
                status_code=404,
                detail={"code": 404, "message": "计划不存在或已过期", "detail": None},
            )
        if temp["user_id"] != user_id:
            raise HTTPException(
                status_code=403,
                detail={"code": 403, "message": "无权限操作此计划", "detail": None},
            )

        saved_id = await self._save_diet_plan(
            db=self.db,
            user_id=user_id,
            task_id=temp["task_id"],
            pet_info=temp["pet_info"],
            plan_data=temp["plan_data"],
        )

        # 直接删除精确 key（比 scan_iter 模式匹配更高效）
        try:
            client = await get_redis()
            await client.delete(f"temp_plan:{plan_id}")
            logger.info("Redis 临时计划已删除: temp_plan:%s", plan_id)
        except Exception as e:
            logger.warning("删除 Redis 临时计划失败: %s", e)

        return saved_id

    async def _save_diet_plan(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        task_id: str,
        pet_info: Dict[str, Any],
        result: Dict[str, Any] | None = None,
        plan_data: Dict[str, Any] | None = None,
    ) -> str:
        """
        保存饮食计划到数据库

        使用 keyword-only 参数防止位置传参导致的类型错位。

        Args:
            db: 数据库 session
            user_id: 用户 ID
            task_id: 任务 ID
            pet_info: 宠物信息
            result: LangGraph 执行结果（非流式后台模式使用）
            plan_data: 已构造的计划数据（confirm 转正时直接传入）

        Returns:
            plan_id: 新创建的饮食计划 ID
        """
        from src.db.models import DietPlan

        if plan_data is None:
            # 兼容非流式后台模式：从 result 中提取 report
            report = (result or {}).get("report", {})
            if hasattr(report, "model_dump"):
                report = report.model_dump()
            plan_data = report

        plan_id = str(uuid.uuid4())
        diet_plan = DietPlan(
            id=plan_id,
            user_id=user_id,
            task_id=task_id,
            pet_id=pet_info.get("pet_id"),
            pet_type=pet_info.get("pet_type", "unknown"),
            pet_breed=pet_info.get("pet_breed"),
            pet_age=pet_info.get("pet_age", 0),
            pet_weight=pet_info.get("pet_weight", 0),
            health_status=pet_info.get("health_status"),
            plan_data=plan_data,
            created_at=datetime.now(timezone.utc),
        )

        db.add(diet_plan)
        await db.commit()
        return plan_id
