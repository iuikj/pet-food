"""
流式输出工具
支持 SSE (Server-Sent Events) 格式输出 LangGraph 执行过程
基于 LangGraph 最新的 astream_events API
"""
import json
from typing import AsyncGenerator, Dict, Any
from datetime import datetime, timezone
from langgraph.graph.state import CompiledStateGraph



async def stream_langgraph_execution(
    graph: CompiledStateGraph,
    inputs: Dict[str, Any],
    config: Dict[str, Any]
) -> AsyncGenerator[str, None]:
    """
    流式执行 LangGraph 并返回 SSE 事件

    基于 LangGraph v1.0+ 的 astream_events API
    参考: https://langchain-ai/langgraph

    Args:
        graph: 编译后的 LangGraph 图
        inputs: 图的输入数据
        config: 配置，包含 thread_id 等

    Yields:
        SSE 格式的事件字符串（"data: {json}\\n\\n"）
    """
    try:
        # 使用最新的 astream_events API (v2)
        async for event in graph.astream_events(
            inputs,
            config=config,
            version="v2"  # 使用 v2 版本的事件格式
        ):
            event_type = event.get("event", "")
            event_name = event.get("name", "")

            # 解析事件类型
            if "on_chain_start" in event_type:
                # 链/节点开始执行
                yield _create_sse_event({
                    "type": "node_started",
                    "node": event_name,
                    "timestamp": _get_timestamp()
                })

            elif "on_chain_end" in event_type:
                # 链/节点执行完成
                output = event.get("data", {}).get("output", {})
                yield _create_sse_event({
                    "type": "node_completed",
                    "node": event_name,
                    "output": _serialize_output(output),
                    "timestamp": _get_timestamp()
                })

            elif "on_chat_model_start" in event_type:
                # LLM 开始生成
                yield _create_sse_event({
                    "type": "llm_started",
                    "node": event_name,
                    "timestamp": _get_timestamp()
                })

            elif "on_chat_model_stream" in event_type:
                # LLM 流式输出
                chunk = event.get("data", {}).get("chunk", {})
                content = getattr(chunk, "content", None)

                if content:
                    yield _create_sse_event({
                        "type": "llm_token",
                        "node": event_name,
                        "token": content,
                        "timestamp": _get_timestamp()
                    })

            elif "on_chat_model_end" in event_type:
                # LLM 生成完成
                yield _create_sse_event({
                    "type": "llm_completed",
                    "node": event_name,
                    "timestamp": _get_timestamp()
                })

            elif "on_tool_start" in event_type:
                # 工具开始调用
                tool_name = event.get("data", {}).get("input", {}).get("name", "unknown")
                yield _create_sse_event({
                    "type": "tool_started",
                    "node": event_name,
                    "tool": tool_name,
                    "timestamp": _get_timestamp()
                })

            elif "on_tool_end" in event_type:
                # 工具调用完成
                tool_output = event.get("data", {}).get("output", {})
                yield _create_sse_event({
                    "type": "tool_completed",
                    "node": event_name,
                    "output": _serialize_output(tool_output),
                    "timestamp": _get_timestamp()
                })

            elif "error" in event_type.lower():
                # 错误事件
                error = event.get("data", {})
                yield _create_sse_event({
                    "type": "error",
                    "node": event_name,
                    "error": str(error),
                    "timestamp": _get_timestamp()
                })

        # 流式输出完成
        yield _create_sse_event({
            "type": "done",
            "timestamp": _get_timestamp()
        })

    except Exception as e:
        # 发生错误
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
    if hasattr(output, "dict"):
        # Pydantic 模型
        return output.dict()
    elif isinstance(output, (dict, list, str, int, float, bool, type(None))):
        # 基本类型
        return output
    else:
        # 其他类型转为字符串
        return str(output)


def _get_timestamp() -> str:
    """
    获取当前时间戳（ISO 格式）

    Returns:
        ISO 格式时间戳
    """
    from datetime import datetime
    return datetime.now(timezone.utc).isoformat() + "Z"
