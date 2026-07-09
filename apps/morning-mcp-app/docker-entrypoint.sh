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
except Exception:
    print('NGROK_AUTHTOKEN=')
    print('NGROK_DOMAIN=')
    print('MCP_PORT=8000')
" 2>/dev/null) || NGROK_CONFIG=""
eval "$NGROK_CONFIG"

mkdir -p /app/logs

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
        python3 -c "
import json, urllib.request
try:
    with urllib.request.urlopen('http://127.0.0.1:4040/api/tunnels', timeout=5) as resp:
        data = json.load(resp)
    print('ngrok public URL:', data['tunnels'][0]['public_url'])
except Exception as exc:
    print('Could not fetch ngrok public URL yet (check /app/logs/ngrok.log):', exc)
" || true
    fi
else
    echo "No mcp.ngrok_authtoken configured - server only reachable within the container network/port mapping."
fi

exec python3 -m denidin_mcp_morning.server
