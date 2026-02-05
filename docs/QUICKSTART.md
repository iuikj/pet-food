# 快速开始

> 5 分钟快速了解和对接 Pet-Food API

---

## 1. 启动后端

```bash
# 克隆项目
git clone <repository-url>
cd pet-food

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入 LLM API 密钥

# 启动依赖服务（PostgreSQL + Redis）
docker-compose -f deployment/docker-compose.dev.yml up -d

# 启动 API
uv pip install -e .
uvicorn src.api.main:app --reload
```

**访问地址：**
- FastAPI: http://localhost:8000
- API 文档: http://localhost:8000/docs
- pgAdmin: http://localhost:5050

---

## 2. 前端对接步骤

### 步骤 1：安装依赖

```bash
npm install axios
```

### 步骤 2：配置 API 客户端

```typescript
// src/api/client.ts
import axios from 'axios';

export const apiClient = axios.create({
  baseURL: 'http://localhost:8000/api/v1',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

// 请求拦截器 - 添加 Token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default apiClient;
```

### 步骤 3：用户登录

```typescript
import apiClient from './client';

interface LoginRequest {
  username: string;
  password: string;
}

async function login(username: string, password: string) {
  const response = await apiClient.post('/auth/login', { username, password });
  return response.data;
}

// 使用
const result = await login('user@example.com', 'password123');
if (result.code === 0) {
  localStorage.setItem('access_token', result.data.tokens.access_token);
  localStorage.setItem('refresh_token', result.data.tokens.refresh_token);
}
```

### 步骤 4：创建饮食计划（SSE 流式）

```typescript
import apiClient from './client';

interface PlanRequest {
  pet_type: 'cat' | 'dog';
  pet_age: number;
  pet_weight: number;
}

async function createPlanStream(data: PlanRequest) {
  const token = localStorage.getItem('access_token');
  const response = await fetch('http://localhost:8000/api/v1/plans/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify(data),
  });

  const eventSource = new EventSource(response.url);

  eventSource.addEventListener('open', () => {
    eventSource.setRequestHeader('Authorization', `Bearer ${token}`);
  }, { once: true });

  eventSource.addEventListener('message', (e) => {
    const data = JSON.parse(e.data);
    console.log('SSE 事件:', data.type, data);
  });

  return eventSource;
}

// 使用
const eventSource = await createPlanStream({
  pet_type: 'dog',
  pet_age: 2,
  pet_weight: 10,
});
```

---

## 3. SSE 事件类型

| 事件 | 说明 |
|------|------|
| `task_created` | 任务创建，返回 task_id |
| `resumed` | 连接恢复，返回当前进度 |
| `node_started` | 节点开始执行 |
| `node_completed` | 节点执行完成 |
| `tool_started` | 工具开始调用 |
| `tool_completed` | 工具调用完成 |
| `task_completed` | 任务完成，返回结果 |
| `error` | 错误发生 |

---

## 4. 断线重连

```typescript
// 连接断开后，通过 task_id 重连

async function reconnectStream(taskId: string) {
  const token = localStorage.getItem('access_token');
  const eventSource = new EventSource(`http://localhost:8000/api/v1/plans/stream?task_id=${taskId}`);

  eventSource.addEventListener('message', (e) => {
    const data = JSON.parse(e.data);

    if (data.type === 'resumed') {
      console.log('连接恢复，进度:', data.progress);
    } else if (data.type === 'task_completed') {
      console.log('任务完成:', data.result);
    }
  });

  eventSource.addEventListener('error', () => {
    console.error('连接错误，3 秒后重连...');
    setTimeout(() => reconnectStream(taskId), 3000);
  });
}
```

---

## 5. 错误处理

| 错误码 | 含义 | 处理方式 |
|--------|------|----------|
| 0 | 成功 | 使用返回数据 |
| 401 | Token 过期 | 刷新 Token 或跳转登录 |
| 403 | 资源不存在 | 提示刷新 |
| 404 | 资源已存在 | 提示更换用户名/邮箱 |
| 422 | 验证失败 | 提示重新输入验证码 |
| 429 | 请求过于频繁 | 显示冷却倒计时 |
| 500 | 服务器错误 | 提示稍后重试 |

---

## 常用问题

### Q: 如何获取 API 密钥？

A: 访问以下服务商网站获取 API 密钥：
- [DashScope](https://dashscope.console.aliyun.com/)
- [DeepSeek](https://platform.deepseek.com/)
- [ZAI](https://www.zai.cloud/)
- [Tavily](https://tavily.com/)

### Q: 如何配置 CORS？

A: 在 `.env` 文件中设置 `CORS_ORIGINS`，例如：
```env
CORS_ORIGINS=["http://localhost:3000","http://localhost:8080"]
```

### Q: SSE 连接中断了怎么办？

A: 使用混合架构的重连功能：
1. 查询任务状态：`GET /api/v1/tasks/{task_id}`
2. 如果任务在运行中，通过 `GET /api/v1/plans/stream?task_id=xxx` 重新建立 SSE 连接
3. 恢复事件会返回当前进度

### Q: Token 过期了怎么办？

A: 在响应拦截器中自动刷新 Token：
```typescript
if (response.status === 401) {
  const refreshResult = await apiClient.post('/auth/refresh', {
    refresh_token: localStorage.getItem('refresh_token'),
  });
  if (refreshResult.data.code === 0) {
    localStorage.setItem('access_token', refreshResult.data.data.access_token);
  }
}
```

---

## 详细文档

- [前端对接完整指南](./frontend/README.md)
- [后端开发文档](./backend/README.md)
- [部署指南](./deployment/README.md)
- [系统架构](./architecture/README.md)
- [错误码说明](./reference/ERROR_CODES.md)
- [SSE 事件说明](./reference/SSE_EVENTS.md)
- [混合架构设计](./reference/HYBRID_ARCHITECTURE.md)
