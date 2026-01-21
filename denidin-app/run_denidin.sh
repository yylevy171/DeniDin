#!/bin/bash
# Script to run DeniDin application with single-instance enforcement
# Checks for existing application processes and prevents duplicates

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_SCRIPT="denidin.py"
PIDFILE="$SCRIPT_DIR/.denidin.pid"
LOGFILE="$SCRIPT_DIR/logs/denidin.log"

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
        # Verify it's actually our application (case-insensitive match)
        if ps -p "$pid" -o command= | grep -iq "python.*denidin\.py"; then
            return 0
        fi
    fi
    return 1
}

# Check for existing PID file
if [ -f "$PIDFILE" ]; then
    OLD_PID=$(cat "$PIDFILE")
    if is_running "$OLD_PID"; then
        echo "ERROR: Application is already running with PID $OLD_PID"
        echo "To stop it, run: kill $OLD_PID"
        echo "Or use: ./stop_denidin.sh"
        echo ""
        echo "Running process:"
        ps -p "$OLD_PID" -o pid,etime,command
        exit 1
    else
        echo "Cleaning up stale PID file (process $OLD_PID not running)"
        rm -f "$PIDFILE"
    fi
fi

# Double-check for any orphaned application processes (in case PID file was deleted)
ORPHANED_PIDS=$(ps aux | grep "[p]ython.*denidin.py" | awk '{print $2}')
if [ -n "$ORPHANED_PIDS" ]; then
    echo "ERROR: Found orphaned application process(es): $ORPHANED_PIDS"
    echo "Please stop them manually first:"
    echo "  kill $ORPHANED_PIDS"
    exit 1
fi

# Start the application
cd "$SCRIPT_DIR"
echo "Starting DeniDin application..."
echo "Logs: $LOGFILE"

# Run application in background with proper redirection
# Use nohup to prevent SIGHUP and keep process alive when terminal closes
# Important: Redirect order matters - stdin first, then stdout/stderr
nohup python3 "$APP_SCRIPT" </dev/null >>"$LOGFILE" 2>&1 &
APP_PID=$!

# Give the shell a moment to fork the process
sleep 0.5

# Save PID to file
echo "$APP_PID" > "$PIDFILE"

# Wait a moment and verify it started
# Application takes time to initialize (connect to WhatsApp API, load memory, etc.)
sleep 5
if is_running "$APP_PID"; then
    echo "✓ Application started successfully"
    echo ""
    echo "Process info:"
    ps -p "$APP_PID" -o pid,etime,command
    echo ""
    echo "To view logs: tail -f $LOGFILE"
    echo "To stop application: ./stop_denidin.sh"
else
    echo "✗ Application failed to start. Check logs at: $LOGFILE"
    rm -f "$PIDFILE"
    exit 1
fi
