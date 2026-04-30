"""
饮食计划服务
调用 LangGraph 多智能体系统生成宠物饮食计划。

实际使用的 agent 图版本由 `settings.diet_plan_agent_version` 控制：
- `v1`：旧版图
- `v2`：新版 deep-agent 图
"""
import json
import asyncio
import logging
from typing import Dict, Any, AsyncGenerator, TYPE_CHECKING, Literal
from datetime import datetime, timezone, date
import uuid

from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import AsyncSessionLocal
from src.api.services.task_service import TaskService
from src.api.services.pet_service import PetService
from src.api.services.meal_service import MealService
from src.api.services.event_bus import (
    publish_end_sentinel,
    publish_event,
    stream_exists,
    subscribe_events,
)
from src.api.models.response import (
    DietPlanDetailResponse,
    DietPlanListResponse,
    DietPlanSummaryResponse,
    PetType as ResponsePetType,
)
from src.api.config import settings
from src.api.utils.stream import create_sse_event, stream_with_heartbeat
from src.utils.strtuct import PetInformation

if TYPE_CHECKING:
    # 仅用于类型标注，避免启动期引入 langgraph / langchain 重栈。
    from langgraph.graph.state import CompiledStateGraph

logger = logging.getLogger(__name__)

# 控制高频进度事件的落库频率，避免数据库被事件流打满。
PROGRESS_DB_WRITE_INTERVAL_SECONDS = 1.0
PROGRESS_DB_WRITE_DELTA = 5

# 后台任务强引用集合：防止 asyncio.create_task 创建的任务被 GC 回收
# 任务完成后通过 done callback 自动从集合中移除
_BACKGROUND_TASKS: set[asyncio.Task] = set()


def _spawn_background_task(coro) -> asyncio.Task:
    """启动后台任务并保留强引用，避免被 GC。任务完成后自动清理。"""
    task = asyncio.create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
    return task


class PlanService:
    """饮食计划服务类"""

    def __init__(self, db: AsyncSession | None, *, app_state: Any | None = None):
        self.db = db
        self.app_state = app_state
        self.task_service = TaskService(db) if db else None
        self.pet_service = PetService(db) if db else None

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

    async def list_diet_plans(
        self,
        *,
        user_id: str,
        pet_type: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> DietPlanListResponse:
        from src.db.models import DietPlan

        query = select(DietPlan).where(DietPlan.user_id == user_id)
        if pet_type:
            query = query.where(DietPlan.pet_type == pet_type)

        total_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(total_query)).scalar_one()

        offset = (page - 1) * page_size
        plans_query = query.order_by(DietPlan.created_at.desc()).offset(offset).limit(page_size)
        plans = (await self.db.execute(plans_query)).scalars().all()

        items = [
            DietPlanSummaryResponse(
                id=plan.id,
                task_id=plan.task_id,
                pet_id=plan.pet_id,
                pet_type=ResponsePetType(plan.pet_type),
                pet_breed=plan.pet_breed,
                pet_age=plan.pet_age,
                pet_weight=float(plan.pet_weight),
                health_status=plan.health_status,
                is_active=plan.is_active,
                applied_at=plan.applied_at,
                created_at=plan.created_at,
                updated_at=plan.updated_at,
            )
            for plan in plans
        ]

        return DietPlanListResponse(
            total=total,
            page=page,
            page_size=page_size,
            items=items,
        )

    async def get_diet_plan_detail(
        self,
        *,
        plan_id: str,
        user_id: str,
    ) -> DietPlanDetailResponse:
        from src.db.models import DietPlan

        result = await self.db.execute(
            select(DietPlan).where(
                DietPlan.id == plan_id,
                DietPlan.user_id == user_id,
            )
        )
        plan = result.scalars().first()

        if not plan:
            raise HTTPException(
                status_code=404,
                detail={"code": 404, "message": "饮食计划不存在", "detail": None},
            )

        return DietPlanDetailResponse(
            id=plan.id,
            task_id=plan.task_id,
            user_id=plan.user_id,
            pet_type=ResponsePetType(plan.pet_type),
            pet_breed=plan.pet_breed,
            pet_age=plan.pet_age,
            pet_weight=float(plan.pet_weight),
            health_status=plan.health_status,
            plan_data=plan.plan_data or {},
            created_at=plan.created_at,
            updated_at=plan.updated_at,
        )

    async def delete_diet_plan(
        self,
        *,
        plan_id: str,
        user_id: str,
    ) -> str:
        from src.db.models import DietPlan, MealRecord

        result = await self.db.execute(
            select(DietPlan).where(
                DietPlan.id == plan_id,
                DietPlan.user_id == user_id,
            )
        )
        plan = result.scalars().first()

        if not plan:
            raise HTTPException(
                status_code=404,
                detail={"code": 404, "message": "饮食计划不存在", "detail": None},
            )

        # 如果是活跃计划，清除状态
        if plan.is_active:
            plan.is_active = False
            plan.applied_at = None
            plan.active_start_date = None

        # 先删关联的 MealRecord（外键约束）
        await self.db.execute(
            delete(MealRecord).where(MealRecord.plan_id == plan_id)
        )
        await self.db.execute(delete(DietPlan).where(DietPlan.id == plan_id))
        await self.db.commit()
        return plan_id

    async def apply_diet_plan(
        self,
        *,
        plan_id: str,
        user_id: str,
    ) -> dict:
        """
        应用饮食计划：停用旧活跃计划 → 激活新计划 → 从今天起生成 MealRecords

        Args:
            plan_id: 要应用的计划 ID
            user_id: 当前用户 ID

        Returns:
            包含 plan_id, is_active, applied_at, meals_created 的字典
        """
        from src.db.models import DietPlan, MealRecord, Pet

        # 1. 校验计划归属
        result = await self.db.execute(
            select(DietPlan).where(
                DietPlan.id == plan_id,
                DietPlan.user_id == user_id,
            )
        )
        plan = result.scalars().first()
        if not plan:
            raise HTTPException(
                status_code=404,
                detail={"code": 404, "message": "饮食计划不存在", "detail": None},
            )

        if not plan.pet_id:
            raise HTTPException(
                status_code=400,
                detail={"code": 400, "message": "该计划未关联宠物，无法应用", "detail": None},
            )

        # 校验宠物存在
        pet_result = await self.db.execute(
            select(Pet).where(Pet.id == plan.pet_id, Pet.user_id == user_id, Pet.is_active == True)
        )
        pet = pet_result.scalars().first()
        if not pet:
            raise HTTPException(
                status_code=404,
                detail={"code": 404, "message": "关联宠物不存在", "detail": None},
            )

        today = date.today()
        now = datetime.now(timezone.utc)

        # 2. 停用该宠物当前活跃计划
        active_plans_result = await self.db.execute(
            select(DietPlan).where(
                DietPlan.pet_id == plan.pet_id,
                DietPlan.is_active == True,
                DietPlan.id != plan_id,
            )
        )
        for active_plan in active_plans_result.scalars().all():
            active_plan.is_active = False

        # 3. 删除旧计划的未来未完成 MealRecords
        await self.db.execute(
            delete(MealRecord).where(
                MealRecord.pet_id == plan.pet_id,
                MealRecord.meal_date >= today,
                MealRecord.is_completed == False,
            )
        )

        # 4. 激活新计划
        plan.is_active = True
        plan.applied_at = now
        plan.active_start_date = today

        await self.db.flush()

        # 5. 从今天起生成 MealRecords（4 周循环）
        meal_service = MealService(self.db)
        records = await meal_service.create_meal_records_from_plan(
            user_id=user_id,
            pet_id=plan.pet_id,
            plan_id=plan_id,
            plan_data=plan.plan_data,
        )

        return {
            "plan_id": plan_id,
            "is_active": True,
            "applied_at": now.isoformat(),
            "meals_created": len(records),
        }

    async def execute_diet_plan_stream(
        self,
        user_id: str,
        pet_info: Dict[str, Any],
    ) -> AsyncGenerator[str, None]:
        """
        执行饮食计划生成（流式模式 / SSE 与图执行解耦版）

        架构：
        1. 创建任务记录
        2. asyncio.create_task 启动独立后台任务执行 LangGraph 图
        3. SSE 端点订阅 Redis Streams 进度通道，把事件实时转发给客户端

        关键特性：
        - 客户端断开/挂起不影响后台图执行
        - 客户端重连可通过 GET /plans/stream?task_id=… 回放历史事件
        - 心跳通过 stream_with_heartbeat 保活

        Args:
            user_id: 用户 ID
            pet_info: 宠物信息字典

        Yields:
            SSE 格式事件字符串
        """
        # 创建任务记录使用独立 session（流式响应生命周期长）
        async with AsyncSessionLocal() as create_db:
            task_service = TaskService(create_db)
            task = await task_service.create_task(
                user_id=user_id,
                task_type="diet_plan",
                input_data=pet_info,
            )
            task_id = task.id

        yield create_sse_event({"type": "task_created", "task_id": task_id})

        # 启动后台任务（独立 session、独立生命周期、强引用防 GC）
        _spawn_background_task(self._run_plan_task_in_background(task_id, user_id, pet_info))

        # SSE 流：订阅事件总线 + 心跳保活
        # 使用 from_beginning=True 避免后台任务先于订阅 publish 时丢失早期事件
        async def _bus_to_sse() -> AsyncGenerator[str, None]:
            async for event in subscribe_events(task_id, from_beginning=True):
                yield create_sse_event(event)
            # 终止 sentinel 收到后通知客户端流结束
            yield create_sse_event({"type": "done", "task_id": task_id})

        async for chunk in stream_with_heartbeat(_bus_to_sse()):
            yield chunk

    async def _run_plan_task_in_background(
        self,
        task_id: str,
        user_id: str,
        pet_info: Dict[str, Any],
    ) -> None:
        """
        独立后台任务：执行 LangGraph 图并把所有进度事件发布到 Redis Stream。

        与 SSE 客户端连接完全解耦：客户端断开/挂起不影响本任务推进。
        所有 chunk 通过 publish_event 写入事件总线，结束后 publish_end_sentinel
        通知订阅者关流。

        Args:
            task_id: 任务 ID
            user_id: 用户 ID
            pet_info: 宠物信息
        """
        async with AsyncSessionLocal() as db:
            task_service = TaskService(db)
            completed_data: Dict[str, Any] = {}
            progress_state = {"progress": -1, "node": "", "saved_at": 0.0}

            try:
                graph = await self._build_graph()
                config = {
                    "configurable": {
                        "thread_id": task_id,
                        "user_id": user_id,
                    }
                }

                await task_service.update_task_status(task_id, "running")

                inputs, context = self._prepare_inputs(
                    pet_info,
                    user_id=user_id,
                )

                async for namespace, mode, chunk in graph.astream(
                    input=inputs,
                    config=config,
                    stream_mode=["custom"],
                    context=context,
                    subgraphs=True,
                ):
                    if mode != "custom":
                        continue
                    if not isinstance(chunk, dict):
                        continue

                    # 截获 completed 事件用于持久化
                    if chunk.get("type") == "completed":
                        completed_data.update(chunk)

                    # 更新数据库进度（节流）
                    await self._update_task_progress_from_chunk(
                        task_id,
                        chunk,
                        task_service=task_service,
                        progress_state=progress_state,
                    )

                    # 发布到事件总线供 SSE 端点消费
                    await publish_event(task_id, chunk)

                # 流式结束 → 持久化临时计划 → 通知订阅者
                await task_service.complete_task(task_id, completed_data)
                plan_id = str(uuid.uuid4())
                await self._save_temp_plan(plan_id, user_id, task_id, pet_info, completed_data)

                await publish_event(task_id, {
                    "type": "task_completed",
                    "task_id": task_id,
                    "plan_id": plan_id,
                })

            except asyncio.CancelledError:
                logger.warning("后台任务被取消: task_id=%s", task_id)
                try:
                    await task_service.fail_task(task_id, "任务已取消")
                except Exception:
                    pass
                await publish_event(task_id, {
                    "type": "error",
                    "task_id": task_id,
                    "error": "任务已取消",
                })
                raise
            except Exception as exc:
                logger.error("后台任务执行失败 task_id=%s: %s", task_id, exc, exc_info=True)
                try:
                    await db.rollback()
                except Exception:
                    pass
                try:
                    await task_service.fail_task(task_id, str(exc))
                except Exception as fail_err:
                    logger.error("标记任务失败时出错 task_id=%s: %s", task_id, fail_err)
                await publish_event(task_id, {
                    "type": "error",
                    "task_id": task_id,
                    "error": str(exc),
                })
            finally:
                # 无论如何都通知订阅者关流
                await publish_end_sentinel(task_id)

    async def resume_diet_plan_stream(
        self,
        user_id: str,
        task_id: str,
    ) -> AsyncGenerator[str, None]:
        """
        恢复流式连接（断线重连 / 移动端切回前台）

        新架构下后台任务独立运行，本端点只负责：
        1. 检查任务最终状态（已完成/失败 → 短路返回）
        2. 否则订阅事件流 from_beginning=True 回放历史 + 实时跟进

        Args:
            user_id: 用户 ID
            task_id: 任务 ID

        Yields:
            SSE 格式事件字符串
        """
        async with AsyncSessionLocal() as resume_db:
            task_service = TaskService(resume_db)
            try:
                task = await task_service.get_task(task_id, user_id)
            except Exception as exc:
                yield create_sse_event({"type": "error", "error": str(exc)})
                return

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

            # running 或 pending：先确认事件流存在
            has_history = await stream_exists(task_id)
            yield create_sse_event({
                "type": "resumed",
                "task_id": task.id,
                "status": task.status,
                "progress": task.progress,
                "current_node": task.current_node or "",
                "has_history": has_history,
            })

        # 释放 db session 后再开始长连接订阅，避免持有 session 时间过长
        async def _bus_to_sse() -> AsyncGenerator[str, None]:
            # from_beginning=True 让客户端拿到完整历史，前端按事件 type 自行去重/合并
            async for event in subscribe_events(task_id, from_beginning=True):
                yield create_sse_event(event)
            yield create_sse_event({"type": "done", "task_id": task_id})

        async for chunk in stream_with_heartbeat(_bus_to_sse()):
            yield chunk

    # ──────────── 内部方法 ────────────

    def _get_agent_version(self) -> Literal["v1", "v2"]:
        return settings.diet_plan_agent_version

    async def _build_graph(self) -> "CompiledStateGraph":
        """按配置返回当前饮食计划图。"""
        agent_version = self._get_agent_version()

        if agent_version == "v2":
            if self.app_state is not None:
                graph = getattr(self.app_state, "v2_graph", None)
                if graph is not None:
                    return graph

            from src.agent.v2.graph import graph as v2_graph

            return v2_graph

        # 延迟导入：只有真正触发计划生成时才加载 agent/v1 + langgraph 栈，
        # 避免冷启动成本分摊到不调用 LLM 的路径（登录、宠物 CRUD 等）。
        from src.agent.v1.graph import build_v1_graph

        return await build_v1_graph()

    def _prepare_inputs(self, pet_info: Dict[str, Any], *, user_id: str | None = None) -> tuple:
        """按配置准备图的输入数据和上下文。"""
        pet_info_filtered = {
            k: v for k, v in pet_info.items()
            if k in PetInformation.model_fields
        }
        pet_information = PetInformation(**pet_info_filtered)

        if self._get_agent_version() == "v2":
            from src.agent.v2.utils.context import ContextV2

            return {
                "pet_information": pet_information,
            }, ContextV2(
                user_id=user_id or "anonymous",
                pet_information=pet_information,
            )

        from src.agent.v1.utils.context import ContextV1

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

                running_task = await task_service.update_task_status(task_id, "running")

                inputs, context = self._prepare_inputs(
                    pet_info,
                    user_id=running_task.user_id,
                )
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
        *,
        task_service: "TaskService | None" = None,
    ) -> AsyncGenerator[str, None]:
        """
        轮询任务进度直到终态

        Args:
            task_id: 任务 ID
            user_id: 用户 ID
            poll_interval: 轮询间隔（秒）
            timeout: 超时时间（秒）
            task_service: 可选的独立 TaskService（流式方法传入）

        Yields:
            SSE 格式事件字符串
        """
        svc = task_service or self.task_service
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

            task = await svc.get_task(task_id, user_id)

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

    async def _update_task_progress_from_event(
        self,
        task_id: str,
        event: str,
        *,
        task_service: "TaskService | None" = None,
        progress_state: Dict[str, Any] | None = None,
    ):
        """
        从 SSE 事件字符串中提取进度并更新任务（兼容旧接口）

        新代码请使用 _update_task_progress_from_chunk 直接传 dict。
        """
        try:
            if event.startswith("data: "):
                data = json.loads(event[6:].strip())
                await self._update_task_progress_from_chunk(
                    task_id, data,
                    task_service=task_service,
                    progress_state=progress_state,
                )
        except (json.JSONDecodeError, KeyError):
            pass

    async def _update_task_progress_from_chunk(
        self,
        task_id: str,
        chunk: Dict[str, Any],
        *,
        task_service: "TaskService | None" = None,
        progress_state: Dict[str, Any] | None = None,
    ):
        """
        从原始 chunk dict 中提取进度并节流写入数据库。

        Args:
            task_id: 任务 ID
            chunk: ProgressEvent 序列化后的 dict（含 progress / node / type 等）
            task_service: 后台任务专用 TaskService（持有独立 session）
            progress_state: 跨调用复用的状态字典，控制写库频率
        """
        svc = task_service or self.task_service
        progress = chunk.get("progress")
        if progress is None:
            return

        try:
            progress_value = int(progress)
        except (TypeError, ValueError):
            return

        node = chunk.get("node", "") or chunk.get("type", "")

        if progress_state is None:
            await svc.update_task_progress_lightweight(task_id, progress_value, node)
            return

        now = asyncio.get_running_loop().time()
        last_progress = progress_state.get("progress", -1)
        last_node = progress_state.get("node", "")
        last_saved = progress_state.get("saved_at", 0.0)
        progress_delta = abs(progress_value - last_progress) if last_progress >= 0 else progress_value
        progress_changed = progress_value != last_progress
        node_changed = node != last_node
        enough_time_elapsed = now - last_saved >= PROGRESS_DB_WRITE_INTERVAL_SECONDS
        should_persist = (
            last_progress < 0
            or progress_value >= 100
            or (progress_changed and progress_delta >= PROGRESS_DB_WRITE_DELTA)
            or (node_changed and enough_time_elapsed)
            or (progress_changed and enough_time_elapsed)
        )

        if not should_persist:
            return

        await svc.update_task_progress_lightweight(task_id, progress_value, node)
        progress_state["progress"] = progress_value
        progress_state["node"] = node
        progress_state["saved_at"] = now

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
