# Feature Spec: MCP Server for Morning (Green Invoice) — Invoice Management

**Feature ID**: 005-mcp-morning-green-receipt
**Priority**: P2 (Medium)
**Status**: Implemented (Phases 1–3 of `tasks.md`; Phase 4 polish remaining)
**Created**: January 17, 2026
**Last Updated**: July 9, 2026
**App**: `apps/morning-mcp-app/` (standalone, does not import from or depend on `apps/denidin-app/`)

---

## Terminology Glossary

- **Morning / Green Invoice**: the Israeli invoicing SaaS this server integrates with. API brand is "Green Invoice"; product brand is "Morning" (חשבונית ירוקה).
- **MCP**: Model Context Protocol. This feature exposes tools over MCP so MCP clients (OpenAI models, Claude Desktop, etc.) can call them.
- **MCP tool**: a function registered on the MCP server (via `@mcp.tool()`) that a client can discover and invoke. This is the feature's **external entry point** (replaces the WhatsApp `@bot.router.message` concept, which belongs to `denidin-app`, not here).
- **document**: Morning's generic term for an invoice/receipt/order. Created via `POST /documents`; `type` distinguishes them (e.g. `305` = tax invoice, `320` = receipt).
- **`invoice_id`**: Morning `documentId` (GUID string). Primary identifier for a document.
- **JWT**: short-lived bearer token obtained by exchanging the API key id+secret at `POST /account/token`. Managed by `MorningAuth`.
- **flat config**: `config/config.json` with `api_key_id` / `api_key_secret` / `api_url` at the **top level** (not nested). This is the real, canonical shape.

---

## Problem Statement

Users want to manage their Morning invoices through natural language via MCP clients
(OpenAI models today; potentially WhatsApp via `denidin-app` in a future feature). The MCP
server exposes a focused set of invoice-management tools so a model can create invoices,
query them, track payment status, manage clients, produce financial summaries, and fetch
invoice PDFs — all backed by the real Morning REST API.

**Desired capabilities (examples):**
- "Create an invoice for Tech Corp for 5000 NIS for consulting services"
- "Show me all unpaid invoices from this month"
- "What's the status of invoice #12345?"
- "Add a new client named Tech Solutions Ltd"
- "What's my total revenue for Q4 2025?"
- "Get me the PDF for invoice #789"

## Scope

**In scope** — one MCP server (`apps/morning-mcp-app/`) exposing **7 invoice-management
tools** (see §MCP Tools). Backed by the Morning REST API. Responses formatted for humans
(Hebrew by default; ₪; Israeli date format).

**Out of scope (this feature):**
- **Receipt parsing / file upload / webhook flow** — split into a separate future feature,
  `specs/in-definition/017-mcp-morning-receipt-parsing/`.
- **`send_invoice` (dropped, not a tool)** — Morning's public API has **no documented
  endpoint to email/deliver a document to a client** (confirmed by diffing the full official
  API reference against the community Postman collection: every endpoint this app uses
  appears in the official docs, but the `/documents/{id}/distribute` endpoint the Postman
  collection includes does not — it consistently returns `errorCode 3003` "unsupported
  operation type" regardless of document type or account settings, because it's an
  internal/browser-session-only endpoint powering Morning's own web UI "Send" button, not a
  supported partner/API-key integration point). A dedicated `send_invoice` tool would only
  have recombined `get_invoice_details` + `download_invoice_pdf` with no real delivery
  capability behind it — the calling MCP client (e.g. the model) can already compose those
  two tools itself, so a redundant wrapper tool adds no value. See §Future Work for what a
  real delivery channel (e.g. via denidin-app/WhatsApp) would require.
- **Multi-tenant / high-scale / SLA guarantees** — single sandbox tenant for the initial
  rollout; revisit in a later phase.

---

## Background: Morning (Green Invoice) API

- **Product**: Morning Green Receipt (חשבונית ירוקה) — Israeli digital invoicing.
- **API base URLs** (canonical; see `endpoints.md`):
  - Sandbox: `https://sandbox.d.greeninvoice.co.il/api/v1/`
  - Production: `https://api.greeninvoice.co.il/api/v1/`
- **Authentication**: exchange `api_key_id` + `api_key_secret` at `POST /account/token`
  for a JWT bearer token (see `contracts/morning_token_exchange.json`). Already implemented
  in `MorningAuth`.
- **Rate limit**: ~3 requests/second (HTTP 429 if exceeded). Enforce client-side; retry
  429/5xx with backoff (already implemented via urllib3 `Retry` in `MorningClient`).
- **Language**: full Hebrew support (fields, error messages).

---

## Current Implementation Status (ground truth)

This feature is **fully implemented** (Phases 1–3 of `tasks.md`); only Phase 4 polish
(quickstart docs) remains:

**Implemented** in `apps/morning-mcp-app/src/denidin_mcp_morning/`:
- `auth.py` — `MorningAuth`: JWT exchange via `POST /account/token`, token caching with
  refresh-before-expiry, thread-safe.
- `morning_client.py` — `MorningClient`: `create_invoice`, `list_invoices`, `get_invoice`,
  `close_invoice`/`open_invoice`, `add_client`; urllib3 retry on 429/500/502/503/504.
- `config.py` — loads & validates flat `config/config.json` against a self-contained
  `config/config.schema.json`.
- `models.py` — Pydantic models (`Invoice`, `Client`, `Payment`, `FinancialSummary`) mapping
  the real Morning document shape, including several live-discovered normalizations (`number`
  as int, numeric `status` codes).
- `formatters.py` — Hebrew/₪/VAT/date formatting of tool responses.
- `tools.py` — all 7 MCP tools (thin wrappers over the client + formatters).
- `server.py` — FastMCP server registering all 7 tools over streamable-HTTP, gated by
  `feature_flags.enable_mcp_server`.
- Real-sandbox integration tests for every tool plus an E2E test that starts the actual
  server and drives a tool call through a real MCP client: `tests/integration/*.py` (no mocks).

See `tasks.md` for the full history of real-sandbox discoveries that shaped each tool
(several endpoints/mechanisms turned out different from what this spec originally assumed).

---

## Configuration

Per CONSTITUTION §I, **all** runtime config comes from `config/config.json`. **No
environment variables** (`os.getenv`/`os.environ` are forbidden). For CI/deploy, inject
`config/config.json` from your secret manager; never commit live secrets. Validate config
at startup against `artifacts/config.schema.json`.

The config is **flat** (matches the real `config.example.json` / `config.test.json` and
the existing integration tests). Example `apps/morning-mcp-app/config/config.json`
(placeholders — never commit real secrets):

```json
{
  "api_key_id": "PASTE_TEST_API_KEY_ID",
  "api_key_secret": "PASTE_TEST_API_KEY_SECRET",
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
    "enable_mcp_server": false
  }
}
```

The MCP server startup is gated behind `feature_flags.enable_mcp_server` (default `false`,
per CONSTITUTION §I/§VI). When disabled, the existing client library and its integration
tests are unaffected.

---

## Technology Choice: MCP framework — FastMCP (official MCP Python SDK) over streamable-HTTP

- **Decision Date**: July 8, 2026
- **Decision**: use the official MCP Python SDK's **FastMCP** server, served over the
  **streamable-HTTP** transport. Tools are registered with `@mcp.tool()`.
- **Rationale**:
  - The server must be consumable by **OpenAI models as a remote MCP tool**; OpenAI's
    Responses API connects to remote MCP servers over HTTP (streamable-HTTP / SSE), so an
    HTTP-reachable MCP endpoint is required.
  - FastMCP gives native MCP tool discovery/dispatch with minimal boilerplate and runs
    locally with a single command — satisfying "easiest to deploy locally."
  - Keeps the app self-contained and Dockerizable (already has its own `Dockerfile`).
- **Alternatives considered**:
  - *stdio-only MCP* — great for local desktop clients, but not reachable by OpenAI's
    remote-MCP connector over the network. Rejected as the primary transport.
  - *Plain FastAPI/uvicorn REST* (the earlier draft) — not an MCP server; an MCP client
    couldn't discover the tools without a separate adapter. Rejected.
- **Migration Path**: FastMCP can also expose `stdio`/`sse`; `transport` is a config field,
  so switching transports later is a config change, not a rewrite.

---

## MCP Tools (7)

Each tool has a JSON contract under `contracts/`. Inputs are validated against the contract
(and Pydantic models) before any Morning call. Tool → Morning endpoint mapping (endpoints
below are the ones actually verified live — see `tasks.md` for the discoveries that
corrected several of these from the original draft):

| # | Tool | Morning endpoint | Contract |
|---|------|------------------|----------|
| 1 | `create_invoice` | `POST /documents` | `contracts/create_invoice.json` |
| 2 | `list_invoices` | `POST /documents/search` | `contracts/list_invoices.json` |
| 3 | `get_invoice_details` | `GET /documents/{id}` | `contracts/get_invoice_details.json` |
| 4 | `update_invoice_status` | "paid" → linked Receipt (type 400) via `POST /documents`; "cancelled" → linked Credit Invoice (type 330) via `POST /documents`; "unpaid" → idempotent/rejected (no reversal exists) | `contracts/update_invoice_status.json` |
| 5 | `add_client` | `POST /clients` | `contracts/add_client.json` |
| 6 | `get_financial_summary` | `POST /documents/search` (aggregated client-side — no dedicated summary endpoint exists) | `contracts/get_financial_summary.json` |
| 7 | `download_invoice_pdf` | `GET /documents/{id}` → PDF/preview URL or Base64 | `contracts/download_invoice_pdf.json` |

**`send_invoice` was dropped** — see §Scope for why (no documented delivery endpoint exists;
a wrapper tool wouldn't add anything the calling MCP client can't already compose from
`get_invoice_details` + `download_invoice_pdf`).

Auth is not a tool — `POST /account/token` is handled internally by `MorningAuth`
(`contracts/morning_token_exchange.json`).

### Tool input schemas

#### 1. `create_invoice`
Friendly inputs mapped onto the real Morning document payload (nested `client{}`,
`income[]`, `payment[]`, `type`, `vatType`, `currency`, `date`).
```json
{
  "name": "create_invoice",
  "description": "Create a new invoice/document in Morning",
  "inputSchema": {
    "type": "object",
    "properties": {
      "client_name": {"type": "string", "description": "Client name (resolved/created via add_client flow if needed)"},
      "amount": {"type": "number", "minimum": 0, "description": "Amount in NIS"},
      "description": {"type": "string", "description": "Service/product description"},
      "due_date": {"type": "string", "format": "date", "description": "YYYY-MM-DD"},
      "vat_included": {"type": "boolean", "default": true}
    },
    "required": ["client_name", "amount", "description"]
  }
}
```

#### 2. `list_invoices`
```json
{
  "name": "list_invoices",
  "description": "List/search invoices with optional filters",
  "inputSchema": {
    "type": "object",
    "properties": {
      "status": {"type": "string", "enum": ["paid", "unpaid", "overdue", "all"]},
      "from_date": {"type": "string", "format": "date"},
      "to_date": {"type": "string", "format": "date"},
      "client_name": {"type": "string"}
    }
  }
}
```
Response returns at most 10 items plus a continuation token when more exist.

#### 3. `get_invoice_details`
```json
{
  "name": "get_invoice_details",
  "description": "Get full detail (status, payments, dates) for one invoice",
  "inputSchema": {
    "type": "object",
    "properties": {"invoice_id": {"type": "string"}},
    "required": ["invoice_id"]
  }
}
```

#### 4. `update_invoice_status`
```json
{
  "name": "update_invoice_status",
  "description": "Update an invoice's payment status",
  "inputSchema": {
    "type": "object",
    "properties": {
      "invoice_id": {"type": "string"},
      "status": {"type": "string", "enum": ["paid", "unpaid", "cancelled"]},
      "payment_date": {"type": "string", "format": "date"}
    },
    "required": ["invoice_id", "status"]
  }
}
```

#### 5. `add_client`
```json
{
  "name": "add_client",
  "description": "Add a new client to Morning",
  "inputSchema": {
    "type": "object",
    "properties": {
      "name": {"type": "string"},
      "email": {"type": "string", "format": "email"},
      "phone": {"type": "string"},
      "tax_id": {"type": "string", "description": "Israeli business tax ID (ע\"מ)"},
      "address": {"type": "string"}
    },
    "required": ["name"]
  }
}
```

#### 6. `get_financial_summary`
```json
{
  "name": "get_financial_summary",
  "description": "Aggregate totals/counts for a period",
  "inputSchema": {
    "type": "object",
    "properties": {
      "period": {"type": "string", "enum": ["month", "quarter", "year", "custom"]},
      "from_date": {"type": "string", "format": "date"},
      "to_date": {"type": "string", "format": "date"}
    },
    "required": ["period"]
  }
}
```

#### 7. `download_invoice_pdf`
```json
{
  "name": "download_invoice_pdf",
  "description": "Return a PDF download URL (or Base64) for an invoice",
  "inputSchema": {
    "type": "object",
    "properties": {"invoice_id": {"type": "string"}},
    "required": ["invoice_id"]
  }
}
```

---

## Morning API Client (canonical shape)

`MorningClient` (`apps/morning-mcp-app/src/denidin_mcp_morning/morning_client.py`) uses
`MorningAuth` for JWT and follows one pattern throughout: token via `self._auth_headers()`,
explicit timeouts, urllib3 retry on 429/5xx. Rather than duplicate its method list here
(which has already drifted from reality once — the original draft assumed a `PUT
/documents/{id}` status endpoint and a `/documents/{id}/send` delivery endpoint, neither of
which exist), **read the source file directly** for the current, authoritative set of
client methods; `tasks.md` documents the real-sandbox discoveries behind each one as they
were made.

## Data Models

See `data-model.md`. Pydantic models validate tool inputs/outputs and map 1:1 to Morning
API responses; persistence is not required for this feature. All datetimes are UTC
(CONSTITUTION §II).

---

## Requirements

- **REQ-CONFIG-001**: All config from flat `config/config.json`; validated at startup
  against `artifacts/config.schema.json`. No environment variables.
- **REQ-AUTH-001**: JWT obtained/cached/refreshed by `MorningAuth`; refresh when within
  `refresh_before_seconds` of expiry. Tokens are in-memory only (never persisted/logged).
- **REQ-RATE-001**: Stay under ~3 req/s; retry 429/5xx once-plus-backoff (existing urllib3
  `Retry`); never retry 4xx other than 429.
- **REQ-TOOL-001..007**: Each of the 7 tools validates input against its `contracts/*.json`
  before any Morning call and returns a human-readable (Hebrew-by-default) result.
- **REQ-ERR-001**: Map Morning/API errors to friendly user messages (see §Error Handling);
  full technical detail to logs only (CONSTITUTION §X).
- **REQ-I18N-001**: Responses in Hebrew by default — ₪ currency, DD/MM/YYYY dates, Hebrew
  status terms (שולם / לא שולם / פג תוקף / בוטל).
- **REQ-MCP-001**: All 7 tools registered on the FastMCP server and discoverable/dispatchable
  over streamable-HTTP; server startup gated by `feature_flags.enable_mcp_server`.

---

## Security Considerations

- **API key storage**: in flat `config/config.json` only (gitignored); injected from a
  secret manager at deploy time. **Never** in environment variables (CONSTITUTION §I).
- **JWT handling**: in-memory only; masked in logs (first/last 4 chars).
- **Rate limiting**: respect Morning's ~3 req/s.
- **Input validation**: sanitize amounts/descriptions; validate against contracts.
- **HTTPS only**; server-side only (Morning does not support CORS/browser calls).
- **Audit**: log all non-read operations (create/update/send) with correlation IDs.

---

## Error Handling

Implemented in `errors.py`, applied at the MCP tool-call boundary in `server.py`
(`_call_with_error_boundary`) — without this, FastMCP's default behavior surfaces the raw
exception string (including the internal Morning API URL) directly to the caller, confirmed
live. Technical detail (status, body, stack) always goes to logs at WARNING/ERROR, tagged
with a correlation id; the caller only ever sees one of these:

| Condition | User-facing message (Hebrew) |
|-----------|-------------------------------|
| Auth failed (401/403) | "❌ האימות מול Morning נכשל. בדקו את פרטי ה-API." |
| Not found (404) | "❌ לא נמצא. בדקו את מספר החשבונית/הלקוח." |
| Rate limit (429) | "❌ יותר מדי בקשות. נסו שוב בעוד דקה." |
| Network / 5xx | "❌ לא ניתן להתחבר ל-Morning כרגע. נסו שוב מאוחר יותר." |
| Other 4xx (Morning rejected the request) | "❌ הבקשה נדחתה על ידי Morning. בדקו את הפרטים ונסו שוב." |
| Business-rule violation (e.g. reopening an already-paid invoice, unsupported status/period) | "❌ הבקשה אינה תקינה. בדקו את הפרטים שסיפקתם." (the specific English detail is logged, not echoed to the caller — REQ-I18N-001: Hebrew by default) |
| Unexpected error | "❌ משהו השתבש. נסו שוב." |

**Not implemented (deferred; see §Future Work "Client resolution UX")**: client-side
pre-flight amount validation, fuzzy client-name matching with a disambiguation prompt ("❓
Multiple clients match…"), and any messaging tied to the dropped `send_invoice` tool. These
richer UX flows would need real design work, not just an error-mapping entry.

---

## Testing Strategy

Per CONSTITUTION §V + ZERO-MOCKING and the project's real-API-E2E preference, this app is
tested with **real Morning-sandbox integration tests only** — no `unittest.mock`, no
`requests-mock`, no mock-based unit tests. This matches the existing
`tests/integration/test_morning_sandbox_*.py` suite.

- **Entry point** for each test is the **MCP tool** (the real external entry point), driven
  through `server → tools.py → MorningClient → live Morning sandbox`.
- At least one E2E test starts the FastMCP server and invokes a tool via an MCP client,
  proving tool registration/dispatch (the §V routing requirement, reframed from
  `@bot.router.message` to MCP tool dispatch).
- **TDD**: each tool's real-sandbox test is written first and must **fail** before the
  implementation exists (RED), then pass (GREEN), with a human approval gate on the test
  plan + failing tests before implementation (METHODOLOGY §VI).
- Sandbox is free (no paid API), so these are ordinary integration tests — **not**
  `@pytest.mark.expensive` (that marker is for `denidin-app`'s paid OpenAI calls).

---

## Success Metrics

- All 7 tools create/manage invoices against the sandbox successfully.
- Accurate VAT/total math and Hebrew/₪ formatting.
- Friendly error handling for the conditions above.
- Tools discoverable and callable by an OpenAI model over remote MCP.

---

## Future Work (explicitly deferred)

- **Invoice delivery (email/WhatsApp)** — dropped from this feature entirely (no
  `send_invoice` tool exists; see §Scope). Morning's public API has no documented delivery
  endpoint at all, so a real delivery feature would need its own mechanism: assemble the
  invoice + PDF link via the existing `get_invoice_details`/`download_invoice_pdf` tools,
  then deliver over a channel this app or a caller controls — e.g. WhatsApp from
  denidin-app's number (architecture **TBD**; the two apps do not currently share code) or a
  direct email service. No design in this feature.
- **Receipt parsing / file-upload / webhook product** — `specs/in-definition/017-mcp-morning-receipt-parsing/`.
- **Client resolution UX** (fuzzy match + disambiguation, Chroma-assisted) — the model/MCP
  client drives disambiguation via `add_client` + `list_invoices`; a richer server-side
  resolution flow is a later enhancement.
- Recurring invoices, bulk operations, multi-currency, analytics dashboard.

---

## Dependencies

- **None on `denidin-app`.** This app is fully standalone (own `src/`, `tests/`, `config/`,
  `requirements.txt`, `Dockerfile`).
- New Python deps to add: `mcp` (FastMCP) and `pydantic` (see `plan.md` / `tasks.md`).
