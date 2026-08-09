#!/bin/bash
# Starts BOTH denidin-app and morning-mcp-app for a given environment.
# The two apps within one environment are still bundled - neither app's
# container may run alone (see CLAUDE.md's "Environments (dev/prod)"
# section). Use this instead of calling run_denidin.sh/run_morning_mcp.sh
# individually, unless specifically asked to start only one. (Dev and prod
# themselves may now run concurrently - see the same section - but that's
# orthogonal to this per-environment app-pairing rule, which is unchanged.)
#
# Order matters (2026-08-07): morning-mcp-app starts FIRST, denidin-app
# SECOND - denidin-app depends on morning-mcp-app (it discovers and calls
# the Morning MCP tunnel at startup/per-request), never the other way
# around, so morning-mcp-app must already be up before denidin-app starts.
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

"$REPO_ROOT/apps/morning-mcp-app/run_morning_mcp.sh" "$ENV"
"$REPO_ROOT/apps/denidin-app/run_denidin.sh" "$ENV"
