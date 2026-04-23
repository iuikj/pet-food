"""
基于 Redis Streams 的任务进度事件总线

将后台 LangGraph 任务的进度事件与 SSE 响应解耦：
- 后台任务执行时往 stream 写事件（publish_event）
- SSE 端点订阅 stream 实时读取（subscribe_events）
- 客户端断线重连时可从 stream 头部回放历史

设计要点：
- 每个任务一个 stream key: plan:events:{task_id}
- TTL 24 小时（与 temp_plan 对齐）
- MAXLEN ~ 2000 防止单流无限增长
- sentinel 事件 type='__end__' 标记流终止，订阅者收到后退出
"""
import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict

from src.db.redis import get_redis

logger = logging.getLogger(__name__)

EVENT_STREAM_KEY_PREFIX = "plan:events:"
EVENT_STREAM_TTL_SECONDS = 86400  # 24h
EVENT_STREAM_MAXLEN = 2000
END_SENTINEL_TYPE = "__end__"


def _stream_key(task_id: str) -> str:
    return f"{EVENT_STREAM_KEY_PREFIX}{task_id}"


async def publish_event(task_id: str, event: Dict[str, Any]) -> None:
    """
    向任务事件流发布一条事件。

    使用 pipeline 一次性 XADD + EXPIRE，确保 TTL 滚动刷新。
    """
    client = await get_redis()
    key = _stream_key(task_id)
    payload = json.dumps(event, ensure_ascii=False, default=str)
    try:
        pipe = client.pipeline()
        pipe.xadd(key, {"data": payload}, maxlen=EVENT_STREAM_MAXLEN, approximate=True)
        pipe.expire(key, EVENT_STREAM_TTL_SECONDS)
        await pipe.execute()
    except Exception as exc:
        logger.error("publish_event 失败 task_id=%s: %s", task_id, exc)


async def publish_end_sentinel(task_id: str) -> None:
    """写入终止 sentinel，订阅者收到后立即退出生成器。"""
    await publish_event(task_id, {"type": END_SENTINEL_TYPE})


async def subscribe_events(
    task_id: str,
    *,
    from_beginning: bool = False,
    block_ms: int = 15000,
    idle_timeout_seconds: float = 1800.0,
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    订阅任务事件流。

    Args:
        from_beginning: True 从头读所有历史事件再实时跟进；False 只读新事件
        block_ms: XREAD BLOCK 毫秒数（单次阻塞上限，影响心跳节奏）
        idle_timeout_seconds: 持续无任何事件超时退出，默认 30 分钟，
                              覆盖最长生成时长 + 余量，防止订阅永久挂起

    Yields:
        dict: 解码后的事件字典（不含 sentinel）
    """
    client = await get_redis()
    key = _stream_key(task_id)
    last_id = "0-0" if from_beginning else "$"

    last_event_at = asyncio.get_event_loop().time()

    while True:
        now = asyncio.get_event_loop().time()
        if now - last_event_at > idle_timeout_seconds:
            logger.info(
                "subscribe_events 空闲超时退出: task_id=%s last_id=%s", task_id, last_id
            )
            return

        try:
            resp = await client.xread({key: last_id}, count=100, block=block_ms)
        except Exception as exc:
            logger.error("XREAD 失败 task_id=%s: %s", task_id, exc)
            await asyncio.sleep(1)
            continue

        if not resp:
            # 阻塞超时未读到事件 — 继续下一轮，让外层心跳包装器有机会发心跳
            continue

        for _stream_name, entries in resp:
            for entry_id, fields in entries:
                last_id = entry_id
                last_event_at = asyncio.get_event_loop().time()
                raw = fields.get("data") if isinstance(fields, dict) else None
                if not raw:
                    continue
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("事件 JSON 解析失败 task_id=%s id=%s", task_id, entry_id)
                    continue
                if event.get("type") == END_SENTINEL_TYPE:
                    logger.info("收到终止 sentinel，退出订阅: task_id=%s", task_id)
                    return
                yield event


async def stream_exists(task_id: str) -> bool:
    """判断任务事件流是否存在（用于 resume 时判断历史是否可回放）。"""
    client = await get_redis()
    try:
        return bool(await client.exists(_stream_key(task_id)))
    except Exception as exc:
        logger.error("stream_exists 失败 task_id=%s: %s", task_id, exc)
        return False
