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
# Usage: ./killall_containers.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Stopping and removing ALL dev containers..."
docker compose -f docker-compose.dev.yml down --remove-orphans || true

echo "Stopping and removing ALL prod containers..."
docker compose -f docker-compose.prod.yml down --remove-orphans || true

python3 -c "
import json
from datetime import datetime, timezone
with open('shared/active_env.json', 'w', encoding='utf-8') as f:
    json.dump({'active_env': None, 'updated_at': datetime.now(timezone.utc).isoformat()}, f, indent=2)
    f.write('\n')
"

echo "shared/active_env.json reset to null (no environment active)."
echo "All environments torn down."
