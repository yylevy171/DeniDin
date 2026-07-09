# morning-mcp-app

Standalone client for the Morning (Green Invoice) API — Israeli invoicing/receipts.

## Status

This app ships a working FastMCP server (`src/denidin_mcp_morning/server.py`,
streamable-HTTP) exposing 7 invoice-management tools — `create_invoice`,
`list_invoices`, `get_invoice_details`, `update_invoice_status`, `add_client`,
`get_financial_summary`, `download_invoice_pdf` — backed by the real Morning
sandbox API, per `specs/in-definition/005-mcp-morning-green-receipt/plan.md`
and `tasks.md`. (`send_invoice` was investigated and dropped — Morning's
public API has no documented delivery endpoint; see `spec.md` §Scope.)

This app was split out of the main `denidin-app` monorepo so that the MCP server
has its own independently runnable, testable, and deployable home.

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full layer-by-layer breakdown
(config → auth → client → tools → server), the request-flow diagram, and the
current implementation status per layer.

## Setup

**Requires Python 3.10+** (the `mcp` SDK does not support 3.9). Developed against
3.11 to match `apps/denidin-app`'s recommended version.

```bash
cd apps/morning-mcp-app
python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp config/config.example.json config/config.json  # then fill in real credentials
```

## Configuration

`config/config.json` (gitignored, real credentials) — flat shape:
```json
{
  "api_key_id": "YOUR_MORNING_API_KEY_ID",
  "api_key_secret": "YOUR_MORNING_API_KEY_SECRET",
  "api_url": "https://sandbox.d.greeninvoice.co.il/api/v1/"
}
```
`config/config.test.json` (committed) is read by the integration tests under
`tests/integration/` — it must contain real sandbox credentials for those tests to
run; without them, the tests skip automatically.

## Testing

```bash
python3 -m pytest tests/ -v --tb=short
```
Integration tests hit the real Morning **sandbox** API (no mocking, per this
repo's constitution) — they skip gracefully if `config/config.test.json` lacks
real credentials or contains placeholder-looking values.

## Running the MCP server

```bash
python3 -m denidin_mcp_morning.server
```
Starts the FastMCP server over streamable-HTTP (host/port/transport configurable
under `mcp{}` in `config/config.json`). Startup is gated behind
`feature_flags.enable_mcp_server` (default `false`) — with it off, the process
exits immediately with a clear message rather than silently serving nothing.

## Docker

```bash
docker build -t morning-mcp-app .
docker run --rm -p 8000:8000 -v "$(pwd)/config:/app/config:ro" morning-mcp-app
```
Runs the MCP server (same feature-flag gate as above — set
`feature_flags.enable_mcp_server: true` in the mounted `config/config.json` or
the container exits immediately). Can also be run via the root
`docker-compose.yml` (`docker compose up morning-mcp-app`).
