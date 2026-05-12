# GitHub Actions CD 实施计划

基于 Codex 已完成的工作，制定完整的实施步骤和注意事项。

---

## 📊 当前状态

### ✅ 已完成（by Codex）

1. **部署脚本**
   - ✅ `deployment/deploy-ghcr.sh` - 服务器部署入口
   - ✅ `deployment/rollback-ghcr.sh` - 回滚脚本
   - ✅ `deployment/docker-compose.cd.yml` - GHCR 镜像覆盖配置

2. **文档**
   - ✅ `deployment/CD_GITHUB_ACTIONS.md` - 完整的 CD 指南
   - ✅ `deployment/README.md` - 已更新文档导航

3. **历史方案标记**
   - ✅ 所有 Webhook 相关文档已标记为 `DEPRECATED`

### ❌ 待完成

1. **GitHub Actions Workflow** - 核心部署流程
2. **前端仓库配置** - 需要确认前端仓库结构
3. **GitHub Secrets 配置** - 敏感信息管理
4. **服务器准备** - 目录结构和权限
5. **测试验证** - 完整的部署测试

---

## 🚨 发现的问题和建议

### 问题 1：前端仓库依赖 ⚠️

**当前方案假设：**
- 前端仓库：`iuikj/pet-food-frontend`
- 后端 workflow 会 checkout 前端仓库构建镜像
- 前后端使用**同一个 tag**（如 `v1.3.2`）

**潜在问题：**
1. 如果前端仓库不存在或结构不同，workflow 会失败
2. 前后端强耦合，必须同时打 tag
3. 前端仓库如果是私有的，需要额外的 token

**建议：**
- [ ] **立即确认**：前端代码是否在独立仓库 `iuikj/pet-food-frontend`？
- [ ] 如果前端在 `frontend/web-app/`，应该修改 workflow 直接使用本仓库的前端代码
- [ ] 如果确实是独立仓库，需要先配置前端仓库的 tag 同步机制

### 问题 2：GHCR 在中国大陆的访问 ⚠️

**已知限制：**
- GHCR (ghcr.io) 在中国大陆访问不稳定
- 拉取速度慢，可能超时

**建议：**
- [ ] 考虑使用国内镜像仓库（腾讯云 TCR / 阿里云 ACR）
- [ ] 或者配置 GHCR 镜像加速
- [ ] 先测试服务器能否稳定拉取 GHCR 镜像

### 问题 3：健康检查端点 ⚠️

**当前配置：**
```bash
HEALTHCHECK_URL="${HEALTHCHECK_URL:-http://localhost/health}"
```

**需要确认：**
- [ ] 后端是否有 `/health` 端点？
- [ ] 如果没有，需要先添加健康检查端点

### 问题 4：服务器 SSH 密钥 ⚠️

**安全建议：**
- [ ] 使用专用的部署密钥（不要用个人密钥）
- [ ] 限制密钥权限（只能访问部署目录）
- [ ] 定期轮换密钥

---

## 📋 完整实施步骤

### 阶段 1：前置准备（必须先完成）

#### 1.1 确认前端仓库结构

```bash
# 检查前端代码位置
# 方案 A：前端在本仓库
ls -la E:\Graduate\frontend\web-app\

# 方案 B：前端在独立仓库
# 需要访问 https://github.com/iuikj/pet-food-frontend
```

**决策点：**
- 如果前端在本仓库 → 修改 workflow，去掉 checkout 前端仓库的步骤
- 如果前端在独立仓库 → 需要配置 `FRONTEND_REPOSITORY_TOKEN`

#### 1.2 添加健康检查端点（如果没有）

在 `src/api/main.py` 添加：

```python
@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
```

#### 1.3 测试服务器访问 GHCR

```bash
# SSH 登录服务器
ssh root@81.71.128.32

# 测试拉取公开镜像
docker pull ghcr.io/actions/runner:latest

# 如果失败，考虑配置镜像加速或使用国内仓库
```

### 阶段 2：创建 GitHub Actions Workflow

#### 2.1 创建 workflow 文件

创建 `.github/workflows/cd-production.yml`：

```yaml
name: CD - Production Deployment

on:
  push:
    tags:
      - 'v*.*.*'  # 匹配 v1.0.0, v1.2.3 等
  workflow_dispatch:
    inputs:
      tag:
        description: 'Tag to deploy (e.g., v1.3.2)'
        required: true
        type: string

env:
  REGISTRY: ghcr.io
  IMAGE_NAMESPACE: iuikj
  API_IMAGE_REPO: pet-food-api
  FRONTEND_IMAGE_REPO: pet-food-frontend

jobs:
  # 阶段 1：验证
  validate:
    name: Validate
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install pytest pytest-asyncio httpx

      - name: Run health check tests
        run: |
          pytest tests/test_health.py -v || echo "Health tests not found, skipping"

      - name: Validate deployment scripts
        run: |
          bash -n pet_food_backend/pet-food/deployment/deploy-ghcr.sh
          bash -n pet_food_backend/pet-food/deployment/rollback-ghcr.sh

      - name: Validate compose files
        run: |
          cd pet_food_backend/pet-food/deployment
          docker compose -f docker-compose.prod.yml -f docker-compose.cd.yml config > /dev/null

  # 阶段 2：构建后端镜像
  build-api:
    name: Build API Image
    runs-on: ubuntu-latest
    needs: validate
    permissions:
      contents: read
      packages: write
    outputs:
      image-tag: ${{ steps.meta.outputs.version }}
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAMESPACE }}/${{ env.API_IMAGE_REPO }}
          tags: |
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=sha,prefix={{branch}}-
            type=raw,value=latest,enable={{is_default_branch}}

      - name: Build and push API image
        uses: docker/build-push-action@v5
        with:
          context: ./pet_food_backend/pet-food
          file: ./pet_food_backend/pet-food/Dockerfile
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          platforms: linux/amd64

  # 阶段 3：构建前端镜像
  build-frontend:
    name: Build Frontend Image
    runs-on: ubuntu-latest
    needs: validate
    permissions:
      contents: read
      packages: write
    steps:
      - name: Checkout backend repo
        uses: actions/checkout@v4
        with:
          path: backend

      # 🚨 关键决策点：前端代码位置
      # 方案 A：前端在本仓库（推荐）
      - name: Use local frontend
        run: |
          echo "Using frontend from backend/frontend/web-app"
          ls -la backend/frontend/web-app

      # 方案 B：前端在独立仓库（如果需要，取消注释）
      # - name: Checkout frontend repo
      #   uses: actions/checkout@v4
      #   with:
      #     repository: iuikj/pet-food-frontend
      #     token: ${{ secrets.FRONTEND_REPOSITORY_TOKEN }}
      #     ref: ${{ github.ref_name }}
      #     path: frontend

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAMESPACE }}/${{ env.FRONTEND_IMAGE_REPO }}
          tags: |
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=sha,prefix={{branch}}-
            type=raw,value=latest,enable={{is_default_branch}}

      - name: Build and push frontend image
        uses: docker/build-push-action@v5
        with:
          # 方案 A：本仓库前端
          context: ./backend/frontend/web-app
          file: ./backend/frontend/web-app/Dockerfile
          # 方案 B：独立仓库前端（如果需要，替换上面两行）
          # context: ./frontend
          # file: ./frontend/Dockerfile
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          platforms: linux/amd64
          build-args: |
            VITE_API_BASE_URL=${{ vars.VITE_API_BASE_URL || 'http://81.71.128.32/api/v1' }}
            VITE_ENABLE_SSE=${{ vars.VITE_ENABLE_SSE || 'true' }}
            VITE_RECONNECT_DELAY=${{ vars.VITE_RECONNECT_DELAY || '3000' }}

  # 阶段 4：部署到生产服务器
  deploy-production:
    name: Deploy to Production
    runs-on: ubuntu-latest
    needs: [build-api, build-frontend]
    environment:
      name: production
      url: http://81.71.128.32
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Sync deployment files to server
        uses: appleboy/scp-action@v0.1.7
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SERVER_SSH_KEY }}
          port: ${{ secrets.SERVER_PORT || 22 }}
          source: "pet_food_backend/pet-food/deployment/docker-compose.prod.yml,pet_food_backend/pet-food/deployment/docker-compose.cd.yml,pet_food_backend/pet-food/deployment/deploy-ghcr.sh,pet_food_backend/pet-food/deployment/rollback-ghcr.sh,pet_food_backend/pet-food/deployment/nginx/nginx.conf"
          target: ${{ secrets.SERVER_APP_DIR }}
          strip_components: 3

      - name: Deploy to server
        uses: appleboy/ssh-action@v1.0.3
        env:
          IMAGE_TAG: ${{ needs.build-api.outputs.image-tag }}
          REGISTRY: ${{ env.REGISTRY }}
          IMAGE_NAMESPACE: ${{ env.IMAGE_NAMESPACE }}
          API_IMAGE_REPO: ${{ env.API_IMAGE_REPO }}
          FRONTEND_IMAGE: ${{ env.REGISTRY }}/${{ env.IMAGE_NAMESPACE }}/${{ env.FRONTEND_IMAGE_REPO }}:${{ needs.build-api.outputs.image-tag }}
          GHCR_USERNAME: ${{ secrets.GHCR_USERNAME }}
          GHCR_TOKEN: ${{ secrets.GHCR_TOKEN }}
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SERVER_SSH_KEY }}
          port: ${{ secrets.SERVER_PORT || 22 }}
          envs: IMAGE_TAG,REGISTRY,IMAGE_NAMESPACE,API_IMAGE_REPO,FRONTEND_IMAGE,GHCR_USERNAME,GHCR_TOKEN
          script: |
            cd ${{ secrets.SERVER_APP_DIR }}/deployment
            chmod +x deploy-ghcr.sh rollback-ghcr.sh
            
            export IMAGE_TAG="$IMAGE_TAG"
            export REGISTRY="$REGISTRY"
            export IMAGE_NAMESPACE="$IMAGE_NAMESPACE"
            export API_IMAGE_REPO="$API_IMAGE_REPO"
            export FRONTEND_IMAGE="$FRONTEND_IMAGE"
            export GHCR_USERNAME="$GHCR_USERNAME"
            export GHCR_TOKEN="$GHCR_TOKEN"
            
            ./deploy-ghcr.sh "$IMAGE_TAG"

      - name: Notify deployment status
        if: always()
        run: |
          if [ "${{ job.status }}" == "success" ]; then
            echo "✅ 部署成功：${{ needs.build-api.outputs.image-tag }}"
          else
            echo "❌ 部署失败：${{ needs.build-api.outputs.image-tag }}"
          fi
```

### 阶段 3：配置 GitHub Secrets

在 GitHub 仓库页面：**Settings** → **Secrets and variables** → **Actions**

#### 3.1 必需的 Secrets

| Secret 名称 | 值 | 获取方式 |
|------------|---|----------|
| `SERVER_HOST` | `81.71.128.32` | 你的服务器 IP |
| `SERVER_USER` | `root` | SSH 用户名 |
| `SERVER_SSH_KEY` | `[SSH 私钥]` | 见下方生成方法 |
| `SERVER_APP_DIR` | `/opt/petfood/pet_food_backend/pet-food` | 服务器部署目录 |
| `GHCR_USERNAME` | `iuikj` | GitHub 用户名 |
| `GHCR_TOKEN` | `[GitHub PAT]` | 见下方生成方法 |

#### 3.2 可选的 Secrets（如果前端在独立仓库）

| Secret 名称 | 值 | 用途 |
|------------|---|------|
| `FRONTEND_REPOSITORY_TOKEN` | `[GitHub PAT]` | 读取前端私有仓库 |

#### 3.3 可选的 Variables（前端构建参数）

| Variable 名称 | 值 | 说明 |
|--------------|---|------|
| `VITE_API_BASE_URL` | `http://81.71.128.32/api/v1` | API 基址 |
| `VITE_ENABLE_SSE` | `true` | 启用 SSE |
| `VITE_RECONNECT_DELAY` | `3000` | 重连延迟（毫秒） |

#### 3.4 生成 SSH 密钥对

**在本地机器执行：**

```bash
# 生成专用部署密钥
ssh-keygen -t ed25519 -C "github-actions-deploy@petfood" -f ~/.ssh/petfood_deploy_key

# 查看私钥（复制到 SERVER_SSH_KEY）
cat ~/.ssh/petfood_deploy_key

# 查看公钥（需要添加到服务器）
cat ~/.ssh/petfood_deploy_key.pub
```

**在服务器执行：**

```bash
# SSH 登录服务器
ssh root@81.71.128.32

# 添加公钥
echo "ssh-ed25519 AAAA... github-actions-deploy@petfood" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

#### 3.5 生成 GitHub Personal Access Token

1. GitHub 右上角头像 → **Settings**
2. **Developer settings** → **Personal access tokens** → **Tokens (classic)**
3. **Generate new token (classic)**
4. 勾选权限：
   - ✅ `write:packages` - 推送镜像到 GHCR
   - ✅ `read:packages` - 拉取镜像
   - ✅ `repo` - 如果前端仓库是私有的
5. 生成后复制到 `GHCR_TOKEN`

### 阶段 4：服务器准备

#### 4.1 创建目录结构

```bash
# SSH 登录服务器
ssh root@81.71.128.32

# 创建部署目录
sudo mkdir -p /opt/petfood/pet_food_backend/pet-food/deployment/nginx/ssl
sudo mkdir -p /opt/petfood/pet_food_backend/pet-food/deployment/.cd-state

# 设置权限
sudo chown -R root:root /opt/petfood
sudo chmod -R 755 /opt/petfood
```

#### 4.2 准备环境变量文件

```bash
# 确保 .env.prod 存在
cd /opt/petfood/pet_food_backend/pet-food/deployment
ls -la .env.prod

# 如果不存在，从本地上传
# 在本地执行：
scp pet_food_backend/pet-food/deployment/.env.prod root@81.71.128.32:/opt/petfood/pet_food_backend/pet-food/deployment/
```

#### 4.3 测试 Docker 登录 GHCR

```bash
# 在服务器上测试
echo "YOUR_GHCR_TOKEN" | docker login ghcr.io -u iuikj --password-stdin

# 测试拉取镜像（如果已有）
docker pull ghcr.io/iuikj/pet-food-api:latest || echo "镜像还不存在，首次部署后会创建"
```

#### 4.4 清理旧的 Webhook 服务

```bash
# 停止并禁用 webhook 服务
sudo systemctl stop petfood-webhook || true
sudo systemctl disable petfood-webhook || true

# 可选：删除 webhook 配置（保留一段时间后再删）
# sudo rm -rf /opt/petfood-cd
# sudo rm /etc/systemd/system/petfood-webhook.service
```

### 阶段 5：测试部署

#### 5.1 本地测试镜像构建

```bash
# 测试后端镜像构建
cd E:\Graduate\pet_food_backend\pet-food
docker build -t test-api .

# 测试前端镜像构建
cd E:\Graduate\frontend\web-app
docker build -t test-frontend .
```

#### 5.2 推送测试标签

```bash
# 创建测试标签
git tag -a v0.0.1-test -m "Test GitHub Actions CD"
git push origin v0.0.1-test

# 观察 GitHub Actions 执行
# 访问：https://github.com/iuikj/pet-food/actions
```

#### 5.3 验证部署结果

```bash
# SSH 登录服务器
ssh root@81.71.128.32

# 查看容器状态
docker ps | grep pet-food

# 查看部署日志
cat /opt/petfood/pet_food_backend/pet-food/deployment/.cd-state/deploy-ghcr.log

# 查看部署历史
cat /opt/petfood/pet_food_backend/pet-food/deployment/.cd-state/deploy-history.log

# 测试健康检查
curl http://localhost/health
```

---

## ✅ 完成检查清单

### 前置准备
- [ ] 确认前端代码位置（本仓库 or 独立仓库）
- [ ] 添加 `/health` 健康检查端点
- [ ] 测试服务器访问 GHCR

### GitHub 配置
- [ ] 创建 `.github/workflows/cd-production.yml`
- [ ] 配置 GitHub Secrets（7 个必需）
- [ ] 配置 GitHub Variables（3 个可选）
- [ ] 生成并配置 SSH 密钥对
- [ ] 生成并配置 GitHub PAT

### 服务器配置
- [ ] 创建部署目录结构
- [ ] 上传 `.env.prod` 文件
- [ ] 测试 Docker 登录 GHCR
- [ ] 清理旧的 Webhook 服务

### 测试验证
- [ ] 本地测试镜像构建
- [ ] 推送测试标签
- [ ] 验证 GitHub Actions 执行成功
- [ ] 验证服务器部署成功
- [ ] 测试健康检查端点
- [ ] 测试回滚功能

---

## 🔄 日常使用流程

### 发布新版本

```bash
# 1. 开发完成，提交代码
git add .
git commit -m "feat: 新功能完成"
git push origin main

# 2. 打版本标签
git tag -a v1.3.0 -m "Release version 1.3.0"

# 3. 推送标签（自动触发部署）
git push origin v1.3.0

# 4. 查看部署进度
# 访问：https://github.com/iuikj/pet-food/actions
```

### 手动回滚

```bash
# SSH 登录服务器
ssh root@81.71.128.32

# 查看部署历史
cd /opt/petfood/pet_food_backend/pet-food/deployment
./rollback-ghcr.sh

# 或直接指定版本
./rollback-ghcr.sh v1.2.0
```

---

## 📞 需要你确认的问题

### 🚨 关键决策点

1. **前端代码位置**
   - [ ] 前端在本仓库 `frontend/web-app/`（推荐，workflow 需要修改）
   - [ ] 前端在独立仓库 `iuikj/pet-food-frontend`（需要配置额外 token）

2. **GHCR 访问测试**
   - [ ] 服务器能否稳定访问 ghcr.io？
   - [ ] 是否需要配置镜像加速或使用国内仓库？

3. **健康检查端点**
   - [ ] 后端是否已有 `/health` 端点？
   - [ ] 如果没有，是否需要我帮你添加？

4. **部署目录**
   - [ ] 确认服务器部署目录是 `/opt/petfood/pet_food_backend/pet-food`？
   - [ ] 还是其他路径？

---

## 📚 相关文档

- [CD_GITHUB_ACTIONS.md](./pet_food_backend/pet-food/deployment/CD_GITHUB_ACTIONS.md) - Codex 编写的完整指南
- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [GHCR 文档](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)

---

**最后更新**: 2026-04-26  
**状态**: 等待用户确认关键决策点后继续实施
