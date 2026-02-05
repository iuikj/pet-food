# API 接口文档

本文档包含 FastAPI 接口的详细使用示例。

---

## 目录

1. [认证接口](#认证接口)
2. [验证码接口](#验证码接口)
3. [饮食计划接口](#饮食计划接口)
4. [任务管理接口](#任务管理接口)
5. [通用响应格式](#通用响应格式)
6. [错误处理](#错误处理)

---

## 认证接口

### Base URL
```
http://localhost:8000/api/v1/auth
```

### 1. 用户注册（直接注册）

**接口**: `POST /auth/register`

**请求体**:
```json
{
  "username": "testuser",
  "email": "test@example.com",
  "password": "password123"
}
```

**验证规则**:
- `username`: 3-50 字符，只允许字母、数字、下划线和连字符
- `email`: 有效的邮箱格式（正则验证）
- `password`: 至少 6 个字符

**成功响应**:
```json
{
  "code": 0,
  "message": "注册成功",
  "data": {
    "user": {
      "id": "550e8400-e29b-41d4-a7c2-9866cc3e1",
      "username": "testuser",
      "email": "test@example.com",
      "is_active": true,
      "is_superuser": false,
      "created_at": "2025-02-04T00:00:00Z"
    },
    "tokens": {
      "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "token_type": "bearer",
      "expires_in": 1800
    }
  }
}
```

**错误响应**:
```json
// 用户名已存在
{
  "code": 404,
  "message": "用户名已存在",
  "detail": null
}

// 邮箱已被注册
{
  "code": 404,
  "message": "邮箱已被注册",
  "detail": null
}
```

### 2. 用户登录

**接口**: `POST /auth/login`

**请求体**:
```json
{
  "username": "test@example.com",  // 支持用户名或邮箱
  "password": "password123"
}
```

**成功响应**:
```json
{
  "code": 0,
  "message": "登录成功",
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

**错误响应**:
```json
// 用户不存在
{
  "code": 404,
  "message": "用户不存在",
  "detail": null
}

// 密码错误
{
  "code": 401,
  "message": "用户名或密码错误",
  "detail": null
}

// 用户已被禁用
{
  "code": 401,
  "message": "用户已被禁用",
  "detail": null
}
```

### 3. 刷新 Token

**接口**: `POST /auth/refresh`

**请求头**:
```
Authorization: Bearer {refresh_token}
```

**请求体**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**成功响应**:
```json
{
  "code": 0,
  "message": "刷新成功",
  "data": {
    "access_token": "新的访问令牌",
    "refresh_token": "新的刷新令牌",
    "token_type": "bearer",
    "expires_in": 1800
  }
}
```

**错误响应**:
```json
// Token 无效或过期
{
  "code": 401,
  "message": "Token 无效或已过期",
  "detail": "Invalid or expired token"
}
```

### 4. 获取用户信息

**接口**: `GET /auth/me`

**请求头**:
```
Authorization: Bearer {access_token}
```

**成功响应**:
```json
{
  "code": 0,
  "message": "获取成功",
  "data": {
    "id": "550e8400-e29b-41d4-a7c2-9866cc3e1",
    "username": "testuser",
    "email": "test@example.com",
    "is_active": true,
    "is_superuser": false,
    "created_at": "2025-02-04T00:00:00Z"
  }
}
```

### 5. 修改密码（需登录）

**接口**: `PUT /auth/password`

**请求头**:
```
Authorization: Bearer {access_token}
```

**请求体**:
```json
{
  "old_password": "password123",
  "new_password": "newpassword456"
}
```

**成功响应**:
```json
{
  "code": 0,
  "message": "密码修改成功",
  "data": null
}
```

**错误响应**:
```json
// 旧密码错误
{
  "code": 401,
  "message": "旧密码错误",
  "detail": null
}

// 密码不符合要求
{
  "code": 400,
  "message": "新密码必须至少 6 个字符",
  "detail": "Password must be at least 6 characters"
}
```

---

## 验证码接口

### Base URL
```
http://localhost:8000/api/v1/auth
```

### 1. 发送验证码

**接口**: `POST /auth/send-code`

**请求体**:
```json
{
  "email": "test@example.com",
  "code_type": "register"  // 或 "password_reset"
}
```

**成功响应**:
```json
{
  "code": 0,
  "message": "验证码已发送",
  "data": {
    "email": "test@example.com",
    "code_type": "register",
    "cooldown_seconds": 60,
    "remaining_daily_sends": 9,
    "expire_minutes": 10
  }
}
```

**错误响应**:
```json
// 发送过于频繁
{
  "code": 429,
  "message": "请求过于频繁，请稍后再试",
  "detail": "Too many requests, please try again later"
}

// 邮箱格式错误
{
  "code": 400,
  "message": "邮箱格式不正确",
  "detail": "Invalid email format"
}
```

### 2. 验证验证码

**接口**: `POST /auth/verify-code`

**请求体**:
```json
{
  "email": "test@example.com",
  "code": "123456",
  "code_type": "register"  // 或 "password_reset"
}
```

**成功响应**:
```json
{
  "code": 0,
  "message": "验证成功",
  "data": {
    "is_valid": true,
    "message": "验证码有效"
  }
}
```

**错误响应**:
```json
// 验证码错误或已过期
{
  "code": 422,
  "message": "验证码错误或已过期",
  "detail": null
}
```

### 3. 验证码注册（推荐）

**接口**: `POST /auth/verify-register`

**请求体**:
```json
{
  "username": "testuser",
  "email": "test@example.com",
  "password": "password123",
  "code": "123456"
}
```

**成功响应**:
```json
{
  "code": 0,
  "message": "注册成功",
  "data": {
    "user": { /* 用户信息 */ },
    "tokens": { /* Tokens */ }
  }
}
```

**错误响应**:
```json
// 验证码错误
{
  "code": 422,
  "message": "验证码错误或已过期",
  "detail": null
}

// 验证码已使用
{
  "code": 422,
  "message": "验证码已被使用",
  "detail": "Verification code has been used"
}

// 超过验证次数
{
  "code": 422,
  "message": "验证码尝试次数过多",
  "detail": "Too many attempts, please request a new code"
}
```

### 4. 找回密码 - 发送验证码

**接口**: `POST /auth/password/send-code`

**请求体**:
```json
{
  "email": "test@example.com"
}
```

**响应**:
```json
{
  "code": 0,
  "message": "如果该邮箱已注册，您将收到验证码",
  "data": {
    "email": "test@example.com",
    "code_type": "password_reset",
    "cooldown_seconds": 60,
    "remaining_daily_sends": 9,
    "expire_minutes": 10
  }
}
```

> 注意：无论邮箱是否存在，都会返回相同的响应（防止枚举攻击）

### 5. 找回密码 - 重置密码

**接口**: `POST /auth/password/reset`

**请求体**:
```json
{
  "email": "test@example.com",
  "code": "123456",
  "new_password": "newpassword456"
}
```

**成功响应**:
```json
{
  "code": 0,
  "message": "密码重置成功，请使用新密码登录",
  "data": null
}
```

**错误响应**:
```json
// 验证码错误或已过期
{
  "code": 422,
  "message": "验证码错误或已过期",
  "detail": null
}
```

---

## 饮食计划接口

### Base URL
```
http://localhost:8000/api/v1/plans
```

### 1. 创建饮食计划（同步）

**接口**: `POST /plans/create`

**请求头**:
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**请求体**:
```json
{
  "pet_type": "dog",
  "pet_breed": "金毛巡回",
  "age": 2,
  "pet_weight": 25,
  "pet_health_status": "健康"
  "special_requirements": "需要低脂饮食"
}
```

**成功响应**:
```json
{
  "code": 0,
  "message": "饮食计划创建成功",
  "data": {
    "plan_id": "550e8400-e29b-41d4-a7c2-9866cc3e1",
    "status": "pending"
  }
}
```

**错误响应**:
```json
// 未认证
{
  "code": 401,
  "message": "未认证，请重新登录",
  "detail": "Invalid or expired token"
}
```

### 2. 创建饮食计划（流式）

**接口**: `POST /plans/create`

**请求头**:
```
Authorization: Bearer {access_token}
Content-Type: application/json
Accept: text/event-stream
```

**请求体**:
```json
{
  "pet_type": "cat",
  "pet_breed": "英短",
  "age": 3,
  "pet_weight": 4,
  "pet_health_status": "健康",
  "use_stream": true
}
```

**SSE 流式响应**:
```
event: message_created

data: {"message": "开始分析宠物信息..."}

event: task_started
data: {"task_id": "550e8400-e29b-41d4-a7c2-9866cc3e1"}

event: tool_called
data: {"tool": "write_plan", "arguments": {...}}

event: agent_message
data: {"agent": "main", "content": "正在规划任务..."}

event: status_update
data: {"progress": 50, "message": "任务执行中..."}
```

### 3. 查询计划历史

**接口**: `GET /plans/history`

**请求头**:
```
Authorization: Bearer {access_token}
```

**成功响应**:
```json
{
  "code": 0,
  "message": "获取成功",
  "data": {
    "plans": [
      {
        "id": "plan-1",
        "pet_type": "dog",
        "created_at": "2025-02-04T00:00:00Z",
        "status": "completed"
      }
    ],
    "total": 1
  }
}
```

**分页参数**:
- `page`: 页码（从 1 开始）
- `page_size`: 每页数量（默认 10）

### 4. 获取计划详情

**接口**: `GET /plans/{plan_id}`

**请求头**:
```
Authorization: Bearer {access_token}
```

**成功响应**:
```json
{
  "code": 0,
  "message": "获取成功",
  "data": {
    "plan": {
      "id": "plan-1",
      "pet_type": "dog",
      "pet_breed": "金毛巡回",
      "pet_information": { /* 宠物信息 */ },
      "ai_suggestions": "...",
      "pet_diet_plan": { /* 月度计划 */ }
    }
  }
}
```

---

## 任务管理接口

### Base URL
```
http://localhost:8000/api/v1/tasks
```

### 1. 创建任务

**接口**: `POST /tasks/`

**请求头**:
```
Authorization: Bearer {access_token}
Content-Type: application/json
```

**请求体**:
```json
{
  "pet_type": "dog",
  "pet_breed": "金毛巡回",
  "age": 2,
  "pet_weight": 25,
  "pet_health_status": "健康",
  "use_stream": false
}
```

**成功响应**:
```json
{
  "code": 0,
  "message": "任务创建成功",
  "data": {
    "task_id": "task-1",
    "status": "pending",
    "created_at": "2025-02-04T00:00:00Z"
  }
}
```

### 2. 查询任务列表

**接口**: `GET /tasks/`

**查询参数**:
- `page`: 页码
- `page_size`: 每页数量
- `status`: 筛选状态（pending/running/completed/cancelled）

**请求头**:
```
Authorization: Bearer {access_token}
```

**成功响应**:
```json
{
  "code": 0,
  "message": "获取成功",
  "data": {
    "tasks": [
      {
        "id": "task-1",
        "status": "pending",
        "progress": 0,
        "created_at": "2025-02-04T00:00:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "page_size": 10,
      "total": 25
    }
  }
}
```

### 3. 查询任务详情

**接口**: `GET /tasks/{task_id}`

**请求头**:
```
Authorization: Bearer {access_token}
```

**成功响应**:
```json
{
  "code": 0,
  "message": "获取成功",
  "data": {
    "task": {
      "id": "task-1",
      "status": "running",
      "progress": 45,
      "result": null,
      "created_at": "2025-02-04T00:00:00Z",
      "updated_at": "2025-02-04T00:05:00Z"
    }
  }
}
```

### 4. 取消任务

**接口**: `POST /tasks/{task_id}/cancel`

**请求头**:
```
Authorization: Bearer {access_token}
```

**成功响应**:
```json
{
  "code": 0,
  "message": "任务已取消",
  "data": {
    "task_id": "task-1",
    "status": "cancelled"
  }
}
```

### 5. SSE 流式输出

**接口**: `GET /tasks/{task_id}/stream`

**请求头**:
```
Authorization: Bearer {access_token}
Accept: text/event-stream
```

**SSE 事件类型**:

| 事件 | 说明 | data 格式 |
|------|------|----------|
| `message_created` | 新消息推送 | `{"message": "..."}` |
| `task_started` | 任务开始 | `{"task_id": "..."}` |
| `task_progress` | 任务进度 | `{"progress": 50, "message": "..."}` |
| `task_completed` | 任务完成 | `{"task_id": "...", "result": {...}}` |
| `task_cancelled` | 任务取消 | `{"task_id": "..."}` |
| `error` | 错误发生 | `{"error": "..."}` |

**SSE 连接示例**:
```javascript
const eventSource = new EventSource('http://localhost:8000/api/v1/tasks/task-1/stream');

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('[%s] %o', data.event, data);

  if (data.event === 'task_completed') {
    eventSource.close();
  }
};

eventSource.onerror = (error) => {
  console.error('SSE Error:', error);
  eventSource.close();
};

// 连接时带上认证 token
eventSource.addEventListener('open', () => {
  eventSource.setRequestHeader('Authorization', `Bearer ${accessToken}`);
}, { once: true });
```

---

## 通用响应格式

### 成功响应
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { /* 返回数据 */ }
}
```

### 错误响应
```json
{
  "code": 错误码,
  "message": "错误描述",
  "detail": "详细错误信息（仅开发环境）"
}
```

---

## 错误处理

### Token 过期处理

```javascript
const fetchWithAuth = async (url, options = {}) => {
  const accessToken = localStorage.getItem('access_token');
  const response = await fetch(url, {
    ...options,
    headers: {
      ...options.headers,
      'Authorization': `Bearer ${accessToken}`
    }
  });

  if (response.status === 401) {
    // Token 过期，尝试刷新
    const refreshResult = await fetch('/api/v1/auth/refresh', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        refresh_token: localStorage.getItem('refresh_token')
      })
    });

    if (refreshResult.ok) {
      // 刷新成功，重试原请求
      return fetch(url, options);
    } else {
        // 刷新失败，跳转登录页
        window.location.href = '/login';
      }
    }
  }

  return response.json();
};
```

### 统一错误提示

```javascript
const errorMessages = {
  401: '请重新登录',
  403: '资源不存在，请刷新后重试',
  404: '用户名或邮箱已被注册',
  409: '资源已存在',
  422: '验证码错误，请重新输入',
  429: '请求过于频繁，请稍后再试',
  500: '服务器繁忙，请稍后再试'
};

const showError = (code) => {
  const message = errorMessages[code] || '未知错误';
  alert(message);
};
```

---

## 相关文档

- [API 错误码说明](../API_ERRORS.md)
- [API 配置说明](../API_CONFIG.md)
- [认证流程说明](../AUTH_FLOW.md)
- [系统架构图](../ARCHITECTURE.md)
- [部署指南](../DEPLOYMENT.md)
