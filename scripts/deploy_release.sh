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
# ORDER, when deploying both apps to the same environment (2026-08-07): deploy morning-mcp-app
# FIRST, denidin-app SECOND. This script only ever takes one <app> per call, so the order is on
# the caller - denidin-app depends on morning-mcp-app (never the other way around), same
# dependency direction scripts/run_all.sh's own start order follows.
#
# Usage: ./scripts/deploy_release.sh <app> <env> <version> [--artifacts-root <path>] [--verify-timeout <seconds>] [--remote-host <ssh-alias>] [--remote-deploy-dir <name>] [--local]
#   <app>     : denidin-app | morning-mcp-app | webapp
#   <env>     : dev | prod
#   <version> : exact version already cut via scripts/cut_release.sh
#
# webapp is a TWO-image release (webapp-backend + webapp-frontend, one bundled tar). This
# script loads both, retags both to their compose image names, and brings up
# webapp-backend-<env> + webapp-frontend-<env> (+ cloudflared-<env> iff docker/cloudflared.<env>.env
# exists). Verification polls webapp-backend-<env>'s /health for the deployed version, same
# shape as morning-mcp-app's /health check.
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
# only exists on the box, see specs/done/v0.2.0/035-windows-always-on-prod/) must be the one actually used
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
    echo "Usage: $0 <denidin-app|morning-mcp-app|webapp> <dev|prod> <version> [--artifacts-root <path>] [--verify-timeout <seconds>]" >&2
}

if [ "$APP" != "denidin-app" ] && [ "$APP" != "morning-mcp-app" ] && [ "$APP" != "webapp" ]; then
    echo "Error: <app> must be denidin-app, morning-mcp-app or webapp (got: '${APP}')." >&2
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

# webapp fans out to two compose services (backend + frontend) from one bundled artifact,
# plus an optional cloudflared sidecar. Everything else is one service, unchanged.
#   DEPLOY_SERVICES  - every service `docker compose up -d` should (re)create
#   RUNNING_SERVICES - services that MUST end up 'running' (cloudflared is allowed to stay
#                      down when its token file is absent, so it's excluded here)
#   VERIFY_SERVICE   - the service whose /health (or logs) carries the version to poll for
if [ "$APP" == "webapp" ]; then
    IS_WEBAPP=1
    DEPLOY_SERVICES=("webapp-backend-${ENV}" "webapp-frontend-${ENV}")
    RUNNING_SERVICES=("webapp-backend-${ENV}" "webapp-frontend-${ENV}")
    if [ -f "docker/cloudflared.${ENV}.env" ]; then
        DEPLOY_SERVICES+=("cloudflared-${ENV}")
    fi
    VERIFY_SERVICE="webapp-backend-${ENV}"
    VERIFY_HTTP_PORT=8100
else
    IS_WEBAPP=0
    DEPLOY_SERVICES=("${SERVICE_NAME}")
    RUNNING_SERVICES=("${SERVICE_NAME}")
    VERIFY_SERVICE="${SERVICE_NAME}"
    VERIFY_HTTP_PORT=8000
fi

# HTTP-poll /health for the version (morning-mcp-app + webapp); log-grep for "[vX.Y.Z]"
# (denidin-app, which has no HTTP surface).
if [ "$APP" == "morning-mcp-app" ] || [ "$IS_WEBAPP" -eq 1 ]; then
    VERIFY_VIA_HTTP=1
else
    VERIFY_VIA_HTTP=0
fi

# Retag one loaded image ref to the compose image name its service expects. webapp's two
# images map by their embedded repo name; single-image apps map to ${SERVICE_NAME}.
_compose_image_for() {
    case "$1" in
        webapp-backend:*)  echo "${PROJECT_NAME}-webapp-backend-${ENV}:latest" ;;
        webapp-frontend:*) echo "${PROJECT_NAME}-webapp-frontend-${ENV}:latest" ;;
        *)                 echo "${PROJECT_NAME}-${SERVICE_NAME}:latest" ;;
    esac
}

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

# The image tag(s) this artifact's tar is supposed to contain - straight from the manifest
# cut_release.sh wrote at `docker save` time (authoritative for WHAT should be in the tar).
# This drives the retag loop below instead of parsing `docker load`'s own stdout for it,
# because over the wsl.exe/base64 SSH transport that multi-line output can be collapsed to a
# single line (real incident 2026-09-06: webapp's 2-image tar retagged only the first image,
# then `docker compose up -d` failed on the missing second one). `docker load`'s output is
# still checked - via _verify_loaded_matches_manifest below - but only to catch an image the
# manifest does NOT list (a swapped/corrupt tarball), never as the retag source of truth.
# Manifests cut before the `images` array existed (older single-image denidin-app/
# morning-mcp-app releases) fall back to the one <app>:<version> tag `docker save` embedded.
MANIFEST_IMAGES="$(python3 -c "import json,sys; print('\n'.join(json.load(open(sys.argv[1])).get('images') or []))" "$MANIFEST_PATH" 2>/dev/null || echo "")"
if [ -z "$MANIFEST_IMAGES" ]; then
    MANIFEST_IMAGES="${APP}:${VERSION}"
fi

# Fail if `docker load`'s output names an image tag the manifest does NOT list - that means the
# tarball's content doesn't match its manifest (e.g. bytes swapped after the cut). The reverse -
# a manifest image NOT appearing in the load output - is NOT failed here: the SSH transport can
# drop lines from multi-line stdout; each manifest image's real presence is confirmed separately
# by `docker image inspect` at the retag step. $1 = captured `docker load` output; $2 = optional
# host label for the error message.
_verify_loaded_matches_manifest() {
    local load_output="$1" where="" t
    [ -n "$2" ] && where=" on $2"
    while IFS= read -r t; do
        [ -z "$t" ] && continue
        if ! printf '%s\n' "$MANIFEST_IMAGES" | grep -qxF "$t"; then
            echo "🚨 DEPLOY FAILED at the load step${where}: the tarball loaded image '${t}', which the release manifest for ${APP} v${VERSION} does not list ($(echo "$MANIFEST_IMAGES" | tr '\n' ' ')). The artifact's content does not match its manifest - refusing to deploy." >&2
            return 1
        fi
    done <<< "$(echo "$load_output" | tr -d '\r' | grep -oE 'Loaded image: [^ ]+' | sed 's/^Loaded image: //')"
    return 0
}

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

    # Every step below is verified individually and fails LOUDLY, naming exactly which step
    # failed, on which host, with the actual command output attached - "some step in this SSH
    # session succeeded" is never good enough (2026-08-03, per-step verification requirement).

    # Step R1: ship the artifact.
    echo "== [R1/R8] Shipping ${ARTIFACT_NAME} to ${REMOTE_HOST}:~/${REMOTE_DEPLOY_DIR} (prod runs exclusively on the Windows box - Feature 035) =="
    if ! scp -o BatchMode=yes -o ConnectTimeout=10 "$TAR_PATH" "${REMOTE_HOST}:~/${ARTIFACT_NAME}"; then
        echo "🚨 DEPLOY FAILED at step R1 (scp artifact -> ${REMOTE_HOST}): scp exited non-zero. Nothing on ${REMOTE_HOST} was touched." >&2
        exit 1
    fi

    # Step R2: resolve the Windows-side home directory (SFTP's "~" != WSL bash's "~" - see
    # header comment). Split from the load step so a wslpath/cmd.exe failure is never
    # misreported as a docker load failure.
    echo "== [R2/R8] Resolving Windows-side home directory on ${REMOTE_HOST} =="
    WIN_HOME_OUTPUT="$(remote_run "wslpath -u \"\$(cmd.exe /c echo %USERPROFILE% | tr -d '\\r')\"" 2>&1)"
    WIN_HOME="$(echo "$WIN_HOME_OUTPUT" | tail -1)"
    if [ -z "$WIN_HOME" ]; then
        echo "🚨 DEPLOY FAILED at step R2 (resolve WIN_HOME on ${REMOTE_HOST}): got empty output. Raw output was:" >&2
        echo "$WIN_HOME_OUTPUT" >&2
        exit 1
    fi

    # Step R3: load the artifact on the box - no rebuild, ever (REQ-DEPLOY-001). webapp's
    # bundled tar carries two images. Exit codes don't propagate through `wsl.exe -e bash -c`,
    # so success is confirmed two ways: (a) `docker load`'s output must not name any image the
    # manifest doesn't list (corrupt/swapped tar), and (b) every manifest image must actually
    # be present afterward (`docker image inspect`) - the transport can drop a "Loaded image:"
    # line from multi-line stdout without the load itself having failed.
    echo "== [R3/R8] Loading ${ARTIFACT_NAME} into Docker on ${REMOTE_HOST} =="
    LOAD_OUTPUT="$(remote_run "docker load -i \"${WIN_HOME}/${ARTIFACT_NAME}\"" 2>&1)"
    echo "$LOAD_OUTPUT" | sed 's/^/   /'
    _verify_loaded_matches_manifest "$LOAD_OUTPUT" "$REMOTE_HOST" || exit 1
    LOADED_REFS="$MANIFEST_IMAGES"
    while IFS= read -r _ref; do
        [ -z "$_ref" ] && continue
        _present="$(remote_run "docker image inspect ${_ref} >/dev/null 2>&1 && echo PRESENT || echo MISSING" 2>&1 | tail -1)"
        if [ "$_present" != "PRESENT" ]; then
            echo "🚨 DEPLOY FAILED at step R3 (docker load on ${REMOTE_HOST}): image ${_ref} (from the release manifest) is not present after load." >&2
            exit 1
        fi
    done <<< "$LOADED_REFS"

    # Step R4: clean up the shipped tarball off the box - separately checked so a failure here
    # (disk full, permissions) is never silently swallowed by the load step's own success.
    echo "== [R4/R8] Removing the shipped tarball from ${REMOTE_HOST} =="
    if ! remote_run "rm \"${WIN_HOME}/${ARTIFACT_NAME}\""; then
        echo "🚨 DEPLOY FAILED at step R4 (rm shipped tarball on ${REMOTE_HOST}): the image loaded fine (step R3), but cleanup failed - investigate disk/permissions on the box before retrying." >&2
        exit 1
    fi

    # Step R5: retag + recreate, executed ON the box - never via a Mac-side remote Docker
    # context against this checkout's local YAML (see top-of-file comment: the box's own
    # docker-compose.prod.local.yml is the one that must apply). One image normally; two for
    # webapp.
    echo "== [R5/R8] Retagging loaded image(s) to their compose names on ${REMOTE_HOST} =="
    while IFS= read -r _ref; do
        [ -z "$_ref" ] && continue
        _target="$(_compose_image_for "$_ref")"
        echo "   ${_ref} -> ${_target}"
        # Exit codes don't propagate through the SSH/wsl transport - confirm the retag landed
        # by inspecting the target, not by `remote_run`'s return status.
        _tagged="$(remote_run "docker tag ${_ref} ${_target} && docker image inspect ${_target} >/dev/null 2>&1 && echo OK || echo FAIL" 2>&1 | tail -1)"
        if [ "$_tagged" != "OK" ]; then
            echo "🚨 DEPLOY FAILED at step R5 (docker tag ${_ref} -> ${_target} on ${REMOTE_HOST})." >&2
            exit 1
        fi
    done <<< "$LOADED_REFS"

    # Step R6 (bugfix-021): ensure shared/active_env.json exists as a real FILE, not a
    # directory, before `docker compose up -d`'s bind mount touches it. Docker silently
    # creates a directory at a missing bind-mount source path - since nothing in this deploy
    # path (nor the retired deploy_and_verify.sh before it) ever wrote this file, every prod
    # container's /app/active-env/active_env.json ended up as an empty directory, which broke
    # watchdog.py's env-mismatch safety check on both apps. Same schema/intent as
    # env_lock.sh's env_lock_acquire, which the LOCAL (dev) path already gets for free via
    # env_lock_acquire below - prod is never owner-locked (CLAUDE.md), so owner is always null.
    #
    # webapp has NO watchdog and never reads active_env.json (its compose services don't mount
    # it) - so this step is skipped for webapp. It also stays UNCHANGED for denidin-app /
    # morning-mcp-app rather than being "fixed" here: the printf below still writes the
    # pre-2026-08-05 scalar shape ({"active_env": ...}) which newer watchdogs read as "no
    # active_envs key -> skip the check". Correcting that is its own change for those apps, not
    # something to fold into a webapp deploy.
    if [ "$IS_WEBAPP" -ne 1 ]; then
        echo "== [R6/R8] Ensuring shared/active_env.json is a real file on ${REMOTE_HOST} (bugfix-021) =="
        ACTIVE_ENV_STATE="$(remote_run "cd ~/${REMOTE_DEPLOY_DIR} && mkdir -p shared && if [ -d shared/active_env.json ]; then if [ -z \"\$(ls -A shared/active_env.json)\" ]; then rmdir shared/active_env.json && echo REMOVED_EMPTY_DIR; else echo NONEMPTY_DIR; fi; else echo OK; fi" 2>&1)"
        if echo "$ACTIVE_ENV_STATE" | grep -q "NONEMPTY_DIR"; then
            echo "🚨 DEPLOY FAILED at step R6 (shared/active_env.json on ${REMOTE_HOST}): it's a NON-EMPTY directory, not the expected file - refusing to remove it automatically. Investigate by hand before retrying." >&2
            exit 1
        fi
        if ! echo "$ACTIVE_ENV_STATE" | grep -qE "OK|REMOVED_EMPTY_DIR"; then
            echo "🚨 DEPLOY FAILED at step R6 (checking shared/active_env.json state on ${REMOTE_HOST}): unexpected output:" >&2
            echo "$ACTIVE_ENV_STATE" >&2
            exit 1
        fi
        UPDATED_AT="$(date -u +%Y-%m-%dT%H:%M:%S+00:00)"
        if ! remote_run "printf '{\"active_env\": \"prod\", \"owner\": null, \"updated_at\": \"${UPDATED_AT}\"}\n' > ~/${REMOTE_DEPLOY_DIR}/shared/active_env.json"; then
            echo "🚨 DEPLOY FAILED at step R6 (writing shared/active_env.json on ${REMOTE_HOST})." >&2
            exit 1
        fi
        ACTIVE_ENV_VERIFY="$(remote_run "test -f ~/${REMOTE_DEPLOY_DIR}/shared/active_env.json && echo FILE || echo NOTFILE")"
        if [ "$ACTIVE_ENV_VERIFY" != "FILE" ]; then
            echo "🚨 DEPLOY FAILED at step R6 (verifying shared/active_env.json is a file on ${REMOTE_HOST}): got '${ACTIVE_ENV_VERIFY}'." >&2
            exit 1
        fi
    else
        echo "== [R6/R8] Skipped for webapp (no watchdog, no active_env.json mount) =="
    fi

    REMOTE_COMPOSE="cd ~/${REMOTE_DEPLOY_DIR} && docker compose --project-directory . -f docker/docker-compose.prod.yml -f docker/docker-compose.prod.local.yml"

    # webapp: only include cloudflared-prod if the box actually has its token file.
    REMOTE_DEPLOY_SERVICES=("${DEPLOY_SERVICES[@]}")
    if [ "$IS_WEBAPP" -eq 1 ]; then
        REMOTE_DEPLOY_SERVICES=("webapp-backend-${ENV}" "webapp-frontend-${ENV}")
        if remote_run "test -f ~/${REMOTE_DEPLOY_DIR}/docker/cloudflared.${ENV}.env" 2>/dev/null; then
            REMOTE_DEPLOY_SERVICES+=("cloudflared-${ENV}")
        fi
    fi

    echo "== [R7/R8] Recreating ${REMOTE_DEPLOY_SERVICES[*]} on ${REMOTE_HOST} (docker compose up -d --no-build) =="
    if ! remote_run "${REMOTE_COMPOSE} up -d --no-build ${REMOTE_DEPLOY_SERVICES[*]}"; then
        echo "🚨 DEPLOY FAILED at step R7 (docker compose up -d on ${REMOTE_HOST})." >&2
        exit 1
    fi

    # Step R8: confirm each required container is actually running, not just that `up -d`
    # exited 0 - compose can return success even if a container immediately crashed (restart
    # policy is "no" repo-wide). cloudflared is excluded (allowed to stay down without a token).
    for _svc in "${RUNNING_SERVICES[@]}"; do
        _cname="${PROJECT_NAME}-${_svc}-1"
        echo "== [R8/R8] Confirming ${_cname} is running on ${REMOTE_HOST} =="
        _status="$(remote_run "docker inspect --format '{{.State.Status}}' ${_cname}" 2>&1)"
        if [ "$_status" != "running" ]; then
            echo "🚨 DEPLOY FAILED at step R8 (${_cname} on ${REMOTE_HOST}): expected status 'running', got '${_status}'." >&2
            remote_run "docker logs ${_cname} --tail 20" >&2 2>&1 || true
            exit 1
        fi
    done

    VERIFY_CONTAINER="${PROJECT_NAME}-${VERIFY_SERVICE}-1"

    # Final verification (REQ-DEPLOY-002): a started-but-unverified container is not a success.
    # Checked over the same kind of SSH round-trip verify_windows_prod.sh already uses.
    echo "== Final check: polling ${APP}'s health/version endpoint on ${REMOTE_HOST} until it reports v${VERSION} =="
    VERIFIED=0
    ELAPSED=0
    while [ "$ELAPSED" -lt "$VERIFY_TIMEOUT" ]; do
        if [ "$VERIFY_VIA_HTTP" -eq 1 ]; then
            HEALTH_JSON="$(remote_run "cd ~/${REMOTE_DEPLOY_DIR} && PORT=\$(docker compose -f docker/docker-compose.prod.yml port ${VERIFY_SERVICE} ${VERIFY_HTTP_PORT} | cut -d: -f2) && curl -sf http://127.0.0.1:\$PORT/health" 2>/dev/null || echo "")"
            HEALTH_VERSION="$(echo "$HEALTH_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('version',''))" 2>/dev/null || echo "")"
            if [ "$HEALTH_VERSION" == "$VERSION" ]; then
                VERIFIED=1
                break
            fi
        else
            if remote_run "docker logs ${VERIFY_CONTAINER} --tail 20" 2>&1 | grep -q "\[v${VERSION}\]"; then
                VERIFIED=1
                break
            fi
        fi
        sleep "$VERIFY_POLL_INTERVAL"
        ELAPSED=$((ELAPSED + VERIFY_POLL_INTERVAL))
    done

    if [ "$VERIFIED" -ne 1 ]; then
        echo "🚨 DEPLOY FAILED at final verification: ${APP} v${VERSION} not confirmed live in ${ENV} on ${REMOTE_HOST} within ${VERIFY_TIMEOUT}s (container is running - step R7 passed - but never reported the right version)." >&2
        echo "Last observed container state:" >&2
        remote_run "docker logs ${VERIFY_CONTAINER} --tail 20" >&2 2>&1 || true
        exit 1
    fi

    echo "✅ Deployed and verified: ${APP} v${VERSION} is live in ${ENV} (${REMOTE_HOST})."
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
#
# Every step below is verified individually and fails LOUDLY, naming exactly which step failed
# with the actual command output attached (2026-08-03, per-step verification requirement) -
# matching the same discipline as the remote/prod path above.

# Step L1: load the artifact - no rebuild, ever, for any of the 3 shapes (REQ-DEPLOY-001).
# The retag list (step L2) is the manifest's image tags, NOT whatever `docker load` prints -
# see MANIFEST_IMAGES above. `docker load`'s output is still checked, to reject a tarball
# containing an image the manifest doesn't list (swapped/corrupt bytes); step L2 then confirms
# each manifest image is actually present. This is what mis-handled webapp's 2-image tar
# before (2026-09-06) and what the swapped-tarball verification test exercises.
echo "== [L1/L4] Loading ${TAR_PATH} into Docker (local) =="
set +e
LOAD_OUTPUT="$(docker load -i "$TAR_PATH" 2>&1)"
LOAD_STATUS=$?
set -e
echo "$LOAD_OUTPUT" | sed 's/^/   /'
if [ "$LOAD_STATUS" -ne 0 ]; then
    echo "🚨 DEPLOY FAILED at step L1 (docker load, local)." >&2
    exit 1
fi
_verify_loaded_matches_manifest "$LOAD_OUTPUT" || exit 1
LOADED_REFS="$MANIFEST_IMAGES"

# Step L2: retag each loaded image to whatever docker-compose expects for its service - this
# is what preserves the environment's existing volume mounts (config/logs/data) instead of a
# bare `docker run` silently missing them. webapp loads two images; everything else one.
echo "== [L2/L4] Retagging loaded image(s) to their compose names (local) =="
while IFS= read -r _ref; do
    [ -z "$_ref" ] && continue
    if ! docker image inspect "$_ref" >/dev/null 2>&1; then
        echo "🚨 DEPLOY FAILED at step L2 (image ${_ref} from the release manifest not present after docker load, local)." >&2
        exit 1
    fi
    _target="$(_compose_image_for "$_ref")"
    echo "   ${_ref} -> ${_target}"
    if ! docker tag "$_ref" "$_target"; then
        echo "🚨 DEPLOY FAILED at step L2 (docker tag ${_ref} -> ${_target}, local)." >&2
        exit 1
    fi
done <<< "$LOADED_REFS"

# Declare intent in the shared active-env file BEFORE starting, same as run_denidin.sh - only
# in a real repo checkout (see the env_lock.sh presence check above).
if [ -f "$SCRIPT_DIR/env_lock.sh" ]; then
    env_lock_acquire "$ENV"
fi

echo "== [L3/L4] Recreating ${DEPLOY_SERVICES[*]} (local, docker compose up -d --no-build) =="
if ! docker compose "${COMPOSE_ARGS[@]}" up -d --no-build "${DEPLOY_SERVICES[@]}"; then
    echo "🚨 DEPLOY FAILED at step L3 (docker compose up -d, local)." >&2
    exit 1
fi

# Step L4: confirm each required container is actually running, not just that `up -d` exited 0
# - compose can return success even if a container immediately crashed (restart policy is "no"
# repo-wide, so a crash shows as Exited, not a silent respawn-loop). cloudflared is NOT in
# RUNNING_SERVICES - it's allowed to stay down when no token file is present.
for _svc in "${RUNNING_SERVICES[@]}"; do
    _cname="${PROJECT_NAME}-${_svc}-1"
    echo "== [L4/L4] Confirming ${_cname} is running (local) =="
    _status="$(docker inspect --format '{{.State.Status}}' "$_cname" 2>&1)"
    if [ "$_status" != "running" ]; then
        echo "🚨 DEPLOY FAILED at step L4 (${_cname}, local): expected status 'running', got '${_status}'." >&2
        docker logs "$_cname" --tail 20 >&2 2>&1 || true
        exit 1
    fi
done

VERIFY_CONTAINER="${PROJECT_NAME}-${VERIFY_SERVICE}-1"

# Final verification (REQ-DEPLOY-002) - block until confirmed or timeout. A container that
# merely started, without this passing, is a FAILED deploy, not a success.
echo "== Final check: polling ${APP}'s health/version endpoint (local) until it reports v${VERSION} =="
VERIFIED=0
ELAPSED=0
while [ "$ELAPSED" -lt "$VERIFY_TIMEOUT" ]; do
    if [ "$VERIFY_VIA_HTTP" -eq 1 ]; then
        HOST_PORT="$(docker compose "${COMPOSE_ARGS[@]}" port "$VERIFY_SERVICE" "$VERIFY_HTTP_PORT" 2>/dev/null | cut -d: -f2)"
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
        if docker logs "$VERIFY_CONTAINER" --tail 20 2>&1 | grep -q "\[v${VERSION}\]"; then
            VERIFIED=1
            break
        fi
    fi
    sleep "$VERIFY_POLL_INTERVAL"
    ELAPSED=$((ELAPSED + VERIFY_POLL_INTERVAL))
done

if [ "$VERIFIED" -ne 1 ]; then
    echo "🚨 DEPLOY FAILED at final verification: ${APP} v${VERSION} not confirmed live in ${ENV} within ${VERIFY_TIMEOUT}s (container is running - step L4 passed - but never reported the right version)." >&2
    echo "Last observed container state:" >&2
    docker logs "$VERIFY_CONTAINER" --tail 20 >&2 2>&1 || true
    exit 1
fi

echo "✅ Deployed and verified: ${APP} v${VERSION} is live in ${ENV}."
