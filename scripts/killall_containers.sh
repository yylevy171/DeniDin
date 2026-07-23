#!/bin/bash
# Tears down EVERY DeniDin container in EVERY environment - both apps, dev
# AND prod, unconditionally. Run this whenever switching environments, or to
# fully reset local state - see CLAUDE.md's "ONE ENVIRONMENT SET AT A TIME"
# rule: at most one full environment set (dev OR prod, never both) may be
# running, and this is the tool that guarantees a clean slate before
# starting the other one.
#
# Also used by each app's own in-container watchdog: on an env mismatch
# (this container's own `environment` config value disagrees with
# shared/active_env.json), the watchdog kills its app subprocess but leaves
# the container itself running (so its own crash-loop doesn't restart the
# app) - this script is what actually removes those now-app-less zombie
# containers, same as any other cleanup.
#
# Usage: ./scripts/killall_containers.sh [-force]
#
# If "dev" is currently locked to a DIFFERENT clone (coder) than the one
# running this script, this refuses to tear anything down unless -force is
# passed - see env_lock.sh. (prod carries no such lock; it's always killed.)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

FORCE="$1"
source "$SCRIPT_DIR/env_lock.sh"

ME="$(env_lock_identity)"
env_lock_ensure_shared_symlink
env_lock_read

if [ "$LOCK_ACTIVE_ENV" = "dev" ] && [ "$LOCK_OWNER" != "null" ] && [ "$LOCK_OWNER" != "$ME" ] && [ "$FORCE" != "-force" ]; then
    echo "ERROR: dev is locked by '$LOCK_OWNER', not '$ME'. Refusing to kill everything." >&2
    echo "       Pass -force to override (only if you're sure), or ask '$LOCK_OWNER' to free it first." >&2
    exit 1
fi

DEV_ARGS=(--project-directory "$REPO_ROOT" -f docker/docker-compose.dev.yml)
[ -f docker/docker-compose.dev.local.yml ] && DEV_ARGS+=(-f docker/docker-compose.dev.local.yml)
PROD_ARGS=(--project-directory "$REPO_ROOT" -f docker/docker-compose.prod.yml)
[ -f docker/docker-compose.prod.local.yml ] && PROD_ARGS+=(-f docker/docker-compose.prod.local.yml)

echo "Stopping and removing ALL dev containers..."
docker compose "${DEV_ARGS[@]}" down --remove-orphans || true

echo "Stopping and removing ALL prod containers..."
docker compose "${PROD_ARGS[@]}" down --remove-orphans || true

python3 -c "
import json
from datetime import datetime, timezone
with open('shared/active_env.json', 'w', encoding='utf-8') as f:
    json.dump({'active_env': None, 'owner': None, 'updated_at': datetime.now(timezone.utc).isoformat()}, f, indent=2)
    f.write('\n')
"

echo "shared/active_env.json reset to null/null (no environment active, no owner)."
echo "All environments torn down."
