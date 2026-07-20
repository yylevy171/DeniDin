#!/bin/bash
# Starts denidin-app for a given environment as a Docker Compose service.
# Containers only (019-env-separation) - never starts a local, non-containerized
# process, and no PID-file logic: Docker itself prevents/no-ops a duplicate
# start of an already-running service. See
# specs/019-env-separation/contracts/run-stop-script-contract.md.
#
# Usage: ./run_denidin.sh dev|prod

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

ENV="$1"
if [ "$ENV" != "dev" ] && [ "$ENV" != "prod" ]; then
    echo "Usage: $0 dev|prod" >&2
    exit 1
fi

if [ "$ENV" = "dev" ]; then
    echo "NOTE: denidin-app-dev shares one real Green API instance with denidin-app-prod (FR-014)."
    echo "      Only one of denidin-app-dev/denidin-app-prod should be actively running at a time"
    echo "      whenever real WhatsApp traffic could arrive. See quickstart.md's hand-off procedure."
    echo ""
fi

COMPOSE_FILE="$REPO_ROOT/docker-compose.$ENV.yml"
SERVICE="denidin-app-$ENV"

docker compose -f "$COMPOSE_FILE" up -d "$SERVICE"
docker compose -f "$COMPOSE_FILE" ps "$SERVICE"
