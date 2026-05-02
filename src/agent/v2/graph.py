"""
V2 Agent 图拓扑

START → plan_agent → generate_coordination_guide → dispatch_weeks → week_agent (×4 并行) → gather_and_structure → END

Checkpoint：复用 settings.database_url 自动接入 PostgreSQL 持久化。
- 由 FastAPI lifespan 托管：startup 打开连接池，shutdown 关闭
- 首次启动自动建表（checkpoints / checkpoint_blobs / checkpoint_writes）
- 非 PostgreSQL 或显式关闭时降级为无持久化模式
"""
import logging
import os
from typing import Any

from langgraph.graph.state import StateGraph, START, END
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from src.api.config import settings
from src.agent.v2.node import (
    plan_agent_with_sub,
    generate_coordination_guide,
    dispatch_weeks,
    week_agent,
    gather_and_structure,
)
from src.agent.v2.state import State
from src.agent.v2.utils.context import ContextV2

logger = logging.getLogger(__name__)

# 限制 checkpoint 反序列化范围，防止数据库被攻破时执行任意代码（官方安全建议）
os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")


def _build_graph_definition() -> StateGraph:
    """定义节点与边，不绑定 checkpoint（checkpoint 由 lifespan 托管）。"""
    return (
        StateGraph(state_schema=State, context_schema=ContextV2)
        .add_node("plan_agent", plan_agent_with_sub)
        .add_node("generate_coordination_guide", generate_coordination_guide)
        .add_node("dispatch_weeks", dispatch_weeks)
        .add_node("week_agent", week_agent)
        .add_node("gather_and_structure", gather_and_structure)
        .add_edge(START, "plan_agent")
        .add_edge("plan_agent", "generate_coordination_guide")
        .add_edge("generate_coordination_guide", "dispatch_weeks")
        .add_edge("week_agent", "gather_and_structure")
        .add_edge("gather_and_structure", END)
    )


def compile_v2_graph(*, checkpointer: Any = None):
    """编译 V2 图。

    传入 checkpointer 后，调用时需要：
        config = {"configurable": {"thread_id": "<plan_id>"}}
        await graph.ainvoke(input, config, durability="exit")
    """
    return _build_graph_definition().compile(checkpointer=checkpointer).with_config(recursion_limit=1000)


def _resolve_postgres_dsn() -> str | None:
    """从 settings.database_url 推导 psycopg 可识别的 PostgreSQL DSN。

    规则：
    - 显式关闭 → None
    - 非 PostgreSQL（如 sqlite）→ None
    - 移除 SQLAlchemy 方言后缀（+asyncpg / +psycopg2）
    """
    if not settings.langgraph_checkpoint_enabled:
        return None

    dsn = settings.database_url
    for driver in ("+asyncpg", "+psycopg2", "+psycopg"):
        dsn = dsn.replace(driver, "")

    if not dsn.lower().startswith(("postgres://", "postgresql://")):
        logger.warning("V2 checkpoint 跳过：当前数据库不是 PostgreSQL")
        return None

    return dsn


async def open_v2_checkpointer() -> tuple[AsyncConnectionPool, AsyncPostgresSaver] | None:
    """打开 V2 PostgreSQL checkpointer（连接池模式）。

    必备 psycopg 参数（kwargs 注入到每个连接）：
    - autocommit=True：setup() 建表 DDL 必须立即提交
    - row_factory=dict_row：PostgresSaver 通过 row["col"] 访问字段

    返回 (pool, checkpointer)；失败或未启用返回 None。
    调用方在 lifespan shutdown 时 `await pool.close()` 即可。
    """
    dsn = _resolve_postgres_dsn()
    if not dsn:
        return None

    pool: AsyncConnectionPool | None = None
    try:
        pool = AsyncConnectionPool(
            conninfo=dsn,
            min_size=1,
            max_size=20,
            kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
            open=False,
        )
        await pool.open()

        checkpointer = AsyncPostgresSaver(pool)
        try:
            await checkpointer.setup()
        except Exception as setup_exc:
            # 多 worker 并发建表时，第二个进程可能遇到 UniqueViolation（表/类型已存在）
            # 这是正常的，静默忽略即可（setup() 内部已有 IF NOT EXISTS，但 CREATE TYPE 仍会冲突）
            if "already exists" in str(setup_exc).lower():
                logger.debug("V2 checkpoint 表已存在（多 worker 并发建表，忽略）：%s", setup_exc)
            else:
                raise

        logger.info("V2 PostgreSQL checkpoint 已启用")
        return pool, checkpointer
    except Exception as exc:
        logger.error("V2 checkpoint 初始化失败，降级为无持久化模式：%s", exc, exc_info=True)
        if pool is not None:
            try:
                await pool.close()
            except Exception:
                pass
        return None


# 无 checkpoint 默认图，供本地调试 / langgraph.json 直接引用
graph = compile_v2_graph()
