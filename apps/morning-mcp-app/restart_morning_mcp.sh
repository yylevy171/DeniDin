#!/bin/bash
# Script to restart the morning-mcp-app MCP server gracefully (Docker Compose,
# per environment - 019-env-separation).
#
# Usage: ./restart_morning_mcp.sh dev|prod

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

ENV="$1"
if [ "$ENV" != "dev" ] && [ "$ENV" != "prod" ]; then
    echo "Usage: $0 dev|prod" >&2
    exit 1
fi

echo "Restarting morning-mcp-app-$ENV..."
echo "================================================"

"$SCRIPT_DIR/stop_morning_mcp.sh" "$ENV"

echo "Waiting for cleanup..."
sleep 2

"$SCRIPT_DIR/run_morning_mcp.sh" "$ENV"

echo "================================================"
echo "✓ Restart complete"
