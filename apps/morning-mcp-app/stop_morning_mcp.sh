#!/bin/bash
# Script to stop the morning-mcp-app MCP server gracefully
# Mirrors apps/denidin-app/stop_denidin.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDFILE="$SCRIPT_DIR/.morning_mcp.pid"
NGROK_PIDFILE="$SCRIPT_DIR/.ngrok.pid"

# Stop the ngrok tunnel (if one was started by run_morning_mcp.sh) whenever
# this script exits, regardless of which path/exit code below was taken.
stop_ngrok_if_running() {
    if [ ! -f "$NGROK_PIDFILE" ]; then
        return 0
    fi
    local ngrok_pid
    ngrok_pid=$(cat "$NGROK_PIDFILE")
    if ps -p "$ngrok_pid" > /dev/null 2>&1 && ps -p "$ngrok_pid" -o command= | grep -iq "ngrok"; then
        echo "Stopping ngrok tunnel (PID $ngrok_pid)..."
        kill -TERM "$ngrok_pid" 2>/dev/null || true
        sleep 1
        if ps -p "$ngrok_pid" > /dev/null 2>&1; then
            kill -9 "$ngrok_pid" 2>/dev/null || true
        fi
        echo "✓ ngrok tunnel stopped"
    fi
    rm -f "$NGROK_PIDFILE"
}
trap stop_ngrok_if_running EXIT

# Check if PID file exists
if [ ! -f "$PIDFILE" ]; then
    echo "No PID file found. Application may not be running."

    # Check for orphaned processes
    ORPHANED_PIDS=$(ps aux | grep "[p]ython.*denidin_mcp_morning\.server" | awk '{print $2}')
    if [ -n "$ORPHANED_PIDS" ]; then
        echo "Found orphaned application process(es): $ORPHANED_PIDS"
        echo -n "Kill them? [y/N] "
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            kill $ORPHANED_PIDS
            echo "✓ Stopped orphaned processes"
        fi
    else
        echo "No application processes found."
    fi
    exit 0
fi

# Read PID
APP_PID=$(cat "$PIDFILE")

# Check if process is running
if ! ps -p "$APP_PID" > /dev/null 2>&1; then
    echo "Application process (PID $APP_PID) is not running."
    rm -f "$PIDFILE"
    exit 0
fi

# Show process info before stopping
echo "Stopping application:"
ps -p "$APP_PID" -o pid,etime,command
echo ""

# Send SIGTERM for graceful shutdown
echo "Sending SIGTERM to PID $APP_PID..."
kill -TERM "$APP_PID"

# Wait for process to terminate (max 10 seconds)
for i in {1..10}; do
    if ! ps -p "$APP_PID" > /dev/null 2>&1; then
        echo "✓ Application stopped gracefully (PID $APP_PID)"
        rm -f "$PIDFILE"
        exit 0
    fi
    sleep 1
done

# If still running, force kill
if ps -p "$APP_PID" > /dev/null 2>&1; then
    echo "Process didn't stop gracefully, forcing..."
    kill -9 "$APP_PID"
    sleep 1
    if ! ps -p "$APP_PID" > /dev/null 2>&1; then
        echo "✓ Application stopped (forced) (PID $APP_PID)"
        rm -f "$PIDFILE"
    else
        echo "✗ Failed to stop application (PID $APP_PID)"
        exit 1
    fi
fi
