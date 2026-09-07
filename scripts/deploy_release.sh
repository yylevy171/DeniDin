#!/bin/bash
# Deploys BOTH apps (denidin-app + morning-mcp-app) at ONE shared version to an environment, in a
# SINGLE stop/start cycle (2026-09-07, bugfix-043 follow-up).
#
# Why this exists: scripts/deploy_release_single.sh deploys one app per call, but each call does
# a FULL stop_env.sh/run_env.sh cycle for the WHOLE environment (both apps together - see the
# "no per-app games" rationale further down). Calling it twice to deploy both apps therefore costs
# TWO full environment stop/start cycles - each app gets bounced once for no reason on the OTHER
# app's call. This script instead does ONE stop, loads+retags BOTH apps' images, then ONE start -
# each app genuinely restarts exactly once.
#
# Both apps share ONE version string here - a deliberate, human-confirmed decision (2026-09-07):
# the two apps DO version independently in general (see CLAUDE.md's "Versioning & Release
# Management"), but this script is for the common case where both were just cut together at the
# same version (as this bugfix's own b43v4 was). For genuinely independent per-app versions, use
# scripts/deploy_release_single.sh for each app instead (accepting its own double-cycle cost, or
# whatever the situation calls for).
#
# 🚨 HUMAN-ONLY, HARD CONSTRAINT (CLAUDE.md): <env> and <version> below must always come directly
# from a human in that specific request. No AI agent may decide on its own to deploy, promote, or
# roll back, or infer a target version - see REQ-DEPLOY-005. This is IN ADDITION to CLAUDE.md's
# pre-existing "never start an environment without approval" rule - both gates apply to every call.
#
# Deploy order is fixed: morning-mcp-app FIRST, denidin-app SECOND (matches scripts/run_all.sh's
# own start order - denidin-app depends on morning-mcp-app, never the other way around). Both
# apps' images are loaded+retagged in that order BEFORE the single start, so whichever order
# run_env.sh's bootstrap actually starts them in, both freshly-tagged images are already in place.
#
# Simplification vs. deploy_release_single.sh (deliberate, see below): every version this script
# deploys MUST have the bugfix-043 ops-scripts bundle for BOTH apps (cut_release.sh has produced
# one for every cut since 2026-09-06) - there is no pre-bugfix-043 legacy fallback path here. A
# version predating the bundle must be deployed via deploy_release_single.sh instead.
#
# Usage: ./scripts/deploy_release.sh <env> <version> [--artifacts-root <path>] [--verify-timeout <seconds>] [--remote-host <ssh-alias>] [--remote-deploy-dir <name>] [--local]
#   <env>     : dev | prod
#   <version> : exact version already cut, for BOTH apps, via scripts/cut_release.sh
#   --artifacts-root    : optional override of the artifacts folder (test-only seam)
#   --verify-timeout    : optional override of the verification timeout in seconds (default 30,
#                         test-only seam)
#   --remote-host       : SSH host alias for a remote `prod` target (Feature 035's Windows box).
#                         Default: denidin-winprod. Ignored for `dev`.
#   --remote-deploy-dir : deploy directory name on that box, relative to its own home. Default:
#                         denidin-prod. Ignored for `dev`.
#   --local             : force the old local-Docker path even for `env=prod` (test-only seam -
#                         real `prod` calls should never pass this; see
#                         scripts/deploy_release_single.sh's own header for why).
#
# See scripts/deploy_release_single.sh's own header comment for the full remote/local path
# rationale (Feature 035 Windows box over SSH, WIN_HOME resolution, the ops-scripts bundle, why
# stop_env.sh/run_env.sh - not raw `docker compose up/stop` - are the only sanctioned entry
# points) - all of that applies identically here, just looped over both apps between one
# stop_env.sh and one run_env.sh instead of wrapping each app's own call.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

# Fixed deploy order - morning-mcp-app must be up before denidin-app (see header comment).
APPS=(morning-mcp-app denidin-app)

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

ENV="${POSITIONAL[0]}"
VERSION="${POSITIONAL[1]}"

usage() {
    echo "Usage: $0 <dev|prod> <version> [--artifacts-root <path>] [--verify-timeout <seconds>]" >&2
}

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

COMPOSE_FILE="docker/docker-compose.${ENV}.yml"
if [ ! -f "$COMPOSE_FILE" ]; then
    echo "Error: compose file not found: ${COMPOSE_FILE}." >&2
    exit 1
fi
PROJECT_NAME="$(grep -m1 '^name:' "$COMPOSE_FILE" | sed 's/^name:[[:space:]]*//')"
if [ -z "$PROJECT_NAME" ]; then
    echo "Error: could not determine compose project name from ${COMPOSE_FILE}." >&2
    exit 1
fi

# --- Preconditions for BOTH apps, up front - fail before any side effect if either is missing. ---
#
# Plain functions instead of associative arrays (2026-09-07): macOS ships bash 3.2 by default
# (no `declare -A` support - that's a bash 4+ feature), and this script must run as a plain
# `#!/bin/bash` invocation on a developer's Mac (dev deploys) same as every other script in this
# repo - no `#!/usr/bin/env bash` + a newer Homebrew bash assumed. Each of these is a pure,
# deterministic function of an app name (given ENV/VERSION/ARTIFACTS_ROOT/PROJECT_NAME, all
# already fixed globals by this point), so a lookup function is exactly equivalent to an
# associative array here and needs no bash-version assumption at all.
_tar_path() { echo "${ARTIFACTS_ROOT}/$1/$1-v${VERSION}.tar"; }
_manifest_path() { echo "${ARTIFACTS_ROOT}/$1/$1-v${VERSION}.json"; }
_scripts_bundle_path() { echo "${ARTIFACTS_ROOT}/$1/$1-v${VERSION}-scripts.tar.gz"; }
_service_name() { echo "$1-${ENV}"; }
_container_name() { echo "${PROJECT_NAME}-$(_service_name "$1")-1"; }
_compose_image() { echo "${PROJECT_NAME}-$(_service_name "$1"):latest"; }

for APP in "${APPS[@]}"; do
    if [ ! -f "$(_tar_path "$APP")" ]; then
        echo "Error: no release found for ${APP} v${VERSION} - checked $(_tar_path "$APP")." >&2
        exit 1
    fi
    if [ ! -f "$(_manifest_path "$APP")" ]; then
        echo "Error: manifest missing for ${APP} v${VERSION} - checked $(_manifest_path "$APP")." >&2
        exit 1
    fi
    MANIFEST_APP="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['app'])" "$(_manifest_path "$APP")" 2>/dev/null || echo "")"
    MANIFEST_VERSION="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['version'])" "$(_manifest_path "$APP")" 2>/dev/null || echo "")"
    if [ "$MANIFEST_APP" != "$APP" ] || [ "$MANIFEST_VERSION" != "$VERSION" ]; then
        echo "Error: manifest at $(_manifest_path "$APP") doesn't match requested ${APP} v${VERSION} (found: app=${MANIFEST_APP:-<none>}, version=${MANIFEST_VERSION:-<none>})." >&2
        exit 1
    fi
    if [ ! -f "$(_scripts_bundle_path "$APP")" ]; then
        echo "Error: no ops-scripts bundle found for ${APP} v${VERSION} ($(_scripts_bundle_path "$APP")) - this script requires the bugfix-043 bundle for BOTH apps (see header comment). Deploy this version via scripts/deploy_release_single.sh instead." >&2
        exit 1
    fi
done

# --- Remote path: env=prod ships to Feature 035's Windows box over SSH, unless --local forces
#     the old same-machine behavior (test-only seam). See deploy_release_single.sh's header for
#     why prod can't just reuse this repo checkout's local compose files. ---
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
    UNPACK_SCRIPTS_HELPER="$SCRIPT_DIR/lib/unpack_scripts_bundle.sh"
    # shellcheck source=/dev/null
    source "$SCRIPT_DIR/lib/deploy_final_health_check.sh"

    TOTAL_STEPS=10  # R1(x2 apps as one step) R2 R3 R4 R5(x2) R6(x2) R7(x2) R8 R9(x2) final(x2)

    # Step R1: ship both artifacts.
    echo "== [R1] Shipping both apps' tarballs to ${REMOTE_HOST}:~/${REMOTE_DEPLOY_DIR} =="
    for APP in "${APPS[@]}"; do
        ARTIFACT_NAME="$(basename "$(_tar_path "$APP")")"
        echo "  -> ${ARTIFACT_NAME}"
        if ! scp -o BatchMode=yes -o ConnectTimeout=10 "$(_tar_path "$APP")" "${REMOTE_HOST}:~/${ARTIFACT_NAME}"; then
            echo "🚨 DEPLOY FAILED at step R1 (scp ${ARTIFACT_NAME} -> ${REMOTE_HOST}): scp exited non-zero. Nothing on ${REMOTE_HOST} was touched." >&2
            exit 1
        fi
    done

    # Step R2: resolve the Windows-side home directory (SFTP's "~" != WSL bash's "~").
    echo "== [R2] Resolving Windows-side home directory on ${REMOTE_HOST} =="
    WIN_HOME_OUTPUT="$(remote_run "wslpath -u \"\$(cmd.exe /c echo %USERPROFILE% | tr -d '\\r')\"" 2>&1)"
    WIN_HOME="$(echo "$WIN_HOME_OUTPUT" | tail -1)"
    if [ -z "$WIN_HOME" ]; then
        echo "🚨 DEPLOY FAILED at step R2 (resolve WIN_HOME on ${REMOTE_HOST}): got empty output. Raw output was:" >&2
        echo "$WIN_HOME_OUTPUT" >&2
        exit 1
    fi

    # Step R3: ship + unpack the shared ops-scripts bundle ONCE (both apps' bundles for the same
    # version carry the identical repo-wide scripts/ snapshot - see header comment; using
    # morning-mcp-app's is an arbitrary but deterministic choice, not a meaningful difference).
    BUNDLE_APP="${APPS[0]}"
    SCRIPTS_BUNDLE_NAME="$(basename "$(_scripts_bundle_path "$BUNDLE_APP")")"
    UNPACK_HELPER_NAME="$(basename "$UNPACK_SCRIPTS_HELPER")"
    MANIFEST_HELPER_NAME="release_scripts_manifest.sh"
    echo "== [R3] Shipping + unpacking the shared ops-scripts bundle on ${REMOTE_HOST} (from ${BUNDLE_APP}'s v${VERSION} bundle) =="
    if ! scp -o BatchMode=yes -o ConnectTimeout=10 "$(_scripts_bundle_path "$BUNDLE_APP")" "${REMOTE_HOST}:~/${SCRIPTS_BUNDLE_NAME}"; then
        echo "🚨 DEPLOY FAILED at step R3 (scp scripts bundle -> ${REMOTE_HOST}): scp exited non-zero. Nothing on ${REMOTE_HOST} was touched." >&2
        exit 1
    fi
    if ! scp -o BatchMode=yes -o ConnectTimeout=10 "$UNPACK_SCRIPTS_HELPER" "${REMOTE_HOST}:~/${UNPACK_HELPER_NAME}"; then
        echo "🚨 DEPLOY FAILED at step R3 (scp unpack helper -> ${REMOTE_HOST}): scp exited non-zero." >&2
        exit 1
    fi
    if ! scp -o BatchMode=yes -o ConnectTimeout=10 "$SCRIPT_DIR/lib/release_scripts_manifest.sh" "${REMOTE_HOST}:~/${MANIFEST_HELPER_NAME}"; then
        echo "🚨 DEPLOY FAILED at step R3 (scp release-scripts manifest -> ${REMOTE_HOST}): scp exited non-zero." >&2
        exit 1
    fi
    UNPACK_OUTPUT="$(remote_run "bash \"${WIN_HOME}/${UNPACK_HELPER_NAME}\" \"${WIN_HOME}/${SCRIPTS_BUNDLE_NAME}\" ~/${REMOTE_DEPLOY_DIR}" 2>&1)"
    if ! echo "$UNPACK_OUTPUT" | grep -q "^OK:"; then
        echo "🚨 DEPLOY FAILED at step R3 (unpacking scripts bundle on ${REMOTE_HOST}): the box's ops scripts may now be in an incomplete state - investigate before retrying. Raw output was:" >&2
        echo "$UNPACK_OUTPUT" >&2
        exit 1
    fi
    echo "$UNPACK_OUTPUT"
    remote_run "rm -f \"${WIN_HOME}/${SCRIPTS_BUNDLE_NAME}\" \"${WIN_HOME}/${UNPACK_HELPER_NAME}\" \"${WIN_HOME}/${MANIFEST_HELPER_NAME}\"" \
        || echo "Warning: could not clean up shipped scripts-bundle helper files on ${REMOTE_HOST} - harmless, but worth a look." >&2

    # Step R4: stop the environment ONCE - disables the prober's schedule, archives its state,
    # stops BOTH apps. This is the whole point of this script vs. two deploy_release_single.sh
    # calls: exactly one stop, not two.
    echo "== [R4] Stopping ${ENV} via stop_env.sh on ${REMOTE_HOST} (once, for both apps) =="
    if ! remote_run "bash ~/${REMOTE_DEPLOY_DIR}/scripts/stop_env.sh ${ENV}"; then
        echo "🚨 DEPLOY FAILED at step R4 (stop_env.sh ${ENV} on ${REMOTE_HOST}): nothing further attempted." >&2
        exit 1
    fi

    # Steps R5-R7: load + retag each app's image while everything is stopped - no rebuild, ever
    # (REQ-DEPLOY-001). Both must be correctly tagged BEFORE the single run_env.sh call below,
    # since the prober's own bootstrap-triggered run_all.sh needs both :latest images in place.
    for APP in "${APPS[@]}"; do
        ARTIFACT_NAME="$(basename "$(_tar_path "$APP")")"
        echo "== [R5] Loading ${ARTIFACT_NAME} into Docker on ${REMOTE_HOST} =="
        LOAD_OUTPUT="$(remote_run "docker load -i \"${WIN_HOME}/${ARTIFACT_NAME}\"" 2>&1)"
        LOADED_REF="$(echo "$LOAD_OUTPUT" | grep -oE 'Loaded image( ID)?: .*' | sed -E 's/^Loaded image( ID)?: //')"
        if [ -z "$LOADED_REF" ]; then
            echo "🚨 DEPLOY FAILED at step R5 (docker load ${APP} on ${REMOTE_HOST}): could not determine the loaded image reference. The environment is currently STOPPED (step R4 already ran) - rerun this deploy, or run_env.sh ${ENV} on ${REMOTE_HOST} to bring it back up as-is. Raw output was:" >&2
            echo "$LOAD_OUTPUT" >&2
            exit 1
        fi

        echo "== [R6] Removing the shipped ${ARTIFACT_NAME} from ${REMOTE_HOST} =="
        if ! remote_run "rm \"${WIN_HOME}/${ARTIFACT_NAME}\""; then
            echo "🚨 DEPLOY FAILED at step R6 (rm ${ARTIFACT_NAME} on ${REMOTE_HOST}): the image loaded fine (step R5), but cleanup failed - investigate disk/permissions on the box before retrying." >&2
            exit 1
        fi

        echo "== [R7] Retagging ${LOADED_REF} -> $(_compose_image "$APP") on ${REMOTE_HOST} =="
        if ! remote_run "docker tag ${LOADED_REF} $(_compose_image "$APP")"; then
            echo "🚨 DEPLOY FAILED at step R7 (docker tag ${APP} on ${REMOTE_HOST}): the environment is currently STOPPED (step R4 already ran)." >&2
            exit 1
        fi
    done

    # Step R8: start the environment ONCE - re-enables the prober's schedule and triggers one
    # immediate probe, which itself calls run_all.sh (the "bootstrap" action) now that both
    # apps' images are freshly tagged.
    echo "== [R8] Starting ${ENV} via run_env.sh on ${REMOTE_HOST} (once, for both apps) =="
    if ! remote_run "bash ~/${REMOTE_DEPLOY_DIR}/scripts/run_env.sh ${ENV}"; then
        echo "🚨 DEPLOY FAILED at step R8 (run_env.sh ${ENV} on ${REMOTE_HOST}): the environment may be left STOPPED - investigate before retrying." >&2
        exit 1
    fi

    # Step R9 + final verification, per app - a container merely started (or the previous step
    # merely exiting 0) is not a success; block until each app is genuinely confirmed.
    for APP in "${APPS[@]}"; do
        echo "== [R9] Confirming $(_container_name "$APP") is running on ${REMOTE_HOST} =="
        CONTAINER_UP=0
        CONTAINER_CHECK_ELAPSED=0
        while [ "$CONTAINER_CHECK_ELAPSED" -lt "$VERIFY_TIMEOUT" ]; do
            CONTAINER_STATUS="$(remote_run "docker inspect --format '{{.State.Status}}' $(_container_name "$APP")" 2>&1)"
            if [ "$CONTAINER_STATUS" == "running" ]; then
                CONTAINER_UP=1
                break
            fi
            sleep "$VERIFY_POLL_INTERVAL"
            CONTAINER_CHECK_ELAPSED=$((CONTAINER_CHECK_ELAPSED + VERIFY_POLL_INTERVAL))
        done
        if [ "$CONTAINER_UP" -ne 1 ]; then
            echo "🚨 DEPLOY FAILED at step R9 ($(_container_name "$APP") on ${REMOTE_HOST}): expected status 'running' within ${VERIFY_TIMEOUT}s, got '${CONTAINER_STATUS}'." >&2
            remote_run "docker logs $(_container_name "$APP") --tail 20" >&2 2>&1 || true
            exit 1
        fi

        # Version-image check (2026-09-07, bugfix-076 revision): fast log-grep, confirms the
        # RIGHT image got loaded - deliberately kept separate from the real health check below,
        # which used to be combined with this same grep for denidin-app (see
        # lib/deploy_final_health_check.sh's header for why that was wrong).
        echo "== Confirming $(_container_name "$APP") is running the v${VERSION} image on ${REMOTE_HOST} =="
        VERSION_OK=0
        ELAPSED=0
        while [ "$ELAPSED" -lt "$VERIFY_TIMEOUT" ]; do
            if remote_run "docker logs $(_container_name "$APP") --tail 20" 2>&1 | grep -q "\[v${VERSION}\]"; then
                VERSION_OK=1
                break
            fi
            sleep "$VERIFY_POLL_INTERVAL"
            ELAPSED=$((ELAPSED + VERIFY_POLL_INTERVAL))
        done
        if [ "$VERSION_OK" -ne 1 ]; then
            echo "🚨 DEPLOY FAILED at version-image check: ${APP} v${VERSION} not confirmed running in ${ENV} on ${REMOTE_HOST} within ${VERIFY_TIMEOUT}s (container is running - step R9 passed - but never logged the right version)." >&2
            echo "Last observed container state:" >&2
            remote_run "docker logs $(_container_name "$APP") --tail 20" >&2 2>&1 || true
            exit 1
        fi
    done

    # Real health verification (2026-09-07, bugfix-076): ONE combined poll for both apps, via
    # verify.py - see lib/deploy_final_health_check.sh's header for the full incident/rationale.
    if ! deploy_final_health_check_remote "$REMOTE_HOST" "$REMOTE_DEPLOY_DIR" "$ENV" 1 1; then
        exit 1
    fi

    echo "✅ Deployed and verified: BOTH apps v${VERSION} are live AND genuinely healthy in ${ENV} (${REMOTE_HOST})."
    exit 0
fi

# --- Local path (env=dev always; env=prod only with --local) ---

# shellcheck source=/dev/null
source "$SCRIPT_DIR/lib/deploy_final_health_check.sh"

# Cross-clone env lock + mandatory per-clone local-override file - see
# deploy_release_single.sh's own comment for the full rationale.
COMPOSE_ARGS=(--project-directory "$REPO_ROOT" -f "$COMPOSE_FILE")
if [ -f "$SCRIPT_DIR/env_lock.sh" ]; then
    # shellcheck source=/dev/null
    source "$SCRIPT_DIR/env_lock.sh"
    env_lock_require_local_override "$ENV"
    LOCAL_OVERRIDE="$REPO_ROOT/docker/docker-compose.${ENV}.local.yml"
    COMPOSE_ARGS+=(-f "$LOCAL_OVERRIDE")
fi

echo "Note: scripts bundle present for both apps' v${VERSION} but not applied - local/dev deploys use this checkout's own ops scripts as-is (bugfix-043)."

# Step L1: stop the environment ONCE - disables the prober's schedule, archives its state, stops
# BOTH apps. See header comment - this single stop (vs. deploy_release_single.sh's per-app stop)
# is the entire point of this script.
echo "== [L1] Stopping ${ENV} via stop_env.sh (local, once, for both apps) =="
if ! "$SCRIPT_DIR/stop_env.sh" "$ENV"; then
    echo "🚨 DEPLOY FAILED at step L1 (stop_env.sh ${ENV}, local): nothing further attempted." >&2
    exit 1
fi

# Steps L2-L3: load + retag each app's image while everything is stopped.
for APP in "${APPS[@]}"; do
    echo "== [L2] Loading $(_tar_path "$APP") into Docker (local) =="
    LOAD_OUTPUT="$(docker load -i "$(_tar_path "$APP")" 2>&1)"
    LOADED_REF="$(echo "$LOAD_OUTPUT" | grep -oE 'Loaded image( ID)?: .*' | sed -E 's/^Loaded image( ID)?: //')"
    if [ -z "$LOADED_REF" ]; then
        echo "🚨 DEPLOY FAILED at step L2 (docker load ${APP}, local): could not determine the loaded image reference. The environment is currently STOPPED (step L1 already ran) - rerun this deploy, or run_env.sh ${ENV} to bring it back up as-is. Raw output was:" >&2
        echo "$LOAD_OUTPUT" >&2
        exit 1
    fi

    echo "== [L3] Retagging ${LOADED_REF} -> $(_compose_image "$APP") (local) =="
    if ! docker tag "$LOADED_REF" "$(_compose_image "$APP")"; then
        echo "🚨 DEPLOY FAILED at step L3 (docker tag ${APP}, local): the environment is currently STOPPED (step L1 already ran)." >&2
        exit 1
    fi
done

# Step L4: start the environment ONCE - (re-)enables the prober's schedule and triggers one
# immediate probe, which itself calls run_all.sh (the "bootstrap" action) now that both apps'
# images are freshly tagged.
echo "== [L4] Starting ${ENV} via run_env.sh (local, once, for both apps) =="
if ! "$SCRIPT_DIR/run_env.sh" "$ENV"; then
    echo "🚨 DEPLOY FAILED at step L4 (run_env.sh ${ENV}, local): the environment may be left STOPPED - investigate before retrying." >&2
    exit 1
fi

# Step L5 + final verification, per app.
for APP in "${APPS[@]}"; do
    echo "== [L5] Confirming $(_container_name "$APP") is running (local) =="
    CONTAINER_UP=0
    CONTAINER_CHECK_ELAPSED=0
    while [ "$CONTAINER_CHECK_ELAPSED" -lt "$VERIFY_TIMEOUT" ]; do
        CONTAINER_STATUS="$(docker inspect --format '{{.State.Status}}' "$(_container_name "$APP")" 2>&1)"
        if [ "$CONTAINER_STATUS" == "running" ]; then
            CONTAINER_UP=1
            break
        fi
        sleep "$VERIFY_POLL_INTERVAL"
        CONTAINER_CHECK_ELAPSED=$((CONTAINER_CHECK_ELAPSED + VERIFY_POLL_INTERVAL))
    done
    if [ "$CONTAINER_UP" -ne 1 ]; then
        echo "🚨 DEPLOY FAILED at step L5 ($(_container_name "$APP"), local): expected status 'running' within ${VERIFY_TIMEOUT}s, got '${CONTAINER_STATUS}'." >&2
        docker logs "$(_container_name "$APP")" --tail 20 >&2 2>&1 || true
        exit 1
    fi

    # Version-image check (2026-09-07, bugfix-076 revision): fast log-grep, confirms the RIGHT
    # image got loaded - deliberately kept separate from the real health check below (see
    # lib/deploy_final_health_check.sh's header for why the old combined denidin-app check was
    # wrong).
    echo "== Confirming $(_container_name "$APP") is running the v${VERSION} image (local) =="
    VERSION_OK=0
    ELAPSED=0
    while [ "$ELAPSED" -lt "$VERIFY_TIMEOUT" ]; do
        if docker logs "$(_container_name "$APP")" --tail 20 2>&1 | grep -q "\[v${VERSION}\]"; then
            VERSION_OK=1
            break
        fi
        sleep "$VERIFY_POLL_INTERVAL"
        ELAPSED=$((ELAPSED + VERIFY_POLL_INTERVAL))
    done
    if [ "$VERSION_OK" -ne 1 ]; then
        echo "🚨 DEPLOY FAILED at version-image check: ${APP} v${VERSION} not confirmed running in ${ENV} within ${VERIFY_TIMEOUT}s (container is running - step L5 passed - but never logged the right version)." >&2
        echo "Last observed container state:" >&2
        docker logs "$(_container_name "$APP")" --tail 20 >&2 2>&1 || true
        exit 1
    fi
done

# Real health verification (2026-09-07, bugfix-076): ONE combined poll for both apps, via
# verify.py - see lib/deploy_final_health_check.sh's header for the full incident/rationale.
if ! deploy_final_health_check_local "$ENV" 1 1; then
    exit 1
fi

echo "✅ Deployed and verified: BOTH apps v${VERSION} are live AND genuinely healthy in ${ENV}."
