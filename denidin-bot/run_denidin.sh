#!/bin/bash
# Script to run DeniDin bot with single-instance enforcement
# Checks for existing bot processes and prevents duplicates

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOT_SCRIPT="denidin.py"
PIDFILE="$SCRIPT_DIR/.bot.pid"
LOGFILE="$SCRIPT_DIR/logs/bot.log"

# Ensure logs directory exists
mkdir -p "$SCRIPT_DIR/logs"

# Function to check if process is running
is_running() {
    local pid=$1
    if [ -z "$pid" ]; then
        return 1
    fi
    
    # Check if PID exists and is a python process running denidin.py
    if ps -p "$pid" > /dev/null 2>&1; then
        # Verify it's actually our bot
        if ps -p "$pid" -o command= | grep -q "python.*denidin.py"; then
            return 0
        fi
    fi
    return 1
}

# Check for existing PID file
if [ -f "$PIDFILE" ]; then
    OLD_PID=$(cat "$PIDFILE")
    if is_running "$OLD_PID"; then
        echo "ERROR: Bot is already running with PID $OLD_PID"
        echo "To stop it, run: kill $OLD_PID"
        echo "Or use: ./stop_denidin.sh"
        exit 1
    else
        echo "Cleaning up stale PID file (process $OLD_PID not running)"
        rm -f "$PIDFILE"
    fi
fi

# Double-check for any orphaned bot processes (in case PID file was deleted)
ORPHANED_PIDS=$(ps aux | grep "[p]ython.*denidin.py" | awk '{print $2}')
if [ -n "$ORPHANED_PIDS" ]; then
    echo "ERROR: Found orphaned bot process(es): $ORPHANED_PIDS"
    echo "Please stop them manually first:"
    echo "  kill $ORPHANED_PIDS"
    exit 1
fi

# Start the bot
cd "$SCRIPT_DIR"
echo "Starting DeniDin bot..."
echo "Logs: $LOGFILE"

# Run bot in background with proper redirection
# Use setsid to start in new session (detach from terminal)
python3 "$BOT_SCRIPT" < /dev/null >> "$LOGFILE" 2>&1 &
BOT_PID=$!

# Disown the process so it doesn't receive SIGHUP
disown $BOT_PID 2>/dev/null || true

# Save PID to file
echo "$BOT_PID" > "$PIDFILE"

# Wait a moment and verify it started
sleep 3
if is_running "$BOT_PID"; then
    echo "✓ Bot started successfully (PID: $BOT_PID)"
    echo "To view logs: tail -f $LOGFILE"
    echo "To stop bot: ./stop_denidin.sh"
else
    echo "✗ Bot failed to start. Check logs at: $LOGFILE"
    rm -f "$PIDFILE"
    exit 1
fi
