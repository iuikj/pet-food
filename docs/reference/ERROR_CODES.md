# 错误码说明

> API 错误码详细说明和处理建议

---

## 错误码总览

| 错误码 | HTTP 状态 | 含义 | 相关接口 |
|---------|-------------|------|----------|
| 0 | 200 | 成功 | 所有接口 |
| 400 | 400 | 请求参数错误 | 部分接口 |
| 401 | 401 | 未认证 / Token 过期 | 部分接口 |
| 403 | 403 | 资源不存在 | 部分接口 |
| 404 | 404 | 资源已存在 | 注册接口 |
| 409 | 409 | 资源已存在 | 注册接口 |
| 422 | 422 | 验证失败 | 验证码接口 |
| 429 | 429 | 请求过多（速率限制） | 部分接口 |
| 500 | 500 | 服务器内部错误 | 所有接口 |

---

## 详细说明

### 0 - 成功

表示请求处理成功，返回期望的数据。

**响应格式：**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { /* 返回数据 */ }
}
```

**处理建议：**
- 检查 `code === 0` 判断请求成功
- 使用 `data` 字段获取返回的数据

---

### 400 - 请求参数错误

请求参数不符合预期格式或验证规则。

**常见原因：**
- 缺少必填参数
- 参数类型错误
- 参数值超出允许范围
- JSON 格式错误

**响应格式：**
```json
{
  "code": 400,
  "message": "缺少必填参数: pet_type",
  "detail": "The 'pet_type' field is required"
}
```

**处理建议：**
- 检查请求体是否符合 schema 定义
- 显示 `message` 或 `detail` 给用户

---

### 401 - 未认证

访问需要认证的接口时，未提供有效的凭证。

**常见原因：**
- 未携带 Authorization 请求头
- Access Token 已过期
- Refresh Token 已过期或被撤销
- Token 格式错误

**响应格式：**
```json
{
  "code": 401,
  "message": "未认证，请重新登录",
  "detail": "Invalid or expired token"
}
```

**处理建议：**
```typescript
// 统一错误处理
if (error.response?.status === 401) {
  // 1. 尝试刷新 Token
  const refreshToken = localStorage.getItem('refresh_token');
  if (refreshToken) {
    const result = await refreshToken(refreshToken);
    if (result.code === 0) {
      // 保存新 Token 并重试原请求
      return;
    }
  }

  // 2. 刷新失败，跳转登录页
  localStorage.clear();
  window.location.href = '/login';
}
```

---

### 403 - 资源不存在

请求的资源（如饮食计划、任务）不存在。

**常见原因：**
- 饮食计划 ID 不存在
- 任务 ID 不存在
- 用户 ID 不存在

**响应格式：**
```json
{
  "code": 403,
  "message": "饮食计划不存在",
  "detail": "Plan with id 'xxx' not found"
}
```

**处理建议：**
- 显示友好错误提示
- 引导用户刷新列表或返回上一页

---

### 404 - 资源已存在

尝试创建已存在的资源。

**常见原因：**
- 用户名已被注册
- 邮箱已被注册

**响应格式：**
```json
{
  "code": 404,
  "message": "用户名已存在",
  "detail": "Username 'user123' is already taken"
}
```

**处理建议：**
```typescript
// 注册表单错误提示
const registerErrors: Record<number, string> = {
  404: '该用户名或邮箱已被注册，请更换',
  409: '验证码错误或已过期',
};

// 显示错误
if (result.code === 404 || result.code === 409) {
  alert(registerErrors[result.code]);
}
```

---

### 409 - 资源已存在（与 404 语义相同）

部分接口使用 409 表示资源冲突，与 404 语义相同。

**相关接口：**
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/verify-register`

**处理建议：** 同 404

---

### 422 - 验证失败

验证码验证失败，但参数格式正确。

**常见原因：**
- 验证码错误
- 验证码已过期
- 验证码已被使用
- 验证码尝试次数过多

**响应格式：**
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

// 验证码尝试次数过多
{
  "code": 422,
  "message": "验证码尝试次数过多",
  "detail": "Too many attempts, please request a new code"
}
```

**处理建议：**
```typescript
if (result.code === 422) {
  const { message } = result;

  // 清空输入框并提示
  alert(message);
  setCodeInput('');

  // 如果是已使用，请求新验证码
  if (message.includes('已使用')) {
    await sendCode();
  }
}
```

---

### 429 - 请求过多（速率限制）

请求频率超出限制。

**相关接口：**
- 验证码发送接口
- 登录接口
- 注册接口

**响应格式：**
```json
{
  "code": 429,
  "message": "请求过于频繁，请稍后再试",
  "detail": "Too many requests, please try again later"
}
```

**处理建议：**
```typescript
// 显示冷却倒计时
if (result.code === 429 && result.data?.cooldown_seconds) {
  const cooldown = result.data.cooldown_seconds;
  startCooldown(cooldown);
}

function startCooldown(seconds: number) {
  let remaining = seconds;

  const timer = setInterval(() => {
    if (remaining <= 0) {
      clearInterval(timer);
      enableSendButton();
    } else {
      disableSendButton();
      setButtonText(`${remaining}秒后重试`);
    }
    remaining--;
  }, 1000);
}
```

---

### 500 - 服务器内部错误

服务器处理请求时发生未预期的错误。

**响应格式：**
```json
{
  "code": 500,
  "message": "服务器内部错误",
  "detail": null
}
```

**处理建议：**
- 显示友好提示："服务器繁忙，请稍后再试"
- 记录错误日志供后端排查

---

## TypeScript 类型定义

```typescript
// src/api/types.ts

export type ErrorCode =
  | 0    // 成功
  | 400  // 请求参数错误
  | 401  // 未认证
  | 403  // 资源不存在
  | 404  // 资源已存在
  | 409  // 资源已存在
  | 422  // 验证失败
  | 429  // 请求过多
  | 500; // 服务器内部错误

export interface ApiResponse<T = any> {
  code: ErrorCode;
  message: string;
  data: T;
  detail?: any;
}

export interface ApiError {
  code: ErrorCode;
  message: string;
  detail?: any;
}
```

---

## 错误处理 Hook

```typescript
// src/hooks/useApiError.ts
import { useCallback } from 'react';

const ERROR_MESSAGES: Record<number, string> = {
  401: '请重新登录',
  403: '资源不存在，请刷新后重试',
  404: '用户名或邮箱已被注册',
  409: '验证码错误或已过期',
  422: '验证码错误，请重新输入',
  429: '请求过于频繁，请稍后再试',
  500: '服务器繁忙，请稍后再试',
};

export function useApiError() {
  const handleError = useCallback((error: any) => {
    const status = error.response?.status;
    const data = error.response?.data as ApiResponse<null>;

    if (status && ERROR_MESSAGES[status]) {
      // 使用 Toast 显示错误
      showToast({
        title: '操作失败',
        description: ERROR_MESSAGES[status],
        variant: 'destructive',
      });

      // 401 特殊处理：跳转登录
      if (status === 401) {
        localStorage.clear();
        setTimeout(() => {
          window.location.href = '/login';
        }, 1000);
      }
    }
  }, []);

  return { handleError };
}
```

---

## 相关文档

- [前端对接指南](../frontend/README.md)
- [SSE 事件说明](./SSE_EVENTS.md)
