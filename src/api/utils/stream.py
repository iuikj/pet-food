"""
流式输出工具
支持 SSE (Server-Sent Events) 格式输出 LangGraph 执行过程
使用 astream(stream_mode=["custom", "updates"]) 消费业务级 ProgressEvent
"""
import json
from typing import AsyncGenerator, Dict, Any
from datetime import datetime, timezone
from langgraph.graph.state import CompiledStateGraph


async def stream_langgraph_execution(
    graph: CompiledStateGraph,
    inputs: Dict[str, Any],
    config: Dict[str, Any],
    final_output: Dict[str, Any] | None = None,
) -> AsyncGenerator[str, None]:
    """
    流式执行 LangGraph 并返回 SSE 事件。

    使用 astream(stream_mode=["custom", "updates"]):
    - "custom" 模式接收各节点通过 get_stream_writer() 发送的 ProgressEvent
    - "updates" 模式接收每个节点的状态更新

    图只执行一次，通过 final_output 可变 dict 收集最终状态供调用方使用。

    Args:
        graph: 编译后的 LangGraph 图
        inputs: 图的输入数据
        config: 配置，包含 thread_id 等
        final_output: 可选的可变 dict，迭代结束后包含累积的最终状态（用于持久化）

    Yields:
        SSE 格式的事件字符串（"data: {json}\\n\\n"）
    """
    if final_output is None:
        final_output = {}

    try:
        async for mode, chunk in graph.astream(
            inputs, config=config, stream_mode=["custom", "updates"]
        ):
            if mode == "custom":
                # ProgressEvent 数据，直接转发为 SSE
                yield _create_sse_event(chunk)

            elif mode == "updates":
                # 节点状态更新
                if isinstance(chunk, dict):
                    for node_name, node_output in chunk.items():
                        # 累积最终状态
                        if isinstance(node_output, dict):
                            final_output.update(node_output)

                        yield _create_sse_event({
                            "type": "node_completed",
                            "node": node_name,
                            "output": _serialize_output(node_output),
                            "timestamp": _get_timestamp(),
                        })

        # 发送最终结果
        if "report" in final_output:
            yield _create_sse_event({
                "type": "final_result",
                "data": _serialize_output(final_output["report"]),
                "timestamp": _get_timestamp(),
            })

        yield _create_sse_event({
            "type": "done",
            "timestamp": _get_timestamp()
        })

    except Exception as e:
        yield _create_sse_event({
            "type": "error",
            "error": str(e),
            "timestamp": _get_timestamp()
        })


async def stream_langgraph_simple(
    graph: CompiledStateGraph,
    inputs: Dict[str, Any],
    config: Dict[str, Any]
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    简化的流式执行（返回原始事件，不格式化为 SSE）

    Args:
        graph: 编译后的 LangGraph 图
        inputs: 图的输入数据
        config: 配置

    Yields:
        原始事件字典
    """
    async for event in graph.astream_events(inputs, config=config, version="v2"):
        yield event


def _create_sse_event(data: Dict[str, Any]) -> str:
    """
    创建 SSE 格式的事件

    Args:
        data: 事件数据

    Returns:
        SSE 格式字符串（"data: {json}\\n\\n"）
    """
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
