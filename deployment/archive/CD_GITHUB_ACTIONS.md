# GitHub Actions + GHCR CD 指南

当前生产 CD 的推荐方案是：

```text
git tag / GitHub Release
  -> GitHub Actions
  -> checkout backend repo + frontend repo
  -> build backend image
  -> build frontend image
  -> push ghcr.io/<owner>/pet-food-api:<tag>
  -> push ghcr.io/<owner>/pet-food-frontend:<tag>
  -> SSH 到服务器
  -> docker compose pull api/frontend && up -d
  -> /health 健康检查
  -> 失败时自动回滚到上一个成功 tag
```

---

## 1. 方案边界

- 后端仓库：`iuikj/pet-food`
- 前端仓库：`iuikj/pet-food-frontend`
- GitHub Actions 运行在后端仓库内，但会额外 checkout 前端仓库的 `web-app` 目录来构建前端镜像。
- 默认约定：前后端使用**同一个发布 tag**，例如都发布 `v1.3.2`。
- `nginx/postgres/redis/minio` 继续由服务器本地 compose 管理。

如果后续前后端拆成各自独立发版流，再把部署编排抽成单独 workflow 即可。

---

## 2. 仓库内新增文件

- `.github/workflows/cd-production.yml`
- `deployment/docker-compose.cd.yml`
- `deployment/deploy-ghcr.sh`
- `deployment/rollback-ghcr.sh`

其中：

- `docker-compose.prod.yml` 仍保留基础服务定义
- `docker-compose.cd.yml` 只覆盖 `api` 和 `frontend` 的镜像来源
- `deploy-ghcr.sh` 是服务器上的实际部署入口

---

## 3. GitHub Actions 触发方式

当前 workflow 默认在以下情况触发：

- 推送语义化版本 tag，如 `v1.3.2`
- 手动执行 `workflow_dispatch`

推荐发布方式：

```bash
git tag -a v1.3.2 -m "Release v1.3.2"
git push origin v1.3.2
```

---

## 4. GHCR 镜像命名

后端 API 镜像：

```text
ghcr.io/<github_owner>/pet-food-api:<tag>
ghcr.io/<github_owner>/pet-food-api:latest
```

示例：

```text
ghcr.io/iuikj/pet-food-api:v1.3.2
ghcr.io/iuikj/pet-food-api:latest
```

前端镜像：

```text
ghcr.io/<github_owner>/pet-food-frontend:<tag>
ghcr.io/<github_owner>/pet-food-frontend:latest
```

---

## 5. GitHub Secrets

至少配置以下 secrets：

| Secret | 用途 |
|------|------|
| `SERVER_HOST` | 服务器 IP 或域名 |
| `SERVER_PORT` | SSH 端口，默认 `22` |
| `SERVER_USER` | SSH 用户 |
| `SERVER_SSH_KEY` | 部署私钥 |
| `SERVER_APP_DIR` | 服务器部署目录，例如 `/opt/petfood/pet_food_backend/pet-food` |
| `GHCR_USERNAME` | 服务器拉取 GHCR 镜像所用账号 |
| `GHCR_TOKEN` | 服务器拉取 GHCR 镜像所用 PAT |
| `FRONTEND_REPOSITORY_TOKEN` | 读取 `iuikj/pet-food-frontend` 仓库所需的 token（前端仓库为私有时必填） |

可选：

| Variable | 用途 |
|------|------|
| `VITE_API_BASE_URL` | 前端构建时写入的 API 基址 |
| `VITE_ENABLE_SSE` | 前端构建参数 |
| `VITE_RECONNECT_DELAY` | 前端构建参数 |

说明：

- workflow 推送 GHCR 时使用 GitHub 自带的 `GITHUB_TOKEN`
- 服务器拉取镜像时使用 `GHCR_USERNAME` / `GHCR_TOKEN`
- 读取前端私有仓库时，需要单独的 `FRONTEND_REPOSITORY_TOKEN`
- 如果你的 GHCR 包是公开的，服务器通常也能匿名拉取，但生产环境仍建议保留登录

---

## 6. 服务器首次准备

### 6.1 创建目录

```bash
sudo mkdir -p /opt/petfood/pet_food_backend/pet-food/deployment/nginx/ssl
sudo mkdir -p /opt/petfood/pet_food_backend/pet-food/deployment/.cd-state
```

如果你准备使用其他目录，也可以，只要与 `SERVER_APP_DIR` 一致。

### 6.2 放置生产环境文件

服务器目录至少需要保留：

```text
<SERVER_APP_DIR>/
└── deployment/
    ├── .env.prod
    └── nginx/
        ├── nginx.conf
        └── ssl/
```

其中：

- `.env.prod` 需要你手动放到服务器并长期保留
- `docker-compose.prod.yml`、`docker-compose.cd.yml`、`deploy-ghcr.sh`、`rollback-ghcr.sh`、`nginx.conf` 之后会由 GitHub Actions 自动同步

### 6.3 服务器手动登录 GHCR

首次建议在服务器上手动执行一次：

```bash
echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USERNAME" --password-stdin
```

### 6.4 前端仓库发版要求

当前方案会在后端 workflow 中 checkout 前端仓库并构建前端镜像，因此你需要保证：

```text
iuikj/pet-food-frontend
```

中也存在与后端一致的发布 tag，例如：

```bash
# backend repo
git tag -a v1.3.2 -m "Release v1.3.2"
git push origin v1.3.2

# frontend repo
git tag -a v1.3.2 -m "Release v1.3.2"
git push origin v1.3.2
```

更稳的做法是先给前端打 tag，再给后端打同名 tag。

---

## 7. workflow 实际做什么

### 7.1 `validate`

- 安装依赖
- 运行 `pytest tests/test_health.py`
- 检查 `deploy-ghcr.sh` / `rollback-ghcr.sh` 语法
- 检查 compose 合并结果是否可解析

### 7.2 `build-api`

- 构建后端 Docker 镜像
- 推送到 GHCR
- 生成本次发布 tag

### 7.3 `build-frontend`

- checkout `iuikj/pet-food-frontend`
- 以同名 tag 取前端代码
- 构建前端 Docker 镜像
- 推送到 GHCR

### 7.4 `deploy-production`

- 把部署相关文件同步到服务器
- 通过 SSH 执行 `deployment/deploy-ghcr.sh <tag>`
- 服务器拉取新的 API / Frontend 镜像
- 通过 `/health` 做健康检查
- 失败时自动回滚到上一个成功 tag

---

## 8. 服务器部署脚本行为

`deploy-ghcr.sh` 的关键逻辑：

1. 读取目标 tag
2. 组合目标镜像地址
3. 登录 GHCR
4. `docker compose pull api frontend`
5. `docker compose up -d api frontend nginx`
6. 检查 `http://localhost/health`
7. 成功则记录 `last_successful_api_tag`
8. 失败则回滚到上一个成功 tag

状态文件位于：

```text
deployment/.cd-state/
├── deploy-ghcr.log
├── deploy-history.log
└── last_successful_api_tag
```

---

## 9. 手动回滚

服务器上执行：

```bash
cd <SERVER_APP_DIR>
./deployment/rollback-ghcr.sh
```

或者直接指定 tag：

```bash
cd <SERVER_APP_DIR>
./deployment/rollback-ghcr.sh v1.3.1
```

---

## 10. 从 webhook 迁移到 Actions 的收口原则

当前仓库中的 webhook 文档和脚本不会立刻删除，但都视为历史方案：

- 保留内容，方便回溯
- 标记为 `DEPRECATED`
- 文档标题统一使用 `~~划掉~~`
- 不再继续维护 webhook 触发链路

你还需要在服务器和 GitHub 上做这几件事：

```bash
sudo systemctl stop petfood-webhook
sudo systemctl disable petfood-webhook
```

然后：

- 删除 GitHub 仓库里的旧 webhook
- 关闭服务器上为 webhook 开过的 9100 端口
- 保留 `/opt/petfood-cd` 一段时间后再归档

---

## 11. 当前限制

- GHCR 在中国大陆服务器上拉取速度和稳定性一般，只能算“先可用”
- 当前方案依赖前端仓库存在与后端一致的发布 tag
- 如果未来切换到 TCR / ACR，只需要改 workflow secrets 和镜像前缀，不必重写整套 CD

---

## 12. 推荐发布节奏

生产环境建议只在 tag 发布时部署：

```bash
git add .
git commit -m "feat: xxx"
git push origin main

git tag -a v1.3.2 -m "Release v1.3.2"
git push origin v1.3.2
```

这样主分支开发和生产发版是分离的，回滚也更清晰。
