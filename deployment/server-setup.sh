#!/bin/bash
# ============================================================
# Pet Food CD 服务器准备脚本（GitHub Actions 版本）
# 使用方式：在服务器上执行 bash server-setup.sh
# ============================================================

set -e

echo "=========================================="
echo "🚀 Pet Food GitHub Actions CD 服务器准备"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查是否为 root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}❌ 请使用 root 权限运行此脚本${NC}"
    echo "   sudo bash server-setup.sh"
    exit 1
fi

# 配置变量
PROJECT_DIR="/opt/petfood/pet_food_backend/pet-food"
DEPLOYMENT_DIR="$PROJECT_DIR/deployment"
STATE_DIR="$DEPLOYMENT_DIR/.cd-state"

echo -e "${GREEN}✓${NC} 开始准备服务器环境"

# 步骤 1: 创建目录结构
echo ""
echo "步骤 1/5: 创建目录结构"
echo "----------------------------------------"

mkdir -p "$DEPLOYMENT_DIR/nginx/ssl"
mkdir -p "$STATE_DIR"

echo -e "${GREEN}✓${NC} 目录创建完成"

# 步骤 2: 检查环境文件
echo ""
echo "步骤 2/5: 检查环境文件"
echo "----------------------------------------"

if [ -f "$DEPLOYMENT_DIR/.env.prod" ]; then
    echo -e "${GREEN}✓${NC} .env.prod 文件已存在"
else
    echo -e "${YELLOW}⚠${NC} .env.prod 文件不存在"
    echo "   请从本地上传 .env.prod 文件到："
    echo "   $DEPLOYMENT_DIR/.env.prod"
    echo ""
    echo "   在本地执行："
    echo "   scp pet_food_backend/pet-food/deployment/.env.prod root@81.71.128.32:$DEPLOYMENT_DIR/"
fi

# 步骤 3: 清理旧的 webhook 服务
echo ""
echo "步骤 3/5: 清理旧的 Webhook 服务"
echo "----------------------------------------"

if systemctl is-active --quiet petfood-webhook; then
    echo "停止 webhook 服务..."
    systemctl stop petfood-webhook
    echo -e "${GREEN}✓${NC} Webhook 服务已停止"
fi

if systemctl is-enabled --quiet petfood-webhook 2>/dev/null; then
    echo "禁用 webhook 服务..."
    systemctl disable petfood-webhook
    echo -e "${GREEN}✓${NC} Webhook 服务已禁用"
fi

if [ -d "/opt/petfood-cd" ]; then
    echo -e "${YELLOW}⚠${NC} 旧的 webhook 目录仍存在: /opt/petfood-cd"
    echo "   建议保留一段时间后手动删除："
    echo "   sudo rm -rf /opt/petfood-cd"
fi

echo -e "${GREEN}✓${NC} Webhook 清理完成"

# 步骤 4: 配置 GHCR 登录
echo ""
echo "步骤 4/5: 配置 GHCR 登录"
echo "----------------------------------------"

read -p "请输入 GitHub 用户名 (默认: iuikj): " GHCR_USERNAME
GHCR_USERNAME=${GHCR_USERNAME:-iuikj}

read -sp "请输入 GitHub Personal Access Token: " GHCR_TOKEN
echo ""

if [ -z "$GHCR_TOKEN" ]; then
    echo -e "${YELLOW}⚠${NC} 未输入 Token，跳过 GHCR 登录"
else
    echo "正在登录 GHCR..."
    echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USERNAME" --password-stdin > /dev/null 2>&1

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} GHCR 登录成功"

        # 测试拉取镜像
        echo "测试拉取镜像..."
        if docker pull hello-world > /dev/null 2>&1; then
            echo -e "${GREEN}✓${NC} 镜像拉取测试成功"
        else
            echo -e "${YELLOW}⚠${NC} 镜像拉取测试失败，但登录成功"
        fi
    else
        echo -e "${RED}❌ GHCR 登录失败${NC}"
        echo "   请检查用户名和 Token 是否正确"
    fi
fi

# 步骤 5: 验证 Docker 环境
echo ""
echo "步骤 5/5: 验证 Docker 环境"
echo "----------------------------------------"

if command -v docker &> /dev/null; then
    echo -e "${GREEN}✓${NC} Docker 已安装: $(docker --version)"
else
    echo -e "${RED}❌ Docker 未安装${NC}"
    exit 1
fi

if command -v docker compose &> /dev/null; then
    echo -e "${GREEN}✓${NC} Docker Compose 已安装: $(docker compose version)"
else
    echo -e "${RED}❌ Docker Compose 未安装${NC}"
    exit 1
fi

# 检查现有容器
echo ""
echo "当前运行的容器："
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "pet-food|postgres|redis|minio|nginx" || echo "  (无相关容器)"

# 完成
echo ""
echo "=========================================="
echo -e "${GREEN}✅ 服务器准备完成！${NC}"
echo "=========================================="
echo ""
echo "📋 下一步操作："
echo ""
echo "1. 确保 .env.prod 文件已上传到："
echo "   $DEPLOYMENT_DIR/.env.prod"
echo ""
echo "2. 在 GitHub 仓库配置 Secrets："
echo "   https://github.com/iuikj/pet-food/settings/secrets/actions"
echo ""
echo "   必需的 Secrets："
echo "   - SERVER_HOST: 81.71.128.32"
echo "   - SERVER_USER: root"
echo "   - SERVER_SSH_KEY: [SSH 私钥]"
echo "   - SERVER_APP_DIR: $PROJECT_DIR"
echo "   - GHCR_USERNAME: $GHCR_USERNAME"
echo "   - GHCR_TOKEN: [刚才输入的 Token]"
echo "   - FRONTEND_REPOSITORY_TOKEN: [前端仓库访问 Token]"
echo ""
echo "3. 推送测试标签触发部署："
echo "   git tag -a v0.0.1-test -m 'Test CD'"
echo "   git push origin v0.0.1-test"
echo ""
echo "4. 查看部署日志："
echo "   tail -f $STATE_DIR/deploy-ghcr.log"
echo ""
echo "=========================================="
echo ""
