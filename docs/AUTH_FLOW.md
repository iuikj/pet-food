# 认证系统实现说明

本文档描述了用户认证系统的完整实现流程，包括注册、登录、Token 刷新和用户信息获取。

---

## 目录

1. [技术架构](#技术架构)
2. [数据模型](#数据模型)
3. [安全机制](#安全机制)
4. [API 接口说明](#api-接口说明)
5. [客户端集成指南](#客户端集成指南)
6. [使用示例](#使用示例)
7. [最佳实践](#最佳实践)
8. [常见问题](#常见问题)

---

## 技术架构

### 认证流程图

```mermaid
graph LR
    User[用户] --> Web[Web 界面]
    User --> | 注册[注册]
    User --> | 登录[登录]

    Web <-->| API[FastAPI]

    API <-->| SMTP[邮件服务]
    API <-->| Redis[验证码缓存]
    API <-->| DB[(PostgreSQL]

    注册 -->| API
    登录 -->| API

    API <-->| Token刷新

    API --> | DB
```

### 分层架构

| 层 | 说明 | 技术栈 |
|------|------|----------|
| **表现层** | React/Vue 组件 | React 18+ / Vue 3+ |
| **API 层** | Axios 拦截封装 | 带自动 Token 刷新 |
| **路由层** | React Router / Vue Router | 路由守卫 |
| **状态层** | Zustand / Pinia | 认证状态管理 |
| **工具层** | 工具函数、加密解密 |

---

## 数据模型

### User 表

```sql
users 表
├── id (String, Primary Key)
├── username (String, Unique, Index)
├── email (String, Unique, Index)
├── hashed_password (String)
├── is_active (Boolean)
├── is_superuser (Boolean)
├── created_at (DateTime)
└── updated_at (DateTime)
```

### RefreshToken 表

```sql
refresh_tokens 表
├── id (String, Primary Key)
├── user_id (String, ForeignKey)
├── token (String, Unique, Index)
├── is_revoked (Boolean, Index)
├── expires_at (DateTime)
└── created_at (DateTime)
```

---

## 安全机制

| 安全措施 | 实现方式 |
|---------|---------|
| 密码存储 | bcrypt 哈希（成本因子 12） |
| 认证方式 | JWT (Access Token + Refresh Token） |
| Token 有效期 | Access: 30 分钟, Refresh: 7 天 |
| Token 撤销 | Refresh Token 黑名单机制 |
| 速率限制 | 基于 Redis 的分布式限流 |

---

## API 接口说明

### 认证接口

| 方法 | 路径 | 功能 | 认证要求 |
|------|------|----------|
| POST | `/auth/register` | 用户注册 | 无 |
| POST | `/auth/login` | 用户登录 | 无 |
| POST | `/auth/refresh` | 刷新 Token | Refresh Token |
| GET | `/auth/me` | 获取用户信息 | Access Token |

### 验证码接口

| 方法 | 路径 | 功能 |
|------|------|----------|
| POST | `/auth/send-code` | 发送验证码 | 无 |
| POST | `/auth/verify-code` | 验证验证码 | 无 |
| POST | `/auth/verify-register` | 验证码注册 | 无 |
| POST | `/auth/password/send-code` | 找回密码验证码 | 无 |
| POST | `/auth/password/reset` | 重置密码 | 无 |
| PUT | `/auth/password` | 修改密码 | Access Token |

---

## 客户端集成指南

### 1. Axios 客户端配置

```typescript
import axios from 'axios';

const apiClient = axios.create({
  baseURL: 'http://localhost:8000/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
});

// 请求拦截器 - 添加认证 Token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器 - 处理 Token 过期（自动刷新）
apiClient.interceptors.response.use(
  async (response) => {
    if (response.status === 401) {
      // Token 过期，自动刷新
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        const refreshResponse = await axios.post('/auth/refresh', {
          refresh_token: refreshToken
        });
        if (refreshResponse.data.code === 0) {
          localStorage.setItem('access_token', refreshResponse.data.data.access_token);
          localStorage.setItem('refresh_token', refreshResponse.data.data.refresh_token);
        }
      }
    }
    return response;
  }
);

export default apiClient;
```

### 2. 登录流程

```
1. 用户输入用户名/邮箱 + 密码
2. 调用 POST /auth/login
3. 保存返回的 access_token 和 refresh_token
4. 后续请求携带 Bearer token
5. 检测到 401 时自动刷新 token
```

### 3. 注册流程

```
选项 A: 直接注册
1. 用户输入信息
2. 调用 POST /auth/register
3. 保存 token

选项 B: 验证码注册（推荐）
1. 用户输入邮箱
2. 调用 POST /auth/send-code 获取验证码
3. 用户输入验证码 + 其他信息
4. 调用 POST /auth/verify-register
5. 保存 token
```

### 4. 找回密码流程

```
1. 用户输入邮箱
2. 调用 POST /auth/password/send-code
3. 用户输入验证码 + 新密码
4. 调用 POST /auth/password/reset
5. 提示用户使用新密码登录
```

---

## 使用示例

### 登录请求

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "test@example.com",
    "password": "password123"
  }'
```

### 刷新 Token 请求

```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_REFRESH_TOKEN" \
  -d '{
    "refresh_token": "YOUR_REFRESH_TOKEN"
  }'
```

### 验证码注册请求

```bash
curl -X POST http://localhost:8000/api/v1/auth/verify-register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "password123",
    "code": "123456"
  }'
```

---

## 最佳实践

### Token 存储

```javascript
// 推荐：存储在 localStorage
localStorage.setItem('access_token', accessToken);
localStorage.setItem('refresh_token', refreshToken);

// 移动端：考虑使用 Keychain
// 生产环境：考虑使用 HttpOnly Cookie
```

### 自动刷新

```javascript
// 在响应拦截器中实现
// 检测 401 错误自动刷新
// 刷新成功后重试原请求
```

### 安全注意事项

1. **HTTPS**: 生产环境必须使用 HTTPS
2. **XSS**: 防止 XSS，不信任用户输入
3. **CSRF**: API 已处理，前端无需额外处理
4. **Token 安全**: 不要将 Token 暴露在 URL 或日志中

---

## 常见问题

### Q1: Token 过期后如何处理？

A: 客户端应该：
1. 检测 API 返回的 401 状态码
2. 使用 Refresh Token 调用刷新接口
3. 如果刷新成功，重试原请求
4. 如果刷新失败，跳转到登录页面

### Q2: 验证码发送失败？

A: 检查以下几点：
1. SMTP 配置是否正确
2. 邮箱授权码是否正确
3. QQ 邮箱需要在设置中开启 SMTP 服务
4. Gmail 需要开启两步验证并生成应用专用密码

### Q3: 如何确保用户安全？

A: 实现以下安全措施：
- 密码哈希存储
- HTTPS 加密传输
- Token 短期有效
- 请求速率限制
- 记录异常登录尝试

---

## 相关文档

- [API 接口文档](api/)
- [API 错误码说明](api/errors.md)
- [API 配置说明](../API_CONFIG.md)
- [前端开发指南](frontend/)
