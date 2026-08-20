# Implementation Plan: Client Management (Morning/Green Invoice CRM Clients) — Feature 026

**Feature**: 026-client-management
**Branch**: `026-client-management`
**Spec**: `./spec.md` · **User stories**: `./user-stories.md`
**Status**: Ready for Task Generation
**Updated**: July 29, 2026

**Compliance**: CONSTITUTION.md (§I no env vars, §II UTC, §III git workflow, §V real-sandbox
integration tests / zero mocking of external services, §VIII test immutability, §X friendly
errors, §XVII no monkey-patching) and METHODOLOGY.md (§I spec-first, §VI TDD, §VII integration
contracts). No new feature flags: both apps are past the "pre-production, no gating" stage
Feature 018 used, but this feature is purely additive (new tools) plus one narrow, deliberate
behavior reversal (Feature 022's `add_client` exemption) that the spec explicitly approved — not
a toggle, a real behavior change per CONSTITUTION §VIII (tests updated with re-approval, not
gated).

---

## Summary

Add `list_clients`, `get_client_details`, and `update_client` as new MCP tools on the existing
`apps/morning-mcp-app` FastMCP server, and change `add_client` to (a) require `name`+`email`+
`phone` (drop `address` entirely), (b) validate email format and normalize phone to Israeli local
dashed format before ever hitting the network, and (c) move under Feature 022's approval-gate
mechanism (`update_client` also gated) instead of executing immediately. No new integration
surface: these tools ride the same already-attached, already RBAC-gated (godfather/admin) Morning
MCP server that `apps/denidin-app` talks to over the existing ngrok tunnel (Feature 018). The
approval gate itself is not new infrastructure — it's OpenAI's `require_approval` mechanism plus
`PendingApprovalManager`, already built for Feature 022; extending it here is a one-line addition
to an existing tuple, not new code.

## Technical Context

- **Language/Version**: Python 3.11 (both apps, unchanged).
- **Primary Dependencies**: `apps/morning-mcp-app`: existing `requests`/`urllib3` (MorningClient),
  `mcp` (FastMCP), and **`email-validator`>=2.0.0 / pydantic `EmailStr`** — already declared in
  `requirements.txt` but currently unused by any write path; this feature is what puts it to use.
  No new dependency for phone (hand-rolled Israeli-format normalizer, see Technology Choice in
  spec.md). `apps/denidin-app`: no new dependency — reuses the existing `openai` Responses API +
  `PendingApprovalManager` + `tenacity` retry, all already in place from Features 018/022.
- **Storage**: none new. Morning remains the sole source of truth for client records (no local
  mirror, consistent with invoices).
- **Testing**: real-Morning-sandbox integration tests (`apps/morning-mcp-app/tests/integration/`,
  no mocks — CONSTITUTION §V) for the new/changed tools directly; real-API E2E tests
  (`apps/denidin-app/tests/expensive/test_denidin_morning_mcp_e2e.py`, `@pytest.mark.expensive`)
  through the real Green API webhook router, for the approval-gate + RBAC behavior.
- **Target Platform**: existing containerized runtime for both apps (unchanged — Docker,
  `run_morning_mcp.sh`/`run_denidin.sh`, per 019-env-separation). No new container, no new port.
- **Constraints**: no env vars; UTC; `pathlib.Path`; no monkey-patching; friendly (Hebrew) errors;
  no cross-app imports; tests immutable once approved (one exception below, explicitly approved).

## Constitution Check (pre-Phase 0)

- **No env vars** — PASS: no new config keys needed. `email-validator` config-free;
  the phone normalizer is pure code, no config.
- **UTC** — N/A: this feature adds no new timestamp handling (`created_at`/`updated_at` on
  `Client` already exist and are already UTC-parsed in `models.py`).
- **Feature branch** — PASS: `026-client-management`.
- **Feature flags** — N/A: additive tools need no flag (mirrors how Feature 021's `create_*`
  tools were added directly, no flag). The one **behavior reversal** (`add_client` no longer
  immediate) is a deliberate, spec-approved change, not something to hide behind a flag — per
  CONSTITUTION §VIII, the existing test asserting immediate creation is updated with this
  feature's approval, not preserved behind a toggle.
- **Real-sandbox tests / ZERO-MOCKING** — MUST ADHERE: every story gets a failing real-sandbox
  test (morning-mcp-app) and/or real-API E2E test (denidin-app) approved before implementation;
  no `unittest.mock` of the Green Invoice API or the OpenAI Responses API.
- **No monkey-patching** — PASS: new `MorningClient` methods (`search_clients`, `update_client`)
  and new `tools.py` functions follow the existing dependency-injection pattern (client passed
  in, no globals, no runtime attribute replacement).
- **Test immutability (§VIII)** — **One explicit, spec-approved exception**:
  `test_godfather_add_client_still_single_turn` (`test_denidin_morning_mcp_e2e.py:505-524`)
  currently asserts `add_client` executes immediately with no approval wait — this is the exact
  behavior Feature 026 reverses (spec.md Clarifications round 1). This test MUST be rewritten
  (two-turn `_send_turn_and_approve` pattern, renamed to reflect the new behavior) as part of this
  feature, with explicit human approval at the TDD test-plan gate — not silently left in place,
  and not deleted without replacement.
- **Friendly errors (§X)** — PASS: email/phone validation failures raise `ValueError`, already
  mapped by `errors.py:friendly_error_message` to the existing generic
  `_INVALID_REQUEST` Hebrew message — no new error-message plumbing needed.

## Integration Contracts (METHODOLOGY §VII)

### `apps/morning-mcp-app` tools.py ↔ `MorningClient` (new methods)

**tools.py MUST**:
- Call `client.search_clients({"name": name})` to resolve a client by **name only** (F1, analysis
  2026-07-29: tax-ID lookup was considered and dropped — the real `Search Clients` filters never
  include `taxId`) before any `get_client_details`/`update_client` operation — never guess a
  `client_id`.
- Treat 0 results as "not found" (friendly Hebrew message, no exception), exactly 1 result as
  resolved, and >1 results as ambiguous (return a Hebrew message listing each candidate's name +
  tax_id/phone, asking the user to specify — no tool exception raised, no mutation attempted).
- Validate `email` (when provided) via `EmailStr`/`email-validator` and normalize `phone` (when
  provided) to Israeli local dashed format **before** calling `client.add_client`/
  `client.update_client` — raise `ValueError` on failure (mapped to the existing friendly message).
- **`add_client` performs no proactive duplicate-check** (F2, analysis 2026-07-29: "try and
  fail" chosen over pre-checking for an existing same-name/same-tax-ID client) — attempt creation
  normally; if Morning's real API rejects it (duplicate or otherwise), let that error propagate
  to the existing `_call_with_error_boundary`/`friendly_error_message` mapping so the user sees a
  clear rejection, not a silent no-op or a false "success."
- **Never include `client_id` in any formatted Hebrew string** returned by `list_clients`,
  `get_client_details`, `add_client`, or `update_client` (REQ-CLIENT-018) — this also requires
  fixing the existing `add_client` return string (currently
  `f"נוצר לקוח חדש: {name} (מזהה: {client_id})"`), which leaks it today.

**MorningClient PROVIDES**:
- `search_clients(payload: dict) -> dict` → `POST /clients/search`, returns the raw
  `{items: [...], total, ...}` shape (see Postman collection example) — **items are already full
  records** (name/email/phone/tax_id and more), so no separate GET-by-id call is needed anywhere
  in this feature; `search_clients` alone backs both listing and name-resolution.
- `update_client(client_id: str, payload: dict) -> dict` → `PUT /clients/{id}` (partial payload —
  only changed fields; `client_id` comes from a prior `search_clients` resolution, never guessed).
- `add_client(payload: dict) -> dict` → `POST /clients` (unchanged signature; payload-building
  changes live in `tools.py`, not here).

**MorningClient EXPECTS**:
- A valid bearer token (existing `MorningAuth`, unchanged).
- `client_id`: a real Morning-assigned UUID string (never guessed/constructed).

### `AIHandler` ↔ `PendingApprovalManager` (extended, not new)

**AIHandler MUST**:
- Rename `DOCUMENT_CREATING_MCP_TOOLS`/`NON_DOCUMENT_CREATING_MCP_TOOLS` to
  `APPROVAL_REQUIRED_MCP_TOOLS`/`NO_APPROVAL_MCP_TOOLS` (`ai_handler.py:43-62`) — neither tool
  creates a Morning *document*, so the old names are imprecise; renaming is in scope since both
  tuples are already being edited, not a drive-by refactor of untouched code. Then add
  `"update_client"` to `APPROVAL_REQUIRED_MCP_TOOLS` and move `"add_client"` there from
  `NO_APPROVAL_MCP_TOOLS`.
- No other change: `_build_mcp_tool`, `PendingApprovalManager`, `_is_affirmative_reply`,
  `_resolve_pending_approval`, and the `mcp_approval_request`/`mcp_approval_response` chaining
  (`ai_handler.py:941-1285`) are all reused exactly as built for Feature 022 — zero new code here.

**PendingApprovalManager PROVIDES**: unchanged (`ai_handler.py:329`, one pending approval per
`chat_id`, keyed by `response_id`/`approval_request_id`/`tool_name`).

### `runtime_constitution.md` ↔ model (prompt-level guidance, extended)

**runtime_constitution.md MUST**:
- Move `add_client` out of the "need no confirmation" line (currently line 170) and into the
  "every [...] tool always requires explicit approval first" block (currently lines 174-197),
  alongside a Hebrew pending-action description example (pattern: `"ליצור/לעדכן לקוח ... — לאשר?"`).
- Add `update_client` to that same block.
- Teach the model to **resolve which client "the client" refers to via `get_client_details`
  first, never guessing a name/client_id**, mirroring the existing invoice_id-resolution
  guidance (lines 160-163) — this is the prompt-level defense-in-depth layer; the code-level
  guarantee is `tools.py`'s own search-and-disambiguate step (see contract above).
- Teach the model that `name`/`email`/`phone` are all required for client creation — ask the user
  for whichever is missing rather than calling `add_client` with incomplete data (mirrors the
  existing "missing name" guidance already in `add_client`'s docstring/prompt framing).

## Project Structure

### Documentation (this feature)

```text
specs/in-progress/026-client-management/
├── spec.md               # done, approved
├── user-stories.md       # done, approved
├── checklists/requirements.md
├── plan.md               # this file
├── research.md           # Phase 0 output
├── data-model.md          # Phase 1 output
├── contracts/             # Phase 1 output
│   ├── list_clients.json
│   ├── get_client_details.json
│   ├── update_client.json
│   └── add_client.json    # updated (email/phone required, address removed)
└── quickstart.md          # Phase 1 output
```
(`tasks.md` is Phase 2 output — `/speckit.tasks`, not produced by this command.)

### Source Code

```text
apps/morning-mcp-app/src/denidin_mcp_morning/
├── morning_client.py     # + search_clients, update_client (mirrors existing
│                         #   create_invoice/get_invoice/add_client method style, line ~94)
├── tools.py              # + list_clients, get_client_details, update_client,
│                         #   _resolve_client_by_name (search+disambiguate helper),
│                         #   _validate_email, _normalize_israeli_phone
│                         #   (changed) add_client: email/phone required, address param removed,
│                         #   validation applied before payload build
├── server.py             # + @mcp.tool() list_clients/get_client_details/update_client
│                         #   (changed) add_client tool signature: address param removed
├── models.py             # (changed) Client: address field can stay (still parses whatever
│                         #   Morning returns) but is no longer settable by any tool this
│                         #   feature touches
└── formatters.py          # + format_client_list, format_client_details (mirrors
                            #   format_invoice_list/format_invoice_details style)

apps/morning-mcp-app/tests/integration/
├── test_morning_sandbox_add_client_tool.py   # (changed) mandatory-field + validation tests
├── test_morning_sandbox_list_clients_tool.py       # NEW
├── test_morning_sandbox_get_client_details_tool.py # NEW
└── test_morning_sandbox_update_client_tool.py      # NEW

apps/denidin-app/src/handlers/ai_handler.py
  # rename DOCUMENT_CREATING_MCP_TOOLS → APPROVAL_REQUIRED_MCP_TOOLS (+ add "update_client",
  # "add_client"); rename NON_DOCUMENT_CREATING_MCP_TOOLS → NO_APPROVAL_MCP_TOOLS (- "add_client")
  # require_approval dict construction (line ~546-549): no logic change, just the renamed tuples

apps/denidin-app/config/runtime_constitution.md
  # move add_client into the approval-required block; add update_client; add client-resolution
  # guidance (mirrors invoice_id resolution guidance already present)

apps/denidin-app/tests/expensive/test_denidin_morning_mcp_e2e.py
  # (changed, CONSTITUTION §VIII exception, explicitly approved) rewrite
  # test_godfather_add_client_still_single_turn as a two-turn approve flow; add new scenarios for
  # list_clients/get_client_details/update_client (RBAC-denial, approval-gate, disambiguation)
```

**Structure Decision**: Single-project-per-app structure (unchanged). All new logic lives in
`apps/morning-mcp-app` (tools + client + formatters + tests) since that's where the Morning
integration lives; `apps/denidin-app` gets only the two tuple edits + a runtime-constitution
prompt update — no new denidin-side module, consistent with how Feature 021's `create_*` tools
needed zero denidin-app code changes beyond the approval-tuple entries.

## Phased Execution

### Phase 0 — Research (this plan's Phase 0, see research.md)
Resolve the Green Invoice `/clients` schema/endpoints (already substantially de-risked during
specification — see research.md for the consolidated findings from the checked-in Postman
collection and error-code catalog) and confirm the approval-gate extension mechanism precisely
(already mapped — `ai_handler.py:43-62`/`537-551`, `PendingApprovalManager`). **Checkpoint**: no
unknowns block implementation; only one open verification remains — confirming
`PUT /clients/{id}` accepts a partial payload against the real sandbox (assumed from the Postman
"Update Client" example which only sends `category`/`subCategory`, but not yet empirically
confirmed for our four fields).

### Phase 1 — MorningClient + tools.py foundation (search/get/update), TDD
New `MorningClient` methods, `_resolve_client_by_name`, email/phone validation helpers, and the
three new tool functions + `add_client` changes — each preceded by a real-sandbox test per
CONSTITUTION §V, following METHODOLOGY §VI's EXPLAIN → RED → GREEN → REFACTOR gates.

### Phase 2 — Server registration + formatters
Register the three new `@mcp.tool()`s and update `add_client`'s signature in `server.py`; add
`format_client_list`/`format_client_details`.

### Phase 3 — denidin-app approval-gate + RBAC wiring (TDD, real E2E)
Tuple rename/edit in `ai_handler.py`; `runtime_constitution.md` prompt updates; rewrite the one
existing test per the approved §VIII exception; add new E2E scenarios (list/view read-only,
add-with-approval, update-with-approval, RBAC-denial, disambiguation, phone round-trip
verification per REQ-CLIENT-017).

### Phase 4 — Cross-cutting verification
The dedicated phone round-trip sandbox test (REQ-CLIENT-017); full spec-to-test traceability
pass before `/speckit.analyze`.

## Complexity Tracking

No Constitution Check violations requiring justification — this feature adds no new
infrastructure, no new dependency beyond activating an already-declared one, and reuses the
existing approval-gate mechanism verbatim.
