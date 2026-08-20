# Quickstart — MCP → Morning Invoice Management (local dev)

All commands below run from `apps/morning-mcp-app/`.

## 1. Set up the environment

**Requires Python 3.10+** (the `mcp` SDK does not support 3.9; developed against 3.11).

```bash
cd apps/morning-mcp-app
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

## 2. Configure

Copy the example config and fill in your Morning sandbox credentials. The shape is **flat**
(not nested) — this matches the real, committed `config/config.example.json`:

```bash
cp config/config.example.json config/config.json
```

```json
{
  "api_key_id": "PASTE_YOUR_MORNING_API_KEY_ID_HERE",
  "api_key_secret": "PASTE_YOUR_MORNING_API_KEY_SECRET_HERE",
  "api_url": "https://sandbox.d.greeninvoice.co.il/api/v1/",
  "default_currency": "ILS",
  "default_vat_rate": 0.17,
  "token_ttl_seconds": 3600,
  "refresh_before_seconds": 300,
  "rate_limit_per_second": 3,
  "mcp": {
    "server_name": "denidin-morning",
    "host": "127.0.0.1",
    "port": 8000,
    "transport": "streamable-http",
    "log_level": "INFO"
  },
  "feature_flags": {
    "enable_mcp_server": true
  }
}
```

`feature_flags.enable_mcp_server` **must be `true`** to start the server — this is the
Constitution §I/§VI safety gate; with it `false` (the default), `server.py` exits
immediately with a clear message rather than starting.

## 3. Run the tests

```bash
python3 -m pytest tests/ -v --tb=short
```

Integration tests hit the real Morning **sandbox** (free, no mocking, per this repo's
Constitution) — they skip gracefully if `config/config.test.json` lacks real credentials.

## 4. Start the MCP server

```bash
python3 -m denidin_mcp_morning.server
```

This starts a **FastMCP** server over **streamable-HTTP** on the configured host/port
(default `127.0.0.1:8000`), exposing all 7 invoice-management tools:
`create_invoice`, `list_invoices`, `get_invoice_details`, `update_invoice_status`,
`add_client`, `get_financial_summary`, `download_invoice_pdf`.

Point any MCP client (e.g. an OpenAI model via its remote-MCP connector, or the official
`mcp` Python client) at `http://127.0.0.1:8000/mcp`.

### Quick manual check with the MCP Python client

```python
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

async def main():
    async with streamable_http_client("http://127.0.0.1:8000/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print([t.name for t in tools.tools])

            result = await session.call_tool(
                "create_invoice",
                {"client_name": "Test Corp", "amount": 100.0, "description": "Consulting"},
            )
            print(result.content[0].text)

asyncio.run(main())
```

## 5. Docker

```bash
docker build -t morning-mcp-app .
docker run --rm -p 8000:8000 -v "$(pwd)/config:/app/config:ro" morning-mcp-app
```

Same feature-flag gate applies — the container exits immediately unless
`feature_flags.enable_mcp_server: true` is set in the mounted `config/config.json`.

## Notes

- No environment variables anywhere — all config comes from `config/config.json`
  (CONSTITUTION §I). Never commit real credentials; `config/config.json` is gitignored.
- There is no `send_invoice` tool — Morning's public API has no documented delivery
  endpoint (investigated and dropped; see `spec.md` §Scope). Use `get_invoice_details` +
  `download_invoice_pdf` to assemble what's needed, then deliver via your own channel.
- Webhook/file-upload flows (receipt parsing) are a **separate, deferred** feature —
  see `specs/in-definition/017-mcp-morning-receipt-parsing/`, not this quickstart.
