# 宠物饮食计划智能助手 API

> 基于 LangGraph 多智能体架构的宠物饮食计划生成服务，提供 RESTful API 和流式输出支持。

[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

---

## ✨ 功能特性

### 核心功能
- 🐾 **多智能体协作**: 基于 LangGraph 的 4 智能体架构（主智能体、子智能体、写入智能体、结构化智能体）
- 📊 **异步任务处理**: 支持长时间运行的饮食计划生成任务
- 📡 **流式输出**: SSE 实时推送智能体执行过程
- 🔐 **JWT 认证**: 完整的用户注册、登录、Token 刷新机制
- 📈 **任务管理**: 任务状态跟踪、进度查询、取消任务
- 📝 **数据持久化**: PostgreSQL + Redis 双存储
- 🛡️ **安全防护**: 速率限制、CORS、GZip 压缩

### API 功能
- ✅ 用户注册和登录
- ✅ 创建饮食计划（同步/流式）
- ✅ 查询饮食计划历史
- ✅ 获取计划详情
- ✅ 查询任务状态
- ✅ 任务列表（分页、筛选）
- ✅ 取消任务
- ✅ 健康检查

### 文档和测试
- ✅ Swagger UI 自动文档
- ✅ ReDoc 备选文档
- ✅ 完整的单元测试
- ✅ 认证流程文档
- ✅ 部署文档

---

## 🚀 快速开始

### 环境要求

- Python 3.12+
- PostgreSQL 14+
- Redis 7+
- Docker & Docker Compose（可选）

### 安装依赖

```bash
# 使用 uv 安装依赖（推荐）
uv pip install -e .

# 或使用 pip
pip install -e .
```

### 环境变量配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件，配置以下内容：
# - LLM API 密钥
# - JWT 密钥
# - 数据库连接字符串
# - Redis 连接字符串
```

### 启动开发环境

```bash
# 启动 PostgreSQL 和 Redis
docker-compose -f deployment/docker-compose.dev.yml up -d

# 运行数据库迁移
alembic upgrade head

# 启动 FastAPI 服务
python main.py

# 访问 API 文档
# http://localhost:8000/docs
```

---

## 📁 项目结构

```
pet-food/
├── src/                          # 源代码
│   ├── agent/                  # LangGraph 多智能体系统
│   │   ├── graph.py           # 主图构建
│   │   ├── state.py           # 状态定义
│   │   ├── node.py            # 节点实现
│   │   ├── tools.py           # 工具定义
│   │   ├── prompts/           # 提示词
│   │   ├── sub_agent/         # 子智能体
│   │   ├── write_agent/       # 写入智能体
│   │   └── structrue_agent/  # 结构化智能体
│   ├── api/                    # FastAPI 应用层
│   │   ├── main.py            # FastAPI 主应用
│   │   ├── config.py          # 应用配置
│   │   ├── dependencies.py     # 依赖注入
│   │   ├── middleware/        # 中间件
│   │   │   ├── auth.py       # 认证中间件
│   │   │   ├── logging.py    # 日志中间件
│   │   │   ├── rate_limit.py # 速率限制
│   │   │   └── exceptions.py # 异常处理
│   │   ├── routes/            # API 路由
│   │   │   ├── auth.py       # 认证路由
│   │   │   ├── plans.py      # 饮食计划路由
│   │   │   └── tasks.py      # 任务管理路由
│   │   ├── services/          # 业务服务
│   │   │   ├── auth_service.py  # 认证服务
│   │   │   ├── task_service.py # 任务服务
│   │   │   └── plan_service.py # 计划服务
│   │   ├── models/            # Pydantic 模型
│   │   │   ├── request.py    # 请求模型
│   │   │   └── response.py   # 响应模型
│   │   └── utils/            # 工具函数
│   │       ├── security.py     # 安全工具
│   │       └── stream.py      # 流式输出
│   ├── db/                     # 数据库层
│   │   ├── models.py          # 数据库模型
│   │   └── session.py         # 会话管理
│   └── rag/                    # RAG 模块
├── tests/                     # 测试
│   ├── conftest.py           # 测试配置
│   ├── test_auth.py          # 认证测试
│   └── test_health.py        # 健康检查测试
├── docs/                      # 文档
│   ├── API_CONFIG.md         # API 配置说明
│   ├── AUTH_FLOW.md          # 认证流程
│   └── DEPLOYMENT.md         # 部署文档
├── deployment/                # 部署配置
│   ├── docker-compose.dev.yml # 开发环境编排
│   ├── docker-compose.prod.yml# 生产环境编排
│   ├── nginx/
│   │   └── nginx.conf        # Nginx 配置
│   └── Dockerfile            # 生产环境镜像
├── alembic/                   # 数据库迁移
│   ├── env.py              # Alembic 环境
│   ├── script.py.mako      # 迁移脚本模板
│   └── versions/           # 迁移版本
├── .env.example               # 环境变量模板
├── pyproject.toml             # 项目依赖
├── main.py                    # 项目入口
├── langgraph.json             # LangGraph 配置
└── README.md                 # 本文件
```

---

## 🔌 API 文档

### 基础信息

| 项目 | 值 |
|------|-----|
| Base URL | `http://localhost:8000/api/v1` |
| API 文档 | `http://localhost:8000/docs` |
| ReDoc 文档 | `http://localhost:8000/redoc` |
| OpenAPI Schema | `http://localhost:8000/openapi.json` |

### 认证流程

完整的认证流程说明请参考 [AUTH_FLOW.md](docs/AUTH_FLOW.md)。

### 部署指南

生产环境部署指南请参考 [DEPLOYMENT.md](docs/DEPLOYMENT.md)。

---

## 🧪 测试

### 运行测试

```bash
# 运行所有测试
pytest

# 运行测试并显示输出
pytest -v

# 运行测试并生成覆盖率报告
pytest --cov=src/api --cov-report=html

# 运行特定测试文件
pytest tests/test_auth.py
```

---

## 📦 Docker 部署

### 开发环境

```bash
docker-compose -f deployment/docker-compose.dev.yml up -d
```

### 生产环境

```bash
# 配置环境变量
cp .env.example .env.production
# 编辑 .env.production（生产环境配置）

# 构建并启动
docker-compose -f deployment/docker-compose.prod.yml up -d --build
```

---

## 🔐 安全

- ✅ 密码使用 bcrypt 哈希
- ✅ JWT Token 认证
- ✅ 速率限制（防 DDoS）
- ✅ CORS 配置
- ✅ GZip 压缩
- ✅ SQL 注入防护（使用 SQLAlchemy ORM）
- ✅ XSS 防护

---

## 📝 更新日志

### Version 1.0.0 (2025-01-29)

#### 新增
- ✅ 完整的 FastAPI RESTful API
- ✅ JWT 认证系统
- ✅ 多智能体 LangGraph 集成
- ✅ SSE 流式输出支持
- ✅ 任务管理系统
- ✅ PostgreSQL + Redis 双存储
- ✅ 单元测试和集成测试
- ✅ Docker 化部署

#### 技术栈
- Python 3.12+
- FastAPI 0.115+
- LangGraph 0.6.6+
- PostgreSQL 16+
- Redis 7+
- Docker & Docker Compose

---

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

---

## 👥 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📧 联系方式

- 项目地址: [https://github.com/your-org/pet-food](https://github.com/your-org/pet-food)
- 问题反馈: [Issues](https://github.com/your-org/pet-food/issues)
