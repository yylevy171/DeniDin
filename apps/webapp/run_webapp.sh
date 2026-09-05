#!/bin/bash
# Starts the Feature 068 Ledger Web UI (webapp-backend + webapp-frontend + cloudflared)
# for a given environment as Docker Compose services. Containers only, same env-lock
# discipline as run_morning_mcp.sh / run_denidin.sh.
#
# Usage: ./run_webapp.sh dev|prod
#
# NOTE: this only (re)deploys the images already on disk - it does NOT build. After any
# code change run `docker compose ... build` for the webapp services first, or this keeps
# serving stale code (same rule as the other apps - see CLAUDE.md).

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
SERVICES=("webapp-backend-$ENV" "webapp-frontend-$ENV" "cloudflared-$ENV")

# "dev" is locked to whichever clone acquires it - see scripts/env_lock.sh.
source "$REPO_ROOT/scripts/env_lock.sh"

# MANDATORY per-clone override - refuses to start rather than silently falling back to this
# clone's own volume paths (real incident, 2026-07-30).
env_lock_require_local_override "$ENV"

COMPOSE_ARGS=(--project-directory "$REPO_ROOT" -f "$COMPOSE_FILE" -f "$LOCAL_OVERRIDE")

# Declare intent in the shared active-env file BEFORE starting - watchdog.py in every
# denidin-app / morning-mcp-app container checks this and tears itself down on a mismatch.
env_lock_acquire "$ENV"

docker compose "${COMPOSE_ARGS[@]}" up -d "${SERVICES[@]}"
docker compose "${COMPOSE_ARGS[@]}" ps "${SERVICES[@]}"

echo ""
echo "Frontend: http://localhost:$([ "$ENV" = "dev" ] && echo 5100 || echo 5101)  (backend :$([ "$ENV" = "dev" ] && echo 8100 || echo 8101))"
echo "Remote:   via the $ENV Cloudflare Tunnel (needs docker/cloudflared.$ENV.env - see quickstart.md)"
