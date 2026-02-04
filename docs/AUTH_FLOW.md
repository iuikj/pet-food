# 认证系统实现计划

## 概述

本文档描述了用户认证系统的完整实现流程，包括注册、登录、Token 刷新和用户信息获取。

---

## 技术架构

### 数据模型

```
users 表
├── id (String, Primary Key)
├── username (String, Unique, Index)
├── email (String, Unique, Index)
├── hashed_password (String)
├── is_active (Boolean)
├── is_superuser (Boolean)
├── created_at (DateTime)
└── updated_at (DateTime)

refresh_tokens 表
├── id (String, Primary Key)
├── user_id (String, ForeignKey)
├── token (String, Unique, Index)
├── is_revoked (Boolean, Index)
├── expires_at (DateTime)
└── created_at (DateTime)
```

### 安全机制

| 安全措施 | 实现方式 |
|---------|---------|
| 密码存储 | bcrypt 哈希（成本因子 12）|
| 认证方式 | JWT (Access Token + Refresh Token）|
| Token 有效期 | Access: 30 分钟, Refresh: 7 天 |
| Token 撤销 | Refresh Token 黑名单机制 |
| 速率限制 | 基于 Redis 的分布式限流 |

---

## API 接口说明

### 1. 用户注册

**接口**: `POST /api/v1/auth/register`

**请求体**:
```json
{
  "username": "user123",
  "email": "user@example.com",
  "password": "password123"
}
```

**验证规则**:
- `username`: 3-50 字符，只允许字母、数字、下划线和连字符
- `email`: 有效的邮箱格式
- `password`: 至少 6 个字符

**响应**:
```json
{
  "code": 0,
  "message": "注册成功",
  "data": {
    "user": {
      "id": "uuid",
      "username": "user123",
      "email": "user@example.com",
      "is_active": true,
      "is_superuser": false,
      "created_at": "2025-01-29T12:00:00Z"
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
  "code": 409,
  "message": "用户名已存在",
  "detail": null
}

// 邮箱已被注册
{
  "code": 409,
  "message": "邮箱已被注册",
  "detail": null
}
```

---

### 2. 用户登录

**接口**: `POST /api/v1/auth/login`

**请求体**:
```json
{
  "username": "user@example.com",  // 支持用户名或邮箱
  "password": "password123"
}
```

**响应**:
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

---

### 3. 刷新 Token

**接口**: `POST /api/v1/auth/refresh`

**请求体**:
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**响应**:
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

**注意**:
- 每次刷新会撤销旧的 Refresh Token
- 新的 Refresh Token 有效期重置为 7 天
- 如果 Refresh Token 被撤销或过期，返回 401

---

### 4. 获取用户信息

**接口**: `GET /api/v1/auth/me`

**请求头**:
```
Authorization: Bearer {access_token}
```

**响应**:
```json
{
  "code": 0,
  "message": "获取成功",
  "data": {
    "id": "uuid",
    "username": "user123",
    "email": "user@example.com",
    "is_active": true,
    "is_superuser": false,
    "created_at": "2025-01-29T12:00:00Z"
  }
}
```

---

## 客户端集成指南

### 1. 注册流程

```
客户端 → POST /api/v1/auth/register (用户信息)
       ↓
    服务端 → 验证用户名/邮箱唯一性
              ↓ 哈希密码
              ↓ 创建用户记录
              ↓ 生成 Access Token (30分钟) + Refresh Token (7天)
              ↓ 保存 Refresh Token 到数据库
       ↓
    客户端 ← 返回用户信息和 Tokens
       ↓
    客户端 → 存储 Tokens 到本地存储
              ↓
    客户端 → 自动使用 Access Token 认证
              ↓ Refresh Token 在 Access Token 过期前刷新
```

### 2. 登录流程

```
客户端 → POST /api/v1/auth/login (用户名/邮箱 + 密码)
       ↓
    服务端 → 查找用户
              ↓ 验证密码 (bcrypt)
              ↓ 检查用户激活状态
              ↓ 生成新的 Tokens
              ↓ 撤销用户之前的 Refresh Tokens
       ↓
    客户端 ← 返回用户信息和 Tokens
```

### 3. Token 刷新流程

```
客户端 → 检测 Access Token 即将过期（如剩余 5 分钟）
       ↓
    客户端 → POST /api/v1/auth/refresh (Refresh Token)
       ↓
    服务端 → 验证 Refresh Token
              ↓ 检查是否被撤销
              ↓ 检查是否过期
              ↓ 撤销旧的 Refresh Token
              ↓ 生成新的 Tokens
       ↓
    客户端 ← 返回新的 Tokens
       ↓
    客户端 → 更新本地存储的 Tokens
```

---

## 使用示例

### JavaScript (浏览器)

```javascript
// 注册
const register = async (username, email, password) => {
  const response = await fetch('http://localhost:8000/api/v1/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, email, password })
  });
  const data = await response.json();

  if (data.code === 0) {
    // 保存 Tokens
    localStorage.setItem('access_token', data.data.tokens.access_token);
    localStorage.setItem('refresh_token', data.data.tokens.refresh_token);
    localStorage.setItem('user', JSON.stringify(data.data.user));
  }
};

// 登录
const login = async (username, password) => {
  const response = await fetch('http://localhost:8000/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password })
  });
  const data = await response.json();

  if (data.code === 0) {
    localStorage.setItem('access_token', data.data.tokens.access_token);
    localStorage.setItem('refresh_token', data.data.tokens.refresh_token);
  }
};

// 认证请求
const fetchWithAuth = async (url) => {
  const accessToken = localStorage.getItem('access_token');
  const response = await fetch(url, {
    headers: { 'Authorization': `Bearer ${accessToken}` }
  });

  // 如果 401，尝试刷新 Token
  if (response.status === 401) {
    await refreshAccessToken();
    // 重试请求
    return fetch(url, {
      headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` }
    });
  }

  return response.json();
};

// 刷新 Token
const refreshAccessToken = async () => {
  const refreshToken = localStorage.getItem('refresh_token');
  const response = await fetch('http://localhost:8000/api/v1/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: refreshToken })
  });
  const data = await response.json();

  if (data.code === 0) {
    localStorage.setItem('access_token', data.data.tokens.access_token);
    localStorage.setItem('refresh_token', data.data.tokens.refresh_token);
  }
};
```

### Python

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"

class AuthClient:
    """认证客户端"""

    def __init__(self):
        self.access_token = None
        self.refresh_token = None

    def register(self, username: str, email: str, password: str) -> dict:
        """用户注册"""
        response = requests.post(
            f"{BASE_URL}/auth/register",
            json={"username": username, "email": email, "password": password}
        )
        data = response.json()

        if data.get("code") == 0:
            self.access_token = data["data"]["tokens"]["access_token"]
            self.refresh_token = data["data"]["tokens"]["refresh_token"]
            return data["data"]
        raise Exception(data.get("message"))

    def login(self, username: str, password: str) -> dict:
        """用户登录"""
        response = requests.post(
            f"{BASE_URL}/auth/login",
            json={"username": username, "password": password}
        )
        data = response.json()

        if data.get("code") == 0:
            self.access_token = data["data"]["tokens"]["access_token"]
            self.refresh_token = data["data"]["tokens"]["refresh_token"]
            return data["data"]
        raise Exception(data.get("message"))

    def refresh_token(self) -> dict:
        """刷新 Token"""
        response = requests.post(
            f"{BASE_URL}/auth/refresh",
            json={"refresh_token": self.refresh_token}
        )
        data = response.json()

        if data.get("code") == 0:
            self.access_token = data["data"]["tokens"]["access_token"]
            self.refresh_token = data["data"]["tokens"]["refresh_token"]
            return data["data"]
        raise Exception(data.get("message"))

    def get_headers(self) -> dict:
        """获取认证请求头"""
        return {"Authorization": f"Bearer {self.access_token}"}

    def request(self, method: str, path: str, **kwargs) -> dict:
        """发送认证请求"""
        url = f"{BASE_URL}{path}"
        kwargs["headers"] = self.get_headers()

        response = requests.request(method, url, **kwargs)

        # 如果 401，尝试刷新 Token 并重试
        if response.status_code == 401:
            self.refresh_token()
            kwargs["headers"] = self.get_headers()
            response = requests.request(method, url, **kwargs)

        return response.json()


# 使用示例
client = AuthClient()

# 注册
result = client.register("testuser", "test@example.com", "password123")
print(f"注册成功，用户 ID: {result['user']['id']}")

# 登录
result = client.login("testuser", "password123")
print(f"登录成功，用户名: {result['user']['username']}")

# 认证请求
result = client.request("GET", "/auth/me")
print(f"用户信息: {result['data']}")

# 刷新 Token
result = client.refresh_token()
print(f"Token 已刷新，有效期: {result['tokens']['expires_in']} 秒")
```

---

## 安全最佳实践

### 客户端安全

1. **Token 存储**
   - 浏览器: 使用 localStorage 或 sessionStorage
   - 移动应用: 使用安全存储 (Keychain)
   - 不要将 Token 存储在 URL 参数中

2. **HTTPS 通信**
   - 生产环境必须使用 HTTPS
   - 防止中间人攻击

3. **Token 处理**
   - Access Token 过期后立即刷新
   - Refresh Token 丢失后要求用户重新登录
   - 退出登录时清除本地存储的 Token

### 服务端安全

1. **JWT 配置**
   - 生产环境使用强密钥（至少 256 位）
   - 定期轮换 JWT 密钥
   - 设置合理的 Token 有效期

2. **密码策略**
   - 要求至少 8 个字符
   - 建议包含大小写字母、数字和特殊字符
   - 使用 bcrypt 哈希（成本因子 >= 12）

3. **速率限制**
   - 限制登录尝试频率
   - 限制注册请求频率
   - 记录失败的认证尝试

---

## 常见问题

### Q1: Token 过期后如何处理？

A: 客户端应该：
1. 检测 API 返回的 401 状态码
2. 使用 Refresh Token 调用刷新接口
3. 如果刷新成功，重试原请求
4. 如果刷新失败，跳转到登录页面

### Q2: 如何确保用户安全？

A: 实现以下安全措施：
- 密码哈希存储
- HTTPS 加密传输
- Token 短期有效
- 请求速率限制
- 记录异常登录尝试

### Q3: 支持密码重置吗？

A: 当前版本暂不支持密码重置，后续可以添加：
- 发送验证码到邮箱
- 验证码有效期 15 分钟
- 重置成功后撤销所有 Refresh Token

### Q4: 如何注销登录？

A: 注销流程：
1. 客户端清除本地存储的 Tokens
2. 可选：调用服务端接口撤销 Refresh Token
3. 跳转到登录页面
