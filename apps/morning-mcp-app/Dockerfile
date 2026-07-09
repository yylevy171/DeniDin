FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Package lives under src/ (see conftest.py for the equivalent test-time setup);
# set PYTHONPATH so it's importable for any in-container usage, not just pytest.
ENV PYTHONPATH=/app/src

VOLUME ["/app/config"]

# Starts the FastMCP server (streamable-HTTP). Startup is gated behind
# feature_flags.enable_mcp_server in the mounted config/config.json (default
# false, per CONSTITUTION §I/§VI) — with the flag off, the process exits
# immediately with a clear message rather than serving nothing silently.
EXPOSE 8000
CMD ["python3", "-m", "denidin_mcp_morning.server"]
