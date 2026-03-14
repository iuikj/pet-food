"""
流式输出工具
支持 SSE (Server-Sent Events) 格式输出 LangGraph 执行过程
使用 astream(stream_mode=["custom"]) 消费业务级 ProgressEvent

心跳机制：通过 SSE 注释行 (`: heartbeat`) 保持连接活跃，
防止客户端/代理/Nginx 因空闲超时断开长连接。
"""
import json
import asyncio
import logging
from typing import AsyncGenerator, Dict, Any
from datetime import datetime, timezone
from langgraph.graph.state import CompiledStateGraph

logger = logging.getLogger(__name__)

# SSE 心跳间隔（秒）— 必须小于 Nginx proxy_read_timeout（默认 60s）
HEARTBEAT_INTERVAL = 15


async def stream_with_heartbeat(
    event_gen: AsyncGenerator[str, None],
    interval: float = HEARTBEAT_INTERVAL,
) -> AsyncGenerator[str, None]:
    """
    为异步事件生成器添加心跳保活。

    使用 asyncio.Queue + 后台生产者模式：
    - 生产者从 event_gen 读取真实事件放入队列
    - 消费者从队列读取，超时时发送 SSE 注释心跳

    SSE 注释格式 `: heartbeat\\n\\n` 符合规范，客户端应忽略。

    Args:
        event_gen: 原始 SSE 事件异步生成器
        interval: 心跳间隔秒数

    Yields:
        SSE 事件字符串（真实事件或心跳注释）
    """
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def _producer():
        try:
            async for event in event_gen:
                await queue.put(event)
        except Exception as e:
            # 生产者异常：将错误事件放入队列
            await queue.put(create_sse_event({
                "type": "error",
                "error": str(e),
                "timestamp": _get_timestamp(),
            }))
        finally:
            await queue.put(None)  # 哨兵值，标记流结束

    producer_task = asyncio.create_task(_producer())

    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=interval)
                if item is None:
                    break
                yield item
            except asyncio.TimeoutError:
                # 超时未收到事件 → 发送心跳保活
                yield ": heartbeat\n\n"
    finally:
        producer_task.cancel()
        try:
            await producer_task
        except asyncio.CancelledError:
            pass


async def stream_langgraph_execution(
    graph: CompiledStateGraph,
    inputs: Dict[str, Any],
    config: Dict[str, Any],
    completed_data: Dict[str, Any] | None = None,
    context: Any = None,
) -> AsyncGenerator[str, None]:
    """
    流式执行 LangGraph 并返回 SSE 事件。

    使用 astream(stream_mode=["custom"]):
    - "custom" 模式接收各节点通过 get_stream_writer() 发送的 ProgressEvent
    - 遇到 type=="completed" 的 chunk 时，将其存入 completed_data 供调用方使用

    图只执行一次，通过 completed_data 可变 dict 收集最终计划数据供调用方持久化。

    Args:
        graph: 编译后的 LangGraph 图
        inputs: 图的输入数据
        config: 配置，包含 thread_id 等
        completed_data: 可选的可变 dict，用于截获 completed 事件数据（含 plans + ai_suggestions）
        context: 可选的上下文对象（V1 使用 ContextV1，V0 为 None）

    Yields:
        SSE 格式的事件字符串（"data: {json}\\n\\n"）
    """
    try:
        async for namespace, mode, chunk in graph.astream(
            input=inputs,
            config=config,
            stream_mode=["custom"],
            context=context,
            subgraphs=True
        ):
            if mode == "custom":
                # 截获 completed 事件数据，供调用方存 Redis
                if (completed_data is not None
                        and isinstance(chunk, dict)
                        and chunk.get("type") == "completed"):
                    completed_data.update(chunk)

                # ProgressEvent 数据，直接转发为 SSE
                yield create_sse_event(chunk)

        yield create_sse_event({
            "type": "done",
            "timestamp": _get_timestamp()
        })

    except Exception as e:
        yield create_sse_event({
            "type": "error",
            "error": str(e),
            "timestamp": _get_timestamp()
        })


def create_sse_event(data: Dict[str, Any]) -> str:
    """
    创建 SSE 格式的事件

    Args:
        data: 事件数据

    Returns:
        SSE 格式字符串（"data: {json}\\n\\n"）
    """
    logger.debug("create_sse_event: %s", data)
    json_str = json.dumps(data, ensure_ascii=False)
    return f"data: {json_str}\n\n"


def _serialize_output(output: Any) -> Any:
    """
    序列化输出数据

    Args:
        output: 原始输出

    Returns:
        序列化后的输出
    """
    if hasattr(output, "model_dump"):
        # Pydantic v2 模型
        return output.model_dump()
    elif hasattr(output, "dict"):
        # Pydantic v1 模型
        return output.dict()
    elif isinstance(output, (dict, list, str, int, float, bool, type(None))):
        return output
    else:
        return str(output)


def _get_timestamp() -> str:
    """
    获取当前时间戳（ISO 格式）

    Returns:
        ISO 格式时间戳
    """
    return datetime.now(timezone.utc).isoformat() + "Z"
