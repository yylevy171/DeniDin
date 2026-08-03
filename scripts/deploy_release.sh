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
# Usage: ./scripts/deploy_release.sh <app> <env> <version> [--artifacts-root <path>] [--verify-timeout <seconds>] [--remote-host <ssh-alias>] [--remote-deploy-dir <name>] [--local]
#   <app>     : denidin-app | morning-mcp-app
#   <env>     : dev | prod
#   <version> : exact version already cut via scripts/cut_release.sh
#   --artifacts-root    : optional override of the artifacts folder (test-only seam)
#   --verify-timeout    : optional override of the verification timeout in seconds (default 30,
#                         test-only seam)
#   --remote-host       : SSH host alias for a remote `prod` target (Feature 035's Windows box).
#                         Default: denidin-winprod. Ignored for `dev`.
#   --remote-deploy-dir : deploy directory name on that box, relative to its own home. Default:
#                         denidin-prod. Ignored for `dev`.
#   --local             : force the old local-Docker path even for `env=prod` (test-only seam -
#                         real `prod` calls should never pass this; see below for why).
#
# 2026-08-03 (Feature 035 reconciliation): `prod` for both apps now runs EXCLUSIVELY on a
# dedicated Windows/WSL2 box, reached over SSH/Tailscale - never as a local host process on
# whichever Mac clone happens to invoke this script (see CLAUDE.md's "Environments (dev/prod)").
# So unless `--local` is passed, `env=prod` ships the SAME artifact `cut_release.sh` already
# built (no rebuild - REQ-DEPLOY-001 still holds) to that box over SSH and runs `docker load`/
# `docker compose up -d` THERE, not against a Mac-side remote Docker context: the box's own
# `docker-compose.prod.local.yml` (a hand-created, sshfs-compatible data-volume override that
# only exists on the box, see specs/035-windows-always-on-prod/) must be the one actually used
# to resolve bind-mount paths - reusing this repo checkout's own docker-compose.prod.local.yml
# (which doesn't even exist on most clones, since prod never ran locally on them) against a
# remote context would resolve relative paths against the WRONG filesystem. `dev` is unaffected -
# still a plain local deploy, exactly as before.
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
DEFAULT_REMOTE_HOST="denidin-winprod"
DEFAULT_REMOTE_DEPLOY_DIR="denidin-prod"

ARTIFACTS_ROOT="$DEFAULT_ARTIFACTS_ROOT"
VERIFY_TIMEOUT="$DEFAULT_VERIFY_TIMEOUT"
REMOTE_HOST="$DEFAULT_REMOTE_HOST"
REMOTE_DEPLOY_DIR="$DEFAULT_REMOTE_DEPLOY_DIR"
FORCE_LOCAL=0

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
        --remote-host)
            REMOTE_HOST="$2"
            shift 2
            ;;
        --remote-deploy-dir)
            REMOTE_DEPLOY_DIR="$2"
            shift 2
            ;;
        --local)
            FORCE_LOCAL=1
            shift
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

# --- Remote path: env=prod ships to Feature 035's Windows box over SSH, unless --local forces
#     the old same-machine behavior (test-only seam - see the big comment at the top of this
#     file for why prod can't just reuse this repo checkout's local compose files). ---
REMOTE=0
if [ "$ENV" == "prod" ] && [ "$FORCE_LOCAL" -ne 1 ]; then
    REMOTE=1
fi

if [ "$REMOTE" -eq 1 ]; then
    WSL_SSH_HELPER="$REPO_ROOT/scripts/windows_prod/_wsl_ssh.sh"
    if [ ! -f "$WSL_SSH_HELPER" ]; then
        echo "Error: ${WSL_SSH_HELPER} not found - remote prod deploy needs Feature 035's SSH helper (pass --local to force a same-machine deploy instead)." >&2
        exit 1
    fi
    # shellcheck source=/dev/null
    source "$WSL_SSH_HELPER"
    remote_run() { wsl_ssh_run "$REMOTE_HOST" "$@"; }

    ARTIFACT_NAME="$(basename "$TAR_PATH")"

    echo "== Shipping ${ARTIFACT_NAME} to ${REMOTE_HOST}:~/${REMOTE_DEPLOY_DIR} (prod runs exclusively on the Windows box - Feature 035) =="
    if ! scp -o BatchMode=yes -o ConnectTimeout=10 "$TAR_PATH" "${REMOTE_HOST}:~/${ARTIFACT_NAME}"; then
        echo "Error: scp of release artifact to ${REMOTE_HOST} failed." >&2
        exit 1
    fi

    # 1. Load the artifact on the box - no rebuild, ever, same guarantee as the local path
    #    (REQ-DEPLOY-001). Windows' own SFTP "~" is the Windows-side home, a DIFFERENT directory
    #    than WSL bash's "~" - resolved dynamically via wslpath, same as
    #    scripts/windows_prod/deploy_and_verify.sh (verified against the real box, 2026-08-03).
    LOAD_OUTPUT="$(remote_run "WIN_HOME=\$(wslpath -u \"\$(cmd.exe /c echo %USERPROFILE% | tr -d '\\r')\") && docker load -i \"\$WIN_HOME/${ARTIFACT_NAME}\" && rm \"\$WIN_HOME/${ARTIFACT_NAME}\"")"
    LOADED_REF="$(echo "$LOAD_OUTPUT" | grep -oE 'Loaded image( ID)?: .*' | sed -E 's/^Loaded image( ID)?: //')"
    if [ -z "$LOADED_REF" ]; then
        echo "Error: could not determine the image docker load produced on ${REMOTE_HOST}. Output was:" >&2
        echo "$LOAD_OUTPUT" >&2
        exit 1
    fi

    # 2. Retag + recreate, same as the local path, but executed ON the box - never via a
    #    Mac-side remote Docker context against this checkout's local YAML (see top-of-file
    #    comment: the box's own docker-compose.prod.local.yml is the one that must apply).
    COMPOSE_IMAGE="${PROJECT_NAME}-${SERVICE_NAME}:latest"
    if ! remote_run "docker tag ${LOADED_REF} ${COMPOSE_IMAGE}"; then
        echo "Error: docker tag failed on ${REMOTE_HOST}." >&2
        exit 1
    fi

    REMOTE_COMPOSE="cd ~/${REMOTE_DEPLOY_DIR} && docker compose --project-directory . -f docker/docker-compose.prod.yml -f docker/docker-compose.prod.local.yml"
    if ! remote_run "${REMOTE_COMPOSE} up -d --no-build ${SERVICE_NAME}"; then
        echo "Error: docker compose up -d failed on ${REMOTE_HOST}." >&2
        exit 1
    fi

    CONTAINER_NAME="${PROJECT_NAME}-${SERVICE_NAME}-1"

    # 3. Automatically verify (REQ-DEPLOY-002) - same rule as local: a started-but-unverified
    #    container is not a success. Checked over the same kind of SSH round-trip
    #    verify_windows_prod.sh already uses for these exact checks.
    echo "Verifying ${APP} v${VERSION} is live in ${ENV} on ${REMOTE_HOST}..."
    VERIFIED=0
    ELAPSED=0
    while [ "$ELAPSED" -lt "$VERIFY_TIMEOUT" ]; do
        if [ "$APP" == "morning-mcp-app" ]; then
            HEALTH_JSON="$(remote_run "cd ~/${REMOTE_DEPLOY_DIR} && PORT=\$(docker compose -f docker/docker-compose.prod.yml port ${SERVICE_NAME} 8000 | cut -d: -f2) && curl -sf http://127.0.0.1:\$PORT/health" 2>/dev/null || echo "")"
            HEALTH_VERSION="$(echo "$HEALTH_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('version',''))" 2>/dev/null || echo "")"
            if [ "$HEALTH_VERSION" == "$VERSION" ]; then
                VERIFIED=1
                break
            fi
        else
            if remote_run "docker logs ${CONTAINER_NAME} --tail 20" 2>&1 | grep -q "\[v${VERSION}\]"; then
                VERIFIED=1
                break
            fi
        fi
        sleep "$VERIFY_POLL_INTERVAL"
        ELAPSED=$((ELAPSED + VERIFY_POLL_INTERVAL))
    done

    if [ "$VERIFIED" -ne 1 ]; then
        echo "Error: deploy verification FAILED - ${APP} v${VERSION} not confirmed live in ${ENV} on ${REMOTE_HOST} within ${VERIFY_TIMEOUT}s." >&2
        echo "Last observed container state:" >&2
        remote_run "docker logs ${CONTAINER_NAME} --tail 20" >&2 2>&1 || true
        exit 1
    fi

    echo "Deployed and verified: ${APP} v${VERSION} is live in ${ENV} (${REMOTE_HOST})."
    exit 0
fi

# --- Local path (env=dev always; env=prod only with --local) ---

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
