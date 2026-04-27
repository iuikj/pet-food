#!/usr/bin/env bash
# 版本同步脚本 - 由 git tag 驱动
#
# 用法：./scripts/sync-version.sh <version> <component>
#   version:   纯版本号，无 v 前缀（例如 1.2.3）
#   component: backend | frontend | android
#
# 后端组件 (backend):
#   - pyproject.toml       version = "X.Y.Z"
#   - src/__version__.py   __version__ = "X.Y.Z"
#
# 前端组件 (frontend):
#   - package.json         "version": "X.Y.Z"
#
# Android 组件 (android):
#   - 通过 Gradle -P 参数注入（无需修改文件）
#   - versionName=X.Y.Z
#   - versionCode=X*10000 + Y*100 + Z

set -euo pipefail

VERSION="${1:?Usage: sync-version.sh <version> <component>}"
COMPONENT="${2:?Usage: sync-version.sh <version> <component>}"

# 去掉可能的 v 前缀
VERSION="${VERSION#v}"

# 校验版本号格式
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "ERROR: Invalid version format: $VERSION (expected X.Y.Z)" >&2
    exit 1
fi

case "$COMPONENT" in
    backend)
        echo "==> Syncing backend to $VERSION"

        # pyproject.toml (src/__version__.py 会自动读取它)
        if [ -f pyproject.toml ]; then
            sed -i.bak -E "s/^version = \"[^\"]+\"/version = \"$VERSION\"/" pyproject.toml
            rm -f pyproject.toml.bak
            echo "  ✓ pyproject.toml"
        fi

        echo "==> Backend synced:"
        grep "^version" pyproject.toml || true
        ;;

    frontend)
        echo "==> Syncing frontend to $VERSION"

        # package.json
        if [ -f package.json ]; then
            # 用 node 来修改 JSON，保留格式
            node -e "
                const fs = require('fs');
                const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));
                pkg.version = '$VERSION';
                fs.writeFileSync('package.json', JSON.stringify(pkg, null, 2) + '\n');
            "
            echo "  ✓ package.json"
        fi

        echo "==> Frontend synced:"
        grep '"version"' package.json | head -1 || true
        ;;

    android)
        # 计算 versionCode：X.Y.Z -> X*10000 + Y*100 + Z
        IFS='.' read -ra V <<< "$VERSION"
        VERSION_CODE=$((V[0] * 10000 + V[1] * 100 + V[2]))
        echo "==> Android version: $VERSION (code: $VERSION_CODE)"
        echo "VERSION_NAME=$VERSION"
        echo "VERSION_CODE=$VERSION_CODE"

        # 输出到 GITHUB_OUTPUT（如果存在）
        if [ -n "${GITHUB_OUTPUT:-}" ]; then
            echo "version_name=$VERSION" >> "$GITHUB_OUTPUT"
            echo "version_code=$VERSION_CODE" >> "$GITHUB_OUTPUT"
        fi
        ;;

    *)
        echo "ERROR: Unknown component: $COMPONENT" >&2
        echo "Valid: backend | frontend | android" >&2
        exit 1
        ;;
esac
