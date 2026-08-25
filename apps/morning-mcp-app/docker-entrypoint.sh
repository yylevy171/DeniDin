#!/bin/bash
# Docker entrypoint: optionally starts an ngrok tunnel (so the container is
# reachable from OpenAI's remote-MCP connector), then runs the MCP server as
# the main (PID 1) process so it receives signals directly for graceful
# shutdown (CONSTITUTION §XVI).
#
# ngrok is entirely opt-in: reads mcp.ngrok_authtoken/mcp.ngrok_domain from
# the mounted config/config.json via the app's own config loader (single
# source of truth for schema/defaults). If unset (the common case), this
# section no-ops and the container behaves exactly as before this feature
# was added.

set -e

CONFIG_FILE="/app/config/config.json"

NGROK_CONFIG=$(python3 -c "
from pathlib import Path
from denidin_mcp_morning.config import load_config
try:
    config = load_config(Path('$CONFIG_FILE'))
    print(f'NGROK_AUTHTOKEN={config.mcp_ngrok_authtoken or \"\"}')
    print(f'NGROK_DOMAIN={config.mcp_ngrok_domain or \"\"}')
    print(f'MCP_PORT={config.mcp_port}')
    print(f'STATUS_FILE={config.mcp_status_file or \"\"}')
except Exception:
    print('NGROK_AUTHTOKEN=')
    print('NGROK_DOMAIN=')
    print('MCP_PORT=8000')
    print('STATUS_FILE=')
" 2>/dev/null) || NGROK_CONFIG=""
eval "$NGROK_CONFIG"

mkdir -p /app/logs

resolve_status_path() {
    case "$STATUS_FILE" in
        /*) echo "$STATUS_FILE" ;;
        *)  echo "/app/$STATUS_FILE" ;;
    esac
}

# Delegates to denidin_mcp_morning.status_writer (019-env-separation, T009b)
# so the JSON shape/UTC-timestamp logic has one implementation, tested in
# tests/unit/test_status_writer.py, instead of being duplicated here in bash.
write_status_not_running() {
    if [ -z "$STATUS_FILE" ]; then
        return 0
    fi
    STATUS_PATH=$(resolve_status_path)
    python3 -c "
from pathlib import Path
from denidin_mcp_morning.status_writer import write_status_not_running
write_status_not_running(Path('$STATUS_PATH'))
"
}

write_status_running() {
    local public_url="$1"
    if [ -z "$STATUS_FILE" ]; then
        return 0
    fi
    STATUS_PATH=$(resolve_status_path)
    python3 -c "
from pathlib import Path
from denidin_mcp_morning.status_writer import write_status_running
write_status_running(Path('$STATUS_PATH'), '$public_url')
"
    echo "status file: $STATUS_PATH"
}

# Default to "not running" before attempting anything (Feature 018) - matches
# run_morning_mcp.sh's behavior so denidin-app sees an accurate state in every
# failure path, not just a stale or missing file.
write_status_not_running

if [ -n "$NGROK_AUTHTOKEN" ]; then
    if ! command -v ngrok >/dev/null 2>&1; then
        echo "WARNING: mcp.ngrok_authtoken is configured, but ngrok is not installed in this image."
    else
        ngrok config add-authtoken "$NGROK_AUTHTOKEN" >/dev/null 2>&1 || true
        if [ -n "$NGROK_DOMAIN" ]; then
            echo "Starting ngrok tunnel (reserved domain) -> https://$NGROK_DOMAIN"
            ngrok http --domain="$NGROK_DOMAIN" "$MCP_PORT" --log=stdout > /app/logs/ngrok.log 2>&1 &
        else
            echo "Starting ngrok tunnel (free tier, random URL)..."
            ngrok http "$MCP_PORT" --log=stdout > /app/logs/ngrok.log 2>&1 &
        fi

        # Give ngrok a moment to establish the tunnel, then print the
        # assigned public URL for operator convenience (best-effort; if it
        # fails, the server still starts normally below).
        sleep 2
        PUBLIC_URL=$(python3 -c "
import json, urllib.request
try:
    with urllib.request.urlopen('http://127.0.0.1:4040/api/tunnels', timeout=5) as resp:
        data = json.load(resp)
    print(data['tunnels'][0]['public_url'])
except Exception:
    print('')
" 2>/dev/null) || PUBLIC_URL=""
        if [ -n "$PUBLIC_URL" ]; then
            echo "ngrok public URL: $PUBLIC_URL"
        else
            echo "Could not fetch ngrok public URL yet (check /app/logs/ngrok.log)"
        fi

        # Publish the status file (Feature 018) so denidin-app can discover
        # this container's current tunnel URL. No-op if mcp.status_file unset.
        if [[ "$PUBLIC_URL" == https://* ]]; then
            write_status_running "$PUBLIC_URL"
        fi
    fi
else
    echo "No mcp.ngrok_authtoken configured - server only reachable within the container network/port mapping."
fi

# watchdog.py runs as PID 1 from here on (2026-07-21, env-mismatch incident
# response): it spawns the actual server as a child process, forwards
# SIGINT/SIGTERM to it, and periodically confirms this container's own
# declared environment still matches shared/active_env.json - both via an
# internal localhost /health check and an external check through this same
# ngrok tunnel just started above - tearing the server subprocess down
# (without exiting the container itself) on any mismatch.
exec python3 watchdog.py
