# 系统架构

> 宠物饮食计划智能助手的整体系统架构设计

---

## 目录

1. [整体架构](#整体架构)
2. [多智能体系统](#多智能体系统)
3. [数据流转](#数据流转)
4. [数据库设计](#数据库设计)

---

## 整体架构

### 分层架构图

```mermaid
graph TB
    subgraph "客户端层"
        Web[Web 界面]
        Mobile[移动端]
    end

    subgraph "API 层"
        Router[路由层]
        Middleware[中间件层]
            AuthMW[JWT 认证]
            RateLimit[速率限制]
            Logging[请求日志]
            Exception[全局异常]
        Services[服务层]
            AuthService[认证服务]
            VerifyService[验证码服务]
            EmailService[邮件服务]
            PlanService[计划服务]
            TaskService[任务服务]
    end

    subgraph "数据层"
        PG[(PostgreSQL<br/>用户/任务/计划)]
        Redis[(Redis<br/>验证码/Session/限流)]
    end

    subgraph "Agent 层"
        MainAgent[主智能体<br/>任务规划]
        SubAgent[子智能体<br/>任务执行]
        WriteAgent[写入智能体<br/>笔记管理]
        StructAgent[结构化智能体<br/>数据解析]
    end

    subgraph "LLM 层"
        DashScope[DashScope<br/>主模型/子模型]
        ZAI[ZAI<br/>子模型/报告]
        DeepSeek[DeepSeek<br/>可选]
        Tavily[Tavily<br/>互联网搜索]
    end

    Web --> Router
    Mobile --> Router

    Router --> Middleware
    Middleware --> AuthMW
    Middleware --> RateLimit
    Middleware --> Logging
    Middleware --> Exception

    Router --> Services
    Services --> PG
    Services --> Redis

    Services --> MainAgent
    MainAgent --> SubAgent
    MainAgent --> WriteAgent
    MainAgent --> StructAgent
    SubAgent --> WriteAgent
    MainAgent --> DashScope
    SubAgent --> Tavily

    MainAgent -.->|规划任务| SubAgent
    SubAgent -.->|执行任务| WriteAgent
    WriteAgent -.->|保存笔记| StructAgent
    StructAgent -.->|解析数据| DB

    style Web fill:#e1f5ff,stroke:#333,color:#333
    style Mobile fill:#e1f5ff,stroke:#333,color:#333
    style Router fill:#fff3e0,stroke:#333,color:#333
    style Middleware fill:#fff9c4,stroke:#333,color:#333
    style Services fill:#e8f5e9,stroke:#333,color:#333
    style PG fill:#336791,stroke:#333,color:#fff
    style Redis fill:#dc382d,stroke:#333,color:#fff
    style MainAgent fill:#fff9c4,stroke:#333,color:#e65100
    style SubAgent fill:#f3e5f5,stroke:#333,color:#e65100
    style WriteAgent fill:#e0f2f1,stroke:#333,color:#e65100
    style StructAgent fill:#fce4ec,stroke:#333,color:#e65100
    style DashScope fill:#ff6f00,stroke:#333,color:#fff
    style ZAI fill:#ff5722,stroke:#333,color:#fff
    style DeepSeek fill:#4caf50,stroke:#333,color:#fff
    style Tavily fill:#1db954,stroke:#333,color:#fff
```

---

## 多智能体系统

### 智能体协作图

```mermaid
graph TB
    subgraph "LangGraph 执行流程"
        Input[用户输入<br/>宠物信息]

        subgraph "主智能体 (Main Agent)"
            M1[call_model<br/>任务规划]
            M2[write_plan<br/>初始化计划]
            M3[update_plan<br/>更新进度]
            M4[transfor_task<br/>委派任务]
        end

        subgraph "子智能体 (Sub Agent)"
            S1[query_note<br/>查询笔记]
            S2[tavily_search<br/>互联网搜索]
            S3[get_weather<br/>获取天气]
            S4[返回任务结果]
        end

        subgraph "写入智能体 (Write Agent)"
            W1[write<br/>格式化内容]
            W2[summary<br/>生成摘要]
            W3[write_note<br/>保存笔记]
        end

        subgraph "结构化智能体 (Structure Agent)"
            ST1[structure_report<br/>解析周计划]
            ST2[gather<br/>汇总结果]
            ST3[output<br/>最终报告]
        end

        Output[输出<br/>月度饮食计划]

        Input --> M1
        M1 --> M2
        M4 --> S1
        M4 --> S2
        M4 --> S3
        S4 --> W1
        W1 --> W2
        W1 --> ST1
        W2 --> W3
        S3 --> ST2
        ST2 --> ST3
        ST3 --> Output

        style Input fill:#e1f5ff,stroke:#333,color:#333
        style M1 fill:#fff9c4,stroke:#333,color:#e65100
        style M2 fill:#f3e5f5,stroke:#333,color:#e65100
        style M3 fill:#f3e5f5,stroke:#333,color:#e65100
        style M4 fill:#f3e5f5,stroke:#333,color:#e65100
        style S1 fill:#e0f2f1,stroke:#333,color:#e65100
        style S2 fill:#1db954,stroke:#333,color:#fff
        style S3 fill:#4caf50,stroke:#333,color:#fff
        style S4 fill:#4caf50,stroke:#333,color:#fff
        style W1 fill:#e0f2f1,stroke:#333,color:#e65100
        style W2 fill:#e0f2f1,stroke:#333,color:#e65100
        style W3 fill:#e0f2f1,stroke:#333,color:#e65100
        style ST1 fill:#fce4ec,stroke:#333,color:#e65100
        style ST2 fill:#fce4ec,stroke:#333,color:#e65100
        style ST3 fill:#fce4ec,stroke:#333,color:#e65100
        style Output fill:#c8e6c9,stroke:#333,color:#fff
    end
```

### 智能体职责

| 智能体 | 职责 | 关键方法 |
|--------|------|----------|
| **主智能体** | 任务分解、计划管理、整体协调 | `call_model`, `write_plan`, `update_plan` |
| **子智能体** | 执行具体任务、搜索、查询 | `tavily_search`, `query_note`, `get_weather` |
| **写入智能体** | 格式化内容、保存笔记、生成摘要 | `write`, `summary`, `write_note` |
| **结构化智能体** | 解析笔记为结构化数据、汇总报告 | `structure_report`, `gather` |

---

## 数据流转

### 笔记系统

```mermaid
sequenceDiagram
    participant Main as 主智能体
    participant Sub as 子智能体
    participant Write as 写入智能体
    participant Note as 笔记系统

    Main->>Write: transfor_task_to_subagent(task_name="研究宠物营养")
    Sub->>Sub: 执行任务（搜索 + 查询）
    Sub-->>Write: 返回任务结果
    Write->>Write: write(diet_plan, content="...")
    Write->>Write: summary("第1周饮食计划")
    Write->>Note: write_note(type="diet_plan", content="...")

    Note over Main,Write: 所有子任务完成后

    Main->>Write: transfor_task_to_subagent(task_name="第2周计划")
    Main->>Main: 委派第2个任务
```

### 状态流转

```mermaid
stateDiagram-v2
    [*] --> Pending: 任务待处理
    Pending --> Running: 开始执行
    Running --> Running: 更新进度
    Running --> Completed: 任务完成
    Running --> Cancelled: 任务取消
    Completed --> [*]
    Cancelled --> [*]
```

---

## 数据库设计

### ER 图

```mermaid
erDiagram
    User ||--|{ User ||--|{ DietPlan
    PK "id(uuid)"
    FK "user_id"

    User ||--|{ RefreshToken
    PK "id(uuid)"
    FK "user_id"

    User ||--|{ Task
    PK "id(uuid)"
    FK "user_id"

    DietPlan }| {
        PK "id(uuid)"
        FK "user_id"
    FK "task_id"
    FK "user_id"
    FK "task_id"
    FK "user_id"
    FK "task_id"
        FK "task_id"
    FK "task_id"
    FK "task_id"
    FK "task_id"
        FK "task_id"
    FK "task_id"
    FK "task_id"
        FK "task_id"
        FK "task_id"
        FK "task_id"
        FK "task_id"
        FK "task_id"
    }

    Task {
        PK "id(uuid)"
        FK "user_id"
        status "pending/running/completed/cancelled"
        progress "0-100"
        current_node "main_agent/sub_agent/write_agent/structure_agent"
    }
```

### 表关系说明

| 表 | 说明 | 关键字段 |
|------|------|----------|
| `users` | 用户表，存储认证信息 | id, username, email, hashed_password, is_active, is_superuser |
| `tasks` | 任务表，跟踪执行状态和进度 | id, user_id, task_type, status, progress, current_node, input_data, output_data |
| `diet_plans` | 饮食计划表，存储生成的计划 | id, user_id, task_id, pet_type, pet_breed, pet_age, pet_weight, health_status, plan_data |
| `refresh_tokens` | 刷新令牌表，用于 Token 黑名单 | id, user_id, token, is_revoked, expires_at |

---

## 相关文档

- [后端开发文档](./backend/README.md)
- [前端对接指南](./frontend/README.md)
- [部署指南](./deployment/README.md)
