# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

基于 LangGraph 的宠物饮食计划智能助手后端。使用**多智能体架构**为宠物生成定制化的月度营养饮食计划。

**技术栈**: Python 3.12, FastAPI, SQLAlchemy (asyncpg), LangGraph, LangChain, Alembic, Redis

---

## 模块索引

| 模块 | 路径 | 职责 | 文档 |
|------|------|------|------|
| **Agent v1** (当前) | `src/agent/v1/` | 三阶段并行架构：研究→周计划→结构化 | 见下方 |
| **Agent v0** (备用) | `src/agent/v0/` | 串行架构：4 agent 循环调度 | [CLAUDE.md](./src/agent/CLAUDE.md) |
| **API** | `src/api/` | FastAPI REST, JWT 认证, SSE 流式 | 见下方 |
| **DB** | `src/db/` | PostgreSQL + Redis 数据访问层 | |
| **RAG** | `src/rag/` | 知识库管理、Milvus 混合检索、Rerank | [CLAUDE.md](./src/rag/CLAUDE.md) |
| **Utils** | `src/utils/` | 通用工具（含 `strtuct.py` 数据结构） | |
| **部署** | `deployment/` | Docker Compose + Nginx + 迁移脚本 | [README](./deployment/README.md) / [TROUBLESHOOTING](./deployment/TROUBLESHOOTING.md) |

---

## Agent v1 架构（当前活跃版本）

### 三阶段流水线

```
Phase 1: 研究阶段 (串行)
  research_planner <-> subagent/write_agent (2-3 个调研任务循环)
  └─ 完成后调用 finalize_research -> 生成 CoordinationGuide (4 周差异化分配)

Phase 2: 周计划阶段 (并行)
  dispatch_weeks -> Send x4 -> week_agent[1..4] (独立子图, 并行执行)
  └─ 每个 week_agent 搜索+撰写本周饮食计划

Phase 3: 结构化汇总 (并行)
  collect_and_structure -> Send xN -> structure_report -> gather
  └─ 将 Markdown 笔记解析为 WeeklyDietPlan Pydantic 模型
  └─ 汇总为 PetDietPlan 最终报告
```

### 关键文件链

```
v1/graph.py (图拓扑)
  -> v1/state.py (StateV1Input, StateV1, StateV1Output)
  -> v1/node.py (节点逻辑: research_planner, dispatch_weeks, collect_and_structure, gather)
  -> v1/models.py (CoordinationGuide 模型)
  -> v1/tools.py (V1 特定工具)
  -> v1/prompts/prompt.py (提示词)
  -> v1/utils/context.py (ContextV1 模型配置)
  -> v1/week_agent/ (周子图: graph.py, node.py, state.py, tools.py)
  -> v0/structrue_agent/ (结构化复用，注意拼写)
```

### V1 vs V0 对比

| 特性 | V1 (当前) | V0 (备用) |
|------|-----------|-----------|
| 架构 | 三阶段并行 | 串行循环 |
| 周计划生成 | 4 个 week_agent 并行 | 单 agent 串行 |
| 研究阶段 | 独立 CoordinationGuide | 任务列表 |
| 结构化 | 复用 v0/structrue_agent | 原生 |
| LangGraph 图名 | `pet_food_v1` | `pet_food` |

### LangGraph 配置

`langgraph.json` 中同时注册两个图：
- `pet_food`: v0 串行架构
- `pet_food_v1`: v1 并行架构（默认使用）

---

## API 模块

### 目录结构

```
src/api/
├── main.py                 # FastAPI 应用入口
├── config.py               # 配置管理（Pydantic Settings）
├── dependencies.py         # 依赖注入（数据库、Redis）
├── middleware/              # 中间件
│   ├── auth.py             # JWT 认证
│   ├── logging.py          # 请求日志
│   ├── rate_limit.py       # 速率限制
│   └── exceptions.py       # 全局异常处理
├── routes/                 # API 路由
│   ├── auth.py             # 认证（注册、登录、刷新）
│   ├── verification.py     # 验证码（发送、验证、重置）
│   ├── pets.py             # 宠物管理（CRUD、头像上传）
│   ├── plans.py            # 饮食计划（SSE 流式生成、列表、详情）
│   ├── tasks.py            # 任务管理（状态、结果、取消）
│   ├── meals.py            # 餐食记录（今日、完成、历史）
│   ├── calendar.py         # 日历视图（月度、周度）
│   └── analysis.py         # 营养分析
├── services/               # 业务服务层
│   ├── auth_service.py
│   ├── verification_service.py
│   ├── email_service.py
│   ├── plan_service.py     # 调用 Agent V1 图
│   └── task_service.py
├── domain/                 # 领域层
│   ├── verification.py
│   └── email_template.py
├── infrastructure/         # 基础设施层
│   ├── interfaces.py       # 接口定义（IEmailSender, ICodeStorage）
│   ├── redis_code_storage.py
│   ├── code_generator.py
│   └── email_providers/
│       └── smtp_email_sender.py
└── utils/
    ├── security.py         # JWT、密码哈希
    ├── stream.py           # SSE 流式输出
    └── errors.py           # 错误定义
```

### API 路由一览

| 路由前缀 | 核心端点 |
|----------|----------|
| `POST /api/v1/auth/register` | 注册 |
| `POST /api/v1/auth/login` | 登录 |
| `GET /api/v1/auth/me` | 当前用户 |
| `POST /api/v1/auth/refresh` | 刷新 Token |
| `POST /api/v1/auth/send-code` | 发送验证码 |
| `POST /api/v1/auth/verify-register` | 验证码注册 |
| `GET /api/v1/pets/` | 宠物列表 |
| `POST /api/v1/pets/` | 创建宠物 |
| `PUT /api/v1/pets/{id}` | 更新宠物 |
| `DELETE /api/v1/pets/{id}` | 删除宠物 |
| `POST /api/v1/pets/{id}/avatar` | 上传头像 |
| `POST /api/v1/plans/stream` | SSE 流式生成计划 |
| `GET /api/v1/plans/` | 计划列表 |
| `GET /api/v1/plans/{id}` | 计划详情 |
| `DELETE /api/v1/plans/{id}` | 删除计划 |
| `GET /api/v1/tasks/{id}` | 任务状态 |
| `GET /api/v1/tasks/{id}/result` | 任务结果 |
| `DELETE /api/v1/tasks/{id}` | 取消任务 |
| `GET /api/v1/meals/today` | 今日餐食 |
| `POST /api/v1/meals/{id}/complete` | 完成餐食 |
| `GET /api/v1/meals/history` | 历史记录 |
| `GET /api/v1/calendar/monthly` | 月度日历 |
| `GET /api/v1/calendar/weekly` | 周度日历 |
| `GET /api/v1/analysis/nutrition` | 营养分析 |

### 认证系统

JWT 双 Token 机制：
- **Access Token**: 30 分钟有效，API 认证
- **Refresh Token**: 7 天有效，无感刷新
- 验证码系统: Redis 存储，6 位数字，可配置有效期/冷却/限制

### 流式进度事件系统

- Agent 节点通过 `emit_progress()` 发送 `ProgressEvent`（定义在 `src/agent/stream_events.py`）
- `stream.py` 使用 `astream(stream_mode=["custom", "updates"])`
- `plan_service.py` 通过 `final_output` 可变 dict 收集最终状态，**不再二次调用 `ainvoke`**
- 子图 custom 事件自动冒泡到顶层 `astream` 消费者

---

## Agent v0 架构（备用/参考）

串行多智能体架构，4 个 agent 循环调度：

1. **主智能体** (`src/agent/v0/graph.py`): 任务分解、委派、协调
2. **子智能体** (`src/agent/v0/sub_agent/`): 执行具体调研/搜索任务
3. **写入智能体** (`src/agent/v0/write_agent/`): 将结果写入笔记
4. **结构化智能体** (`src/agent/v0/structrue_agent/`): 将笔记解析为 Pydantic 模型

详细文档见 [src/agent/CLAUDE.md](./src/agent/CLAUDE.md)。

---

## 数据结构

核心 Pydantic 模型定义在 `src/utils/strtuct.py`（注意文件名拼写）：

```
PetInformation (宠物信息)
    ↓
PetDietPlan (最终报告)
    ├── pet_information: PetInformation
    ├── ai_suggestions: str
    └── pet_diet_plan: MonthlyDietPlan
            └── monthly_diet_plan: list[WeeklyDietPlan]
                    ├── oder: int (第几周)
                    ├── diet_adjustment_principle: str
                    ├── weekly_diet_plan: DailyDietPlan
                    │       └── daily_diet_plans: list[SingleMealPlan]
                    │               ├── oder: int (第几餐)
                    │               ├── time: str
                    │               ├── food_items: list[FoodItem]
                    │               └── cook_method: str
                    └── suggestions: list
```

---

## 数据库

### 模型关系

```
User 1:N Task         (异步任务)
User 1:N Pet          (宠物)
User 1:N DietPlan     (饮食计划)
Pet  1:N DietPlan     (关联宠物)
Pet  1:N MealRecord   (餐食记录)
User 1:N RefreshToken (JWT 刷新令牌)
```

### Alembic 迁移

```
alembic/versions/
├── 001_initial_migration.py     # users, tasks, diet_plans, refresh_tokens
└── 002_add_pets_and_meals.py    # pets, meal_records, 用户字段扩展
```

- 创建涉及外键的迁移时，**必须先创建被引用表**
- Windows 下需设置 `PYTHONUTF8=1` 避免编码错误

---

## RAG 集成

| 模块 | 文件 | 功能 |
|------|------|------|
| **知识库管理** | `knowledge.py` | 加载 Markdown 文档，按标题分割 |
| **向量数据库** | `milvus.py` | Milvus 混合检索（dense + sparse + BM25） |
| **DeerFlow** | `deer_flow/` | 自定义检索器 |
| **Embedding** | `component.py` | Dashscope Embedding 封装 |

检索策略: dense 0.6 + sparse 0.4，DashScope Rerank 重排序，jieba 中文分词。

---

## 开发环境

### 常用命令

```bash
# 安装依赖 (uv 包管理器)
uv pip install -e .

# 启动 API 服务 (开发)
python main.py
# 或
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# LangGraph Studio (可视化调试)
langgraph dev

# 数据库迁移
$env:PYTHONUTF8='1'; uv run alembic upgrade head    # Windows PowerShell
uv run alembic revision --autogenerate -m "描述"      # 生成迁移

# 测试
pytest                                                # 全部
pytest tests/test_auth.py -v                          # 单文件
pytest --cov=src/api --cov-report=html                # 覆盖率

# Docker 开发环境（仅 PG + Redis）
docker-compose -f deployment/docker-compose.dev.yml up -d

# Docker 生产/本机完整栈（PG + Redis + MinIO + API + 前端 + Nginx）
.\deployment\deploy.ps1 up         # Windows (pwsh)
./deployment/deploy.sh up          # Linux/Mac/Git Bash

# 数据迁移（本机 → 容器，幂等）
.\deployment\migrate.ps1 seed -PgSrcPassword '密码'    # 仅种子表（食材/补剂）
.\deployment\migrate.ps1 all -PgSrcPassword '密码'     # 三件套全量迁移
```

**部署踩坑**：见 [deployment/TROUBLESHOOTING.md](./deployment/TROUBLESHOOTING.md)（PowerShell 编码、compose 路径、Alembic 约束名、PG 跨版本、Vite 编译期变量等 12 条案例）。

### 环境变量

复制 `.env.example` -> `.env`：

| 环境变量 | 用途 | 必需 |
|----------|------|------|
| `DASHSCOPE_API_KEY` | 主模型 (阿里云 DashScope) | 是 |
| `TAVILIY_API_KEY` | 搜索 (Tavily) | 是 |
| `DATABASE_URL` | PostgreSQL (asyncpg) | 是 |
| `REDIS_URL` | Redis | 是 |
| `JWT_SECRET_KEY` | JWT 签名 | 是 |
| `DEEPSEEK_API_KEY` | DeepSeek 模型 | 否 |
| `ZAI_API_KEY` | ZAI 模型 | 否 |
| `MOONSHOT_API_KEY` | Moonshot 模型 | 否 |
| `SILICONFLOW_API_KEY` | SiliconFlow 模型 | 否 |

v1 默认模型: `dashscope:qwen3.5-plus` (规划/周计划/报告), `dashscope:qwen-flash` (写入/摘要)

### 依赖说明

主要依赖 (`pyproject.toml`):
- LangGraph 生态: `langgraph`, `langchain`, `langchain-community`, `langchain-tavily` 等
- Web: `fastapi`, `uvicorn`, `python-multipart`
- DB: `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `redis`
- 认证: `python-jose[cryptography]`, `bcrypt`
- AG-UI (已安装，集成开发中): `ag-ui-langgraph>=0.0.25`, `copilotkit>=0.1.78`

---

## 重要约束与注意事项

### 拼写错误（勿改名）
- `structrue_agent/` — 目录名少了个 c，已在多处引用
- `strtuct.py` — 文件名拼写错误，已在多处引用

### 流式模式
- **绝对不要** 在 `astream` 完成后再调用 `ainvoke`，否则图被执行两次
- `emit_progress()` 内部 try-except 静默处理，`ainvoke` 路径不崩溃
- 子图 `get_stream_writer()` custom 事件自动冒泡到顶层

### 月度计划结构
- 分为 **4 周**，每周内饮食统一（便于采购），各周不同（营养均衡）
- 必须包含宏量营养素和微量营养素，含具体数值和单位

### 测试
- pytest + pytest-asyncio，覆盖率要求 `src/api` 和 `src/db` ≥ 80%
- 标记: `@pytest.mark.asyncio`, `@pytest.mark.slow`, `@pytest.mark.integration`, `@pytest.mark.unit`

---

## 变更记录

### 2026-04-23
- 完成本机 Docker 全栈部署（含 MinIO）：`deployment/docker-compose.prod.yml` + `deploy.ps1`/`deploy.sh` + `migrate.ps1`
- PG 从 16 升级到 17，与本机版本对齐（避免 `pg_dump` 跨版本 `SET transaction_timeout` 坑）
- 修复 Dockerfile 的 `--no-deps` 依赖安装 bug；加入 entrypoint 自动跑 alembic 迁移
- 修复 alembic `53f28db7acbd` 迁移对 FK 约束名的硬编码（改用 `inspect` 按字段反查，幂等）
- 修复 Nginx location 优先级问题（`/api/` 加 `^~`，避免被静态资源正则劫持）
- 新增 [deployment/TROUBLESHOOTING.md](./deployment/TROUBLESHOOTING.md) 沉淀 12 条部署案例

### 2025-03-20
- 优化餐食服务中的营养数据处理和餐名显示
- 解决流式响应中的 Pydantic 模型序列化问题

### 2025-03-11
- 实现 Agent V1 三阶段并行架构（research → weeks ∥ → structure ∥）
- 新增 CoordinationGuide 模型（4 周差异化分配）
- 新增 week_agent 独立子图

### 2025-02-18
- 新增流式进度事件系统（`stream_events.py`）
- API 流式输出改造为 `astream(stream_mode=["custom", "updates"])`
- 修复图二次执行 bug

### 2025-02-04
- 添加 FastAPI RESTful API 层（认证、验证码、任务管理）
- 添加 PostgreSQL + Redis 数据库层
- 添加 Docker 部署配置
