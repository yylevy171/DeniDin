#!/bin/bash
# Stops the Feature 068 Ledger Web UI services for a given environment - the symmetric
# counterpart to run_webapp.sh. Stops only the webapp services, never the paired
# denidin-app / morning-mcp-app services in the same compose file.
#
# Usage: ./stop_webapp.sh dev|prod [ignored]
#
# ENV-LOCK AGNOSTIC (2026-09-06): like run_webapp.sh, this never touches the shared dev
# env-lock (shared/active_env.json) - stop the webapp freely regardless of which clone
# owns dev. A 2nd positional arg (e.g. -force, passed through by stop_all.sh) is accepted
# and ignored for CLI compatibility.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

ENV="$1"
if [ "$ENV" != "dev" ] && [ "$ENV" != "prod" ]; then
    echo "Usage: $0 dev|prod [ignored]" >&2
    exit 1
fi

COMPOSE_FILE="$REPO_ROOT/docker/docker-compose.$ENV.yml"
LOCAL_OVERRIDE="$REPO_ROOT/docker/docker-compose.$ENV.local.yml"
SERVICES=("webapp-backend-$ENV" "webapp-frontend-$ENV" "cloudflared-$ENV")

COMPOSE_ARGS=(--project-directory "$REPO_ROOT" -f "$COMPOSE_FILE")
if [ -f "$LOCAL_OVERRIDE" ]; then
    COMPOSE_ARGS+=(-f "$LOCAL_OVERRIDE")
fi

docker compose "${COMPOSE_ARGS[@]}" stop "${SERVICES[@]}"
