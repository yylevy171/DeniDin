#!/bin/bash
# Script to stop the DeniDin bot gracefully

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIDFILE="$SCRIPT_DIR/.bot.pid"

# Check if PID file exists
if [ ! -f "$PIDFILE" ]; then
    echo "No PID file found. Bot may not be running."
    
    # Check for orphaned processes
    ORPHANED_PIDS=$(ps aux | grep "[p]ython.*denidin.py" | awk '{print $2}')
    if [ -n "$ORPHANED_PIDS" ]; then
        echo "Found orphaned bot process(es): $ORPHANED_PIDS"
        echo -n "Kill them? [y/N] "
        read -r response
        if [[ "$response" =~ ^[Yy]$ ]]; then
            kill $ORPHANED_PIDS
            echo "✓ Stopped orphaned processes"
        fi
    else
        echo "No bot processes found."
    fi
    exit 0
fi

# Read PID
BOT_PID=$(cat "$PIDFILE")

# Check if process is running
if ! ps -p "$BOT_PID" > /dev/null 2>&1; then
    echo "Bot process (PID $BOT_PID) is not running."
    rm -f "$PIDFILE"
    exit 0
fi

# Send SIGTERM for graceful shutdown
echo "Stopping bot (PID $BOT_PID)..."
kill -TERM "$BOT_PID"

# Wait for process to terminate (max 10 seconds)
for i in {1..10}; do
    if ! ps -p "$BOT_PID" > /dev/null 2>&1; then
        echo "✓ Bot stopped gracefully"
        rm -f "$PIDFILE"
        exit 0
    fi
    sleep 1
done

# If still running, force kill
if ps -p "$BOT_PID" > /dev/null 2>&1; then
    echo "Process didn't stop gracefully, forcing..."
    kill -9 "$BOT_PID"
    sleep 1
    if ! ps -p "$BOT_PID" > /dev/null 2>&1; then
        echo "✓ Bot stopped (forced)"
        rm -f "$PIDFILE"
    else
        echo "✗ Failed to stop bot"
        exit 1
    fi
fi
