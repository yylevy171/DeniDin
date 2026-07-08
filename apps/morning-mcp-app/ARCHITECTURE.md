# morning-mcp-app Architecture

**Status**: Feature 005 in progress (Phase 2 of 4 — see
`specs/in-definition/005-mcp-morning-green-receipt/tasks.md`)
**Last Updated**: July 8, 2026

## Boundary

`apps/morning-mcp-app/` is a fully standalone app in the DeniDin monorepo — own
`venv`, `requirements.txt`, `config/`, `Dockerfile`, `tests/`. It does **not**
import from or call into `apps/denidin-app/`; the two are siblings, wired
together only by convention (same repo, same Constitution), never by code.
This is why `send_invoice` cannot deliver over WhatsApp via denidin-app's
number today — there is no import path between the two apps. (That's tracked
as deferred future work with the architecture still TBD; see `spec.md`
§Future Work.)

## Layers (bottom-up)

```
┌─────────────────────────────────────────────────────────┐
│  server.py  (Phase 3 — not yet built)                    │
│  FastMCP server, streamable-HTTP transport.               │
│  Registers 8 @mcp.tool()s. Gated by                        │
│  feature_flags.enable_mcp_server.                          │
└───────────────────────┬───────────────────────────────────┘
                         │ calls
┌───────────────────────▼───────────────────────────────────┐
│  tools.py  (Phase 2 — in progress)                          │
│  One function per MCP tool: create_invoice, list_invoices, │
│  get_invoice_details, update_invoice_status, add_client,   │
│  get_financial_summary, send_invoice, download_invoice_pdf │
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
│  MorningAuth: exchanges       │
│  api_key_id+secret for a JWT  │
│  at POST /account/token,      │
│  caches it, refreshes before  │
│  expiry. Thread-safe.         │
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
`api_key_id`, `api_key_secret`, `api_url`, plus optional tuning
(`token_ttl_seconds`, `refresh_before_seconds`, `rate_limit_per_second`,
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
| `morning_client.py` (3 of 8 operations: create/list/get invoice) | ✅ Done (partial) |
| `config.py` | ✅ Done (Phase 1) |
| `models.py` | ✅ Done (Phase 1) |
| `formatters.py` | ✅ Done (Phase 1) |
| `tools.py` (8 MCP tools) | 🚧 In progress (Phase 2) — `create_invoice` test written, implementation pending approval |
| `server.py` (FastMCP, streamable-HTTP) | ⬜ Not started (Phase 3) |
| Docker `CMD` swap, quickstart docs | ⬜ Not started (Phase 4) |

See `specs/in-definition/005-mcp-morning-green-receipt/tasks.md` for the full
task-by-task checklist.

## Related documents

- `specs/in-definition/005-mcp-morning-green-receipt/spec.md` — functional
  spec, the 8 tools, technology choice rationale (FastMCP/streamable-HTTP).
- `specs/in-definition/005-mcp-morning-green-receipt/plan.md` — technical
  plan, phases, integration contracts.
- `specs/in-definition/005-mcp-morning-green-receipt/data-model.md` — the
  Pydantic model field reference.
- `specs/in-definition/017-mcp-morning-receipt-parsing/` — a separate,
  deferred future feature (file-upload/webhook receipt parsing), split out of
  005 to keep this app's scope to invoice management.
