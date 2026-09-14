#!/bin/bash
# Canonical list of host-side ops scripts bundled into every release artifact (bugfix-043).
#
# These scripts orchestrate `docker compose` itself (run_all.sh, stop_all.sh, env_lock.sh,
# killall_containers.sh, each app's own run_*.sh/stop_*.sh) plus the health-monitoring prober
# (scripts/health_monitoring/prober.py) and the daily prod backup pipeline
# (scripts/backup_prod/*, Feature 078 - added 2026-09-14 per explicit user direction: backups
# are part of the product, not a one-time hand-setup, so they ship on every release exactly like
# the prober does). None of them run INSIDE either app's Docker image - they're what invokes
# `docker compose` (or, for backup_prod, plain filesystem/sqlite3/tar/rsync operations) from the
# host - so a normal app deploy never refreshes them. On a real, non-git deploy directory (prod's
# ~/denidin-prod, Feature 035) they can silently drift stale (confirmed live, 2026-08-31 - see
# specs/in-progress/bugfixes/bugfix-043-health-monitoring-and-auto-restart.md's "Additional
# scope" gap #2). Bundling them into the artifact and unpacking on deploy is the fix.
#
# Sourced by BOTH scripts/cut_release.sh (bundling, at cut time) and
# scripts/lib/unpack_scripts_bundle.sh (verification, after extraction) so the two lists can
# never drift out of sync with each other - add a new script to bundle here, once, not in two
# places.
#
# scripts/backup_prod/config.json is deliberately NOT in this list - it's gitignored, per-host
# real config (same treatment as config.dev.json/config.prod.json/docker-compose.*.local.yml),
# created once by hand on each host and left untouched by every future bundle unpack (an overlay
# extract, never a wipe - see unpack_scripts_bundle.sh).
RELEASE_SCRIPTS_BUNDLE_FILES=(
    "scripts/run_all.sh"
    "scripts/stop_all.sh"
    "scripts/run_env.sh"
    "scripts/stop_env.sh"
    "scripts/run_all_and_verify_healthy.sh"
    "scripts/env_lock.sh"
    "scripts/killall_containers.sh"
    "scripts/health_monitoring/prober.py"
    "scripts/health_monitoring/verify.py"
    "scripts/health_monitoring/prober_paths.sh"
    "scripts/health_monitoring/run_prober_for_env.sh"
    "scripts/health_monitoring/register_prober_schedule.sh"
    "scripts/backup_prod/lib/load_config.sh"
    "scripts/backup_prod/lib/retention_purge.sh"
    "scripts/backup_prod/lib/sqlite_backup.sh"
    "scripts/backup_prod/run_daily_backup.sh"
    "scripts/backup_prod/pull_backups.sh"
    "scripts/backup_prod/verify_restore.sh"
    "scripts/backup_prod/register_backup_schedule.sh"
    "scripts/backup_prod/config.example.json"
    "apps/denidin-app/run_denidin.sh"
    "apps/denidin-app/stop_denidin.sh"
    "apps/morning-mcp-app/run_morning_mcp.sh"
    "apps/morning-mcp-app/stop_morning_mcp.sh"
    "apps/webapp/run_webapp.sh"
    "apps/webapp/stop_webapp.sh"
)
