FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Package lives under src/ (see conftest.py for the equivalent test-time setup);
# set PYTHONPATH so it's importable for any in-container usage, not just pytest.
ENV PYTHONPATH=/app/src

VOLUME ["/app/config"]

# server.py (FastMCP over streamable-HTTP) is being built incrementally per
# specs/in-definition/005-mcp-morning-green-receipt/tasks.md (Phase 3, T013).
# Until it lands, this placeholder keeps the container running so it can be
# exec'd into / used as a base for local iteration, without implying
# functionality that doesn't exist. Once server.py exists, replace with:
#   CMD ["python3", "-m", "denidin_mcp_morning.server"]
CMD ["tail", "-f", "/dev/null"]
