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
# monitored), this just re-confirms it's enabled - harmless, since the
# prober itself no-ops when everything is already healthy.
#
# 2026-09-06 fix (bugfix-043, found via a real dev deploy dry run): this
# used to ALSO explicitly call `trigger-once` right after `enable`. But
# `enable` always does `launchctl unload` then `launchctl load`, and the
# LaunchAgent plist has `RunAtLoad=true` - so `load` alone already fires an
# immediate probe run. Calling `trigger-once` right after started a SECOND,
# concurrent prober invocation racing the first one (one's `stop_all.sh
# -force`, part of its own bootstrap sequence, tore down the lock/
# containers while the other's `run_all.sh` was mid-startup) - observed
# live as a container that started cleanly and then self-terminated via its
# own watchdog's ENVIRONMENT MISMATCH check. `enable`'s own RunAtLoad-driven
# trigger is sufficient on its own; the extra explicit trigger-once was
# both redundant and the actual source of the race.
#
# Usage: ./scripts/run_env.sh dev|prod

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ENV="$1"
if [ "$ENV" != "dev" ] && [ "$ENV" != "prod" ]; then
    echo "Usage: $0 dev|prod" >&2
    exit 1
fi

echo "== Enabling health-monitoring prober for ${ENV} (RunAtLoad bootstraps the apps if not already up) =="
"$SCRIPT_DIR/health_monitoring/register_prober_schedule.sh" "$ENV" enable
