# 宠物饮食计划智能助手 - 文档中心

> 宠物饮食计划智能助手 API 文档中心

---

## 快速导航

| 角色 | 查看文档 |
|------|----------|
| **前端开发** | [前端对接指南](./frontend/README.md) |
| **后端开发** | [后端开发文档](./backend/README.md) |
| **系统部署** | [部署指南](./deployment/README.md) |
| **架构设计** | [系统架构](./architecture/README.md) |

---

## 文档目录

### 📖 核心文档

| 文档 | 说明 |
|------|------|
| [前端对接指南](./frontend/README.md) | 前端快速对接 API，包含 TypeScript 类型、SSE 流式、断线重连等 |
| [后端开发文档](./backend/README.md) | 后端 API 开发、数据库结构、环境配置 |
| [部署指南](./deployment/README.md) | Docker 部署、生产环境配置、Nginx 配置 |
| [系统架构](./architecture/README.md) | 系统整体架构、多智能体设计、数据流转 |

### 📋 API 参考

| 文档 | 说明 |
|------|------|
| [错误码说明](./reference/ERROR_CODES.md) | 所有 API 错误码及处理建议 |
| [SSE 事件说明](./reference/SSE_EVENTS.md) | Server-Sent Events 事件类型及格式 |
| [混合架构设计](./reference/HYBRID_ARCHITECTURE.md) | SSE + 数据库混合架构，断线重连机制 |

---

## 项目概述

宠物饮食计划智能助手是一个基于 **LangGraph 多智能体** 的系统，为宠物（猫、狗等）生成定制化的月度营养饮食计划。

### 核心功能

- 🔐 **JWT 认证** - Access Token + Refresh Token 双 Token 机制
- 📧 **邮箱验证** - 注册/找回密码使用邮箱验证码
- 🤖 **多智能体** - 主智能体 + 子智能体 + 写入智能体 + 结构化智能体
- 📡 **SSE 流式** - 实时推送 Agent 执行过程
- 🔄 **断线重连** - 混合架构支持连接断开后恢复
- 📊 **任务管理** - 任务状态跟踪、进度查询、历史记录

### 技术栈

```
后端: FastAPI + SQLAlchemy + PostgreSQL + Redis
Agent: LangGraph + DashScope/DeepSeek/ZAI
前端: 任意框架 (React/Vue/其他)
```

---

## 快速开始

### 前端开发者

```bash
# 1. 克隆文档或直接查看在线文档
git clone https://github.com/your-org/pet-food.git

# 2. 查看前端对接指南
cat docs/frontend/README.md

# 3. 启动本地 API（如果需要）
docker-compose -f deployment/docker-compose.dev.yml up -d
```

### 后端开发者

```bash
# 1. 克隆项目
git clone https://github.com/your-org/pet-food.git
cd pet-food

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件

# 3. 启动开发环境
uv pip install -e .
uvicorn src.api.main:app --reload
```

---

## 获取帮助

| 问题 | 解决方案 |
|------|----------|
| API 接口问题 | 查看 [前端对接指南](./frontend/README.md) |
| 错误码含义 | 查看 [错误码说明](./reference/ERROR_CODES.md) |
| 部署问题 | 查看 [部署指南](./deployment/README.md) |
| 架构理解 | 查看 [系统架构](./architecture/README.md) |

---

## 版本信息

- **文档版本**: v2.0.0
- **最后更新**: 2025-02-05
- **API 版本**: v1.0
