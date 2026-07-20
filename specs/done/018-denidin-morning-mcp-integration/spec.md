# Feature Spec: DeniDin ↔ Morning MCP Integration — Invoicing over WhatsApp

**Feature ID**: 018-denidin-morning-mcp-integration
**Priority**: P1 (High)
**Status**: Draft — in-definition
**Created**: July 12, 2026
**Branch**: `feature/018-denidin-morning-mcp-integration`
**Apps**: `apps/denidin-app/` (primary changes) + a small addition to `apps/morning-mcp-app/`
(status-file publishing). The two apps remain independent — they connect only over HTTP (the
MCP tunnel), a shared bearer token, and a shared status file. **No cross-app imports.**

---

## Terminology Glossary

- **Responses API**: OpenAI's `client.responses.create(...)` interface (replaces the legacy
  `client.chat.completions.create`). Required because remote MCP tools are only consumable
  through it.
- **remote MCP tool**: an MCP server registered on a Responses call via a
  `{"type":"mcp","server_url":...}` tool entry, letting the model discover/invoke its tools
  over HTTP. Here it is the Feature-005 Morning server (`/mcp` endpoint).
- **Morning MCP server**: `apps/morning-mcp-app/` FastMCP server exposing 7 invoicing tools
  (`create_invoice`, `list_invoices`, `get_invoice_details`, `update_invoice_status`,
  `add_client`, `get_financial_summary`, `download_invoice_pdf`). Already built and proven.
- **status file**: JSON file the Morning app writes when its ngrok tunnel comes up, holding the
  **current** public `server_url` (+ `updated_at`). DeniDin reads it to learn the live URL.
- **bearer token**: shared secret. DeniDin sends `Authorization: Bearer <token>` on the MCP
  tool registration; the Morning server's `BearerTokenMiddleware` enforces it (401 otherwise).
- **role**: denidin RBAC role — `admin`, `godfather`, `client`, `blocked`. Invoicing tools are
  attached **only** for `godfather`/`admin`.
- **mcp_call**: a Responses output item (`type == "mcp_call"`, fields `.name`, `.arguments`,
  `.output`, `.error`) representing one remote-tool invocation. Used to assert tool usage.

---

## Problem Statement

Feature 005 built and *proved* (real billed run 2026-07-12) that OpenAI's Responses API can
drive the Morning MCP server over a public ngrok tunnel with bearer auth — but only from a
test. The production WhatsApp bot (`apps/denidin-app/`) still calls OpenAI via legacy Chat
Completions and has no knowledge of MCP. Nothing lets a real WhatsApp user manage invoices.

This feature connects them: an authorized (godfather/admin) WhatsApp user can create, query,
update, cancel, and report on Morning invoices in natural language, and the bot executes those
actions through the Morning MCP server, replying in the conversation (Hebrew by default).

---

## Scope

**In scope:**
- Migrate **all** of denidin's Chat-Completions call sites to the Responses API (conversational
  reply, session summarization, image/vision extraction). Embeddings stay on the embeddings API.
- Attach the Morning MCP server as a remote tool on the **conversational reply** call, gated to
  `godfather`/`admin`.
- URL discovery via a shared status file the Morning app publishes.
- Shared-bearer-token security + role gating + graceful degrade when the server is down.
- A runtime-constitution section teaching the model when/how to use the tools and when to
  confirm before state-changing actions.
- Real-API E2E test coverage for every tool (positive + negative) and multi-turn scenarios.

**Out of scope:**
- Any change to the Morning tools themselves (Feature 005 owns them).
- Receipt parsing / file upload / webhook product (`specs/in-definition/017-...`).
- WhatsApp *delivery* of invoices from denidin's number (Feature 005 §Future Work).
- Migrating embeddings (no Responses equivalent).

---

## Decisions (this feature)

1. **RBAC** — Morning tools attach only for `godfather`/`admin`; clients/blocked never get them.
2. **URL discovery** — shared status file written by the Morning app, read by denidin per call.
3. **Responses scope** — replace all denidin Chat-Completions calls; embeddings unchanged.
4. **Confirmation** — `require_approval: "never"`; confirmation behavior owned by the runtime
   constitution prompt (no code). OpenAI's `mcp_approval_request` handshake is not used.
5. **No feature flags / no backward-compat** (pre-production) — Chat-Completions paths are
   replaced outright, not gated. Governing invariant: **tests are immutable once approved**
   (CONSTITUTION §VIII).

---

## Technology Choice: OpenAI Responses API + remote MCP

- **Decision Date**: July 12, 2026
- **Decision**: use `client.responses.create(...)` with the Morning server registered via
  `tools=[{"type":"mcp", "server_url": "<current-ngrok>/mcp", "require_approval":"never",
  "headers":{"Authorization":"Bearer <token>"}}]`.
- **Rationale**: remote MCP tools are only reachable through the Responses API; OpenAI
  orchestrates the whole tool round-trip inside a single `create()` call, so denidin needs no
  manual tool-execution loop — it reads `output_text` and any `mcp_call` items. This exact
  shape is already proven end-to-end (Feature 005 T021).
- **Alternatives considered**: keep Chat Completions + a hand-rolled function-calling loop that
  proxies to the Morning HTTP API — rejected (duplicates MCP, more code, unproven). OpenAI's
  formal MCP approval handshake — rejected for v1 (multi-step, decision #4).
- **Migration Path**: `input`/`instructions` mapping is localized to `ai_handler.py` and the
  image extractor; the injected `OpenAI` client already exposes both surfaces.

---

## Configuration (denidin-app)

Per CONSTITUTION §I, all config is in `config/config.json` (no env vars). `AppConfiguration`
strips unknown keys, so a new `mcp` dataclass field is required. New `mcp` block:

```json
"mcp": {
  "morning_auth_token": "",
  "morning_status_file": "data/morning_mcp_status.json",
  "morning_server_label": "morning-invoices",
  "url_max_age_seconds": 0
}
```

- `morning_auth_token` — MUST equal the Morning app's `mcp.auth_token` (static shared secret).
- `morning_status_file` — path to the JSON the Morning app publishes.
- `morning_server_label` — the `server_label` sent on the MCP tool entry.
- `url_max_age_seconds` — `0` = ignore age; `>0` = treat a status file older than this as
  "server down" (graceful degrade).

**No new feature flags** (decision #5). Tool attachment is decided at runtime by role +
status-file availability.

### Status-file protocol (the DeniDin ↔ Morning contract)

- **Morning app publishes**: on tunnel-up, writes
  `{"server_url": "https://<host>.ngrok-free.app/mcp", "updated_at": "<UTC ISO 8601>"}` to a
  configured path (new `mcp.status_file` field); clears it on stop.
- **DeniDin consumes**: a `MorningMcpLocator` reads the file, checks freshness, and returns the
  `server_url` or `None`. `None` ⇒ no tools attached, normal reply, WARNING logged.

---

## Requirements

- **REQ-RESP-001**: The conversational reply is generated via `client.responses.create`.
  `instructions` carries the system prompt (constitution + memories); `input` carries
  conversation history + the current user message. Response text is read from `output_text`;
  token usage from `usage.input_tokens/output_tokens/total_tokens`.
- **REQ-RESP-002**: Session summarization and image/vision extraction also use the Responses
  API. Vision passes the image as an `input_image` item. Embeddings remain on the embeddings
  API. Extractors preserve their existing output contract.
- **REQ-RESP-003**: Existing retry (tenacity: `RateLimitError`/`APITimeoutError`/`APIError`,
  2 attempts, 1s) and friendly user-facing error fallbacks are preserved on the new call path.
- **REQ-MCP-001**: When the resolved role ∈ {godfather, admin} **and** the locator returns a
  live URL, the reply call registers the Morning server as a remote MCP tool with
  `require_approval:"never"` and the bearer header. Otherwise no MCP tool is attached.
- **REQ-DISC-001**: DeniDin obtains the current server URL solely from the status file; it never
  imports Morning code and never hard-codes the URL.
- **REQ-DISC-002**: Missing/stale/unparseable status file ⇒ graceful degrade (no tools, normal
  reply, no crash, WARNING logged).
- **REQ-RBAC-001**: Clients and blocked users never have Morning tools attached; a client's
  invoicing request creates nothing in Morning.
- **REQ-SEC-001**: The bearer token is a static shared secret in each app's `config.json`
  (gitignored), masked in logs (first/last 4). Sent only over the HTTPS tunnel.
- **REQ-SEC-002**: Every reply that attaches MCP tools is logged with role, correlation id,
  masked token, and URL host (audit trail for state-changing operations).
- **REQ-I18N-001**: Replies are Hebrew by default (the Morning tools already return Hebrew; the
  runtime constitution instructs the model to answer in Hebrew).
- **REQ-CONST-001**: The runtime constitution gains a section describing the 7 tools, their
  scope (invoicing/clients/finance only), Hebrew output, and confirm-before-state-change
  guidance (decision #4).

---

## Security Considerations

- **Access control**: role gate (godfather/admin) is the primary control over who can trigger
  real invoicing; the shared bearer token is the transport-level control on the Morning server.
- **Token handling**: config-only, gitignored, masked in logs, never persisted elsewhere.
- **Transport**: HTTPS ngrok tunnel; Morning's DNS-rebinding protection already disabled for
  tunnels (Feature 005). The bearer token is the server's real access boundary.
- **State-changing operations** (`create_invoice`, `update_invoice_status` cancel→credit note,
  `add_client`) are audit-logged (REQ-SEC-002).
- **Graceful degrade**: an unreachable server must never crash the bot or silently mislead the
  user into thinking an action succeeded.

---

## Error Handling

- OpenAI errors → existing denidin friendly fallbacks (CONSTITUTION §X), unchanged.
- Morning tool errors surface as the Morning server's own friendly Hebrew messages (Feature 005
  `errors.py`) inside the model's `mcp_call.output` — the model relays them; denidin does not
  re-map them.
- Locator/status-file errors → graceful degrade (REQ-DISC-002), never surfaced as a stack trace.

---

## Testing Strategy

Per CONSTITUTION §V + ZERO-MOCKING + the project's real-API-E2E preference: **real-API E2E
tests only**, entry point always a real Green API webhook through `@bot.router.message`. All
new tests are `@pytest.mark.expensive` (real OpenAI billing), live in
`apps/denidin-app/tests/expensive/`, spawn the real Morning MCP server (sandbox) + real ngrok
tunnel, and **independently verify** every state-changing effect in the Morning sandbox via a
direct `MorningClient`. One+ positive and one+ negative test per tool, plus RBAC/scope/degrade
cross-cutting tests, plus multi-turn scenarios (lifecycle, slot-filling, confirm-before-act).
Each test is written RED and approved before its implementation; immutable thereafter.

---

## Success Metrics

- A godfather can create/query/update/cancel/report invoices and add clients entirely from
  WhatsApp, with the effects verified in the Morning sandbox.
- Clients/blocked users can never trigger invoicing.
- The bot degrades gracefully when the Morning server is down.
- The default (non-expensive) suite stays green; pylint/mypy pass.

---

## Dependencies

- Feature 005 Morning MCP server (built) — its `mcp.auth_token`, ngrok tunnel, and (new)
  status-file publishing.
- OpenAI Responses API (already in the installed `openai` SDK used by both apps).
