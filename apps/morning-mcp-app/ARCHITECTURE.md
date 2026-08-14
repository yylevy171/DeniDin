# morning-mcp-app Architecture

**Status**: Feature 005 — Phases 1 & 2 complete, Phase 3 (server) complete;
Phase 4 (polish) remaining (see
`specs/done/005-mcp-morning-green-receipt/tasks.md`)
**Last Updated**: July 9, 2026

## Boundary

`apps/morning-mcp-app/` is a fully standalone app in the DeniDin monorepo — own
`venv`, `requirements.txt`, `config/`, `Dockerfile`, `tests/`. It does **not**
import from or call into `apps/denidin-app/`; the two are siblings, wired
together only by convention (same repo, same Constitution), never by code.
There is no `send_invoice` tool — Morning's public API has no documented
endpoint to deliver a document at all (investigated and dropped, see `spec.md`
§Scope); a future delivery feature would assemble info via the existing tools
and deliver over a channel this app or a caller controls (e.g. WhatsApp via
denidin-app's number, architecture still TBD).

## Layers (bottom-up)

```
┌─────────────────────────────────────────────────────────┐
│  server.py  (Phase 3 — DONE)                              │
│  FastMCP server, streamable-HTTP transport.               │
│  Registers 14 @mcp.tool()s (11 invoice + 3 client mgmt,    │
│  the latter added by Feature 026). Gated by                │
│  feature_flags.enable_mcp_server.                          │
└───────────────────────┬───────────────────────────────────┘
                         │ calls
┌───────────────────────▼───────────────────────────────────┐
│  tools.py  (Phase 2 — DONE, 14 tools)                       │
│  One function per MCP tool: create_invoice, list_invoices, │
│  get_invoice_details, create_receipt, create_credit_note,  │
│  create_combo_document_as_reference, add_client, update_client,     │
│  list_clients, get_client_details,                         │
│  get_financial_summary, download_invoice_pdf (+ more,      │
│  see README.md for the full current list - this diagram   │
│  predates features 020/021/022/023/026)                    │
│  - takes friendly args (client_name, amount, ...)          │
│  - maps them onto Morning's real payload shape              │
│  - calls MorningClient                                      │
│  - formats the result via formatters.py                     │
└──────────┬───────────────────────────────┬─────────────────┘
           │ uses                          │ uses
┌──────────▼──────────────┐   ┌────────────▼────────────────┐
│  morning_client.py        │   │  models.py / formatters.py  │
│  (EXISTS)                 │   │  (built Phase 1)             │
│  MorningClient:            │   │  Pydantic Invoice/Client/    │
│  create_invoice,           │   │  Payment/FinancialSummary    │
│  list_invoices, get_invoice│   │  mapping Morning's nested     │
│  (+ 5 more ops to add)     │   │  client{}/income[]/payment[]  │
│  urllib3 retry 429/5xx     │   │  shape; ₪/Hebrew formatters   │
└──────────┬─────────────────┘   └───────────────────────────────┘
           │ uses
┌──────────▼─────────────────┐
│  auth.py  (EXISTS)           │
│  MorningAuth: OAuth2           │
│  client_credentials exchange  │
│  at POST {auth_url}/idp/v1/   │
│  oauth/token (feature 053 -   │
│  different host than the      │
│  main API). Caches the token  │
│  using the real expiresAt,    │
│  refreshes before expiry.     │
│  Thread-safe.                 │
└──────────┬─────────────────┘
           │ reads
┌──────────▼─────────────────┐
│  config.py  (built Phase 1)  │
│  Loads flat config.json,     │
│  validates against            │
│  config.schema.json.          │
│  No env vars anywhere.        │
└─────────────────────────────┘
```

## Request flow for one tool call

```
MCP client (e.g. an OpenAI model)
  → HTTP (streamable-HTTP)
  → server.py dispatches to the named @mcp.tool()
  → tools.py maps friendly args to Morning's real JSON shape
  → morning_client.py adds a fresh/cached JWT header, calls the real Morning API
  → response comes back
  → tools.py builds a models.Invoice (or Client, etc.)
  → formatters.py turns it into a Hebrew, ₪-formatted string
  → that string is the tool's return value, flowing back to the MCP client
```

Nothing in this chain is mocked in tests — the "real Morning API" box really is
`sandbox.d.greeninvoice.co.il`.

## Config & secrets

Single source of truth: `config/config.json` (gitignored), flat shape —
`api_key_id`, `api_key_secret`, `api_url`, `auth_url` (feature 053 - the
OAuth2 token endpoint's host, genuinely different from `api_url`), plus
optional tuning (`refresh_before_seconds`, `rate_limit_per_second`,
`mcp.{host,port,transport,log_level}`, `feature_flags.enable_mcp_server`).
Validated at load time (`config.py`) against `config/config.schema.json`,
which is copied **inside** the app (not just referenced from `specs/`)
specifically so the Docker image — which only `COPY .`s this directory —
stays self-contained. No environment variables anywhere, per
`.github/CONSTITUTION.md` §I.

## Testing architecture

Two tiers, both real, no mocks (`.github/CONSTITUTION.md` ZERO-MOCKING + §V):

- **`tests/unit/`** — pure-logic tests (config parsing, Pydantic model
  validation, string formatting) that never touch the network. Added in
  Phase 1.
- **`tests/integration/`** — hit the live Morning **sandbox** (free, not
  billed) through the real HTTP client. Each of the 8 tools gets one of these
  written *before* it's implemented (TDD RED → GREEN, per
  `.github/TDD-ENFORCEMENT.md`). The Phase 3 checkpoint adds one that starts
  the actual FastMCP server and drives a tool call through a real MCP client,
  proving the server registers/dispatches tools correctly — this app's
  equivalent of denidin-app's "does the router actually catch the webhook"
  integration-test requirement.

## Deployment

`Dockerfile` (`python:3.11-slim`, bumped from 3.9 because the `mcp` SDK
requires ≥3.10) copies the app and installs `requirements.txt`. Once
`server.py` exists, `CMD` becomes `python3 -m denidin_mcp_morning.server`,
which starts FastMCP on streamable-HTTP — reachable by OpenAI's remote-MCP
connector, and runnable via `docker compose up morning-mcp-app` at the repo
root. The server only actually starts when `feature_flags.enable_mcp_server`
is `true`, so merging incomplete work never changes runtime behavior by
accident.

## Current implementation status

| Component | Status |
|---|---|
| `auth.py` (`MorningAuth` — JWT exchange/cache) | ✅ Done |
| `morning_client.py` (all needed operations: create/list/get/close/open invoice, add_client) | ✅ Done |
| `config.py` | ✅ Done (Phase 1) |
| `models.py` | ✅ Done (Phase 1) |
| `formatters.py` | ✅ Done (Phase 1) |
| `tools.py` (7 MCP tools) | ✅ Done (Phase 2) — `send_invoice` investigated and dropped, see §Boundary |
| `server.py` (FastMCP, streamable-HTTP) | ✅ Done (Phase 3) — E2E dispatch test passes against the live sandbox |
| Docker `CMD` swap | ✅ Done |
| Quickstart docs | ⬜ Not started (Phase 4) |

See `specs/done/005-mcp-morning-green-receipt/tasks.md` for the full
task-by-task checklist.

## Related documents

- `specs/done/005-mcp-morning-green-receipt/spec.md` — functional
  spec, the 8 tools, technology choice rationale (FastMCP/streamable-HTTP).
- `specs/done/005-mcp-morning-green-receipt/plan.md` — technical
  plan, phases, integration contracts.
- `specs/done/005-mcp-morning-green-receipt/data-model.md` — the
  Pydantic model field reference.
- `specs/backlog/017-mcp-morning-receipt-parsing/` — a separate,
  deferred future feature (file-upload/webhook receipt parsing), split out of
  005 to keep this app's scope to invoice management.
