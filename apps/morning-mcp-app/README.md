# morning-mcp-app

Standalone client for the Morning (Green Invoice) API — Israeli invoicing/receipts.

## Status

This app ships a working FastMCP server (`src/denidin_mcp_morning/server.py`,
streamable-HTTP) exposing 14 tools — 11 invoice-management tools
(`create_invoice`, `create_transaction_account`, `create_combo_document`,
`create_credit_note`, `create_receipt`, `create_combo_document_as_reference`,
`list_invoices`, `get_invoice_details`, `add_client`, `get_financial_summary`,
`download_invoice_pdf`) plus 3 client-management tools added by Feature 026
(`list_clients`, `get_client_details`, `update_client`) — backed by the real
Morning sandbox API, per `specs/done/v0.0.1/005-mcp-morning-green-receipt/plan.md`
and `tasks.md`, `specs/done/v0.0.1/021-flexible-document-creation/spec.md` for the 4
document-type-specific `create_*` tools, `specs/done/v0.0.1/023-reference-linked-document-creation/spec.md`
for `create_combo_document_as_reference` (which, alongside removing the separate
`update_invoice_status` tool entirely, replaced it), and
`specs/in-progress/026-client-management/spec.md` for client management.
(`send_invoice` was investigated and dropped — Morning's public API has no
documented delivery endpoint; see `spec.md` §Scope.)

**`add_client`'s contract changed with Feature 026**: `name`/`email`/`phone`
are now all required (previously only `name` was), `address` is no longer a
parameter at all (out of scope), email is validated and phone normalized to
Israeli local dashed format before any network call, and the tool is now
approval-gated at the denidin-app layer (previously executed immediately,
single-turn) — same explicit-approval flow as invoice/document creation.
`update_client` is approval-gated too, resolves its target by name (never a
caller-supplied internal id), and accepts a partial set of fields to change.

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
pip install -r requirements.txt   # for local test-running only - the server itself runs containerized
cp config/config.example.json config/config.dev.json    # then fill in real Morning sandbox credentials + dev ngrok authtoken
cp config/config.example.json config/config.prod.json   # then fill in real Morning production credentials + prod ngrok authtoken
```

## Configuration

One config file per environment (019-env-separation), both gitignored, real credentials — flat shape:
```json
{
  "api_key_id": "YOUR_MORNING_API_KEY_ID",
  "api_key_secret": "YOUR_MORNING_API_KEY_SECRET",
  "api_url": "https://sandbox.d.greeninvoice.co.il/api/v1/"
}
```
`config/config.dev.json` points at the Morning **sandbox** host; `config/config.prod.json` points at Morning **production** — see `config/config.example.json` for the full shape to copy (used for both envs), including each environment's own `mcp.ngrok_authtoken` (two separate ngrok accounts, one per environment).

`config/config.test.json` (**gitignored**, not committed) is read by the integration tests under `tests/integration/`,
`tests/billed/`, and `tests/expensive/` — it must contain real sandbox credentials (and, for the
ngrok/OpenAI-driven tests, `openai_api_key`/`mcp.ngrok_authtoken` too) for those
tests to run; without them, the tests skip automatically.

## Testing

```bash
python3 -m pytest tests/ -v --tb=short
```
Integration tests hit the real Morning **sandbox** API (no mocking, per this
repo's constitution) — they skip gracefully if `config/config.test.json` lacks
real credentials or contains placeholder-looking values.

Real-OpenAI-call tests are split into two tiers (mirroring `apps/denidin-app`,
Feature 029): `tests/billed/` (real, text-only OpenAI calls — cheap, can be run
freely, no approval needed) and `tests/expensive/` (real vision/image calls —
none currently exist in this app, but the marker/folder are kept registered
for when they do; would require the same approval-per-run, one-at-a-time
discipline as `apps/denidin-app`'s). Both are excluded by default
(`pytest.ini`'s `addopts`); run with `-m billed` or `-m expensive`.

## Running the MCP server

The server runs **only as a Docker container**, one environment at a time (019-env-separation — no local/foreground process anymore; `run_morning_mcp.sh`/`stop_morning_mcp.sh` are thin `docker compose` wrappers, and Docker itself prevents a duplicate start of an already-running service):

```bash
./run_morning_mcp.sh dev|prod       # start that environment's container (builds if needed)
./stop_morning_mcp.sh dev|prod      # stop it
./restart_morning_mcp.sh dev|prod   # stop + start
```
Starts the FastMCP server over streamable-HTTP inside the container (host/port/transport configurable
under `mcp{}` in that environment's `config/config.<env>.json` — must be `"host": "0.0.0.0"` for Docker, see below). Startup is gated behind
`feature_flags.enable_mcp_server` (default `false`) — with it off, the process
exits immediately with a clear message rather than silently serving nothing.
Logs go to `logs/dev/morning-mcp.log` / `logs/prod/morning-mcp.log` (per environment) or `logs/test_logs/{test_file}.log`
(tests), mirroring `denidin-app`'s logging.

### Exposing the server publicly (optional — needed for OpenAI's remote-MCP connector)

Set `mcp.ngrok_authtoken` in each environment's `config/config.<env>.json` — **two separate ngrok accounts** (one per environment; the free tier only supports one online tunnel per account, so dev and prod each need their own). `run_morning_mcp.sh <env>` then starts ngrok *inside* that environment's container alongside the server and prints its public URL;
`stop_morning_mcp.sh <env>` tears that environment's tunnel down too. Protect the server with
`mcp.auth_token` (a shared bearer secret) before exposing it — see
`ARCHITECTURE.md` for why (the server has no auth by default, and its tools
include state-changing operations).

**Note**: `create_server()` explicitly disables FastMCP's Host-header
DNS-rebinding protection (`TransportSecuritySettings(enable_dns_rebinding_protection=False)`),
which otherwise only allows `Host: 127.0.0.1/localhost` and 424s every request
forwarded through a tunnel (confirmed live 2026-07-12 — see
`specs/done/v0.0.1/005-mcp-morning-green-receipt/tasks.md`, T021). This is
safe here because `mcp.auth_token`'s bearer check, not Host-header matching, is
this server's real access boundary — set it whenever exposing the server
publicly.

## Docker (what the scripts above wrap)

```bash
docker compose --project-directory ../.. -f ../../docker/docker-compose.dev.yml up -d morning-mcp-app-dev     # or docker-compose.prod.yml / morning-mcp-app-prod
```
Runs the MCP server (same feature-flag gate as above — set
`feature_flags.enable_mcp_server: true` in the mounted `config/config.<env>.json` or
the container exits immediately). The image includes `ngrok`; if
`mcp.ngrok_authtoken` is set in the mounted config, `docker-entrypoint.sh`
starts a tunnel automatically before starting the server and prints the
public URL to container logs (`docker logs`), and writes that environment's
shared status file (`shared/mcp-status-<env>/`) for the paired `denidin-app-<env>`
to discover.

**⚠️ Required for Docker**: set `"mcp": {"host": "0.0.0.0"}` in each environment's
`config/config.<env>.json` (already set this way in `config.example.json`).
The default `127.0.0.1` (correct for plain local dev)
binds to the container's own loopback only — confirmed live that `-p`
port-mapped traffic (and an ngrok tunnel targeting the container) cannot
reach the process at all until this is changed to `0.0.0.0`.
