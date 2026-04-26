#!/usr/bin/env bash
# Active rollback helper for the GitHub Actions + GHCR deployment path.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE_DIR="$SCRIPT_DIR/.cd-state"
LAST_SUCCESSFUL_TAG_FILE="$STATE_DIR/last_successful_api_tag"
DEPLOY_HISTORY_FILE="$STATE_DIR/deploy-history.log"

TARGET_TAG="${1:-}"

if [ -z "$TARGET_TAG" ]; then
    echo "Recent deployment history:"
    if [ -f "$DEPLOY_HISTORY_FILE" ]; then
        tail -n 10 "$DEPLOY_HISTORY_FILE"
    else
        echo "  (no history recorded yet)"
    fi

    if [ -f "$LAST_SUCCESSFUL_TAG_FILE" ]; then
        echo
        echo "Last successful API tag: $(cat "$LAST_SUCCESSFUL_TAG_FILE")"
    fi

    echo
    read -r -p "Enter the API tag to deploy again (for example v1.3.2): " TARGET_TAG
fi

if [ -z "$TARGET_TAG" ]; then
    echo "No target tag provided" >&2
    exit 1
fi

"$SCRIPT_DIR/deploy-ghcr.sh" "$TARGET_TAG"
