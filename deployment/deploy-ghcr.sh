#!/usr/bin/env bash
# NOTE:
#   This is the active GitHub Actions + GHCR deployment entrypoint.
#   Legacy webhook-based scripts remain in this directory only for history.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.prod.yml"
COMPOSE_CD_FILE="$SCRIPT_DIR/docker-compose.cd.yml"
ENV_FILE="$SCRIPT_DIR/.env.prod"
STATE_DIR="$SCRIPT_DIR/.cd-state"
LOG_FILE="$STATE_DIR/deploy-ghcr.log"
LAST_SUCCESSFUL_TAG_FILE="$STATE_DIR/last_successful_api_tag"
DEPLOY_HISTORY_FILE="$STATE_DIR/deploy-history.log"

IMAGE_TAG="${1:-${IMAGE_TAG:-}}"
REGISTRY="${REGISTRY:-ghcr.io}"
IMAGE_NAMESPACE="${IMAGE_NAMESPACE:-iuikj}"
API_IMAGE_REPO="${API_IMAGE_REPO:-pet-food-api}"
FRONTEND_IMAGE="${FRONTEND_IMAGE:-pet-food-frontend:latest}"
PULL_FRONTEND_IMAGE="${PULL_FRONTEND_IMAGE:-true}"
GHCR_USERNAME="${GHCR_USERNAME:-}"
GHCR_TOKEN="${GHCR_TOKEN:-}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-http://localhost/health}"
HEALTHCHECK_RETRIES="${HEALTHCHECK_RETRIES:-30}"
HEALTHCHECK_INTERVAL="${HEALTHCHECK_INTERVAL:-2}"
USE_MIRROR="${USE_MIRROR:-true}"
MIRROR_REGISTRY="${MIRROR_REGISTRY:-ghcr.1ms.run}"

mkdir -p "$STATE_DIR"

# 定义 log 函数（必须在使用前定义）
log() {
    local message="$1"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $message" | tee -a "$LOG_FILE"
}

if [ -z "$IMAGE_TAG" ]; then
    echo "Usage: $0 <image-tag>" >&2
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    echo "Missing environment file: $ENV_FILE" >&2
    exit 1
fi

if [ ! -f "$COMPOSE_CD_FILE" ]; then
    echo "Missing compose override: $COMPOSE_CD_FILE" >&2
    exit 1
fi

API_IMAGE="${REGISTRY}/${IMAGE_NAMESPACE,,}/${API_IMAGE_REPO}:${IMAGE_TAG}"

# 如果启用镜像加速，使用镜像地址拉取
if [ "$USE_MIRROR" = "true" ]; then
    API_IMAGE_PULL="${MIRROR_REGISTRY}/${IMAGE_NAMESPACE,,}/${API_IMAGE_REPO}:${IMAGE_TAG}"
    log "Using mirror registry: $MIRROR_REGISTRY"
else
    API_IMAGE_PULL="$API_IMAGE"
fi

compose() {
    docker compose \
        --project-directory "$PROJECT_DIR" \
        -f "$COMPOSE_FILE" \
        -f "$COMPOSE_CD_FILE" \
        --env-file "$ENV_FILE" \
        "$@"
}

healthcheck() {
    local attempt=0
    while [ "$attempt" -lt "$HEALTHCHECK_RETRIES" ]; do
        if curl -fsS "$HEALTHCHECK_URL" > /dev/null 2>&1; then
            return 0
        fi
        attempt=$((attempt + 1))
        log "Waiting for health endpoint... ($attempt/$HEALTHCHECK_RETRIES)"
        sleep "$HEALTHCHECK_INTERVAL"
    done
    return 1
}

deploy_stack() {
    export API_IMAGE
    export FRONTEND_IMAGE

    compose config > /dev/null

    # 使用镜像地址拉取 API 镜像
    if [ "$USE_MIRROR" = "true" ]; then
        log "Pulling API image from mirror: $API_IMAGE_PULL"
        docker pull "$API_IMAGE_PULL"
        # 重新标记为原始镜像名
        docker tag "$API_IMAGE_PULL" "$API_IMAGE"
    else
        compose pull api
    fi

    if [ "$PULL_FRONTEND_IMAGE" = "true" ]; then
        # 前端镜像也使用镜像加速
        if [ "$USE_MIRROR" = "true" ]; then
            FRONTEND_IMAGE_MIRROR="${FRONTEND_IMAGE/ghcr.io/$MIRROR_REGISTRY}"
            log "Pulling frontend image from mirror: $FRONTEND_IMAGE_MIRROR"
            docker pull "$FRONTEND_IMAGE_MIRROR"
            docker tag "$FRONTEND_IMAGE_MIRROR" "$FRONTEND_IMAGE"
        else
            compose pull frontend
        fi
    fi

    compose up -d api frontend nginx
}

rollback_to() {
    local rollback_tag="$1"
    API_IMAGE="${REGISTRY}/${IMAGE_NAMESPACE,,}/${API_IMAGE_REPO}:${rollback_tag}"
    log "Rolling back API to $API_IMAGE"
    deploy_stack
}

if [ -n "$GHCR_USERNAME" ] && [ -n "$GHCR_TOKEN" ]; then
    log "Logging into $REGISTRY"
    printf '%s' "$GHCR_TOKEN" | docker login "$REGISTRY" -u "$GHCR_USERNAME" --password-stdin > /dev/null
else
    log "GHCR credentials not provided; assuming docker is already authenticated"
fi

PREVIOUS_TAG=""
if [ -f "$LAST_SUCCESSFUL_TAG_FILE" ]; then
    PREVIOUS_TAG="$(cat "$LAST_SUCCESSFUL_TAG_FILE")"
fi

log "=========================================="
log "Deploying API image $API_IMAGE"
log "=========================================="

if deploy_stack && healthcheck; then
    printf '%s' "$IMAGE_TAG" > "$LAST_SUCCESSFUL_TAG_FILE"
    printf '[%s] success %s -> %s%s' \
        "$(date '+%Y-%m-%d %H:%M:%S')" \
        "${PREVIOUS_TAG:-none}" \
        "$IMAGE_TAG" \
        $'\n' >> "$DEPLOY_HISTORY_FILE"
    log "Deployment succeeded"
    exit 0
fi

log "Deployment failed for tag $IMAGE_TAG"

if [ -n "$PREVIOUS_TAG" ] && [ "$PREVIOUS_TAG" != "$IMAGE_TAG" ]; then
    log "Attempting automatic rollback to $PREVIOUS_TAG"
    rollback_to "$PREVIOUS_TAG"
    if healthcheck; then
        printf '[%s] rollback %s -> %s%s' \
            "$(date '+%Y-%m-%d %H:%M:%S')" \
            "$IMAGE_TAG" \
            "$PREVIOUS_TAG" \
            $'\n' >> "$DEPLOY_HISTORY_FILE"
        log "Rollback succeeded"
    else
        log "Rollback failed; manual intervention required"
    fi
else
    log "No previous successful tag recorded; skipping rollback"
fi

exit 1
