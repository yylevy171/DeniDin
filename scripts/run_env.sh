#!/bin/bash
# Starts an environment the RIGHT way (bugfix-043, 2026-09-06 revision): all
# this script does is (re-)enable the health-monitoring prober's schedule for
# <env> and trigger one immediate probe cycle. It deliberately never calls
# run_all.sh itself - the prober is the ONLY thing that ever brings the apps
# up (see prober.py's "bootstrap" action), on every kind of start (fresh
# install, admin-requested via this script, crash recovery, reboot recovery
# alike) - so that code path is exercised every single time, not just during
# a rare real crash. See prober.py's module docstring for the full
# rationale, and scripts/stop_env.sh for the symmetric stop side.
#
# Idempotent: if the schedule is already enabled (env already running/being
# monitored), this just re-confirms it's enabled and re-triggers a probe -
# harmless, since the prober itself no-ops when everything is already
# healthy.
#
# Usage: ./scripts/run_env.sh dev|prod

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ENV="$1"
if [ "$ENV" != "dev" ] && [ "$ENV" != "prod" ]; then
    echo "Usage: $0 dev|prod" >&2
    exit 1
fi

echo "== Enabling health-monitoring prober for ${ENV} =="
"$SCRIPT_DIR/health_monitoring/register_prober_schedule.sh" "$ENV" enable

echo "== Triggering an immediate probe for ${ENV} (bootstraps the apps if not already up) =="
"$SCRIPT_DIR/health_monitoring/register_prober_schedule.sh" "$ENV" trigger-once
