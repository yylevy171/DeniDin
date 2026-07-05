FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Package lives under src/ (see conftest.py for the equivalent test-time setup);
# set PYTHONPATH so it's importable for any in-container usage, not just pytest.
ENV PYTHONPATH=/app/src

VOLUME ["/app/config"]

# No MCP server exists yet (structural split only — see README "Status").
# This placeholder keeps the container running so it can be exec'd into /
# used as a base for local iteration, without implying functionality that
# doesn't exist. Once the MCP server exists (see
# specs/in-definition/005-mcp-morning-green-receipt/plan.md), replace with:
#   CMD ["python3", "-m", "uvicorn", "denidin_mcp_morning.server:app", "--host", "0.0.0.0", "--port", "8080"]
CMD ["tail", "-f", "/dev/null"]
