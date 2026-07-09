#!/bin/bash
# Script to run the morning-mcp-app MCP server with single-instance enforcement
# Checks for existing application processes and prevents duplicates
# Mirrors apps/denidin-app/run_denidin.sh

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_MODULE="denidin_mcp_morning.server"
PIDFILE="$SCRIPT_DIR/.morning_mcp.pid"
LOGFILE="$SCRIPT_DIR/logs/morning-mcp.log"
NGROK_PIDFILE="$SCRIPT_DIR/.ngrok.pid"
NGROK_LOGFILE="$SCRIPT_DIR/logs/ngrok.log"
CONFIG_FILE="$SCRIPT_DIR/config/config.json"

# Prefer this app's own venv (it needs Python 3.10+ and the `mcp` package,
# which a bare ambient `python3` may not have/satisfy) - fall back to
# whatever `python3` resolves to if no local venv exists.
if [ -x "$SCRIPT_DIR/venv/bin/python3" ]; then
    PYTHON_BIN="$SCRIPT_DIR/venv/bin/python3"
else
    echo "WARNING: $SCRIPT_DIR/venv not found - falling back to ambient 'python3'."
    echo "         Run setup first: python3.11 -m venv venv && venv/bin/pip install -r requirements.txt"
    PYTHON_BIN="python3"
fi

# Ensure logs directory exists
mkdir -p "$SCRIPT_DIR/logs"

# Function to check if process is running
is_running() {
    local pid=$1
    if [ -z "$pid" ]; then
        return 1
    fi

    # Check if PID exists and is a python process running our server module
    if ps -p "$pid" > /dev/null 2>&1; then
        # Verify it's actually our application (case-insensitive match)
        if ps -p "$pid" -o command= | grep -iq "python.*denidin_mcp_morning\.server"; then
            return 0
        fi
    fi
    return 1
}

# Function to check if the ngrok tunnel process is running
is_ngrok_running() {
    local pid=$1
    if [ -z "$pid" ]; then
        return 1
    fi
    if ps -p "$pid" > /dev/null 2>&1; then
        if ps -p "$pid" -o command= | grep -iq "ngrok"; then
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
        echo "Or use: ./stop_morning_mcp.sh"
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
ORPHANED_PIDS=$(ps aux | grep "[p]ython.*denidin_mcp_morning\.server" | awk '{print $2}')
if [ -n "$ORPHANED_PIDS" ]; then
    echo "ERROR: Found orphaned application process(es): $ORPHANED_PIDS"
    echo "Please stop them manually first:"
    echo "  kill $ORPHANED_PIDS"
    exit 1
fi

# Start the application
cd "$SCRIPT_DIR"
export PYTHONPATH="$SCRIPT_DIR/src"
echo "Starting morning-mcp-app MCP server..."
echo "Logs: $LOGFILE"

# Run application in background with proper redirection
# Redirect only stdin to /dev/null - let Python logger handle file output
# This prevents duplicate logs (shell redirection + Python file handler)
nohup "$PYTHON_BIN" -m "$APP_MODULE" </dev/null >/dev/null 2>&1 &
APP_PID=$!

# Give the shell a moment to fork the process
sleep 0.5

# Save PID to file
echo "$APP_PID" > "$PIDFILE"

# Wait a moment and verify it started
# (also catches the case where feature_flags.enable_mcp_server=false, which
# makes the process exit immediately by design - see server.py)
sleep 3
if is_running "$APP_PID"; then
    echo "✓ Application started successfully"
    echo ""
    echo "Process info:"
    ps -p "$APP_PID" -o pid,etime,command
    echo ""
    echo "To view logs: tail -f $LOGFILE"
    echo "To stop application: ./stop_morning_mcp.sh"
else
    echo "✗ Application failed to start. Check logs at: $LOGFILE"
    echo "  (Common cause: feature_flags.enable_mcp_server is false in config/config.json)"
    rm -f "$PIDFILE"
    exit 1
fi

# --- Optional ngrok tunnel (Phase 5, T021) ---
# Only attempted if the server itself started successfully. Reads
# mcp.ngrok_authtoken/mcp.ngrok_domain via our own config loader (so schema
# validation/defaults stay in one place); no-ops entirely if either is unset
# - this is the common case and changes nothing about local/CI behavior.
NGROK_CONFIG=$(PYTHONPATH="$SCRIPT_DIR/src" "$PYTHON_BIN" -c "
from pathlib import Path
from denidin_mcp_morning.config import load_config
try:
    config = load_config(Path('$CONFIG_FILE'))
    print(f'NGROK_AUTHTOKEN={config.mcp_ngrok_authtoken or \"\"}')
    print(f'NGROK_DOMAIN={config.mcp_ngrok_domain or \"\"}')
    print(f'MCP_PORT={config.mcp_port}')
except Exception:
    print('NGROK_AUTHTOKEN=')
    print('NGROK_DOMAIN=')
    print('MCP_PORT=8000')
" 2>/dev/null) || NGROK_CONFIG=""
eval "$NGROK_CONFIG"

# NOTE: ngrok's free tier only requires an authtoken (free account, no
# payment) - a reserved/static domain is a PAID feature. mcp.ngrok_domain is
# therefore optional here: if unset, we start a plain (free) tunnel with a
# random URL and print it by querying ngrok's local API
# (http://127.0.0.1:4040/api/tunnels) after startup, since the URL isn't
# known ahead of time in that case.
if [ -n "$NGROK_AUTHTOKEN" ]; then
    if ! command -v ngrok >/dev/null 2>&1; then
        echo ""
        echo "WARNING: mcp.ngrok_authtoken is configured, but the 'ngrok' CLI is not"
        echo "         installed. Server is running locally only (no public tunnel)."
        echo "         Install: brew install --cask ngrok  (or https://ngrok.com/download)"
    elif [ -f "$NGROK_PIDFILE" ] && is_ngrok_running "$(cat "$NGROK_PIDFILE")"; then
        echo ""
        echo "ngrok tunnel already running (PID $(cat "$NGROK_PIDFILE")) - not starting a second one."
    else
        echo ""
        ngrok config add-authtoken "$NGROK_AUTHTOKEN" >/dev/null 2>&1 || true
        if [ -n "$NGROK_DOMAIN" ]; then
            echo "Starting ngrok tunnel (reserved domain) -> https://$NGROK_DOMAIN"
            nohup ngrok http --domain="$NGROK_DOMAIN" "$MCP_PORT" </dev/null >"$NGROK_LOGFILE" 2>&1 &
        else
            echo "Starting ngrok tunnel (free tier, random URL)..."
            nohup ngrok http "$MCP_PORT" </dev/null >"$NGROK_LOGFILE" 2>&1 &
        fi
        NGROK_PID=$!
        sleep 0.5
        echo "$NGROK_PID" > "$NGROK_PIDFILE"
        sleep 2
        if is_ngrok_running "$NGROK_PID"; then
            if [ -n "$NGROK_DOMAIN" ]; then
                PUBLIC_URL="https://$NGROK_DOMAIN"
            else
                PUBLIC_URL=$("$PYTHON_BIN" -c "
import json, urllib.request
try:
    with urllib.request.urlopen('http://127.0.0.1:4040/api/tunnels', timeout=5) as resp:
        data = json.load(resp)
    print(data['tunnels'][0]['public_url'])
except Exception:
    print('(check http://127.0.0.1:4040 for the assigned URL)')
" 2>/dev/null)
            fi
            echo "✓ ngrok tunnel started (PID $NGROK_PID) -> $PUBLIC_URL"
            echo "  ngrok logs: $NGROK_LOGFILE"
            echo "  ngrok local inspector: http://127.0.0.1:4040"
        else
            echo "✗ ngrok tunnel failed to start. Check $NGROK_LOGFILE"
            rm -f "$NGROK_PIDFILE"
        fi
    fi
fi
