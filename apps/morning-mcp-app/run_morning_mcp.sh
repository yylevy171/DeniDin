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

COMPOSE_FILE="$REPO_ROOT/docker-compose.$ENV.yml"
LOCAL_OVERRIDE="$REPO_ROOT/docker-compose.$ENV.local.yml"
SERVICE="morning-mcp-app-$ENV"

# Optional per-clone override (plain relative paths, no env vars/symlinks -
# see CLAUDE.md's "Multi-clone lock" section) for dev/prod log volume
# paths, so it doesn't matter which clone last started dev/prod. Gitignored,
# created once per clone by hand; may be empty/absent if this clone's own
# paths are already the canonical ones (e.g. the root clone).
COMPOSE_ARGS=(-f "$COMPOSE_FILE")
if [ -f "$LOCAL_OVERRIDE" ]; then
    COMPOSE_ARGS+=(-f "$LOCAL_OVERRIDE")
fi

# Declare intent in the single shared active-env file BEFORE starting -
# watchdog.py in every container (this app and denidin-app, dev and prod)
# checks against this file and tears its own app down on a mismatch. If
# you're switching from a different environment, run
# ./killall_containers.sh FIRST (see CLAUDE.md's "ONE ENVIRONMENT SET AT A
# TIME" rule) - this script does not do that for you.
#
# The lock is shared across all clones (this one, coder1, coder2, ...) via
# ./shared, and "dev" is additionally locked to whichever clone acquires it
# - see env_lock.sh.
source "$REPO_ROOT/env_lock.sh"
env_lock_acquire "$ENV"

docker compose "${COMPOSE_ARGS[@]}" up -d "$SERVICE"
docker compose "${COMPOSE_ARGS[@]}" ps "$SERVICE"

echo ""
echo "Tunnel status: ./shared/mcp-status-$ENV/morning_mcp_status.$ENV.json (may take a few seconds to show \"running\")"
