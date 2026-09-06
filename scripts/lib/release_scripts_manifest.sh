#!/bin/bash
# Canonical list of host-side ops scripts bundled into every release artifact (bugfix-043).
#
# These scripts orchestrate `docker compose` itself (run_all.sh, stop_all.sh, env_lock.sh,
# killall_containers.sh, each app's own run_*.sh/stop_*.sh) plus the health-monitoring prober
# (scripts/health_monitoring/prober.py). None of them run INSIDE either app's Docker image -
# they're what invokes `docker compose` from the host - so a normal app deploy never refreshes
# them. On a real, non-git deploy directory (prod's ~/denidin-prod, Feature 035) they can
# silently drift stale (confirmed live, 2026-08-31 - see specs/in-progress/bugfixes/
# bugfix-043-health-monitoring-and-auto-restart.md's "Additional scope" gap #2). Bundling them
# into the artifact and unpacking on deploy is the fix.
#
# Sourced by BOTH scripts/cut_release.sh (bundling, at cut time) and
# scripts/lib/unpack_scripts_bundle.sh (verification, after extraction) so the two lists can
# never drift out of sync with each other - add a new script to bundle here, once, not in two
# places.
RELEASE_SCRIPTS_BUNDLE_FILES=(
    "scripts/run_all.sh"
    "scripts/stop_all.sh"
    "scripts/env_lock.sh"
    "scripts/killall_containers.sh"
    "scripts/health_monitoring/prober.py"
    "apps/denidin-app/run_denidin.sh"
    "apps/denidin-app/stop_denidin.sh"
    "apps/morning-mcp-app/run_morning_mcp.sh"
    "apps/morning-mcp-app/stop_morning_mcp.sh"
)
