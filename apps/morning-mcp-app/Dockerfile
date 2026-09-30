FROM python:3.11-slim

WORKDIR /app

# ngrok (opt-in, only used if mcp.ngrok_authtoken is set in the mounted
# config/config.json — see docker-entrypoint.sh) so the container can be
# made reachable from OpenAI's remote-MCP connector without a separate
# sidecar/host-level tunnel process. Official Debian apt install per
# https://ngrok.com/download/linux (bookworm matches this base image).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gnupg ca-certificates \
    && curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc | tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null \
    && echo "deb https://ngrok-agent.s3.amazonaws.com bookworm main" | tee /etc/apt/sources.list.d/ngrok.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends ngrok \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x docker-entrypoint.sh

# Package lives under src/ (see conftest.py for the equivalent test-time setup);
# set PYTHONPATH so it's importable for any in-container usage, not just pytest.
ENV PYTHONPATH=/app/src

# bugfix-067 (2026-09-26): NO `VOLUME ["/app/config"]`. Declaring it made Docker attach an ANONYMOUS
# volume at /app/config that `docker compose up -d` reuses across recreates, freezing whatever
# config files it held at first creation and hiding the image's own (the same trap bugfix-062 hit for
# denidin-app). Everything under /app/config except config.json is baked into the image and must be
# used as shipped; only config.<env>.json is bind-mounted over /app/config/config.json by compose.

# Starts the FastMCP server (streamable-HTTP), optionally behind an ngrok
# tunnel (see docker-entrypoint.sh). Server startup itself is still gated
# behind feature_flags.enable_mcp_server in the mounted config/config.json
# (default false, per CONSTITUTION §I/§VI) — with the flag off, the process
# exits immediately with a clear message rather than serving nothing silently.
EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
