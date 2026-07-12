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
`config/config.test.json` (**gitignored**, not committed — changed 2026-07-09; it
previously was, but real secrets in a git-tracked file is a liability even for
sandbox-tier credentials) is read by the integration tests under `tests/integration/`
and `tests/expensive/` — it must contain real sandbox credentials (and, for the
ngrok/OpenAI-driven tests, `openai_api_key`/`mcp.ngrok_authtoken` too) for those
tests to run; without them, the tests skip automatically. See
`config/config.example.json` for the full shape to copy.

## Testing

```bash
python3 -m pytest tests/ -v --tb=short
```
Integration tests hit the real Morning **sandbox** API (no mocking, per this
repo's constitution) — they skip gracefully if `config/config.test.json` lacks
real credentials or contains placeholder-looking values.

## Running the MCP server

```bash
./run_morning_mcp.sh      # start (PID-file enforced single instance)
./stop_morning_mcp.sh     # graceful stop
./restart_morning_mcp.sh  # stop + start
python3 -m denidin_mcp_morning.server   # or run directly (foreground)
```
Starts the FastMCP server over streamable-HTTP (host/port/transport configurable
under `mcp{}` in `config/config.json`). Startup is gated behind
`feature_flags.enable_mcp_server` (default `false`) — with it off, the process
exits immediately with a clear message rather than silently serving nothing.
Logs go to `logs/morning-mcp.log` (production) or `logs/test_logs/{test_file}.log`
(tests), mirroring `denidin-app`'s logging.

### Exposing the server publicly (optional — needed for OpenAI's remote-MCP connector)

Set `mcp.ngrok_authtoken` in `config/config.json` (a **free** ngrok account is
enough — no paid plan needed; `mcp.ngrok_domain` is optional and only relevant
if you have a paid reserved/static domain). `run_morning_mcp.sh` then starts a
tunnel alongside the server and prints its public URL;
`stop_morning_mcp.sh` tears the tunnel down too. Protect the server with
`mcp.auth_token` (a shared bearer secret) before exposing it — see
`ARCHITECTURE.md` for why (the server has no auth by default, and its tools
include state-changing operations).

**Note**: `create_server()` explicitly disables FastMCP's Host-header
DNS-rebinding protection (`TransportSecuritySettings(enable_dns_rebinding_protection=False)`),
which otherwise only allows `Host: 127.0.0.1/localhost` and 424s every request
forwarded through a tunnel (confirmed live 2026-07-12 — see
`specs/in-definition/005-mcp-morning-green-receipt/tasks.md`, T021). This is
safe here because `mcp.auth_token`'s bearer check, not Host-header matching, is
this server's real access boundary — set it whenever exposing the server
publicly.

## Docker

```bash
docker build -t morning-mcp-app .
docker run --rm -p 8000:8000 -v "$(pwd)/config:/app/config:ro" morning-mcp-app
```
Runs the MCP server (same feature-flag gate as above — set
`feature_flags.enable_mcp_server: true` in the mounted `config/config.json` or
the container exits immediately). The image includes `ngrok`; if
`mcp.ngrok_authtoken` is set in the mounted config, `docker-entrypoint.sh`
starts a tunnel automatically before starting the server and prints the
public URL to container logs (`docker logs`). Can also be run via the root
`docker-compose.yml` (`docker compose up morning-mcp-app`).

**⚠️ Required for Docker**: set `"mcp": {"host": "0.0.0.0"}` in the mounted
`config/config.json`. The default `127.0.0.1` (correct for plain local dev)
binds to the container's own loopback only — confirmed live that `-p`
port-mapped traffic (and an ngrok tunnel targeting the container) cannot
reach the process at all until this is changed to `0.0.0.0`.
