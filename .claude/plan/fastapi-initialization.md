# FastAPI 初始化规划文档

**项目**: 宠物饮食计划智能助手
**版本**: v1.0.0
**创建日期**: 2025-01-29
**作者**: AI 规划专家
**状态**: 待审核

---

## 目录

1. [规划概述](#1-规划概述)
2. [技术架构设计](#2-技术架构设计)
3. [目录结构设计](#3-目录结构设计)
4. [API 接口设计](#4-api-接口设计)
5. [数据模型定义](#5-数据模型定义)
6. [核心实现方案](#6-核心实现方案)
7. [配置方案](#7-配置方案)
8. [错误处理](#8-错误处理)
9. [测试方案](#9-测试方案)
10. [部署方案](#10-部署方案)
11. [安全考虑](#11-安全考虑)
12. [实施计划](#12-实施计划)

---

## 1. 规划概述

### 1.1 项目目标

为"宠物饮食计划智能助手"项目添加 **FastAPI RESTful API 层**，使其能够通过 HTTP 接口对外提供服务，支持多用户访问、流式输出、异步任务处理和完善的认证授权机制。

### 1.2 核心需求

| 需求类别 | 具体需求 | 优先级 |
|---------|---------|--------|
| **认证授权** | JWT Token 认证、用户注册/登录、Token 刷新 | P0 |
| **多用户隔离** | 用户数据隔离、会话管理、权限控制 | P0 |
| **异步执行** | 异步任务队列、状态轮询、超时处理 | P0 |
| **流式输出** | SSE (Server-Sent Events) 实时推送智能体执行过程 | P1 |
| **API 文档** | OpenAPI/Swagger 自动文档、接口示例 | P1 |
| **数据持久化** | PostgreSQL 存储用户和任务历史、Redis 缓存状态 | P1 |
| **错误处理** | 全局异常处理、统一错误响应格式、日志记录 | P1 |
| **性能优化** | 并发控制、连接池管理、响应压缩 | P2 |

### 1.3 技术栈

#### 新增技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| **FastAPI** | ^0.115.0 | Web 框架 |
| **uvicorn** | ^0.37.0 | ASGI 服务器 |
| **pydantic** | ^2.10.0 | 数据验证（已有） |
| **python-jose** | ^3.3.0 | JWT Token 处理 |
| **passlib** | ^1.7.4 | 密码哈希 |
| **python-multipart** | ^0.0.20 | 表单数据支持 |
| **sqlalchemy** | ^2.0.36 | ORM |
| **asyncpg** | ^0.30.0 | PostgreSQL 异步驱动 |
| **redis** | ^5.2.1 | Redis 客户端 |
| **alembic** | ^1.14.0 | 数据库迁移 |
| **pytest-asyncio** | ^0.24.0 | 异步测试 |
| **httpx** | ^0.28.1 | 异步 HTTP 客户端（已有） |

#### 现有技术栈（复用）

- **LangGraph** 0.6.6: 多智能体系统
- **LangChain** 0.3.27: LLM 集成
- **Pydantic**: 数据模型
- **python-dotenv**: 环境变量

### 1.4 预期成果

1. **完整的 RESTful API 系统**
   - 15+ API 接口
   - JWT 认证机制
   - 自动生成的 API 文档

2. **异步任务处理能力**
   - 支持长时间运行的饮食计划生成任务
   - 任务状态查询和管理
   - 流式输出支持

3. **多用户数据隔离**
   - 用户注册和登录
   - 数据隔离和权限控制
   - 会话管理

4. **生产级部署方案**
   - Docker 容器化
   - docker-compose 编排
   - 监控和日志配置

---

## 2. 技术架构设计

### 2.1 整体架构

```mermaid
graph TB
    subgraph "客户端层"
        A[Web 前端]
        B[移动应用]
        C[第三方服务]
    end

    subgraph "API 网关层"
        D[Nginx 反向代理]
        E[FastAPI 应用]
        F[认证中间件]
    end

    subgraph "业务逻辑层"
        G[任务服务]
        H[饮食计划服务]
        I[认证服务]
        J[流式输出服务]
    end

    subgraph "多智能体层"
        K[主智能体]
        L[子智能体]
        M[写入智能体]
        N[结构化智能体]
    end

    subgraph "数据层"
        O[(PostgreSQL)]
        P[(Redis)]
        Q[LangGraph 状态]
    end

    A --> D
    B --> D
    C --> D
    D --> E
    E --> F
    F --> G
    F --> H
    F --> I
    F --> J
    G --> K
    H --> K
    J --> K
    K --> L
    K --> M
    K --> N
    G --> O
    G --> P
    H --> O
    I --> O
    J --> P
    K --> Q
```

### 2.2 认证架构

```mermaid
sequenceDiagram
    participant U as 用户
    participant API as FastAPI
    participant Auth as 认证服务
    participant DB as PostgreSQL
    participant Redis as Redis

    U->>API: POST /api/v1/auth/register
    API->>Auth: 创建用户
    Auth->>DB: 保存用户信息
    DB-->>Auth: 用户已创建
    Auth-->>API: 用户信息
    API-->>U: 注册成功

    U->>API: POST /api/v1/auth/login
    API->>Auth: 验证凭证
    Auth->>DB: 查询用户
    DB-->>Auth: 用户信息
    Auth->>Auth: 验证密码
    Auth->>Auth: 生成 JWT Token
    Auth->>Redis: 缓存 Token
    Auth-->>API: Access Token + Refresh Token
    API-->>U: 登录成功

    U->>API: GET /api/v1/plans (携带 Token)
    API->>Auth: 验证 Token
    Auth->>Redis: 检查 Token 有效性
    Redis-->>Auth: Token 有效
    Auth-->>API: 用户信息
    API-->>U: 返回数据
```

### 2.3 流式输出架构

```mermaid
sequenceDiagram
    participant C as 客户端
    participant API as FastAPI
    participant Task as 任务服务
    participant LangGraph as 多智能体系统
    participant Redis as Redis

    C->>API: POST /api/v1/plans (stream=true)
    API->>Task: 创建异步任务
    Task->>Redis: 保存任务状态（pending）
    Task-->>API: 任务 ID
    API-->>C: 返回 SSE 连接

    Task->>LangGraph: 执行图
    loop 每个节点执行
        LangGraph-->>Task: 节点输出
        Task->>Redis: 更新状态
        Task-->>C: SSE 事件（data: {...}）
    end

    LangGraph-->>Task: 最终结果
    Task->>Redis: 保存完成状态
    Task-->>C: SSE 事件（done）
    C-->>API: 关闭连接
```

### 2.4 技术选型理由

#### 认证方案：JWT Token

**优点**:
- 无状态，易于扩展
- 标准化，跨平台支持好
- 性能好（无需查库验证）

**缺点**:
- Token 无法主动撤销
- 需要配合 Redis 黑名单

**替代方案**:
- **Session + Cookie**: 传统方案，但不适合 RESTful API
- **OAuth2**: 复杂，适合第三方集成场景

#### 状态存储：Redis + PostgreSQL

| 数据类型 | 存储方案 | 理由 |
|---------|---------|------|
| 用户信息 | PostgreSQL | 持久化、事务支持、关系查询 |
| 任务状态 | Redis | 高性能、支持过期、适合缓存 |
| 饮食计划历史 | PostgreSQL | 持久化、复杂查询、数据分析 |
| Token 黑名单 | Redis | 快速验证、自动过期 |
| 会话数据 | Redis | 高并发、临时数据 |

#### 流式输出：SSE (Server-Sent Events)

**优点**:
- 单向推送，简单易用
- 自动重连机制
- 文本格式，易于调试

**缺点**:
- 仅支持服务器到客户端
- 不支持二进制数据

**替代方案**:
- **WebSocket**: 双向通信，但复杂度高
- **流式 HTTP**: 兼容性好，但无自动重连

---

## 3. 目录结构设计

### 3.1 完整目录树

```
pet-food/
├── .claude/
│   └── plan/
│       └── fastapi-initialization.md  # 本文档
├── .env.example                       # 环境变量示例（已有）
├── .env                               # 环境变量（已有）
├── pyproject.toml                     # 项目依赖（已有）
├── langgraph.json                     # LangGraph 配置（已有）
├── main.py                            # CLI 入口（已有）
├── README.md                          # 项目说明
│
├── src/
│   ├── agent/                         # 多智能体系统（已有，保持不变）
│   │   ├── graph.py
│   │   ├── state.py
│   │   ├── node.py
│   │   ├── tools.py
│   │   ├── prompts/
│   │   ├── utils/
│   │   ├── entity/
│   │   ├── sub_agent/
│   │   ├── write_agent/
│   │   └── structrue_agent/
│   │
│   ├── api/                           # 🆕 FastAPI 应用层
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI 应用入口
│   │   ├── config.py                  # API 配置
│   │   ├── dependencies.py            # 依赖注入
│   │   │
│   │   ├── middleware/                # 中间件
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                # 认证中间件
│   │   │   ├── cors.py                # CORS 中间件
│   │   │   ├── logging.py             # 日志中间件
│   │   │   └── rate_limit.py          # 速率限制中间件
│   │   │
│   │   ├── routes/                    # 路由
│   │   │   ├── __init__.py
│   │   │   ├── auth.py                # 认证路由
│   │   │   ├── plans.py               # 饮食计划路由
│   │   │   ├── tasks.py               # 任务管理路由
│   │   │   └── health.py              # 健康检查路由
│   │   │
│   │   ├── models/                    # Pydantic 模型
│   │   │   ├── __init__.py
│   │   │   ├── request.py             # 请求模型
│   │   │   ├── response.py            # 响应模型
│   │   │   └── schemas.py             # 业务模型
│   │   │
│   │   ├── services/                  # 业务逻辑层
│   │   │   ├── __init__.py
│   │   │   ├── task_service.py        # 任务管理服务
│   │   │   ├── plan_service.py        # 饮食计划服务
│   │   │   └── auth_service.py        # 认证服务
│   │   │
│   │   └── utils/                     # API 工具
│   │       ├── __init__.py
│   │       ├── stream.py              # 流式输出处理
│   │       ├── errors.py              # 错误处理
│   │       └── security.py            # 安全工具（JWT、密码哈希）
│   │
│   ├── db/                            # 🆕 数据库层
│   │   ├── __init__.py
│   │   ├── base.py                    # 数据库基类
│   │   ├── models.py                  # SQLAlchemy 模型
│   │   ├── session.py                 # 数据库会话
│   │   └── redis.py                   # Redis 客户端
│   │
│   ├── rag/                           # RAG 模块（已有）
│   └── utils/                         # 通用工具（已有）
│
├── tests/                             # 🆕 测试目录
│   ├── __init__.py
│   ├── conftest.py                    # pytest 配置
│   ├── test_api/                      # API 测试
│   │   ├── test_auth.py
│   │   ├── test_plans.py
│   │   ├── test_tasks.py
│   │   └── test_health.py
│   ├── test_services/                 # 服务测试
│   │   ├── test_task_service.py
│   │   ├── test_plan_service.py
│   │   └── test_auth_service.py
│   └── fixtures/                      # 测试夹具
│       ├── pet_info.json
│       └── user_data.json
│
├── alembic/                           # 🆕 数据库迁移
│   ├── versions/
│   │   └── 001_initial.py             # 初始化迁移
│   ├── env.py
│   └── script.py.mako
│   ├── alembic.ini                    # Alembic 配置
│
├── deployment/                        # 🆕 部署配置
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── nginx.conf
│   └── gunicorn_conf.py
│
└── scripts/                           # 🆕 脚本目录
    ├── init_db.py                     # 初始化数据库
    └── migrate.py                     # 运行迁移
```

### 3.2 核心文件说明

| 文件 | 行数估计 | 职责 |
|------|----------|------|
| **api/main.py** | ~100 | FastAPI 应用入口、中间件注册、路由注册 |
| **api/config.py** | ~50 | API 配置（CORS、JWT、数据库等） |
| **api/dependencies.py** | ~80 | 依赖注入（获取当前用户、数据库会话、Redis） |
| **api/routes/auth.py** | ~150 | 认证路由（注册、登录、刷新 Token） |
| **api/routes/plans.py** | ~200 | 饮食计划路由（创建、查询、流式执行） |
| **api/routes/tasks.py** | ~100 | 任务管理路由（状态查询、取消、列表） |
| **api/models/request.py** | ~100 | 请求 Pydantic 模型 |
| **api/models/response.py** | ~120 | 响应 Pydantic 模型 |
| **api/services/task_service.py** | ~200 | 任务管理服务（创建、更新、查询） |
| **api/services/plan_service.py** | ~150 | 饮食计划服务（调用 LangGraph） |
| **api/services/auth_service.py** | ~100 | 认证服务（JWT、密码哈希） |
| **api/utils/stream.py** | ~80 | SSE 流式输出处理 |
| **api/utils/errors.py** | ~60 | 自定义异常类 |
| **api/utils/security.py** | ~80 | JWT 和密码哈希工具 |
| **db/models.py** | ~150 | SQLAlchemy 模型（User、Task、DietPlan） |
| **db/session.py** | ~50 | 数据库会话管理 |
| **db/redis.py** | ~40 | Redis 客户端 |

---

## 4. API 接口设计

### 4.1 API 版本管理

**基础 URL**: `http://localhost:8000/api/v1`

**版本策略**: URL 路径前缀（简单直观）

### 4.2 认证接口

#### 4.2.1 用户注册

```http
POST /api/v1/auth/register
Content-Type: application/json
```

**请求体**:
```json
{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "SecurePass123!@#"
}
```

**响应**:
```json
{
  "code": 0,
  "message": "注册成功",
  "data": {
    "user": {
      "id": "uuid",
      "username": "john_doe",
      "email": "john@example.com",
      "created_at": "2025-01-29T10:00:00Z"
    },
    "tokens": {
      "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
      "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
      "token_type": "bearer",
      "expires_in": 3600
    }
  }
}
```

#### 4.2.2 用户登录

```http
POST /api/v1/auth/login
Content-Type: application/json
```

**请求体**:
```json
{
  "username": "john_doe",
  "password": "SecurePass123!@#"
}
```

**响应**:
```json
{
  "code": 0,
  "message": "登录成功",
  "data": {
    "user": {
      "id": "uuid",
      "username": "john_doe",
      "email": "john@example.com"
    },
    "tokens": {
      "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
      "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
      "token_type": "bearer",
      "expires_in": 3600
    }
  }
}
```

#### 4.2.3 刷新 Token

```http
POST /api/v1/auth/refresh
Content-Type: application/json
```

**请求体**:
```json
{
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc..."
}
```

**响应**:
```json
{
  "code": 0,
  "message": "Token 刷新成功",
  "data": {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
    "token_type": "bearer",
    "expires_in": 3600
  }
}
```

#### 4.2.4 获取当前用户信息

```http
GET /api/v1/auth/me
Authorization: Bearer <access_token>
```

**响应**:
```json
{
  "code": 0,
  "message": "获取成功",
  "data": {
    "id": "uuid",
    "username": "john_doe",
    "email": "john@example.com",
    "created_at": "2025-01-29T10:00:00Z"
  }
}
```

### 4.3 饮食计划接口

#### 4.3.1 创建饮食计划（同步）

```http
POST /api/v1/plans
Authorization: Bearer <access_token>
Content-Type: application/json
```

**请求体**:
```json
{
  "pet_information": {
    "pet_type": "猫",
    "pet_breed": "英国短毛猫",
    "age": "3岁",
    "pet_weight": 4.5,
    "pet_health_status": "健康"
  },
  "stream": false
}
```

**响应**:
```json
{
  "code": 0,
  "message": "饮食计划生成成功",
  "data": {
    "task_id": "uuid",
    "status": "completed",
    "report": {
      "pet_information": { ... },
      "ai_suggestions": "...",
      "pet_diet_plan": { ... }
    },
    "created_at": "2025-01-29T10:00:00Z",
    "completed_at": "2025-01-29T10:05:00Z"
  }
}
```

#### 4.3.2 创建饮食计划（流式）

```http
POST /api/v1/plans
Authorization: Bearer <access_token>
Content-Type: application/json
```

**请求体**:
```json
{
  "pet_information": {
    "pet_type": "猫",
    "pet_breed": "英国短毛猫",
    "age": "3岁",
    "pet_weight": 4.5,
    "pet_health_status": "健康"
  },
  "stream": true
}
```

**响应** (SSE 流):
```
data: {"type": "task_created", "task_id": "uuid", "status": "pending"}

data: {"type": "node_started", "node": "call_model", "message": "主智能体开始规划..."}

data: {"type": "node_completed", "node": "call_model", "message": "任务规划完成"}

data: {"type": "node_started", "node": "subagent", "message": "子智能体执行任务：收集宠物营养信息"}

data: {"type": "node_completed", "node": "subagent", "message": "任务完成"}

data: {"type": "node_started", "node": "write_note", "message": "写入笔记"}

data: {"type": "node_completed", "node": "write_note", "message": "笔记已保存"}

...

data: {"type": "completed", "report": {...}}

data: [DONE]
```

#### 4.3.3 查询饮食计划历史

```http
GET /api/v1/plans?page=1&page_size=10
Authorization: Bearer <access_token>
```

**响应**:
```json
{
  "code": 0,
  "message": "获取成功",
  "data": {
    "total": 25,
    "page": 1,
    "page_size": 10,
    "items": [
      {
        "task_id": "uuid",
        "pet_information": { ... },
        "status": "completed",
        "created_at": "2025-01-29T10:00:00Z",
        "completed_at": "2025-01-29T10:05:00Z"
      }
    ]
  }
}
```

#### 4.3.4 获取单个饮食计划

```http
GET /api/v1/plans/:task_id
Authorization: Bearer <access_token>
```

**响应**:
```json
{
  "code": 0,
  "message": "获取成功",
  "data": {
    "task_id": "uuid",
    "status": "completed",
    "report": {
      "pet_information": { ... },
      "ai_suggestions": "...",
      "pet_diet_plan": { ... }
    },
    "created_at": "2025-01-29T10:00:00Z",
    "completed_at": "2025-01-29T10:05:00Z"
  }
}
```

### 4.4 任务管理接口

#### 4.4.1 查询任务状态

```http
GET /api/v1/tasks/:task_id
Authorization: Bearer <access_token>
```

**响应**:
```json
{
  "code": 0,
  "message": "获取成功",
  "data": {
    "task_id": "uuid",
    "status": "running",
    "progress": 60,
    "current_node": "subagent",
    "message": "子智能体执行任务：收集宠物营养信息",
    "created_at": "2025-01-29T10:00:00Z",
    "updated_at": "2025-01-29T10:03:00Z"
  }
}
```

#### 4.4.2 取消任务

```http
POST /api/v1/tasks/:task_id/cancel
Authorization: Bearer <access_token>
```

**响应**:
```json
{
  "code": 0,
  "message": "任务已取消",
  "data": {
    "task_id": "uuid",
    "status": "cancelled"
  }
}
```

#### 4.4.3 获取任务列表

```http
GET /api/v1/tasks?status=running&page=1&page_size=10
Authorization: Bearer <access_token>
```

**响应**:
```json
{
  "code": 0,
  "message": "获取成功",
  "data": {
    "total": 5,
    "page": 1,
    "page_size": 10,
    "items": [
      {
        "task_id": "uuid",
        "status": "running",
        "progress": 60,
        "current_node": "subagent",
        "created_at": "2025-01-29T10:00:00Z"
      }
    ]
  }
}
```

### 4.5 健康检查接口

#### 4.5.1 基础健康检查

```http
GET /api/v1/health
```

**响应**:
```json
{
  "code": 0,
  "message": "服务正常",
  "data": {
    "status": "healthy",
    "version": "1.0.0",
    "timestamp": "2025-01-29T10:00:00Z"
  }
}
```

#### 4.5.2 详细健康检查

```http
GET /api/v1/health/detail
```

**响应**:
```json
{
  "code": 0,
  "message": "服务正常",
  "data": {
    "status": "healthy",
    "version": "1.0.0",
    "timestamp": "2025-01-29T10:00:00Z",
    "components": {
      "database": {
        "status": "healthy",
        "latency_ms": 5
      },
      "redis": {
        "status": "healthy",
        "latency_ms": 1
      },
      "langgraph": {
        "status": "healthy"
      }
    }
  }
}
```

### 4.6 错误响应格式

所有错误响应统一格式：

```json
{
  "code": 1001,
  "message": "用户名已存在",
  "errors": [
    {
      "field": "username",
      "message": "该用户名已被注册"
    }
  ],
  "timestamp": "2025-01-29T10:00:00Z"
}
```

**错误码列表**:

| 错误码 | 说明 |
|-------|------|
| 0 | 成功 |
| 1001 | 用户名已存在 |
| 1002 | 邮箱已存在 |
| 1003 | 用户名或密码错误 |
| 1004 | Token 无效或已过期 |
| 1005 | Token 刷新失败 |
| 2001 | 任务不存在 |
| 2002 | 任务已被取消 |
| 2003 | 任务执行失败 |
| 3001 | 数据库错误 |
| 3002 | Redis 错误 |
| 4001 | 请求参数错误 |
| 4999 | 内部服务器错误 |

---

## 5. 数据模型定义

### 5.1 请求模型 (api/models/request.py)

```python
from pydantic import BaseModel, EmailStr, Field
from src.agent.v0.utils import PetInformation


class RegisterRequest(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=3, max_length=50, description="用户名")
    email: EmailStr = Field(..., description="邮箱")
    password: str = Field(..., min_length=8, max_length=100, description="密码")


class LoginRequest(BaseModel):
    """用户登录请求"""
    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")


class RefreshTokenRequest(BaseModel):
    """刷新 Token 请求"""
    refresh_token: str = Field(..., description="刷新 Token")


class CreatePlanRequest(BaseModel):
    """创建饮食计划请求"""
    pet_information: PetInformation = Field(..., description="宠物信息")
    stream: bool = Field(False, description="是否使用流式输出")


class QueryPlansRequest(BaseModel):
    """查询饮食计划列表请求"""
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页数量")
    status: str | None = Field(None, description="状态筛选")


class QueryTasksRequest(BaseModel):
    """查询任务列表请求"""
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页数量")
    status: str | None = Field(None, description="状态筛选")
```

### 5.2 响应模型 (api/models/response.py)

```python
from pydantic import BaseModel
from typing import Generic, TypeVar
from datetime import datetime

T = TypeVar('T')


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应格式"""
    code: int = Field(0, description="错误码，0 表示成功")
    message: str = Field("success", description="响应消息")
    data: T | None = Field(None, description="响应数据")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")


class TokenResponse(BaseModel):
    """Token 响应"""
    access_token: str = Field(..., description="访问 Token")
    refresh_token: str = Field(..., description="刷新 Token")
    token_type: str = Field("bearer", description="Token 类型")
    expires_in: int = Field(..., description="过期时间（秒）")


class UserResponse(BaseModel):
    """用户信息响应"""
    id: str = Field(..., description="用户 ID")
    username: str = Field(..., description="用户名")
    email: str = Field(..., description="邮箱")
    created_at: datetime = Field(..., description="创建时间")


class AuthResponse(BaseModel):
    """认证响应"""
    user: UserResponse = Field(..., description="用户信息")
    tokens: TokenResponse = Field(..., description="Token 信息")


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: str = Field(..., description="任务 ID")
    status: str = Field(..., description="任务状态")
    progress: int | None = Field(None, description="进度百分比")
    current_node: str | None = Field(None, description="当前执行的节点")
    message: str | None = Field(None, description="当前消息")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")
    completed_at: datetime | None = Field(None, description="完成时间")


class PlanListItem(BaseModel):
    """饮食计划列表项"""
    task_id: str = Field(..., description="任务 ID")
    pet_information: dict = Field(..., description="宠物信息")
    status: str = Field(..., description="任务状态")
    created_at: datetime = Field(..., description="创建时间")
    completed_at: datetime | None = Field(None, description="完成时间")


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应"""
    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    items: list[T] = Field(..., description="数据列表")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="健康状态")
    version: str = Field(..., description="版本号")
    timestamp: datetime = Field(..., description="时间戳")


class HealthDetailResponse(HealthResponse):
    """详细健康检查响应"""
    components: dict = Field(..., description="组件状态")
```

### 5.3 业务模型 (api/models/schemas.py)

```python
from pydantic import BaseModel
from datetime import datetime


class User(BaseModel):
    """用户模型"""
    id: str
    username: str
    email: str
    hashed_password: str
    created_at: datetime
    updated_at: datetime


class Task(BaseModel):
    """任务模型"""
    id: str
    user_id: str
    pet_information: dict
    status: str  # pending, running, completed, failed, cancelled
    progress: int
    current_node: str | None
    message: str | None
    report: dict | None
    error: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class DietPlanHistory(BaseModel):
    """饮食计划历史模型"""
    id: str
    user_id: str
    task_id: str
    pet_information: dict
    report: dict
    created_at: datetime
```

### 5.4 数据库模型 (db/models.py)

```python
from sqlalchemy import Column, String, DateTime, Integer, Text, ForeignKey, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

Base = declarative_base()


class UserModel(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # 关系
    tasks = relationship("TaskModel", back_populates="user", cascade="all, delete-orphan")
    diet_plans = relationship("DietPlanModel", back_populates="user", cascade="all, delete-orphan")


class TaskModel(Base):
    """任务表"""
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    pet_information = Column(JSONB, nullable=False)
    status = Column(
        Enum("pending", "running", "completed", "failed", "cancelled", name="task_status"),
        default="pending",
        nullable=False,
        index=True
    )
    progress = Column(Integer, default=0, nullable=False)
    current_node = Column(String(50), nullable=True)
    message = Column(Text, nullable=True)
    report = Column(JSONB, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # 关系
    user = relationship("UserModel", back_populates="tasks")


class DietPlanModel(Base):
    """饮食计划历史表"""
    __tablename__ = "diet_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    pet_information = Column(JSONB, nullable=False)
    report = Column(JSONB, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # 关系
    user = relationship("UserModel", back_populates="diet_plans")
```

---

## 6. 核心实现方案

### 6.1 FastAPI 应用初始化 (api/main.py)

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging

from src.api.config import settings
from src.api.middleware.logging import LoggingMiddleware
from src.api.middleware.rate_limit import RateLimitMiddleware
from src.api.routes import auth, plans, tasks, health
from src.api.utils.errors import (
    APIException,
    api_exception_handler,
    generic_exception_handler
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("FastAPI 应用启动中...")
    # 初始化数据库连接池
    # 初始化 Redis 连接池
    yield
    # 关闭时
    logger.info("FastAPI 应用关闭中...")
    # 关闭数据库连接
    # 关闭 Redis 连接


# 创建 FastAPI 应用
app = FastAPI(
    title="宠物饮食计划智能助手 API",
    description="为宠物（猫、狗等）生成定制化的月度营养饮食计划",
    version="1.0.0",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 自定义中间件
app.add_middleware(LoggingMiddleware)
app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)

# 异常处理器
app.add_exception_handler(APIException, api_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# 路由注册
app.include_router(
    auth.router,
    prefix="/api/v1/auth",
    tags=["认证"]
)

app.include_router(
    plans.router,
    prefix="/api/v1/plans",
    tags=["饮食计划"]
)

app.include_router(
    tasks.router,
    prefix="/api/v1/tasks",
    tags=["任务管理"]
)

app.include_router(
    health.router,
    prefix="/api/v1/health",
    tags=["健康检查"]
)


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "宠物饮食计划智能助手 API",
        "version": "1.0.0",
        "docs": "/api/v1/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        workers=1 if settings.DEBUG else 4
    )
```

### 6.2 JWT 认证中间件 (api/middleware/auth.py)

```python
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from src.api.utils.security import decode_token
from src.api.config import settings


class AuthMiddleware(BaseHTTPMiddleware):
    """认证中间件"""

    async def dispatch(self, request: Request, call_next):
        # 跳过不需要认证的路径
        if request.url.path in [
            "/",
            "/api/v1/docs",
            "/api/v1/redoc",
            "/api/v1/openapi.json",
            "/api/v1/auth/register",
            "/api/v1/auth/login",
            "/api/v1/health",
            "/api/v1/health/detail"
        ]:
            return await call_next(request)

        # 提取 Token
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "code": 1004,
                    "message": "未提供认证 Token",
                    "timestamp": datetime.now().isoformat()
                }
            )

        token = auth_header.split(" ")[1]

        # 验证 Token
        try:
            payload = decode_token(token)
            # 将用户信息注入到请求状态
            request.state.user_id = payload.get("sub")
            request.state.username = payload.get("username")
        except Exception as e:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "code": 1004,
                    "message": str(e),
                    "timestamp": datetime.now().isoformat()
                }
            )

        return await call_next(request)
```

### 6.3 流式输出处理 (api/utils/stream.py)

```python
from fastapi import Request
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
import json
import asyncio
from logging import getLogger

from src.agent.v0.graph import build_graph_with_langgraph_studio
from src.api.models.request import CreatePlanRequest

logger = getLogger(__name__)


async def execute_plan_stream(
        user_id: str,
        request: CreatePlanRequest
) -> AsyncGenerator[str, None]:
    """
    执行饮食计划生成并流式输出

    Args:
        user_id: 用户 ID
        request: 创建计划请求

    Yields:
        SSE 格式的字符串
    """
    try:
        # 1. 构建图
        graph = build_graph_with_langgraph_studio()

        # 2. 准备输入
        inputs = {
            "messages": [
                {"role": "user", "content": f"为我的宠物生成月度饮食计划"}
            ],
            "pet_information": request.pet_information.model_dump()
        }

        # 3. 配置
        config = {
            "configurable": {
                "user_id": user_id
            }
        }

        # 4. 流式执行
        async for event in graph.astream_events(inputs, config=config, version="v1"):

            # 解析事件
            event_type = event.get("event")
            node_name = event.get("name", "")

            # 发送 SSE 事件
            if "start" in event_type:
                yield _format_sse({
                    "type": "node_started",
                    "node": node_name,
                    "message": f"开始执行节点: {node_name}"
                })
            elif "end" in event_type:
                yield _format_sse({
                    "type": "node_completed",
                    "node": node_name,
                    "message": f"节点执行完成: {node_name}"
                })
            elif "chain" in event_type:
                # 提取消息内容
                data = event.get("data", {})
                if "input" in data:
                    yield _format_sse({
                        "type": "node_output",
                        "node": node_name,
                        "data": data["input"]
                    })

        # 5. 完成标记
        yield _format_sse({
            "type": "completed",
            "message": "饮食计划生成完成"
        })

    except Exception as e:
        logger.error(f"流式执行出错: {e}")
        yield _format_sse({
            "type": "error",
            "message": str(e)
        })

    # 6. 结束标记
    yield "data: [DONE]\n\n"


def _format_sse(data: dict) -> str:
    """格式化为 SSE 事件"""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def execute_plan_sync(
        user_id: str,
        request: CreatePlanRequest
) -> dict:
    """
    同步执行饮食计划生成

    Args:
        user_id: 用户 ID
        request: 创建计划请求

    Returns:
        最终报告
    """
    graph = build_graph_with_langgraph_studio()

    inputs = {
        "messages": [
            {"role": "user", "content": f"为我的宠物生成月度饮食计划"}
        ],
        "pet_information": request.pet_information.model_dump()
    }

    config = {
        "configurable": {
            "user_id": user_id
        }
    }

    # 等待完成
    result = await graph.ainvoke(inputs, config=config)

    return result.get("report")
```

### 6.4 LangGraph 集成 (api/services/plan_service.py)

```python
from typing import Optional
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.agent.v0.graph import build_graph_with_langgraph_studio
from src.db.models import TaskModel, DietPlanModel
from src.api.models.request import CreatePlanRequest
from src.api.utils.stream import execute_plan_stream, execute_plan_sync


class PlanService:
    """饮食计划服务"""

    def __init__(self, db: AsyncSession, redis_client):
        self.db = db
        self.redis = redis_client
        self.graph = build_graph_with_langgraph_studio()

    async def create_plan(
            self,
            user_id: str,
            request: CreatePlanRequest
    ) -> dict:
        """
        创建饮食计划

        Args:
            user_id: 用户 ID
            request: 创建计划请求

        Returns:
            任务信息
        """
        # 1. 创建任务记录
        task = TaskModel(
            id=uuid.uuid4(),
            user_id=user_id,
            pet_information=request.pet_information.model_dump(),
            status="pending",
            progress=0
        )

        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)

        # 2. 如果是流式，返回任务 ID
        if request.stream:
            return {
                "task_id": str(task.id),
                "status": "pending",
                "message": "任务已创建，请通过 SSE 连接获取进度"
            }

        # 3. 如果是同步，执行任务
        try:
            # 更新状态为运行中
            task.status = "running"
            task.progress = 10
            await self.db.commit()

            # 执行图
            report = await execute_plan_sync(user_id, request)

            # 保存结果
            task.status = "completed"
            task.progress = 100
            task.report = report
            task.completed_at = datetime.utcnow()
            await self.db.commit()

            # 保存到历史
            diet_plan = DietPlanModel(
                id=uuid.uuid4(),
                user_id=user_id,
                task_id=task.id,
                pet_information=request.pet_information.model_dump(),
                report=report
            )
            self.db.add(diet_plan)
            await self.db.commit()

            return {
                "task_id": str(task.id),
                "status": "completed",
                "report": report
            }

        except Exception as e:
            # 错误处理
            task.status = "failed"
            task.error = str(e)
            await self.db.commit()
            raise

    async def get_plan(self, user_id: str, task_id: str) -> Optional[dict]:
        """获取饮食计划"""
        result = await self.db.execute(
            select(TaskModel).where(
                TaskModel.id == task_id,
                TaskModel.user_id == user_id
            )
        )
        task = result.scalar_one_or_none()

        if not task:
            return None

        return {
            "task_id": str(task.id),
            "status": task.status,
            "progress": task.progress,
            "current_node": task.current_node,
            "message": task.message,
            "report": task.report,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
            "completed_at": task.completed_at.isoformat() if task.completed_at else None
        }

    async def list_plans(
            self,
            user_id: str,
            page: int = 1,
            page_size: int = 10,
            status: Optional[str] = None
    ) -> dict:
        """查询饮食计划列表"""
        query = select(TaskModel).where(TaskModel.user_id == user_id)

        if status:
            query = query.where(TaskModel.status == status)

        # 分页
        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(TaskModel.created_at.desc())

        result = await self.db.execute(query)
        tasks = result.scalars().all()

        # 总数
        count_query = select(TaskModel).where(TaskModel.user_id == user_id)
        if status:
            count_query = count_query.where(TaskModel.status == status)
        count_result = await self.db.execute(count_query)
        total = len(count_result.scalars().all())

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "task_id": str(task.id),
                    "pet_information": task.pet_information,
                    "status": task.status,
                    "created_at": task.created_at.isoformat(),
                    "completed_at": task.completed_at.isoformat() if task.completed_at else None
                }
                for task in tasks
            ]
        }
```

### 6.5 任务队列管理 (api/services/task_service.py)

```python
import uuid
from typing import Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from redis import Redis

from src.db.models import TaskModel


class TaskService:
    """任务管理服务"""

    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.redis = redis

    async def get_task(self, user_id: str, task_id: str) -> Optional[dict]:
        """获取任务状态"""
        # 先从 Redis 缓存查询
        cache_key = f"task:{task_id}"
        cached = self.redis.get(cache_key)
        if cached:
            import json
            return json.loads(cached)

        # 从数据库查询
        result = await self.db.execute(
            select(TaskModel).where(
                TaskModel.id == task_id,
                TaskModel.user_id == user_id
            )
        )
        task = result.scalar_one_or_none()

        if not task:
            return None

        data = {
            "task_id": str(task.id),
            "status": task.status,
            "progress": task.progress,
            "current_node": task.current_node,
            "message": task.message,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
            "completed_at": task.completed_at.isoformat() if task.completed_at else None
        }

        # 缓存到 Redis（5 分钟）
        self.redis.setex(cache_key, 300, json.dumps(data))

        return data

    async def cancel_task(self, user_id: str, task_id: str) -> bool:
        """取消任务"""
        result = await self.db.execute(
            select(TaskModel).where(
                TaskModel.id == task_id,
                TaskModel.user_id == user_id
            )
        )
        task = result.scalar_one_or_none()

        if not task:
            return False

        # 只能取消 pending 或 running 的任务
        if task.status not in ["pending", "running"]:
            return False

        task.status = "cancelled"
        await self.db.commit()

        # 清除缓存
        cache_key = f"task:{task_id}"
        self.redis.delete(cache_key)

        return True

    async def list_tasks(
        self,
        user_id: str,
        page: int = 1,
        page_size: int = 10,
        status: Optional[str] = None
    ) -> dict:
        """查询任务列表"""
        query = select(TaskModel).where(TaskModel.user_id == user_id)

        if status:
            query = query.where(TaskModel.status == status)

        query = query.offset((page - 1) * page_size).limit(page_size)
        query = query.order_by(TaskModel.created_at.desc())

        result = await self.db.execute(query)
        tasks = result.scalars().all()

        return {
            "total": len(tasks),
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "task_id": str(task.id),
                    "status": task.status,
                    "progress": task.progress,
                    "current_node": task.current_node,
                    "created_at": task.created_at.isoformat()
                }
                for task in tasks
            ]
        }
```

### 6.6 认证服务 (api/services/auth_service.py)

```python
from typing import Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from passlib.context import CryptContext

from src.db.models import UserModel
from src.api.models.request import RegisterRequest, LoginRequest
from src.api.utils.security import hash_password, verify_password, create_token, decode_token


class AuthService:
    """认证服务"""

    def __init__(self, db: AsyncSession, redis_client):
        self.db = db
        self.redis = redis_client
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    async def register(self, request: RegisterRequest) -> dict:
        """用户注册"""
        # 1. 检查用户名是否存在
        result = await self.db.execute(
            select(UserModel).where(UserModel.username == request.username)
        )
        if result.scalar_one_or_none():
            raise ValueError("用户名已存在")

        # 2. 检查邮箱是否存在
        result = await self.db.execute(
            select(UserModel).where(UserModel.email == request.email)
        )
        if result.scalar_one_or_none():
            raise ValueError("邮箱已存在")

        # 3. 创建用户
        user = UserModel(
            id=uuid.uuid4(),
            username=request.username,
            email=request.email,
            hashed_password=hash_password(request.password)
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        # 4. 生成 Token
        tokens = self._generate_tokens(str(user.id), user.username)

        return {
            "user": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "created_at": user.created_at.isoformat()
            },
            "tokens": tokens
        }

    async def login(self, request: LoginRequest) -> dict:
        """用户登录"""
        # 1. 查询用户
        result = await self.db.execute(
            select(UserModel).where(UserModel.username == request.username)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("用户名或密码错误")

        # 2. 验证密码
        if not verify_password(request.password, user.hashed_password):
            raise ValueError("用户名或密码错误")

        # 3. 生成 Token
        tokens = self._generate_tokens(str(user.id), user.username)

        return {
            "user": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "created_at": user.created_at.isoformat()
            },
            "tokens": tokens
        }

    async def refresh_token(self, refresh_token: str) -> dict:
        """刷新 Token"""
        try:
            # 1. 解析刷新 Token
            payload = decode_token(refresh_token)
            user_id = payload.get("sub")
            token_type = payload.get("type")

            if token_type != "refresh":
                raise ValueError("无效的刷新 Token")

            # 2. 检查黑名单
            if self.redis.get(f"blacklist:{refresh_token}"):
                raise ValueError("Token 已失效")

            # 3. 查询用户
            result = await self.db.execute(
                select(UserModel).where(UserModel.id == user_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                raise ValueError("用户不存在")

            # 4. 生成新的访问 Token
            access_token = create_token(
                sub=str(user.id),
                username=user.username,
                token_type="access",
                expires_delta=timedelta(hours=1)
            )

            return {
                "access_token": access_token,
                "token_type": "bearer",
                "expires_in": 3600
            }

        except Exception as e:
            raise ValueError(f"Token 刷新失败: {str(e)}")

    async def get_current_user(self, user_id: str) -> Optional[dict]:
        """获取当前用户信息"""
        result = await self.db.execute(
            select(UserModel).where(UserModel.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return None

        return {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "created_at": user.created_at.isoformat()
        }

    def _generate_tokens(self, user_id: str, username: str) -> dict:
        """生成 Token 对"""
        access_token = create_token(
            sub=user_id,
            username=username,
            token_type="access",
            expires_delta=timedelta(hours=1)
        )

        refresh_token = create_token(
            sub=user_id,
            username=username,
            token_type="refresh",
            expires_delta=timedelta(days=7)
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": 3600
        }
```

---

## 7. 配置方案

### 7.1 环境变量清单

在 `.env` 文件中添加以下配置：

```bash
# ========== FastAPI 配置 ==========
FASTAPI_HOST=0.0.0.0
FASTAPI_PORT=8000
FASTAPI_DEBUG=true
FASTAPI_WORKERS=4

# ========== CORS 配置 ==========
CORS_ORIGINS=["http://localhost:3000", "http://localhost:8080"]

# ========== JWT 配置 ==========
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=60
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# ========== 数据库配置 ==========
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/pet_food
DATABASE_ECHO=false

# ========== Redis 配置 ==========
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=
REDIS_DB=0

# ========== 速率限制配置 ==========
RATE_LIMIT_MAX_REQUESTS=100
RATE_LIMIT_WINDOW_SECONDS=60

# ========== 日志配置 ==========
LOG_LEVEL=INFO
LOG_FILE=logs/api.log
```

### 7.2 FastAPI 配置类 (api/config.py)

```python
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """FastAPI 配置"""

    # FastAPI 基础配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    WORKERS: int = 4

    # CORS 配置
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080"
    ]

    # JWT 配置
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # 数据库配置
    DATABASE_URL: str
    DATABASE_ECHO: bool = False

    # Redis 配置
    REDIS_URL: str
    REDIS_PASSWORD: str | None = None
    REDIS_DB: int = 0

    # 速率限制配置
    RATE_LIMIT_MAX_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/api.log"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
```

### 7.3 数据库配置 (db/session.py)

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from src.api.config import settings

# 创建异步引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DATABASE_ECHO,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=40
)

# 创建异步会话工厂
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_db() -> AsyncSession:
    """获取数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
```

### 7.4 Redis 配置 (db/redis.py)

```python
from redis import Redis
from src.api.config import settings

# 创建 Redis 客户端
redis_client = Redis.from_url(
    settings.REDIS_URL,
    password=settings.REDIS_PASSWORD,
    db=settings.REDIS_DB,
    decode_responses=True
)


def get_redis() -> Redis:
    """获取 Redis 客户端"""
    return redis_client
```

---

## 8. 错误处理

### 8.1 自定义异常类 (api/utils/errors.py)

```python
from typing import Optional
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from datetime import datetime


class APIException(Exception):
    """API 基础异常"""

    def __init__(
        self,
        code: int,
        message: str,
        http_status: int = status.HTTP_400_BAD_REQUEST,
        errors: Optional[list] = None
    ):
        self.code = code
        self.message = message
        self.http_status = http_status
        self.errors = errors
        super().__init__(message)


class UserExistsError(APIException):
    """用户已存在异常"""

    def __init__(self, field: str = "username"):
        self.code = 1001 if field == "username" else 1002
        self.message = "用户名已存在" if field == "username" else "邮箱已存在"
        self.http_status = status.HTTP_409_CONFLICT
        self.errors = [
            {
                "field": field,
                "message": self.message
            }
        ]
        super().__init__(self.code, self.message, self.http_status, self.errors)


class InvalidCredentialsError(APIException):
    """无效凭证异常"""

    def __init__(self):
        self.code = 1003
        self.message = "用户名或密码错误"
        self.http_status = status.HTTP_401_UNAUTHORIZED
        super().__init__(self.code, self.message, self.http_status)


class TokenInvalidError(APIException):
    """Token 无效异常"""

    def __init__(self, message: str = "Token 无效或已过期"):
        self.code = 1004
        self.message = message
        self.http_status = status.HTTP_401_UNAUTHORIZED
        super().__init__(self.code, self.message, self.http_status)


class TaskNotFoundError(APIException):
    """任务不存在异常"""

    def __init__(self, task_id: str):
        self.code = 2001
        self.message = f"任务 {task_id} 不存在"
        self.http_status = status.HTTP_404_NOT_FOUND
        super().__init__(self.code, self.message, self.http_status)


class TaskFailedError(APIException):
    """任务执行失败异常"""

    def __init__(self, error: str):
        self.code = 2003
        self.message = f"任务执行失败: {error}"
        self.http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
        super().__init__(self.code, self.message, self.http_status)


async def api_exception_handler(request, exc: APIException):
    """API 异常处理器"""
    return JSONResponse(
        status_code=exc.http_status,
        content={
            "code": exc.code,
            "message": exc.message,
            "errors": exc.errors,
            "timestamp": datetime.now().isoformat()
        }
    )


async def generic_exception_handler(request, exc: Exception):
    """通用异常处理器"""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "code": 4999,
            "message": "内部服务器错误",
            "errors": [{"message": str(exc)}],
            "timestamp": datetime.now().isoformat()
        }
    )
```

---

## 9. 测试方案

### 9.1 测试配置 (tests/conftest.py)

```python
import pytest
import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from httpx import AsyncClient, ASGITransport
from src.api.main import app
from src.db.base import Base
from src.db.models import UserModel, TaskModel, DietPlanModel


# 测试数据库 URL
TEST_DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5432/pet_food_test"

# 创建测试引擎
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """创建数据库会话"""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture(scope="function")
async def client(db_session: AsyncSession):
    """创建测试客户端"""
    from src.api.dependencies import get_db
    from src.api.main import app

    # 覆盖依赖
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """创建测试用户"""
    user = UserModel(
        username="testuser",
        email="test@example.com",
        hashed_password="$2b$12$...hashed..."  # 预哈希
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
```

### 9.2 API 测试示例 (tests/test_api/test_auth.py)

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """测试注册成功"""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "john_doe",
            "email": "john@example.com",
            "password": "SecurePass123!@#"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert data["data"]["user"]["username"] == "john_doe"
    assert "access_token" in data["data"]["tokens"]


@pytest.mark.asyncio
async def test_register_duplicate_username(client: AsyncClient):
    """测试注册用户名重复"""
    # 第一次注册
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "john_doe",
            "email": "john1@example.com",
            "password": "SecurePass123!@#"
        }
    )

    # 第二次注册（用户名重复）
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "username": "john_doe",
            "email": "john2@example.com",
            "password": "SecurePass123!@#"
        }
    )

    assert response.status_code == 409
    data = response.json()
    assert data["code"] == 1001


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """测试登录成功"""
    # 先注册
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "john_doe",
            "email": "john@example.com",
            "password": "SecurePass123!@#"
        }
    )

    # 登录
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "username": "john_doe",
            "password": "SecurePass123!@#"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
    assert "access_token" in data["data"]["tokens"]


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient):
    """测试登录密码错误"""
    # 先注册
    await client.post(
        "/api/v1/auth/register",
        json={
            "username": "john_doe",
            "email": "john@example.com",
            "password": "SecurePass123!@#"
        }
    )

    # 登录（密码错误）
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "username": "john_doe",
            "password": "WrongPassword"
        }
    )

    assert response.status_code == 401
    data = response.json()
    assert data["code"] == 1003
```

### 9.3 服务测试示例 (tests/test_services/test_auth_service.py)

```python
import pytest
from src.api.services.auth_service import AuthService
from src.api.models.request import RegisterRequest


@pytest.mark.asyncio
async def test_register_user(db_session):
    """测试注册用户"""
    auth_service = AuthService(db_session, None)

    request = RegisterRequest(
        username="testuser",
        email="test@example.com",
        password="SecurePass123!@#"
    )

    result = await auth_service.register(request)

    assert result["user"]["username"] == "testuser"
    assert "access_token" in result["tokens"]
    assert "refresh_token" in result["tokens"]


@pytest.mark.asyncio
async def test_register_duplicate_user(db_session):
    """测试注册重复用户"""
    auth_service = AuthService(db_session, None)

    request = RegisterRequest(
        username="testuser",
        email="test@example.com",
        password="SecurePass123!@#"
    )

    # 第一次注册
    await auth_service.register(request)

    # 第二次注册（应失败）
    with pytest.raises(ValueError, match="用户名已存在"):
        await auth_service.register(request)
```

---

## 10. 部署方案

### 10.1 Dockerfile

```dockerfile
# 多阶段构建
FROM python:3.12-slim as builder

WORKDIR /app

# 安装 uv
RUN pip install uv

# 复制依赖文件
COPY pyproject.toml ./

# 安装依赖
RUN uv pip install --system -e .

# 运行时镜像
FROM python:3.12-slim

WORKDIR /app

# 复制虚拟环境
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 复制项目文件
COPY . .

# 创建日志目录
RUN mkdir -p logs

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 10.2 docker-compose.yml

```yaml
version: '3.8'

services:
  # FastAPI 应用
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:password@db:5432/pet_food
      - REDIS_URL=redis://redis:6379/0
      - JWT_SECRET_KEY=your-secret-key-change-in-production
    depends_on:
      - db
      - redis
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped

  # PostgreSQL 数据库
  db:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=pet_food
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    restart: unless-stopped

  # Redis
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"
    restart: unless-stopped

  # Nginx 反向代理
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./deployment/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./deployment/ssl:/etc/nginx/ssl:ro
    depends_on:
      - api
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

### 10.3 Nginx 配置 (deployment/nginx.conf)

```nginx
events {
    worker_connections 1024;
}

http {
    upstream api {
        server api:8000;
    }

    # 速率限制
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

    server {
        listen 80;
        server_name your-domain.com;

        # 重定向到 HTTPS
        return 301 https://$server_name$request_uri;
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com;

        # SSL 证书
        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;

        # SSL 配置
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        # 代理到 FastAPI
        location /api/v1/ {
            limit_req zone=api_limit burst=20 nodelay;

            proxy_pass http://api;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;

            # SSE 支持
            proxy_buffering off;
            proxy_cache off;
            proxy_set_header Connection '';
            proxy_http_version 1.1;
            chunked_transfer_encoding off;
        }

        # API 文档
        location /api/v1/docs {
            proxy_pass http://api;
        }

        location /api/v1/redoc {
            proxy_pass http://api;
        }

        location /api/v1/openapi.json {
            proxy_pass http://api;
        }
    }
}
```

### 10.4 Gunicorn 配置 (deployment/gunicorn_conf.py)

```python
import multiprocessing

# 服务器套接字
bind = "0.0.0.0:8000"
backlog = 2048

# Worker 进程
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 300
keepalive = 2

# 日志
accesslog = "logs/access.log"
errorlog = "logs/error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 进程命名
proc_name = "pet-food-api"

# Server 机制
daemon = False
pidfile = "/tmp/gunicorn.pid"
user = None
group = None
tmp_upload_dir = None
```

---

## 11. 安全考虑

### 11.1 CORS 配置

在 `api/main.py` 中：

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # 生产环境应指定具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**生产环境建议**:
```python
allow_origins=[
    "https://your-frontend-domain.com",
    "https://admin.your-domain.com"
]
```

### 11.2 速率限制

在 `api/middleware/rate_limit.py` 中：

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from redis import Redis
import time


class RateLimitMiddleware(BaseHTTPMiddleware):
    """速率限制中间件"""

    def __init__(self, app, redis: Redis, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.redis = redis
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def dispatch(self, request, call_next):
        # 提取客户端 IP
        client_ip = request.client.host

        # 生成 Redis 键
        key = f"rate_limit:{client_ip}"

        # 获取当前请求计数
        current = self.redis.get(key)

        if current is None:
            # 首次请求，设置计数器
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, self.window_seconds)
            pipe.execute()
        else:
            # 检查是否超过限制
            if int(current) >= self.max_requests:
                return JSONResponse(
                    status_code=429,
                    content={
                        "code": 4290,
                        "message": "请求过于频繁，请稍后再试",
                        "timestamp": time.time()
                    }
                )
            else:
                # 增加计数
                self.redis.incr(key)

        return await call_next(request)
```

### 11.3 SQL 注入防护

使用 SQLAlchemy ORM 自动防止 SQL 注入：

```python
# ❌ 错误：直接拼接 SQL
query = f"SELECT * FROM users WHERE username = '{username}'"

# ✅ 正确：使用参数化查询
result = await db.execute(
    select(UserModel).where(UserModel.username == username)
)
```

### 11.4 XSS 防护

FastAPI 自动转义 JSON 响应，但仍需注意：

```python
# 输入验证
from pydantic import BaseModel, Field

class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, regex=r'^[a-zA-Z0-9_]+$')

# 输出转义（FastAPI 自动处理）
return {"message": f"欢迎, {user.username}!"}
```

### 11.5 密码安全

使用 bcrypt 哈希：

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    """哈希密码"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)
```

### 11.6 JWT 安全

```python
# 1. 使用强密钥
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")  # 至少 32 字符

# 2. 设置过期时间
expires_delta = timedelta(hours=1)  # 访问 Token 1 小时

# 3. Token 黑名单（用于注销）
async def logout(token: str):
    redis.setex(f"blacklist:{token}", 3600, "1")

# 4. 验证 Token 时检查黑名单
if redis.get(f"blacklist:{token}"):
    raise TokenInvalidError("Token 已失效")
```

---

## 12. 实施计划

### 12.1 分步骤任务清单

#### 步骤 1: 环境准备（预计 0.5 天）

**任务**:
1. 更新 `pyproject.toml` 添加 FastAPI 相关依赖
2. 创建 `.env` 文件并配置环境变量
3. 安装 PostgreSQL 和 Redis（本地或 Docker）

**涉及文件**:
- `pyproject.toml`
- `.env`

**验收标准**:
- 所有依赖成功安装
- PostgreSQL 和 Redis 可连接

---

#### 步骤 2: 数据库层实现（预计 1 天）

**任务**:
1. 创建数据库模型 (`db/models.py`)
2. 实现数据库会话管理 (`db/session.py`)
3. 实现 Redis 客户端 (`db/redis.py`)
4. 配置 Alembic 迁移
5. 编写初始化迁移脚本

**涉及文件**:
- `db/__init__.py`
- `db/base.py`
- `db/models.py`
- `db/session.py`
- `db/redis.py`
- `alembic/versions/001_initial.py`
- `alembic.ini`

**代码示例**:

```bash
# 初始化 Alembic
alembic init alembic

# 生成迁移
alembic revision --autogenerate -m "Initial migration"

# 运行迁移
alembic upgrade head
```

**验收标准**:
- 数据库表成功创建
- 可以通过 SQLAlchemy 查询和插入数据
- Redis 连接正常

---

#### 步骤 3: 认证服务实现（预计 1 天）

**任务**:
1. 实现 JWT 和密码哈希工具 (`api/utils/security.py`)
2. 实现自定义异常类 (`api/utils/errors.py`)
3. 实现认证服务 (`api/services/auth_service.py`)
4. 实现认证路由 (`api/routes/auth.py`)
5. 实现认证中间件 (`api/middleware/auth.py`)

**涉及文件**:
- `api/utils/security.py`
- `api/utils/errors.py`
- `api/services/auth_service.py`
- `api/routes/auth.py`
- `api/middleware/auth.py`

**代码示例**:

```python
# api/utils/security.py
from datetime import datetime, timedelta
from typing import Dict
from jose import JWTError, jwt
from passlib.context import CryptContext
from src.api.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_token(
    sub: str,
    username: str,
    token_type: str = "access",
    expires_delta: timedelta | None = None
) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)

    to_encode = {
        "sub": sub,
        "username": username,
        "type": token_type,
        "exp": expire
    }

    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise ValueError("Token 无效或已过期")
```

**验收标准**:
- 用户注册成功
- 用户登录成功并返回 Token
- 使用 Token 可以访问受保护的接口

---

#### 步骤 4: 核心服务实现（预计 1.5 天）

**任务**:
1. 实现任务管理服务 (`api/services/task_service.py`)
2. 实现饮食计划服务 (`api/services/plan_service.py`)
3. 实现流式输出工具 (`api/utils/stream.py`)

**涉及文件**:
- `api/services/task_service.py`
- `api/services/plan_service.py`
- `api/utils/stream.py`

**代码示例**:

```python
# api/utils/stream.py
import json
from typing import AsyncGenerator
from fastapi import Request

async def stream_langgraph_execution(graph, inputs, config) -> AsyncGenerator[str, None]:
    """流式执行 LangGraph 并返回 SSE 事件"""
    async for event in graph.astream_events(inputs, config=config, version="v1"):
        event_type = event.get("event")
        node_name = event.get("name", "")

        if "start" in event_type:
            yield f"data: {json.dumps({'type': 'node_started', 'node': node_name})}\n\n"
        elif "end" in event_type:
            yield f"data: {json.dumps({'type': 'node_completed', 'node': node_name})}\n\n"

    yield "data: [DONE]\n\n"
```

**验收标准**:
- 可以创建饮食计划任务
- 可以查询任务状态
- 可以通过 SSE 获取流式输出

---

#### 步骤 5: 路由实现（预计 1 天）

**任务**:
1. 实现饮食计划路由 (`api/routes/plans.py`)
2. 实现任务管理路由 (`api/routes/tasks.py`)
3. 实现健康检查路由 (`api/routes/health.py`)

**涉及文件**:
- `api/routes/plans.py`
- `api/routes/tasks.py`
- `api/routes/health.py`

**代码示例**:

```python
# api/routes/plans.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_db, get_current_user, get_redis
from src.api.models.request import CreatePlanRequest
from src.api.models.response import ApiResponse
from src.api.services.plan_service import PlanService

router = APIRouter()

@router.post("/", response_model=ApiResponse)
async def create_plan(
    request: CreatePlanRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis = Depends(get_redis)
):
    """创建饮食计划"""
    plan_service = PlanService(db, redis)

    if request.stream:
        # 流式输出
        return StreamingResponse(
            plan_service.create_plan_stream(current_user["id"], request),
            media_type="text/event-stream"
        )
    else:
        # 同步执行
        result = await plan_service.create_plan(current_user["id"], request)
        return ApiResponse(data=result)
```

**验收标准**:
- 所有接口可以正常调用
- 返回正确的数据格式
- 错误处理正常

---

#### 步骤 6: 中间件和配置（预计 0.5 天）

**任务**:
1. 实现 CORS 中间件 (`api/middleware/cors.py`)
2. 实现日志中间件 (`api/middleware/logging.py`)
3. 实现速率限制中间件 (`api/middleware/rate_limit.py`)
4. 实现 API 配置 (`api/config.py`)
5. 实现依赖注入 (`api/dependencies.py`)

**涉及文件**:
- `api/middleware/cors.py`
- `api/middleware/logging.py`
- `api/middleware/rate_limit.py`
- `api/config.py`
- `api/dependencies.py`

**验收标准**:
- CORS 配置正确
- 日志正常记录
- 速率限制生效

---

#### 步骤 7: FastAPI 应用入口（预计 0.5 天）

**任务**:
1. 实现 FastAPI 应用入口 (`api/main.py`)
2. 注册所有路由和中间件
3. 配置 OpenAPI 文档
4. 实现健康检查接口

**涉及文件**:
- `api/main.py`

**代码示例**:

```python
# api/main.py
from fastapi import FastAPI
from src.api.routes import auth, plans, tasks, health
from src.api.middleware import auth, cors, logging, rate_limit
from src.api.utils.errors import APIException, api_exception_handler, generic_exception_handler

app = FastAPI(
    title="宠物饮食计划智能助手 API",
    version="1.0.0",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc"
)

# 中间件
app.add_middleware(cors.CORSMiddleware)
app.add_middleware(logging.LoggingMiddleware)
app.add_middleware(rate_limit.RateLimitMiddleware)

# 异常处理
app.add_exception_handler(APIException, api_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# 路由
app.include_router(auth.router, prefix="/api/v1/auth", tags=["认证"])
app.include_router(plans.router, prefix="/api/v1/plans", tags=["饮食计划"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["任务管理"])
app.include_router(health.router, prefix="/api/v1/health", tags=["健康检查"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

**验收标准**:
- FastAPI 应用可以启动
- API 文档可以访问
- 健康检查正常

---

#### 步骤 8: 测试编写（预计 1.5 天）

**任务**:
1. 配置 pytest (`tests/conftest.py`)
2. 编写认证测试 (`tests/test_api/test_auth.py`)
3. 编写饮食计划测试 (`tests/test_api/test_plans.py`)
4. 编写服务测试 (`tests/test_services/`)

**涉及文件**:
- `tests/conftest.py`
- `tests/test_api/test_auth.py`
- `tests/test_api/test_plans.py`
- `tests/test_api/test_tasks.py`
- `tests/test_services/test_auth_service.py`
- `tests/test_services/test_plan_service.py`

**验收标准**:
- 所有测试通过
- 测试覆盖率 > 80%

---

#### 步骤 9: Docker 化（预计 0.5 天）

**任务**:
1. 编写 Dockerfile
2. 编写 docker-compose.yml
3. 编写 Nginx 配置
4. 编写 Gunicorn 配置

**涉及文件**:
- `Dockerfile`
- `docker-compose.yml`
- `deployment/nginx.conf`
- `deployment/gunicorn_conf.py`

**验收标准**:
- 可以通过 Docker Compose 启动所有服务
- API 可以正常访问
- 数据持久化正常

---

#### 步骤 10: 文档和部署（预计 0.5 天）

**任务**:
1. 编写 API 使用文档
2. 编写部署文档
3. 配置 CI/CD（可选）
4. 部署到生产环境

**涉及文件**:
- `docs/api.md`
- `docs/deployment.md`
- `.github/workflows/ci.yml`（可选）

**验收标准**:
- 文档完整清晰
- 生产环境部署成功
- 性能测试通过

---

### 12.2 总工作量估算

| 步骤 | 预计时间 | 累计时间 |
|------|---------|---------|
| 步骤 1: 环境准备 | 0.5 天 | 0.5 天 |
| 步骤 2: 数据库层实现 | 1 天 | 1.5 天 |
| 步骤 3: 认证服务实现 | 1 天 | 2.5 天 |
| 步骤 4: 核心服务实现 | 1.5 天 | 4 天 |
| 步骤 5: 路由实现 | 1 天 | 5 天 |
| 步骤 6: 中间件和配置 | 0.5 天 | 5.5 天 |
| 步骤 7: FastAPI 应用入口 | 0.5 天 | 6 天 |
| 步骤 8: 测试编写 | 1.5 天 | 7.5 天 |
| 步骤 9: Docker 化 | 0.5 天 | 8 天 |
| 步骤 10: 文档和部署 | 0.5 天 | 8.5 天 |

**总计**: 约 **8.5 个工作日**（1.5 周）

---

### 12.3 依赖关系图

```mermaid
graph TD
    A[步骤1: 环境准备] --> B[步骤2: 数据库层]
    B --> C[步骤3: 认证服务]
    B --> D[步骤4: 核心服务]
    C --> E[步骤5: 路由实现]
    D --> E
    E --> F[步骤6: 中间件和配置]
    F --> G[步骤7: FastAPI应用入口]
    G --> H[步骤8: 测试编写]
    G --> I[步骤9: Docker化]
    H --> J[步骤10: 文档和部署]
    I --> J
```

---

## 13. 附录

### 13.1 依赖更新 (pyproject.toml)

在 `pyproject.toml` 的 `dependencies` 中添加：

```toml
dependencies = [
    # 现有依赖...
    "langchain>=0.3.27",
    "langgraph>=0.6.6",

    # 🆕 FastAPI 相关
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.37.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "python-multipart>=0.0.20",

    # 🆕 数据库相关
    "sqlalchemy>=2.0.36",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "redis>=5.2.1",

    # 🆕 配置管理
    "pydantic-settings>=2.6.0",

    # 🆕 测试相关
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.28.1",

    # 现有依赖...
    "python-dotenv>=1.1.1",
]
```

### 13.2 快速启动命令

```bash
# 1. 安装依赖
uv pip install -e .

# 2. 初始化数据库
alembic upgrade head

# 3. 启动 Redis
docker run -d -p 6379:6379 redis:7-alpine

# 4. 启动 PostgreSQL
docker run -d -p 5432:5432 \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=pet_food \
  postgres:16-alpine

# 5. 配置环境变量
cp .env.example .env
# 编辑 .env 文件

# 6. 启动 FastAPI
python -m src.api.main

# 或使用 uvicorn
uvicorn src.api.main:app --reload
```

### 13.3 API 测试命令

```bash
# 1. 注册用户
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","email":"test@example.com","password":"SecurePass123!@#"}'

# 2. 登录
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"SecurePass123!@#"}'

# 3. 创建饮食计划（同步）
curl -X POST http://localhost:8000/api/v1/plans \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "pet_information": {
      "pet_type": "猫",
      "pet_breed": "英国短毛猫",
      "age": "3岁",
      "pet_weight": 4.5,
      "pet_health_status": "健康"
    },
    "stream": false
  }'

# 4. 创建饮食计划（流式）
curl -X POST http://localhost:8000/api/v1/plans \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "pet_information": {
      "pet_type": "猫",
      "pet_breed": "英国短毛猫",
      "age": "3岁",
      "pet_weight": 4.5,
      "pet_health_status": "健康"
    },
    "stream": true
  }'

# 5. 查询任务状态
curl -X GET http://localhost:8000/api/v1/tasks/<task_id> \
  -H "Authorization: Bearer <token>"

# 6. 健康检查
curl -X GET http://localhost:8000/api/v1/health
```

### 13.4 常见问题

**Q1: 如何调试 LangGraph 流式输出？**

在 `api/utils/stream.py` 中添加日志：

```python
import logging
logger = logging.getLogger(__name__)

async def execute_plan_stream(...):
    async for event in graph.astream_events(...):
        logger.debug(f"LangGraph 事件: {event}")
        # ...
```

**Q2: 如何处理任务超时？**

在 `api/services/plan_service.py` 中添加超时控制：

```python
import asyncio

async def create_plan(...):
    try:
        # 设置超时（例如 5 分钟）
        report = await asyncio.wait_for(
            execute_plan_sync(user_id, request),
            timeout=300.0
        )
    except asyncio.TimeoutError:
        task.status = "failed"
        task.error = "任务执行超时"
```

**Q3: 如何优化数据库查询性能？**

1. 使用索引：
```python
username = Column(String(50), unique=True, nullable=False, index=True)
```

2. 使用连接池：
```python
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=20,
    max_overflow=40
)
```

3. 批量查询：
```python
# ❌ N+1 查询
for task in tasks:
    user = await get_user(task.user_id)

# ✅ 使用 JOIN
result = await db.execute(
    select(Task, User).join(User).where(Task.user_id == user_id)
)
```

---

## 14. 总结

本文档提供了完整的 FastAPI 初始化规划，包括：

1. ✅ **技术架构设计**: 清晰的分层架构和组件交互
2. ✅ **完整的目录结构**: 符合最佳实践的项目组织
3. ✅ **详细的 API 接口**: 15+ RESTful 接口设计
4. ✅ **数据模型定义**: Pydantic 和 SQLAlchemy 模型
5. ✅ **核心实现方案**: 关键代码示例
6. ✅ **配置方案**: 环境变量和配置类
7. ✅ **错误处理**: 统一的异常处理机制
8. ✅ **测试方案**: 单元测试和集成测试
9. ✅ **部署方案**: Docker 和 Nginx 配置
10. ✅ **实施计划**: 分 10 步，约 8.5 个工作日

**下一步行动**:
1. 审核本文档
2. 确认技术选型和架构设计
3. 开始按照实施计划逐步执行
4. 定期回顾和调整计划

---

**文档版本**: v1.0.0
**最后更新**: 2025-01-29
**维护者**: AI 规划专家
