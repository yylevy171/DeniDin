#!/bin/bash
# Stops morning-mcp-app for a given environment (Docker Compose service).
# Containers only (019-env-separation) - stops only the named service, never
# the whole compose file (the paired denidin-app service in the same compose
# file must be unaffected). See
# specs/019-env-separation/contracts/run-stop-script-contract.md.
#
# Usage: ./stop_morning_mcp.sh dev|prod

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

ENV="$1"
if [ "$ENV" != "dev" ] && [ "$ENV" != "prod" ]; then
    echo "Usage: $0 dev|prod" >&2
    exit 1
fi

COMPOSE_FILE="$REPO_ROOT/docker-compose.$ENV.yml"
SERVICE="morning-mcp-app-$ENV"

docker compose -f "$COMPOSE_FILE" stop "$SERVICE"
