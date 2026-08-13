#!/bin/bash
# Starts morning-mcp-app for a given environment as a Docker Compose service.
# Containers only (019-env-separation) - never starts a local, non-containerized
# process (including ngrok, which now runs inside the container via
# docker-entrypoint.sh), and no PID-file logic: Docker itself prevents/no-ops
# a duplicate start of an already-running service. See
# specs/019-env-separation/contracts/run-stop-script-contract.md.
#
# Usage: ./run_morning_mcp.sh dev|prod

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

ENV="$1"
if [ "$ENV" != "dev" ] && [ "$ENV" != "prod" ]; then
    echo "Usage: $0 dev|prod" >&2
    exit 1
fi

COMPOSE_FILE="$REPO_ROOT/docker/docker-compose.$ENV.yml"
LOCAL_OVERRIDE="$REPO_ROOT/docker/docker-compose.$ENV.local.yml"
SERVICE="morning-mcp-app-$ENV"

# The lock is shared across all clones (this one, coder1, coder2, ...) via
# ./shared, and "dev" is additionally locked to whichever clone acquires it
# - see scripts/env_lock.sh.
source "$REPO_ROOT/scripts/env_lock.sh"

# MANDATORY per-clone override (plain relative paths, no env vars/symlinks -
# see CLAUDE.md's "Multi-clone lock" section) for dev/prod log volume
# paths, so it doesn't matter which clone last started dev/prod. Gitignored,
# created once per clone by hand - EVERY clone must have this file, including
# the root clone (a no-op stub there). Checked BEFORE building compose args -
# refuses to start rather than silently falling back to this clone's own
# paths (real incident, 2026-07-30 - see env_lock_require_local_override).
env_lock_require_local_override "$ENV"
#
# --project-directory pins relative volume paths inside these compose files
# to REPO_ROOT regardless of which folder (docker/) actually holds them.
COMPOSE_ARGS=(--project-directory "$REPO_ROOT" -f "$COMPOSE_FILE" -f "$LOCAL_OVERRIDE")

# Declare intent in the single shared active-env file BEFORE starting -
# watchdog.py in every container (this app and denidin-app, dev and prod)
# checks against this file and tears its own app down on a mismatch. If
# you're switching from a different environment, run
# ./scripts/killall_containers.sh FIRST (see CLAUDE.md's "ONE ENVIRONMENT SET
# AT A TIME" rule) - this script does not do that for you.
env_lock_acquire "$ENV"

# NOTE: this only (re)deploys the image already on disk - it does NOT build.
# `up -d` starts/recreates the container from whatever image was last built
# (`docker compose build "$SERVICE"`); it never rebuilds from current source.
# After any code change, `build` must be run first or this silently keeps
# serving stale code (real incident, 2026-08-12: a stop/run cycle here alone
# was mistaken for a rebuild - see CLAUDE.md's "Merging a code fix to master
# does not redeploy it" for the general rule this is one instance of).
docker compose "${COMPOSE_ARGS[@]}" up -d "$SERVICE"
docker compose "${COMPOSE_ARGS[@]}" ps "$SERVICE"

echo ""
echo "Tunnel status: ./shared/mcp-status-$ENV/morning_mcp_status.$ENV.json (may take a few seconds to show \"running\")"
