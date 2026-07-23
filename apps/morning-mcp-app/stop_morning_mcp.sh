#!/bin/bash
# Stops morning-mcp-app for a given environment (Docker Compose service).
# Containers only (019-env-separation) - stops only the named service, never
# the whole compose file (the paired denidin-app service in the same compose
# file must be unaffected). See
# specs/019-env-separation/contracts/run-stop-script-contract.md.
#
# Usage: ./stop_morning_mcp.sh dev|prod [-force]
#
# If "dev" is locked to a different clone (coder), this refuses to stop it
# and release the lock unless -force is passed - see env_lock.sh.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

ENV="$1"
FORCE="$2"
if [ "$ENV" != "dev" ] && [ "$ENV" != "prod" ]; then
    echo "Usage: $0 dev|prod [-force]" >&2
    exit 1
fi

source "$REPO_ROOT/env_lock.sh"
env_lock_release "$ENV" "$FORCE"

COMPOSE_FILE="$REPO_ROOT/docker-compose.$ENV.yml"
SERVICE="morning-mcp-app-$ENV"

docker compose -f "$COMPOSE_FILE" --env-file "$REPO_ROOT/.env.local" stop "$SERVICE"
