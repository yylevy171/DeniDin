#!/bin/bash
# Script to restart the morning-mcp-app MCP server gracefully
# Mirrors apps/denidin-app/restart_denidin.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Restarting morning-mcp-app MCP server..."
echo "================================================"

# Stop the application if running
if [ -f "$SCRIPT_DIR/stop_morning_mcp.sh" ]; then
    "$SCRIPT_DIR/stop_morning_mcp.sh"
else
    echo "✗ stop_morning_mcp.sh not found"
    exit 1
fi

# Wait a moment for cleanup
echo "Waiting for cleanup..."
sleep 2

# Start the application
if [ -f "$SCRIPT_DIR/run_morning_mcp.sh" ]; then
    "$SCRIPT_DIR/run_morning_mcp.sh"
else
    echo "✗ run_morning_mcp.sh not found"
    exit 1
fi

echo "================================================"
echo "✓ Restart complete"
