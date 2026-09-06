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
# only exists on the box, see specs/done/v0.2.0/035-windows-always-on-prod/) must be the one actually used
# to resolve bind-mount paths - reusing this repo checkout's own docker-compose.prod.local.yml
# (which doesn't even exist on most clones, since prod never ran locally on them) against a
# remote context would resolve relative paths against the WRONG filesystem. `dev` is unaffected -
# still a plain local deploy, exactly as before.
#
# 2026-09-06 (bugfix-043): the remote/prod path also ships + unpacks the shared host-side
# ops-scripts bundle (scripts/run_all.sh, stop_all.sh, run_env.sh, stop_env.sh, env_lock.sh,
# killall_containers.sh, each app's run_*.sh/stop_*.sh, and the health-monitoring prober - see
# scripts/lib/release_scripts_manifest.sh) that scripts/cut_release.sh now produces alongside
# the docker image tarball. Prod's deploy directory is NOT a git checkout (Feature 035), so
# these host-side scripts - which invoke `docker compose` from OUTSIDE any container - would
# otherwise never refresh after initial setup. Unpacking is done via
# scripts/lib/unpack_scripts_bundle.sh, shipped to the box and run there via SSH; the same
# helper is exercised directly (no SSH) by scripts/tests/test_release_scripts_bundle.py.
#
# 2026-09-06 (bugfix-043, admin stop/start revision): once the bundle includes stop_env.sh/
# run_env.sh, BOTH the local/dev path and the remote/prod path stop the environment via
# stop_env.sh, load+retag the new image, then start it via run_env.sh - never calling
# `docker compose up/stop` directly - so a deploy can never race the health-monitoring prober's
# own independently-scheduled checks (the exact race stop_env.sh/run_env.sh exist to close; see
# prober.py's module docstring). run_env.sh never calls `run_all.sh` itself - it only re-enables
# the prober's schedule and triggers one probe, which itself calls run_all.sh (the "bootstrap"
# action) now that the freshly-tagged image is in place. Backward compatible: a version cut
# before bugfix-043 existed has no bundle at all (HAVE_SCRIPTS_BUNDLE=0) and falls back to the
# original direct `docker compose up -d` + active_env.json bookkeeping this script has always
# done - see the HAVE_SCRIPTS_BUNDLE branch below for exactly where that split happens.
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
# bugfix-043: the shared ops-scripts bundle cut_release.sh packages alongside the image tar.
# Soft-optional (not a hard precondition) - a version cut BEFORE this feature existed has no
# bundle, and rolling back to one must still work; see the HAVE_SCRIPTS_BUNDLE check below.
SCRIPTS_BUNDLE_PATH="${ARTIFACTS_ROOT}/${APP}/${APP}-v${VERSION}-scripts.tar.gz"
UNPACK_SCRIPTS_HELPER="$SCRIPT_DIR/lib/unpack_scripts_bundle.sh"

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

# bugfix-043: soft-optional check, deliberately NOT a hard precondition (see the field's own
# comment above for why a missing bundle - an old, pre-bugfix-043 cut - must still deploy fine).
HAVE_SCRIPTS_BUNDLE=0
if [ -f "$SCRIPTS_BUNDLE_PATH" ]; then
    HAVE_SCRIPTS_BUNDLE=1
else
    echo "Note: no scripts bundle found for ${APP} v${VERSION} (${SCRIPTS_BUNDLE_PATH}) - this version predates bugfix-043's shared ops-scripts bundling. Deploying without refreshing the ops scripts."
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
    echo "== [R1/R9] Shipping ${ARTIFACT_NAME} to ${REMOTE_HOST}:~/${REMOTE_DEPLOY_DIR} (prod runs exclusively on the Windows box - Feature 035) =="
    if ! scp -o BatchMode=yes -o ConnectTimeout=10 "$TAR_PATH" "${REMOTE_HOST}:~/${ARTIFACT_NAME}"; then
        echo "🚨 DEPLOY FAILED at step R1 (scp artifact -> ${REMOTE_HOST}): scp exited non-zero. Nothing on ${REMOTE_HOST} was touched." >&2
        exit 1
    fi

    # Step R2 (bugfix-043): ship + unpack the shared ops-scripts bundle, if this version has one
    # (soft-optional - see HAVE_SCRIPTS_BUNDLE above). Ships the UNPACK HELPER SCRIPT directly
    # from this local checkout (not from the bundle itself) - avoids a chicken-and-egg bootstrap
    # problem on a box that has never received a bundle before. Uses the same helper script
    # scripts/tests/test_release_scripts_bundle.py exercises directly (no SSH) - identical
    # extraction/verification logic either way.
    if [ "$HAVE_SCRIPTS_BUNDLE" -eq 1 ]; then
        SCRIPTS_BUNDLE_NAME="$(basename "$SCRIPTS_BUNDLE_PATH")"
        UNPACK_HELPER_NAME="$(basename "$UNPACK_SCRIPTS_HELPER")"
        MANIFEST_HELPER_NAME="release_scripts_manifest.sh"
        echo "== [R2/R9] Shipping + unpacking the shared ops-scripts bundle on ${REMOTE_HOST} (bugfix-043) =="
        if ! scp -o BatchMode=yes -o ConnectTimeout=10 "$SCRIPTS_BUNDLE_PATH" "${REMOTE_HOST}:~/${SCRIPTS_BUNDLE_NAME}"; then
            echo "🚨 DEPLOY FAILED at step R2 (scp scripts bundle -> ${REMOTE_HOST}): scp exited non-zero. Nothing on ${REMOTE_HOST} was touched." >&2
            exit 1
        fi
        if ! scp -o BatchMode=yes -o ConnectTimeout=10 "$UNPACK_SCRIPTS_HELPER" "${REMOTE_HOST}:~/${UNPACK_HELPER_NAME}"; then
            echo "🚨 DEPLOY FAILED at step R2 (scp unpack helper -> ${REMOTE_HOST}): scp exited non-zero." >&2
            exit 1
        fi
        if ! scp -o BatchMode=yes -o ConnectTimeout=10 "$SCRIPT_DIR/lib/release_scripts_manifest.sh" "${REMOTE_HOST}:~/${MANIFEST_HELPER_NAME}"; then
            echo "🚨 DEPLOY FAILED at step R2 (scp release-scripts manifest -> ${REMOTE_HOST}): scp exited non-zero." >&2
            exit 1
        fi
        UNPACK_OUTPUT="$(remote_run "bash ~/${UNPACK_HELPER_NAME} ~/${SCRIPTS_BUNDLE_NAME} ~/${REMOTE_DEPLOY_DIR}" 2>&1)"
        if ! echo "$UNPACK_OUTPUT" | grep -q "^OK:"; then
            echo "🚨 DEPLOY FAILED at step R2 (unpacking scripts bundle on ${REMOTE_HOST}): the box's ops scripts may now be in an incomplete state - investigate before retrying. Raw output was:" >&2
            echo "$UNPACK_OUTPUT" >&2
            exit 1
        fi
        echo "$UNPACK_OUTPUT"
        # Clean up the shipped helper files off the box - a failure here doesn't undo the
        # (already-verified) unpack, so it's reported but not fatal.
        remote_run "rm -f ~/${SCRIPTS_BUNDLE_NAME} ~/${UNPACK_HELPER_NAME} ~/${MANIFEST_HELPER_NAME}" \
            || echo "Warning: could not clean up shipped scripts-bundle helper files on ${REMOTE_HOST} - harmless, but worth a look." >&2
    fi

    # Step R3: resolve the Windows-side home directory (SFTP's "~" != WSL bash's "~" - see
    # header comment). Split from the load step so a wslpath/cmd.exe failure is never
    # misreported as a docker load failure.
    echo "== [R3/R9] Resolving Windows-side home directory on ${REMOTE_HOST} =="
    WIN_HOME_OUTPUT="$(remote_run "wslpath -u \"\$(cmd.exe /c echo %USERPROFILE% | tr -d '\\r')\"" 2>&1)"
    WIN_HOME="$(echo "$WIN_HOME_OUTPUT" | tail -1)"
    if [ -z "$WIN_HOME" ]; then
        echo "🚨 DEPLOY FAILED at step R3 (resolve WIN_HOME on ${REMOTE_HOST}): got empty output. Raw output was:" >&2
        echo "$WIN_HOME_OUTPUT" >&2
        exit 1
    fi

    COMPOSE_IMAGE="${PROJECT_NAME}-${SERVICE_NAME}:latest"
    CONTAINER_NAME="${PROJECT_NAME}-${SERVICE_NAME}-1"

    if [ "$HAVE_SCRIPTS_BUNDLE" -eq 1 ]; then
        # bugfix-043 (2026-09-06 revision): this version's bundle includes stop_env.sh/
        # run_env.sh (see scripts/lib/release_scripts_manifest.sh), so the box already has the
        # SAME sanctioned start/stop entry points a human or the prober's own schedule uses -
        # go through them instead of hand-rolling `docker compose up/stop` + the active_env.json
        # write directly here. This closes the exact race stop_env.sh/run_env.sh exist to close
        # (a deploy's own container swap racing the prober's independently-scheduled health
        # checks) and, as a side effect, fixes the previously-known-and-deferred stale
        # active_env.json schema gap (env_lock.sh - invoked transitively via stop_all.sh/
        # run_all.sh - already writes the current active_envs dict schema; the old manual R7
        # write below never did).

        # Step R4: stop prod the sanctioned way - disables the prober's schedule, archives its
        # state, stops BOTH apps ("no per-app games" - deploying either app briefly restarts
        # both, same accepted cost as the local/dev path).
        echo "== [R4/R9] Stopping ${ENV} via stop_env.sh on ${REMOTE_HOST} (bugfix-043) =="
        if ! remote_run "bash ~/${REMOTE_DEPLOY_DIR}/scripts/stop_env.sh ${ENV}"; then
            echo "🚨 DEPLOY FAILED at step R4 (stop_env.sh ${ENV} on ${REMOTE_HOST}): nothing further attempted." >&2
            exit 1
        fi

        # Step R5: load the artifact on the box - no rebuild, ever (REQ-DEPLOY-001).
        echo "== [R5/R9] Loading ${ARTIFACT_NAME} into Docker on ${REMOTE_HOST} =="
        LOAD_OUTPUT="$(remote_run "docker load -i \"${WIN_HOME}/${ARTIFACT_NAME}\"" 2>&1)"
        LOADED_REF="$(echo "$LOAD_OUTPUT" | grep -oE 'Loaded image( ID)?: .*' | sed -E 's/^Loaded image( ID)?: //')"
        if [ -z "$LOADED_REF" ]; then
            echo "🚨 DEPLOY FAILED at step R5 (docker load on ${REMOTE_HOST}): could not determine the loaded image reference. The environment is currently STOPPED (step R4 already ran) - rerun this deploy, or run_env.sh ${ENV} on ${REMOTE_HOST} to bring it back up as-is. Raw output was:" >&2
            echo "$LOAD_OUTPUT" >&2
            exit 1
        fi

        # Step R6: clean up the shipped tarball off the box.
        echo "== [R6/R9] Removing the shipped tarball from ${REMOTE_HOST} =="
        if ! remote_run "rm \"${WIN_HOME}/${ARTIFACT_NAME}\""; then
            echo "🚨 DEPLOY FAILED at step R6 (rm shipped tarball on ${REMOTE_HOST}): the image loaded fine (step R5), but cleanup failed - investigate disk/permissions on the box before retrying." >&2
            exit 1
        fi

        # Step R7: retag - must happen BEFORE run_env.sh below, since the prober's own
        # bootstrap-triggered `run_all.sh` needs the correctly-tagged :latest image in place.
        echo "== [R7/R9] Retagging ${LOADED_REF} -> ${COMPOSE_IMAGE} on ${REMOTE_HOST} =="
        if ! remote_run "docker tag ${LOADED_REF} ${COMPOSE_IMAGE}"; then
            echo "🚨 DEPLOY FAILED at step R7 (docker tag on ${REMOTE_HOST}): the environment is currently STOPPED (step R4 already ran)." >&2
            exit 1
        fi

        # Step R8: start prod the sanctioned way - re-enables the prober's schedule and triggers
        # one immediate probe, which itself calls run_all.sh (the "bootstrap" action) now that
        # both apps are stopped and this app's image is freshly tagged.
        echo "== [R8/R9] Starting ${ENV} via run_env.sh on ${REMOTE_HOST} (bugfix-043) =="
        if ! remote_run "bash ~/${REMOTE_DEPLOY_DIR}/scripts/run_env.sh ${ENV}"; then
            echo "🚨 DEPLOY FAILED at step R8 (run_env.sh ${ENV} on ${REMOTE_HOST}): the environment may be left STOPPED - investigate before retrying." >&2
            exit 1
        fi
    else
        # Backward compatibility: this version was cut before bugfix-043's stop_env.sh/
        # run_env.sh existed (HAVE_SCRIPTS_BUNDLE's own note above already logged why) - fall
        # back to the original direct compose-up + active_env.json bookkeeping this script has
        # always done. Never delete this branch just because it looks "old" - it is what makes
        # deploying/rolling back to any pre-bugfix-043 version keep working.

        # Step R4: (no stop_env.sh available yet on this version's box) - nothing to do.
        echo "== [R4/R9] (skipped - no stop_env.sh available for this pre-bugfix-043 version) =="

        # Step R5: load the artifact on the box - no rebuild, ever (REQ-DEPLOY-001).
        echo "== [R5/R9] Loading ${ARTIFACT_NAME} into Docker on ${REMOTE_HOST} =="
        LOAD_OUTPUT="$(remote_run "docker load -i \"${WIN_HOME}/${ARTIFACT_NAME}\"" 2>&1)"
        LOADED_REF="$(echo "$LOAD_OUTPUT" | grep -oE 'Loaded image( ID)?: .*' | sed -E 's/^Loaded image( ID)?: //')"
        if [ -z "$LOADED_REF" ]; then
            echo "🚨 DEPLOY FAILED at step R5 (docker load on ${REMOTE_HOST}): could not determine the loaded image reference. Raw output was:" >&2
            echo "$LOAD_OUTPUT" >&2
            exit 1
        fi

        # Step R6: clean up the shipped tarball off the box.
        echo "== [R6/R9] Removing the shipped tarball from ${REMOTE_HOST} =="
        if ! remote_run "rm \"${WIN_HOME}/${ARTIFACT_NAME}\""; then
            echo "🚨 DEPLOY FAILED at step R6 (rm shipped tarball on ${REMOTE_HOST}): the image loaded fine (step R5), but cleanup failed - investigate disk/permissions on the box before retrying." >&2
            exit 1
        fi

        # Step R7: retag + recreate, executed ON the box - never via a Mac-side remote Docker
        # context against this checkout's local YAML (see top-of-file comment: the box's own
        # docker-compose.prod.local.yml is the one that must apply).
        echo "== [R7/R9] Retagging ${LOADED_REF} -> ${COMPOSE_IMAGE} on ${REMOTE_HOST} =="
        if ! remote_run "docker tag ${LOADED_REF} ${COMPOSE_IMAGE}"; then
            echo "🚨 DEPLOY FAILED at step R7 (docker tag on ${REMOTE_HOST})." >&2
            exit 1
        fi

        # Step R8 (bugfix-021): ensure shared/active_env.json exists as a real FILE, not a
        # directory, before `docker compose up -d`'s bind mount touches it, then recreate the
        # service directly. See git history for the full incident writeup this originally fixed.
        echo "== [R8/R9] Ensuring shared/active_env.json is a real file and recreating ${SERVICE_NAME} on ${REMOTE_HOST} (bugfix-021) =="
        ACTIVE_ENV_STATE="$(remote_run "cd ~/${REMOTE_DEPLOY_DIR} && mkdir -p shared && if [ -d shared/active_env.json ]; then if [ -z \"\$(ls -A shared/active_env.json)\" ]; then rmdir shared/active_env.json && echo REMOVED_EMPTY_DIR; else echo NONEMPTY_DIR; fi; else echo OK; fi" 2>&1)"
        if echo "$ACTIVE_ENV_STATE" | grep -q "NONEMPTY_DIR"; then
            echo "🚨 DEPLOY FAILED at step R8 (shared/active_env.json on ${REMOTE_HOST}): it's a NON-EMPTY directory, not the expected file - refusing to remove it automatically. Investigate by hand before retrying." >&2
            exit 1
        fi
        if ! echo "$ACTIVE_ENV_STATE" | grep -qE "OK|REMOVED_EMPTY_DIR"; then
            echo "🚨 DEPLOY FAILED at step R8 (checking shared/active_env.json state on ${REMOTE_HOST}): unexpected output:" >&2
            echo "$ACTIVE_ENV_STATE" >&2
            exit 1
        fi
        UPDATED_AT="$(date -u +%Y-%m-%dT%H:%M:%S+00:00)"
        if ! remote_run "printf '{\"active_env\": \"prod\", \"owner\": null, \"updated_at\": \"${UPDATED_AT}\"}\n' > ~/${REMOTE_DEPLOY_DIR}/shared/active_env.json"; then
            echo "🚨 DEPLOY FAILED at step R8 (writing shared/active_env.json on ${REMOTE_HOST})." >&2
            exit 1
        fi
        ACTIVE_ENV_VERIFY="$(remote_run "test -f ~/${REMOTE_DEPLOY_DIR}/shared/active_env.json && echo FILE || echo NOTFILE")"
        if [ "$ACTIVE_ENV_VERIFY" != "FILE" ]; then
            echo "🚨 DEPLOY FAILED at step R8 (verifying shared/active_env.json is a file on ${REMOTE_HOST}): got '${ACTIVE_ENV_VERIFY}'." >&2
            exit 1
        fi
        REMOTE_COMPOSE="cd ~/${REMOTE_DEPLOY_DIR} && docker compose --project-directory . -f docker/docker-compose.prod.yml -f docker/docker-compose.prod.local.yml"
        if ! remote_run "${REMOTE_COMPOSE} up -d --no-build ${SERVICE_NAME}"; then
            echo "🚨 DEPLOY FAILED at step R8 (docker compose up -d on ${REMOTE_HOST})." >&2
            exit 1
        fi
    fi

    # Step R9: confirm the container is actually running, not just that the previous step exited
    # 0 - compose can report success even if the container immediately crashed (restart policy
    # is "no" repo-wide, so a crash shows as Exited, not a silent respawn-loop). Poll briefly
    # rather than checking once immediately - the bundle path's run_env.sh trigger and the
    # prober's own run_all.sh call are not perfectly synchronous.
    echo "== [R9/R9] Confirming ${CONTAINER_NAME} is running on ${REMOTE_HOST} =="
    CONTAINER_UP=0
    CONTAINER_CHECK_ELAPSED=0
    while [ "$CONTAINER_CHECK_ELAPSED" -lt "$VERIFY_TIMEOUT" ]; do
        CONTAINER_STATUS="$(remote_run "docker inspect --format '{{.State.Status}}' ${CONTAINER_NAME}" 2>&1)"
        if [ "$CONTAINER_STATUS" == "running" ]; then
            CONTAINER_UP=1
            break
        fi
        sleep "$VERIFY_POLL_INTERVAL"
        CONTAINER_CHECK_ELAPSED=$((CONTAINER_CHECK_ELAPSED + VERIFY_POLL_INTERVAL))
    done
    if [ "$CONTAINER_UP" -ne 1 ]; then
        echo "🚨 DEPLOY FAILED at step R9 (${CONTAINER_NAME} on ${REMOTE_HOST}): expected status 'running' within ${VERIFY_TIMEOUT}s, got '${CONTAINER_STATUS}'." >&2
        remote_run "docker logs ${CONTAINER_NAME} --tail 20" >&2 2>&1 || true
        exit 1
    fi

    # Final verification (REQ-DEPLOY-002): a started-but-unverified container is not a success.
    # Checked over the same kind of SSH round-trip verify_windows_prod.sh already uses.
    echo "== Final check: polling ${APP}'s health/version endpoint on ${REMOTE_HOST} until it reports v${VERSION} =="
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
        echo "🚨 DEPLOY FAILED at final verification: ${APP} v${VERSION} not confirmed live in ${ENV} on ${REMOTE_HOST} within ${VERIFY_TIMEOUT}s (container is running - step R9 passed - but never reported the right version)." >&2
        echo "Last observed container state:" >&2
        remote_run "docker logs ${CONTAINER_NAME} --tail 20" >&2 2>&1 || true
        exit 1
    fi

    echo "✅ Deployed and verified: ${APP} v${VERSION} is live in ${ENV} (${REMOTE_HOST})."
    exit 0
fi

# --- Local path (env=dev always; env=prod only with --local) ---

# bugfix-043: the scripts bundle (if present, see HAVE_SCRIPTS_BUNDLE above) is deliberately
# NEVER unpacked here. Local/dev deploys run against this very git checkout - its ops scripts
# are already current by construction (they're whatever's on disk right now), and unpacking the
# bundle on top would dirty tracked files for no benefit while creating a real risk of masking
# an uncommitted local edit to one of those scripts. The bundle exists purely for the remote/
# prod path above, where the deploy directory is NOT a git checkout (Feature 035).
if [ "$HAVE_SCRIPTS_BUNDLE" -eq 1 ]; then
    echo "Note: scripts bundle present for ${APP} v${VERSION} but not applied - local/dev deploys use this checkout's own ops scripts as-is (bugfix-043)."
fi

# Cross-clone env lock + mandatory per-clone local-override file (CLAUDE.md's "Multi-clone
# lock"/"dev/prod data is also a singleton across clones" sections - the same 2026-07-30
# incident run_denidin.sh guards against). Only applies in a real repo checkout (scratch/test
# fixtures deliberately don't copy env_lock.sh in, since cross-clone locking is meaningless for
# a throwaway git repo) - presence of scripts/env_lock.sh is exactly that signal. Still needed
# here even though stop_env.sh/run_env.sh do their own env_lock work internally (via
# stop_all.sh/run_all.sh) - COMPOSE_ARGS is also used below by the verification step's
# `docker compose port` lookup.
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
#
# bugfix-043 (2026-09-06 revision): stopping/starting containers directly here - a THIRD path
# that could touch them, alongside a human and the prober - is exactly the race this bugfix
# exists to close (a deploy landing mid-way through the prober's own escalation window could
# either get fought by an "unhealthy, restart it" tick, or itself dodge the prober's schedule
# and leave it monitoring a stale state). So deploy now goes through the SAME two sanctioned
# entry points a human/the scheduler use - scripts/stop_env.sh and scripts/run_env.sh - never
# touching `docker compose up/stop` directly. Because stop_env.sh/run_env.sh operate on the
# WHOLE environment (both apps together - "no per-app games", the same rule the prober itself
# follows), deploying either app briefly stops+restarts BOTH - a real, accepted cost of dev being
# a genuine mechanical test ground for the exact same path prod will use.

# Step L1: stop the environment the sanctioned way - disables the prober's schedule first (so it
# can't race with what follows), archives its state file, then stops both apps.
echo "== [L1/L5] Stopping ${ENV} via stop_env.sh (local) =="
if ! "$SCRIPT_DIR/stop_env.sh" "$ENV"; then
    echo "🚨 DEPLOY FAILED at step L1 (stop_env.sh ${ENV}, local): nothing further attempted." >&2
    exit 1
fi

# Step L2: load the artifact - no rebuild, ever, for any of the 3 shapes (REQ-DEPLOY-001).
# Capture the ACTUAL loaded image reference from docker load's own output rather than assuming
# it matches <app>:<version> - a tarball's embedded tag always wins over its filename on disk.
echo "== [L2/L5] Loading ${TAR_PATH} into Docker (local) =="
LOAD_OUTPUT="$(docker load -i "$TAR_PATH" 2>&1)"
LOADED_REF="$(echo "$LOAD_OUTPUT" | grep -oE 'Loaded image( ID)?: .*' | sed -E 's/^Loaded image( ID)?: //')"
if [ -z "$LOADED_REF" ]; then
    echo "🚨 DEPLOY FAILED at step L2 (docker load, local): could not determine the loaded image reference. The environment is currently STOPPED (step L1 already ran) - rerun this deploy, or run_env.sh ${ENV} to bring it back up as-is. Raw output was:" >&2
    echo "$LOAD_OUTPUT" >&2
    exit 1
fi

# Step L3: retag it to whatever docker-compose expects for this service - this is what
# preserves the environment's existing volume mounts (config/logs/data) instead of a bare
# `docker run` silently missing them. Must happen BEFORE run_env.sh below, since the prober's
# own bootstrap-triggered `run_all.sh` needs the correctly-tagged :latest image already in place.
COMPOSE_IMAGE="${PROJECT_NAME}-${SERVICE_NAME}:latest"
echo "== [L3/L5] Retagging ${LOADED_REF} -> ${COMPOSE_IMAGE} (local) =="
if ! docker tag "$LOADED_REF" "$COMPOSE_IMAGE"; then
    echo "🚨 DEPLOY FAILED at step L3 (docker tag, local): the environment is currently STOPPED (step L1 already ran)." >&2
    exit 1
fi

# Step L4: start the environment the sanctioned way - (re-)enables the prober's schedule and
# triggers one immediate probe, which itself calls run_all.sh (the "bootstrap" action - see
# prober.py) now that both apps are stopped and this app's image is freshly tagged.
echo "== [L4/L5] Starting ${ENV} via run_env.sh (local) =="
if ! "$SCRIPT_DIR/run_env.sh" "$ENV"; then
    echo "🚨 DEPLOY FAILED at step L4 (run_env.sh ${ENV}, local): the environment may be left STOPPED - investigate before retrying." >&2
    exit 1
fi

CONTAINER_NAME="${PROJECT_NAME}-${SERVICE_NAME}-1"

# Step L5: confirm the container is actually running, not just that run_env.sh exited 0 - the
# prober's own soft-restart/bootstrap path calls `docker compose up -d` in the background via
# run_all.sh, which can itself report success even if the container immediately crashed
# (restart policy is "no" repo-wide, so a crash shows as Exited, not a silent respawn-loop).
# Poll briefly rather than checking once immediately - run_env.sh's trigger and the prober's own
# run_all.sh call are not perfectly synchronous.
echo "== [L5/L5] Confirming ${CONTAINER_NAME} is running (local) =="
CONTAINER_UP=0
CONTAINER_CHECK_ELAPSED=0
while [ "$CONTAINER_CHECK_ELAPSED" -lt "$VERIFY_TIMEOUT" ]; do
    CONTAINER_STATUS="$(docker inspect --format '{{.State.Status}}' "$CONTAINER_NAME" 2>&1)"
    if [ "$CONTAINER_STATUS" == "running" ]; then
        CONTAINER_UP=1
        break
    fi
    sleep "$VERIFY_POLL_INTERVAL"
    CONTAINER_CHECK_ELAPSED=$((CONTAINER_CHECK_ELAPSED + VERIFY_POLL_INTERVAL))
done
if [ "$CONTAINER_UP" -ne 1 ]; then
    echo "🚨 DEPLOY FAILED at step L5 (${CONTAINER_NAME}, local): expected status 'running' within ${VERIFY_TIMEOUT}s, got '${CONTAINER_STATUS}'." >&2
    docker logs "$CONTAINER_NAME" --tail 20 >&2 2>&1 || true
    exit 1
fi

# Final verification (REQ-DEPLOY-002) - block until confirmed or timeout. A container that
# merely started, without this passing, is a FAILED deploy, not a success.
echo "== Final check: polling ${APP}'s health/version endpoint (local) until it reports v${VERSION} =="
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
    echo "🚨 DEPLOY FAILED at final verification: ${APP} v${VERSION} not confirmed live in ${ENV} within ${VERIFY_TIMEOUT}s (container is running - step L5 passed - but never reported the right version)." >&2
    echo "Last observed container state:" >&2
    docker logs "$CONTAINER_NAME" --tail 20 >&2 2>&1 || true
    exit 1
fi

echo "✅ Deployed and verified: ${APP} v${VERSION} is live in ${ENV}."
