#!/bin/bash
# Starts BOTH denidin-app and morning-mcp-app for a given environment.
# CLAUDE.md's "ONE ENVIRONMENT SET AT A TIME" rule requires them bundled -
# neither app's container may run alone. Use this instead of calling
# run_denidin.sh/run_morning_mcp.sh individually, unless specifically asked
# to start only one.
#
# Usage: ./scripts/run_all.sh dev|prod

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

ENV="$1"
if [ "$ENV" != "dev" ] && [ "$ENV" != "prod" ]; then
    echo "Usage: $0 dev|prod" >&2
    exit 1
fi

"$REPO_ROOT/apps/denidin-app/run_denidin.sh" "$ENV"
"$REPO_ROOT/apps/morning-mcp-app/run_morning_mcp.sh" "$ENV"
