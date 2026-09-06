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

exec python3 "$SCRIPT_DIR/prober.py" \
    --env "$ENV" \
    --denidin-health-url "$(prober_denidin_health_url "$ENV")" \
    --morning-health-url "$(prober_morning_health_url "$ENV")" \
    --state-file "$(prober_state_file "$ENV")" \
    --log-file "$(prober_log_file "$ENV")" \
    --scripts-dir "$REPO_ROOT" \
    --denidin-container "$(prober_denidin_container "$ENV")" \
    --morning-container "$(prober_morning_container "$ENV")" \
    "$@"
