#!/bin/bash
# Tears down EVERY DeniDin container in EVERY environment - both apps, dev
# AND prod, unconditionally. Run this to fully reset local state, or when
# unsure what's currently running. (2026-08-05: dev and prod may now run
# concurrently - see CLAUDE.md's "Environments (dev/prod)" section - so this
# is no longer "the tool that guarantees a clean slate before starting the
# other one"; it's just an unconditional full-reset hammer.)
#
# Also used by each app's own in-container watchdog: on an env mismatch
# (this container's own `environment` config value isn't currently declared
# active in shared/active_env.json), the watchdog kills its app subprocess
# but leaves the container itself running (so its own crash-loop doesn't
# restart the app) - this script is what actually removes those now-app-less
# zombie containers, same as any other cleanup.
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

if [ "$LOCK_DEV_ACTIVE" = "true" ] && [ "$LOCK_DEV_OWNER" != "null" ] && [ "$LOCK_DEV_OWNER" != "$ME" ] && [ "$FORCE" != "-force" ]; then
    echo "ERROR: dev is locked by '$LOCK_DEV_OWNER', not '$ME'. Refusing to kill everything." >&2
    echo "       Pass -force to override (only if you're sure), or ask '$LOCK_DEV_OWNER' to free it first." >&2
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
    json.dump({'active_envs': {}, 'updated_at': datetime.now(timezone.utc).isoformat()}, f, indent=2)
    f.write('\n')
"

echo "shared/active_env.json reset to active_envs: {} (no environment active for anyone)."
echo "All environments torn down."
