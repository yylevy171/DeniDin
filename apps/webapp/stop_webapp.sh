#!/bin/bash
# Stops the Feature 068 Ledger Web UI services for a given environment - the symmetric
# counterpart to run_webapp.sh. Stops only the webapp services, never the paired
# denidin-app / morning-mcp-app services in the same compose file.
#
# Usage: ./stop_webapp.sh dev|prod [-force]
#
# If "dev" is locked to a different clone, this refuses to release the lock unless -force
# is passed - see scripts/env_lock.sh.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

ENV="$1"
FORCE="$2"
if [ "$ENV" != "dev" ] && [ "$ENV" != "prod" ]; then
    echo "Usage: $0 dev|prod [-force]" >&2
    exit 1
fi

source "$REPO_ROOT/scripts/env_lock.sh"
env_lock_release "$ENV" "$FORCE"

COMPOSE_FILE="$REPO_ROOT/docker/docker-compose.$ENV.yml"
LOCAL_OVERRIDE="$REPO_ROOT/docker/docker-compose.$ENV.local.yml"
SERVICES=("webapp-backend-$ENV" "webapp-frontend-$ENV" "cloudflared-$ENV")

COMPOSE_ARGS=(--project-directory "$REPO_ROOT" -f "$COMPOSE_FILE")
if [ -f "$LOCAL_OVERRIDE" ]; then
    COMPOSE_ARGS+=(-f "$LOCAL_OVERRIDE")
fi

docker compose "${COMPOSE_ARGS[@]}" stop "${SERVICES[@]}"
