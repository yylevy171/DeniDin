#!/bin/bash
# Single entrypoint for the Feature 068 Ledger Web UI. One argument selects the mode:
#
#   ./run_webapp.sh host                    host processes, no Docker: uvicorn :8100 +
#                                           Vite dev server :5173, live-reload, Ctrl-C stops
#                                           both. Backend uses backend/config/config.json
#                                           resolution. localhost only.
#
#   ./run_webapp.sh dev                     Docker Compose: webapp-backend-dev (:8100) +
#   ./run_webapp.sh prod                    webapp-frontend-dev nginx (:5100). Ports bind
#                                           0.0.0.0 -> reachable over LAN/WiFi, and for prod
#                                           over Tailscale Serve (HTTPS at the Windows box's
#                                           MagicDNS name, no port - already set up).
#                                           prod uses :8101/:5101.
#
# ENV-LOCK AGNOSTIC (2026-09-06): the webapp is a read-only viewer - it sends no WhatsApp
# traffic, polls no Green API instance, and mutates nothing. There is no contention on
# running it, so it does NOT acquire, release, check, or write the shared dev env-lock
# (shared/active_env.json) - start/stop it freely regardless of which clone "owns" dev.
# The dev/prod Docker modes STILL require this clone's per-clone volume override
# (docker-compose.<env>.local.yml): that guard is about dev-data path fragmentation across
# clones, not locking, and is mandatory for every service (real incident, 2026-07-30 - see
# CLAUDE.md).
#
# NOTE (dev/prod modes): this only (re)deploys the images already on disk - it does NOT
# rebuild on a code change. After editing webapp code run
#   docker compose --project-directory . -f docker/docker-compose.<env>.yml \
#       -f docker/docker-compose.<env>.local.yml build webapp-backend-<env> webapp-frontend-<env>
# first, or this keeps serving stale code (same rule as the other apps - see CLAUDE.md).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

MODE="$1"

case "$MODE" in
  host)
    cd "$SCRIPT_DIR/backend"
    [ -d venv ] || python3 -m venv venv
    ./venv/bin/pip -q install -r requirements.txt
    PYTHONPATH=src ./venv/bin/python -m uvicorn \
      webapp_backend.server:app_factory --factory --host 127.0.0.1 --port 8100 &
    BACKEND_PID=$!

    cd "$SCRIPT_DIR/frontend"
    [ -d node_modules ] || npm install
    npx vite --port 5173 &
    FRONTEND_PID=$!

    trap 'kill $BACKEND_PID $FRONTEND_PID 2>/dev/null' INT TERM EXIT
    echo ""
    echo "  mode    : host (no Docker, live-reload)"
    echo "  backend : http://127.0.0.1:8100/health   (config: $BACKEND_CONFIG)"
    echo "  frontend: http://localhost:5173"
    echo ""
    wait
    ;;

  dev|prod)
    ENV="$MODE"
    COMPOSE_FILE="$REPO_ROOT/docker/docker-compose.$ENV.yml"
    LOCAL_OVERRIDE="$REPO_ROOT/docker/docker-compose.$ENV.local.yml"
    SERVICES=("webapp-backend-$ENV" "webapp-frontend-$ENV")

    source "$REPO_ROOT/scripts/env_lock.sh"

    # MANDATORY per-clone volume override - refuses to start rather than silently falling
    # back to this clone's own dev-data paths (real incident, 2026-07-30). This is NOT the
    # env-lock: the webapp is lock-agnostic (see header) but still must not fragment dev data.
    env_lock_require_local_override "$ENV"

    COMPOSE_ARGS=(--project-directory "$REPO_ROOT" -f "$COMPOSE_FILE" -f "$LOCAL_OVERRIDE")

    docker compose "${COMPOSE_ARGS[@]}" up -d "${SERVICES[@]}"
    docker compose "${COMPOSE_ARGS[@]}" ps "${SERVICES[@]}"

    FPORT=$([ "$ENV" = "dev" ] && echo 5100 || echo 5101)
    BPORT=$([ "$ENV" = "dev" ] && echo 8100 || echo 8101)
    echo ""
    echo "Frontend: http://localhost:$FPORT  (backend :$BPORT)"
    echo "LAN/WiFi: http://<this-host-LAN-IP>:$FPORT  (Docker binds 0.0.0.0)"
    echo "Remote  : prod = https://yaronlaptop.tail274e9b.ts.net/  (Tailscale Serve, HTTPS, no port)"
    ;;

  *)
    echo "Usage: $0 host | dev | prod" >&2
    exit 1
    ;;
esac
