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
SERVICE="morning-mcp-app-$ENV"

docker compose -f "$COMPOSE_FILE" up -d "$SERVICE"
docker compose -f "$COMPOSE_FILE" ps "$SERVICE"

echo ""
echo "Tunnel status: ./shared/mcp-status-$ENV/morning_mcp_status.$ENV.json (may take a few seconds to show \"running\")"
