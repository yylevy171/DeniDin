#!/bin/bash
# What the OS scheduler (Windows Task Scheduler in prod, a macOS LaunchAgent
# in dev) actually invokes on every tick, and what run_env.sh's "trigger one
# immediate probe" step calls directly - resolves prober.py's arguments for
# <env> from this repo's own layout/config (see prober_paths.sh) and execs
# it. No argument here is hardcoded independently of prober_paths.sh, so
# run_env.sh's immediate trigger and the scheduler's own later ticks always
# agree on exactly the same state/log files and health URLs.
#
# Usage: ./scripts/health_monitoring/run_prober_for_env.sh dev|prod [--dry-run]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

ENV="$1"
shift || true
if [ "$ENV" != "dev" ] && [ "$ENV" != "prod" ]; then
    echo "Usage: $0 dev|prod [--dry-run]" >&2
    exit 1
fi

# shellcheck source=/dev/null
source "$SCRIPT_DIR/prober_paths.sh"

# webapp (Feature 068) is deployed independently and isn't present on every box/env. Only monitor
# it when its container actually exists right now - otherwise prober.py would see it as
# permanently unreachable and escalate a restart of the whole env for a service that was never
# meant to be running here. Both webapp containers are checked independently (backend deep
# /health + frontend nginx /healthz) - each guarded on its own container existing.
WEBAPP_ARGS=()
WEBAPP_CONTAINER="$(prober_webapp_container "$ENV")"
if docker inspect "$WEBAPP_CONTAINER" >/dev/null 2>&1; then
    WEBAPP_ARGS=(
        --webapp-health-url "$(prober_webapp_health_url "$ENV")"
        --webapp-container "$WEBAPP_CONTAINER"
    )
fi
WEBAPP_FRONTEND_CONTAINER="$(prober_webapp_frontend_container "$ENV")"
if docker inspect "$WEBAPP_FRONTEND_CONTAINER" >/dev/null 2>&1; then
    WEBAPP_ARGS+=(
        --webapp-frontend-health-url "$(prober_webapp_frontend_health_url "$ENV")"
        --webapp-frontend-container "$WEBAPP_FRONTEND_CONTAINER"
    )
fi

exec python3 "$SCRIPT_DIR/prober.py" \
    --env "$ENV" \
    --denidin-health-url "$(prober_denidin_health_url "$ENV")" \
    --morning-health-url "$(prober_morning_health_url "$ENV")" \
    --state-file "$(prober_state_file "$ENV")" \
    --log-file "$(prober_log_file "$ENV")" \
    --verify-log-file "$(prober_verify_log_file "$ENV")" \
    --scripts-dir "$REPO_ROOT" \
    --denidin-container "$(prober_denidin_container "$ENV")" \
    --morning-container "$(prober_morning_container "$ENV")" \
    "${WEBAPP_ARGS[@]}" \
    "$@"
