# SSE 事件说明

> Server-Sent Events (SSE) 事件类型和格式说明

---

## 事件总览

| 事件类型 | 说明 | 发送时机 |
|---------|------|----------|
| `task_created` | 任务创建成功 | POST /plans/stream 响应时 |
| `resumed` | 连接恢复 | GET /plans/stream 重连时 |
| `progress_update` | 进度更新 | 轮询获取到新进度时 |
| `node_started` | 节点开始执行 | Agent 节点启动时 |
| `node_completed` | 节点执行完成 | Agent 节点完成时 |
| `tool_started` | 工具开始调用 | 工具调用开始时 |
| `tool_completed` | 工具调用完成 | 工具调用完成时 |
| `llm_started` | LLM 开始生成 | LLM 调用开始时 |
| `llm_token` | LLM 生成内容 | LLM 流式输出 token 时 |
| `task_completed` | 任务完成 | 任务执行完成时 |
| `error` | 错误发生 | 任何错误时 |

---

## 事件格式

### task_created

```json
{
  "type": "task_created",
  "task_id": "550e8400-e29b-41d4-a7c2-9866cc3e1"
}
```

### resumed

```json
{
  "type": "resumed",
  "task_id": "550e8400-e29b-41d4-a7c2-9866cc3e1",
  "status": "running",
  "progress": 65,
  "current_node": "write_agent"
}
```

### progress_update

```json
{
  "type": "progress_update",
  "task_id": "550e8400-e29b-41d4-a7c2-9866cc3e1",
  "status": "running",
  "progress": 70,
  "current_node": "structure_agent",
  "timestamp": "2025-02-05T10:30:00Z"
}
```

### node_started

```json
{
  "type": "node_started",
  "node": "main_agent",
  "timestamp": "2025-02-05T10:30:00Z"
}
```

### node_completed

```json
{
  "type": "node_completed",
  "node": "main_agent",
  "progress": 30,
  "timestamp": "2025-02-05T10:31:00Z"
}
```

### tool_started

```json
{
  "type": "tool_started",
  "node": "sub_agent",
  "tool": "tavily_search",
  "input": {
    "query": "猫的营养需求"
  },
  "timestamp": "2025-02-05T10:32:00Z"
}
```

### tool_completed

```json
{
  "type": "tool_completed",
  "node": "sub_agent",
  "tool": "tavily_search",
  "output": {
    "results": [...]
  },
  "timestamp": "2025-02-05T10:33:00Z"
}
```

### llm_started

```json
{
  "type": "llm_started",
  "node": "sub_agent",
  "timestamp": "2025-02-05T10:34:00Z"
}
```

### llm_token

```json
{
  "type": "llm_token",
  "node": "sub_agent",
  "token": "正在",
  "timestamp": "2025-02-05T10:34:01Z"
}
```

### task_completed

```json
{
  "type": "task_completed",
  "task_id": "550e8400-e29b-41d4-a7c2-9866cc3e1",
  "result": {
    "pet_information": {...},
    "ai_suggestions": "...",
    "pet_diet_plan": {...}
  }
}
```

### error

```json
{
  "type": "error",
  "task_id": "550e8400-e29b-41d4-a7c2-9866cc3e1",
  "error": "连接超时或任务执行失败"
}
```

---

## 节点名称映射

| 节点 | 说明 |
|------|------|
| `main_agent` | 主智能体 - 任务规划与协调 |
| `sub_agent` | 子智能体 - 执行具体任务 |
| `write_agent` | 写入智能体 - 保存笔记 |
| `structure_agent` | 结构化智能体 - 解析周计划 |

---

## 前端处理示例

```typescript
// src/hooks/useSSE.ts
import { useEffect, useRef } from 'react';

interface SSEEventMap {
  'task_created': SSETaskCreatedEvent;
  'resumed': SSEResumedEvent;
  'progress_update': SSEProgressUpdateEvent;
  'node_started': SSENodeStartedEvent;
  'node_completed': SSENodeCompletedEvent;
  'tool_started': SSEToolStartedEvent;
  'tool_completed': SSEToolCompletedEvent;
  'llm_started': SSELLMStartedEvent;
  'llm_token': SSELLMTokenEvent;
  'task_completed': SSETaskCompletedEvent;
  'error': SSEErrorEvent;
}

export function useSSE(url: string) {
  const eventSourceRef = useRef<EventSource | null>(null);
  const [events, setEvents] = useState<SSEEvent[]>([]);

  useEffect(() => {
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.addEventListener('message', (e) => {
      try {
        const data = JSON.parse(e.data);
        const type = data.type as keyof SSEEventMap;

        // 根据事件类型处理
        switch (type) {
          case 'task_created':
            setEvents(prev => [...prev, { type, timestamp: new Date().toISOString() }]);
            break;

          case 'resumed':
            setEvents(prev => [...prev, { type, timestamp: new Date().toISOString(), ...data }]);
            break;

          case 'node_started':
            console.log(`节点开始: ${data.node}`);
            setEvents(prev => [...prev, { type, timestamp: new Date().toISOString(), ...data }]);
            break;

          case 'node_completed':
            console.log(`节点完成: ${data.node}`);
            setEvents(prev => [...prev, { type, timestamp: new Date().toISOString(), ...data }]);
            break;

          case 'task_completed':
            es.close();
            console.log('任务完成');
            break;

          case 'error':
            console.error(`错误: ${data.error}`);
            es.close();
            break;

          default:
            // 处理其他事件类型
            break;
        }
      } catch (err) {
        console.error('解析 SSE 事件失败:', err);
      }
    });

    es.addEventListener('error', (error) => {
      console.error('SSE 连接错误:', error);
      es.close();
    });

    return () => {
      es.close();
    };
  }, [url]);

  return { events };
}
```

---

## 浏览器兼容性

| 浏览器 | EventSource 支持 | Polyfill |
|---------|---------------|---------|
| Chrome 6+ | ✅ 原生支持 | - |
| Firefox 6+ | ✅ 原生支持 | - |
| Safari 5+ | ✅ 原生支持 | - |
| Edge | ✅ 原生支持 | - |
| IE 11 | ❌ 不支持 | [event-source-polyfill](https://github.com/Yaffle/EventSource) |

---

## Nginx 配置

```nginx
# 必须禁用缓冲
proxy_buffering off;
proxy_cache off;

# 设置超时
proxy_read_timeout 300s;
proxy_send_timeout 300s;

# 禁用 gzip 对 SSE 的压缩（保持文本格式）
# SSE 需要未压缩的连接
```

---

## 相关文档

- [前端对接指南](../frontend/README.md)
- [混合架构设计](./HYBRID_ARCHITECTURE.md)
- [错误码说明](./ERROR_CODES.md)
