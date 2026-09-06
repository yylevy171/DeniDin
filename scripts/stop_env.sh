#!/bin/bash
# Stops an environment the RIGHT way (bugfix-043, 2026-09-06 revision): the
# health-monitoring prober is disabled FIRST, before the apps themselves are
# stopped - otherwise a scheduled probe tick landing mid-shutdown would see
# both apps unhealthy and race to "helpfully" restart them while this script
# is still trying to bring them down.
#
# This is now the ONE sanctioned way for an admin to take an environment
# down - it replaces calling stop_all.sh directly for that purpose (stop_all.sh
# itself is unchanged and still used internally, by this script, by
# run_env.sh's prober's own soft-restart path, and by anything else that only
# needs the two apps stopped without touching prober scheduling).
#
# Order:
#   1. Disable the OS-level prober schedule for <env> (register_prober_schedule.sh).
#   2. Archive the prober's state file for <env> (prober.py --archive-state) -
#      never silently deleted, and its absence afterward is exactly what
#      makes the next run_env.sh start bootstrap immediately instead of
#      escalating against a stale pre-stop timestamp (see prober.py's
#      module docstring).
#   3. Stop both apps (stop_all.sh <env> -force).
#
# Usage: ./scripts/stop_env.sh dev|prod

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

ENV="$1"
if [ "$ENV" != "dev" ] && [ "$ENV" != "prod" ]; then
    echo "Usage: $0 dev|prod" >&2
    exit 1
fi

# shellcheck source=/dev/null
source "$SCRIPT_DIR/health_monitoring/prober_paths.sh"

echo "== Disabling health-monitoring prober for ${ENV} =="
"$SCRIPT_DIR/health_monitoring/register_prober_schedule.sh" "$ENV" disable

echo "== Archiving prober state for ${ENV} =="
python3 "$SCRIPT_DIR/health_monitoring/prober.py" \
    --env "$ENV" \
    --state-file "$(prober_state_file "$ENV")" \
    --archive-state

echo "== Stopping ${ENV} (both apps) =="
"$SCRIPT_DIR/stop_all.sh" "$ENV" -force
