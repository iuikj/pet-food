# API 参考手册

> FastAPI 接口快速参考手册

---

## 基础信息

| 项目 | 说明 |
|------|------|
| **Base URL** | `http://localhost:8000/api/v1` |
| **认证方式** | JWT Bearer Token |
| **响应格式** | `{ code: number, message: string, data: any }` |

---

## API 端点总览

### 认证模块

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|----------|
| POST | `/auth/register` | 直接注册 | 无 |
| POST | `/auth/login` | 用户登录 | 无 |
| POST | `/auth/refresh` | 刷新 Token | Refresh Token |
| GET | `/auth/me` | 获取用户信息 | Access Token |
| PUT | `/auth/password` | 修改密码 | Access Token |

### 验证码模块

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|----------|
| POST | `/auth/send-code` | 发送验证码 | 无 |
| POST | `/auth/verify-code` | 验证验证码 | 无 |
| POST | `/auth/verify-register` | 验证码注册 | 无 |
| POST | `/auth/password/send-code` | 找回密码验证码 | 无 |
| POST | `/auth/password/reset` | 重置密码 | 无 |

### 饮食计划模块

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|----------|
| POST | `/plans/` | 创建饮食计划（异步） | Access Token |
| POST | `/plans/stream` | 创建饮食计划（流式） | Access Token |
| GET | `/plans/` | 获取计划列表 | Access Token |
| GET | `/plans/{plan_id}` | 获取计划详情 | Access Token |
| DELETE | `/plans/{plan_id}` | 删除计划 | Access Token |

### 任务管理模块

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|----------|
| GET | `/tasks/` | 获取任务列表 | Access Token |
| GET | `/tasks/{task_id}` | 获取任务详情 | Access Token |
| GET | `/tasks/{task_id}/stream` | SSE 流式监听任务 | Access Token |
| GET | `/tasks/{task_id}/result` | 获取任务结果 | Access Token |
| DELETE | `/tasks/{task_id}` | 取消任务 | Access Token |

---

## 认证接口

### POST /auth/register

**请求：**
```json
{
  "username": "testuser",
  "email": "test@example.com",
  "password": "password123"
}
```

**响应（成功）：**
```json
{
  "code": 0,
  "message": "注册成功",
  "data": {
    "user": { /* 用户信息 */ },
    "tokens": {
      "access_token": "...",
      "refresh_token": "...",
      "token_type": "bearer",
      "expires_in": 1800
    }
  }
}
```

### POST /auth/login

**请求：**
```json
{
  "username": "test@example.com",
  "password": "password123"
}
```

**响应（成功）：**
```json
{
  "code": 0,
  "message": "登录成功",
  "data": {
    "user": { /* 用户信息 */ },
    "tokens": { /* 同上 */ }
  }
}
```

---

## 饮食计划接口

### POST /plans/stream

**请求：**
```json
{
  "pet_type": "dog",
  "pet_breed": "金毛巡回",
  "pet_age": 2,
  "pet_weight": 10,
  "health_status": "健康"
}
```

**响应（SSE 流）：**
```
data: {"type":"task_created","task_id":"xxx"}

data: {"type":"node_started","node":"main_agent"}

data: {"type":"node_completed","node":"main_agent","progress":30}

data: {"type":"tool_started","tool":"write_plan"}

data: {"type":"task_completed","task_id":"xxx","result":{...}}
```

### GET /plans/stream?task_id=xxx

**说明：** 恢复 SSE 连接（断线重连）

**响应（恢复）：**
```json
{
  "type": "resumed",
  "task_id": "xxx",
  "status": "running",
  "progress": 65,
  "current_node": "write_agent"
}
```

---

## 任务管理接口

### GET /tasks/{task_id}

**请求：**
```
GET /api/v1/tasks/xxx
Authorization: Bearer {access_token}
```

**响应：**
```json
{
  "code": 0,
  "message": "获取成功",
  "data": {
    "id": "xxx",
    "task_type": "diet_plan",
    "status": "running",
    "progress": 45,
    "current_node": "sub_agent",
    "input_data": { /* 宠物信息 */ },
    "output_data": null,
    "started_at": "2025-02-05T10:30:00Z",
    "completed_at": null
  }
}
```

---

## TypeScript 类型

```typescript
// 请求类型
interface LoginRequest {
  username: string;
  password: string;
}

interface PlanRequest {
  pet_type: 'cat' | 'dog';
  pet_breed?: string;
  pet_age: number;
  pet_weight: number;
  health_status?: string;
}

// 响应类型
interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}

interface UserInfo {
  id: string;
  username: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
}

interface TokenData {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

// SSE 事件类型
type SSEEventType =
  | 'task_created'
  | 'resumed'
  | 'progress_update'
  | 'node_started'
  | 'node_completed'
  | 'tool_started'
  | 'tool_completed'
  | 'llm_started'
  | 'llm_token'
  | 'task_completed'
  | 'error';
```

---

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|----------|
| `API_HOST` | 服务监听地址 | 0.0.0.0 |
| `API_PORT` | 服务端口 | 8000 |
| `DATABASE_URL` | PostgreSQL 连接字符串 | postgresql+asyncpg://... |
| `REDIS_URL` | Redis 连接字符串 | redis://localhost:6379/0 |
| `JWT_SECRET_KEY` | JWT 签名密钥 | **必须修改** |
| `CORS_ORIGINS` | 允许的跨域来源 | ["http://localhost:3000"] |
| `DASHSCOPE_API_KEY` | DashScope API 密钥 | - |
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 | - |
| `ZAI_API_KEY` | ZAI API 密钥 | - |
| `TAVILIY_API_KEY` | Tavily 搜索 API 密钥 | - |

---

## 相关文档

- [快速开始](./QUICKSTART.md)
- [前端对接指南](./frontend/README.md)
- [错误码说明](./reference/ERROR_CODES.md)
- [SSE 事件说明](./reference/SSE_EVENTS.md)
- [混合架构设计](./reference/HYBRID_ARCHITECTURE.md)
