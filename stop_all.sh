#!/bin/bash
# Stops BOTH denidin-app and morning-mcp-app for a given environment - the
# symmetric counterpart to run_all.sh. Use this instead of calling
# stop_denidin.sh/stop_morning_mcp.sh individually, unless specifically
# asked to stop only one.
#
# Usage: ./stop_all.sh dev|prod [-force]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ENV="$1"
FORCE="$2"
if [ "$ENV" != "dev" ] && [ "$ENV" != "prod" ]; then
    echo "Usage: $0 dev|prod [-force]" >&2
    exit 1
fi

"$SCRIPT_DIR/apps/denidin-app/stop_denidin.sh" "$ENV" "$FORCE"
"$SCRIPT_DIR/apps/morning-mcp-app/stop_morning_mcp.sh" "$ENV" "$FORCE"
