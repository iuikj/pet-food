#!/bin/bash
# DEPRECATED: legacy cron-based deployment script kept only for history.
set -e

# ============================================================
# Pet Food 定时拉取部署脚本 (Cron 触发)
# ============================================================

PROJECT_DIR="/opt/petfood"
LOG_FILE="/var/log/petfood-deploy.log"
LOCK_FILE="/tmp/petfood-deploy.lock"

# 防止并发执行
if [ -f "$LOCK_FILE" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 部署正在进行中，跳过" >> "$LOG_FILE"
    exit 0
fi

touch "$LOCK_FILE"
trap "rm -f $LOCK_FILE" EXIT

cd "$PROJECT_DIR" || exit 1

# 检查是否有更新
git fetch origin > /dev/null 2>&1
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 无更新，跳过部署" >> "$LOG_FILE"
    exit 0
fi

# 有更新，执行部署
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 检测到更新 ($LOCAL -> $REMOTE)，开始部署..." >> "$LOG_FILE"
/opt/petfood-cd/deploy-webhook.sh >> "$LOG_FILE" 2>&1

exit_code=$?
if [ $exit_code -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 部署成功" >> "$LOG_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 部署失败，退出码: $exit_code" >> "$LOG_FILE"
fi

exit $exit_code
