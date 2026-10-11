#!/bin/bash
# Stops the Feature 068 webapp, denidin-app and morning-mcp-app for a given
# environment - the symmetric counterpart to run_all.sh (reverse order:
# webapp -> denidin-app -> morning-mcp-app). Use this instead of calling the
# per-app stop scripts individually, unless specifically asked to stop one.
#
# Order matters (2026-08-07): denidin-app stops FIRST, morning-mcp-app
# SECOND - the reverse of run_all.sh's start order. denidin-app depends on
# morning-mcp-app (never the other way around), so the dependent stops
# before the dependency, same principle as run_all.sh, applied in reverse.
# Do not "fix" this to match run_all.sh's literal order - it's intentional.
#
# Usage: ./scripts/stop_all.sh dev|prod [-force]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

ENV="$1"
FORCE="$2"
if [ "$ENV" != "dev" ] && [ "$ENV" != "prod" ]; then
    echo "Usage: $0 dev|prod [-force]" >&2
    exit 1
fi

"$REPO_ROOT/apps/webapp/stop_webapp.sh" "$ENV" "$FORCE"
"$REPO_ROOT/apps/denidin-app/stop_denidin.sh" "$ENV" "$FORCE"
"$REPO_ROOT/apps/morning-mcp-app/stop_morning_mcp.sh" "$ENV" "$FORCE"
