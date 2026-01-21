#!/bin/bash
# Script to restart the DeniDin application gracefully

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Restarting DeniDin application..."
echo "=" * 50

# Stop the application if running
if [ -f "$SCRIPT_DIR/stop_denidin.sh" ]; then
    "$SCRIPT_DIR/stop_denidin.sh"
else
    echo "✗ stop_denidin.sh not found"
    exit 1
fi

# Wait a moment for cleanup
echo "Waiting for cleanup..."
sleep 2

# Start the application
if [ -f "$SCRIPT_DIR/run_denidin.sh" ]; then
    "$SCRIPT_DIR/run_denidin.sh"
else
    echo "✗ run_denidin.sh not found"
    exit 1
fi

echo "=" * 50
echo "✓ Restart complete"
