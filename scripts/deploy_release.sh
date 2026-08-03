#!/bin/bash
# Deploys a previously-cut release to an environment. ONE script for three shapes - initial
# deploy to dev, promotion of a dev-validated version to prod, and rollback to any older
# version - all mechanically identical: load a pre-built artifact, redeploy it, verify it. There
# is no separate "rollback script" (Feature 034, REQ-DEPLOY-001).
#
# 🚨 HUMAN-ONLY, HARD CONSTRAINT (CLAUDE.md): <app>, <env>, and <version> below must always come
# directly from a human in that specific request. No AI agent may decide on its own to deploy,
# promote, or roll back, or infer a target version - see REQ-DEPLOY-005. This is IN ADDITION to
# CLAUDE.md's pre-existing "never start an environment without approval" rule - both gates apply
# to every call.
#
# Usage: ./scripts/deploy_release.sh <app> <env> <version> [--artifacts-root <path>] [--verify-timeout <seconds>]
#   <app>     : denidin-app | morning-mcp-app
#   <env>     : dev | prod
#   <version> : exact version already cut via scripts/cut_release.sh
#   --artifacts-root  : optional override of the artifacts folder (test-only seam)
#   --verify-timeout  : optional override of the verification timeout in seconds (default 30,
#                       test-only seam)
#
# See specs/in-progress/034-versioning-release-mgmt/contracts/deploy_release_cli.md for the full
# contract (preconditions, side effects, exit codes, why this never rebuilds from source).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

DEFAULT_ARTIFACTS_ROOT="/Users/yaron/Projects/DeniDin/artifacts"
DEFAULT_VERIFY_TIMEOUT=30
VERIFY_POLL_INTERVAL=2

ARTIFACTS_ROOT="$DEFAULT_ARTIFACTS_ROOT"
VERIFY_TIMEOUT="$DEFAULT_VERIFY_TIMEOUT"

POSITIONAL=()
while [ $# -gt 0 ]; do
    case "$1" in
        --artifacts-root)
            ARTIFACTS_ROOT="$2"
            shift 2
            ;;
        --verify-timeout)
            VERIFY_TIMEOUT="$2"
            shift 2
            ;;
        *)
            POSITIONAL+=("$1")
            shift
            ;;
    esac
done

APP="${POSITIONAL[0]}"
ENV="${POSITIONAL[1]}"
VERSION="${POSITIONAL[2]}"

usage() {
    echo "Usage: $0 <denidin-app|morning-mcp-app> <dev|prod> <version> [--artifacts-root <path>] [--verify-timeout <seconds>]" >&2
}

if [ "$APP" != "denidin-app" ] && [ "$APP" != "morning-mcp-app" ]; then
    echo "Error: <app> must be denidin-app or morning-mcp-app (got: '${APP}')." >&2
    usage
    exit 2
fi

if [ "$ENV" != "dev" ] && [ "$ENV" != "prod" ]; then
    echo "Error: <env> must be dev or prod (got: '${ENV}')." >&2
    usage
    exit 2
fi

if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.]+)?$ ]]; then
    echo "Error: <version> must be MAJOR.MINOR.PATCH with an optional -suffix (got: '${VERSION}')." >&2
    usage
    exit 2
fi

TAR_PATH="${ARTIFACTS_ROOT}/${APP}/${APP}-v${VERSION}.tar"
MANIFEST_PATH="${ARTIFACTS_ROOT}/${APP}/${APP}-v${VERSION}.json"
COMPOSE_FILE="docker/docker-compose.${ENV}.yml"
SERVICE_NAME="${APP}-${ENV}"

# --- Preconditions (fail before any side effect) ---

if [ ! -f "$TAR_PATH" ]; then
    echo "Error: no release found for ${APP} v${VERSION} - checked ${TAR_PATH}." >&2
    exit 1
fi

if [ ! -f "$MANIFEST_PATH" ]; then
    echo "Error: manifest missing for ${APP} v${VERSION} - checked ${MANIFEST_PATH}." >&2
    exit 1
fi

MANIFEST_APP="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['app'])" "$MANIFEST_PATH" 2>/dev/null || echo "")"
MANIFEST_VERSION="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['version'])" "$MANIFEST_PATH" 2>/dev/null || echo "")"

if [ "$MANIFEST_APP" != "$APP" ] || [ "$MANIFEST_VERSION" != "$VERSION" ]; then
    echo "Error: manifest at ${MANIFEST_PATH} doesn't match requested ${APP} v${VERSION} (found: app=${MANIFEST_APP:-<none>}, version=${MANIFEST_VERSION:-<none>})." >&2
    exit 1
fi

if [ ! -f "$COMPOSE_FILE" ]; then
    echo "Error: compose file not found: ${COMPOSE_FILE}." >&2
    exit 1
fi

# Read the project name from the compose file itself - NEVER hardcode "denidin-${ENV}" here.
# A scratch/test compose file uses a deliberately different name specifically so it can never
# collide with a real running dev/prod environment on the same machine (see
# specs/in-progress/034-versioning-release-mgmt/research.md Decision 5's safety-critical detail).
PROJECT_NAME="$(grep -m1 '^name:' "$COMPOSE_FILE" | sed 's/^name:[[:space:]]*//')"
if [ -z "$PROJECT_NAME" ]; then
    echo "Error: could not determine compose project name from ${COMPOSE_FILE}." >&2
    exit 1
fi

# Cross-clone env lock + mandatory per-clone local-override file (CLAUDE.md's "Multi-clone
# lock"/"dev/prod data is also a singleton across clones" sections - the same 2026-07-30
# incident run_denidin.sh guards against). Only applies in a real repo checkout (scratch/test
# fixtures deliberately don't copy env_lock.sh in, since cross-clone locking is meaningless for
# a throwaway git repo) - presence of scripts/env_lock.sh is exactly that signal.
COMPOSE_ARGS=(--project-directory "$REPO_ROOT" -f "$COMPOSE_FILE")
if [ -f "$SCRIPT_DIR/env_lock.sh" ]; then
    # shellcheck source=/dev/null
    source "$SCRIPT_DIR/env_lock.sh"
    env_lock_require_local_override "$ENV"
    LOCAL_OVERRIDE="$REPO_ROOT/docker/docker-compose.${ENV}.local.yml"
    COMPOSE_ARGS+=(-f "$LOCAL_OVERRIDE")
fi

# --- Side effects (in order) ---

# 1. Load the artifact - no rebuild, ever, for any of the 3 shapes (REQ-DEPLOY-001). Capture the
#    ACTUAL loaded image reference from docker load's own output rather than assuming it matches
#    <app>:<version> - a tarball's embedded tag always wins over its filename on disk.
LOAD_OUTPUT="$(docker load -i "$TAR_PATH")"
LOADED_REF="$(echo "$LOAD_OUTPUT" | grep -oE 'Loaded image( ID)?: .*' | sed -E 's/^Loaded image( ID)?: //')"
if [ -z "$LOADED_REF" ]; then
    echo "Error: could not determine the image docker load just produced. Output was:" >&2
    echo "$LOAD_OUTPUT" >&2
    exit 1
fi

# 2. Retag it to whatever docker-compose expects for this service, then recreate the container
#    from it without rebuilding - this is what preserves the environment's existing volume
#    mounts (config/logs/data) instead of a bare `docker run` silently missing them.
COMPOSE_IMAGE="${PROJECT_NAME}-${SERVICE_NAME}:latest"
docker tag "$LOADED_REF" "$COMPOSE_IMAGE"

# Declare intent in the shared active-env file BEFORE starting, same as run_denidin.sh - only
# in a real repo checkout (see the env_lock.sh presence check above).
if [ -f "$SCRIPT_DIR/env_lock.sh" ]; then
    env_lock_acquire "$ENV"
fi

docker compose "${COMPOSE_ARGS[@]}" up -d --no-build "$SERVICE_NAME"

CONTAINER_NAME="${PROJECT_NAME}-${SERVICE_NAME}-1"

# 3. Automatically verify (REQ-DEPLOY-002) - block until confirmed or timeout. A container that
#    merely started, without this passing, is a FAILED deploy, not a success.
echo "Verifying ${APP} v${VERSION} is live in ${ENV}..."
VERIFIED=0
ELAPSED=0
while [ "$ELAPSED" -lt "$VERIFY_TIMEOUT" ]; do
    if [ "$APP" == "morning-mcp-app" ]; then
        HOST_PORT="$(docker compose "${COMPOSE_ARGS[@]}" port "$SERVICE_NAME" 8000 2>/dev/null | cut -d: -f2)"
        HEALTH_JSON=""
        if [ -n "$HOST_PORT" ]; then
            HEALTH_JSON="$(curl -s "http://localhost:${HOST_PORT}/health" 2>/dev/null || echo "")"
        fi
        HEALTH_VERSION="$(echo "$HEALTH_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('version',''))" 2>/dev/null || echo "")"
        if [ "$HEALTH_VERSION" == "$VERSION" ]; then
            VERIFIED=1
            break
        fi
    else
        if docker logs "$CONTAINER_NAME" --tail 20 2>&1 | grep -q "\[v${VERSION}\]"; then
            VERIFIED=1
            break
        fi
    fi
    sleep "$VERIFY_POLL_INTERVAL"
    ELAPSED=$((ELAPSED + VERIFY_POLL_INTERVAL))
done

if [ "$VERIFIED" -ne 1 ]; then
    echo "Error: deploy verification FAILED - ${APP} v${VERSION} not confirmed live in ${ENV} within ${VERIFY_TIMEOUT}s." >&2
    echo "Last observed container state:" >&2
    docker logs "$CONTAINER_NAME" --tail 20 >&2 2>&1 || true
    exit 1
fi

echo "Deployed and verified: ${APP} v${VERSION} is live in ${ENV}."
