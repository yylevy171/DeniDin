# Tasks: MCP Server for Morning (Green Invoice) — Feature 005

**Spec**: `./spec.md` · **Plan**: `./plan.md` · **User stories**: `./user-stories.md`
**App**: `apps/morning-mcp-app/` · **Branch**: `feature/005-morning-mcp-server`

## Conventions

- **All paths are relative to `apps/morning-mcp-app/`** unless noted.
- Task ID: `T###`. `[P]` = parallelizable. `[US#]` = user story.
- **TDD gate (METHODOLOGY §VI, TDD-ENFORCEMENT.md)**: for each tool, the test task (A) is
  written first, must **fail** (RED), and needs **explicit human approval** before the
  implementation task (B). Tests are immutable once approved.
- **Testing rule (CONSTITUTION §V, ZERO-MOCKING, project preference)**: **real Morning-
  sandbox integration tests only** under `tests/integration/`. No `unittest.mock`, no
  `requests-mock`, no mock-based unit tests. Follow the existing
  `tests/integration/test_morning_sandbox_*.py`. Sandbox is free → these are **not**
  `@pytest.mark.expensive`.
- **Already implemented, do not recreate**: `src/denidin_mcp_morning/auth.py` (MorningAuth,
  JWT) and `src/denidin_mcp_morning/morning_client.py` (`create_invoice`, `list_invoices`,
  `get_invoice`) + their sandbox tests.

---

## Phase 1 — Foundation

- [x] **T001** Add `mcp` (FastMCP) and `pydantic` to `requirements.txt`; pin compatible
  versions; `pip install -r requirements.txt` succeeds. **Note**: `mcp` requires Python
  ≥3.10 — app bumped to Python 3.11 (`Dockerfile` now `python:3.11-slim`; local venv
  recreated with `python3.11`; README updated). Also added `email-validator` (required by
  Pydantic `EmailStr`) and `jsonschema`.
- [x] **T002** [P] Extend `config/config.example.json` to the full flat shape from
  `artifacts/config.schema.json` (added `default_currency`, `default_vat_rate`,
  `token_ttl_seconds`, `refresh_before_seconds`, `rate_limit_per_second`, `mcp{}`,
  `feature_flags.enable_mcp_server`). **Also fixed**: the file previously contained a real
  (committed) sandbox secret identical to `config.test.json`, violating CONSTITUTION §I's
  "safe placeholder values" rule for example configs — replaced with placeholder text;
  `config.test.json` (which intentionally holds real sandbox creds for the integration
  tests) was left untouched.
- [x] **T003** Implemented `src/denidin_mcp_morning/config.py`: loads flat
  `config/config.json` via `pathlib.Path`, validates against a **self-contained**
  `config/config.schema.json` (copied into the app; the `specs/.../artifacts/` copy isn't
  shipped in the Docker image) via `jsonschema`. No env vars (test asserts this).
  Tests: `tests/unit/test_config.py` (7 tests).
- [x] **T004** [P] Implemented `src/denidin_mcp_morning/models.py`: Pydantic `Invoice`,
  `Client`, `Payment`, `FinancialSummary` mapping the real Morning document shape (nested
  `client{}`/`emails[]`, `date`/`dueDate`, `total`/`vatAmount`); UTC-aware where applicable.
  Tests: `tests/unit/test_models.py` (8 tests).
- [x] **T005** [P] Implemented `src/denidin_mcp_morning/formatters.py`: Hebrew/₪/VAT/date
  (DD/MM/YYYY) formatting + Hebrew status terms (שולם/לא שולם/פג תוקף/בוטל).
  Tests: `tests/unit/test_formatters.py` (8 tests).

**Checkpoint**: ✅ met — config loads+validates (incl. rejecting the old nested shape);
models validate a real `/documents` response; `pytest tests/ --collect-only` collects 35
tests (25 new unit + the 10 existing sandbox integration tests, unchanged). Full unit run:
25/25 passed.

---

## Phase 2 — Client extension + MCP tools (per user story, TDD)

> Foundational auth/token/client (3 ops) already exist. For each story: **A** (failing
> real-sandbox test) → **human approval** → **B** (implement client method if needed + the
> `@mcp.tool()` wrapper in `tools.py`).

### US1 — `create_invoice` (client method exists)
- [x] **T006a** [US1] Wrote failing real-sandbox test
  `tests/integration/test_morning_sandbox_create_invoice_tool.py` driving the MCP tool
  (input mapping → `MorningClient.create_invoice` → sandbox document created). Confirmed
  RED (`ModuleNotFoundError: denidin_mcp_morning.tools`) before implementation.
- [x] **T006b** [US1] Implemented `create_invoice` tool in `src/denidin_mcp_morning/tools.py`
  (maps friendly inputs → Morning `/documents` payload — type 305, one `income[]` line, one
  `payment[]` line since the sandbox requires at least one — then formats a Hebrew
  confirmation). **Real-sandbox finding**: Morning's response returns `number` as an int
  (e.g. `50002`), not a string as `models.Invoice` originally assumed; fixed with a
  `field_validator` coercion in `models.py` + a new regression test in
  `tests/unit/test_models.py` (existing approved tests left unmodified, per Test
  Immutability). Both sandbox tests + all 26 unit tests pass; 38/38 full suite green.

### US2 — `list_invoices` (client method exists)
- [x] **T007a** [US2] Wrote failing real-sandbox test
  `test_morning_sandbox_list_invoices_tool.py` (seeds a real invoice via US1's
  `create_invoice`, finds it by `client_name`; no-match returns a readable string;
  ≤10-item cap). Confirmed RED (`ImportError: list_invoices`) before implementation.
- [x] **T007b** [US2] Implemented `list_invoices` in `tools.py`: maps friendly filters
  (`from_date`/`to_date`/`client_name`) onto Morning's real `/documents/search` params
  (`fromDate`/`toDate`/`clientName`); `status` filtered **client-side** (server-side param
  name unconfirmed in available docs); each result parsed via the existing `Invoice` model,
  skipping unparseable items; new `formatters.format_invoice_list()` caps at 10 with a
  "more results" note. **Real-sandbox finding**: `/documents/search` returns `status` as an
  int document-status code, not a string — queried the live `GET /documents/statuses`
  endpoint to get the authoritative mapping (0=open, 1=closed, 2=manually closed,
  3=cancelling, 4=cancelled) and added a `field_validator` on `Invoice.status` mapping
  these onto this app's paid/unpaid/cancelled vocabulary, with new regression tests
  (existing approved tests left unmodified). 47/47 full suite green.

### US3 — `get_invoice_details` (client method exists) + `update_invoice_status` (new)
- [x] **T008a** [US3] Wrote failing real-sandbox test `test_morning_sandbox_invoice_status_tools.py`
  (get details returns status/dates; paid/unpaid/cancelled transitions; idempotency and
  rejection edge cases). Confirmed RED before implementation.
- [x] **T008b** [US3] Implemented `get_invoice_details` (new `formatters.format_invoice_details`)
  and `update_invoice_status` in `tools.py`. **Real-sandbox findings that changed the design
  from what the contract assumed**:
  - There is no `PUT /documents/{id}/status`. `POST /documents/{id}/close` and `/open` exist
    (added to `MorningClient`) but return 400 (`errorCode 3000`) for tax invoices (type 305) —
    live testing showed they only apply to other document lifecycles (orders/proformas), not
    invoices.
  - **"paid"** is instead achieved by issuing a **linked Receipt** (type 400,
    `linkedDocumentIds=[invoice_id]`) via the existing generic `POST /documents` — confirmed
    live: this flips the original's `status` automatically (`None`/`0` → `1`). Idempotent
    no-op if already paid.
  - **"unpaid"**: idempotent no-op if not yet paid; raises `ValueError` if already paid —
    `POST /documents/{id}/open` on a receipt-closed invoice returns 400
    (`errorCode 2401`, `"לא ניתן לפתוח מסמך שאינו סגור ידנית"` — cannot reopen a document that
    wasn't manually closed). No supported reversal exists.
  - **"cancelled" — the case the user explicitly asked to fully support** (mistake made
    creating an invoice; needs voiding so a corrected one can be created): implemented as a
    linked **Credit Invoice** (type 330, `"חשבונית זיכוי"` — confirmed live via
    `GET /documents/types`) via the same generic `POST /documents`, since Israeli law forbids
    deleting/voiding an issued tax invoice outright. `contracts/update_invoice_status.json`
    updated to document all of the above (its original `PUT .../status` assumption was wrong).
  - Status codes (0/1/2/3/4) were confirmed live via `GET /documents/statuses` (see US2 entry).
  - 53/53 full suite green (32 unit + 21 integration).

### US4 — `add_client` (new)
- [x] **T009a** [US4] Wrote failing real-sandbox test `test_morning_sandbox_add_client_tool.py`
  (name-only and full-details cases). Confirmed RED (`ImportError: add_client`) before
  implementation.
- [x] **T009b** [US4] Added `MorningClient.add_client` (`POST /clients`) and the `add_client`
  tool in `tools.py`. Real field names confirmed via the Postman collection's "Add Client"
  example: `emails` (list, not singular `email`), `taxId` (camelCase, not `tax_id`).
  **Real-sandbox finding**: `phone` doesn't appear in the Postman collection's client
  examples at all, so it looked possibly unsupported — tested live and confirmed it **is** a
  real, valid field (round-tripped correctly in the response); the Postman example response
  simply hadn't set it. The only real failure hit was a test-data bug, not a code bug:
  `tax_id="123456789"` fails Morning's Israeli-tax-ID checksum validation (errorCode 1111,
  `"מספר עוסק / ח.פ אינו תקין"`) — fixed by reusing the Postman collection's own known-valid
  example ID (`308253681`). 55/55 full suite green (one unrelated flaky rerun in
  `list_invoices` due to sandbox indexing delay under concurrent test load — passes reliably
  in isolation, not a regression).

### US5 — `get_financial_summary` (new)
- [x] **T010a** [US5] Wrote failing real-sandbox test `test_morning_sandbox_financial_summary_tool.py`
  (month period includes a seeded invoice; custom period requires both dates; unknown period
  rejected; zero-result custom range returns ₪0.00). Confirmed RED before implementation.
- [x] **T010b** [US5] Implemented `get_financial_summary` in `tools.py`, aggregating
  client-side over the existing `MorningClient.list_invoices` (`POST /documents/search`) —
  Morning has **no dedicated summary/aggregation endpoint** (confirmed against the Postman
  collection). New `formatters.format_financial_summary` + reused `FinancialSummary` model.
  **Real-sandbox finding with a genuine scoping consequence**: cancelling an invoice (US3)
  issues a linked Credit Invoice but does **not** change the original's own `status`
  (confirmed live — still `0`/unpaid after cancellation), and `linkedDocumentIds` is not
  returned on read for either document. Since this app is deliberately stateless (`plan.md`),
  a specific cancelled invoice cannot be excluded from the paid/unpaid tally without adding
  persistence this app doesn't have. Documented approximation: counts/paid/unpaid classify
  only primary sale types (305/320); Credit Invoice (330) amounts are netted out of
  `total_invoiced` so cancelled invoices don't inflate reported revenue, but their count still
  shows in `invoice_count`/`unpaid_invoice_count`. `contracts/get_financial_summary.json`
  updated to document this. 59/59 full suite green.

### US6 — `send_invoice` — DROPPED (not a tool; see spec.md §Scope)
- [x] **T011** [US6] Investigated `POST /documents/{id}/distribute` (Postman-only endpoint)
  live: returns `errorCode 3003` "unsupported operation type" regardless of document type
  (305/320) or the `senderEnabled` account setting (tested both `false`→`true`→reverted).
  **Proved this is not a sandbox restriction but a genuinely undocumented endpoint**: diffed
  every `documents/*` path in the full official API reference (`jsapi.apiary.io`) — `info`,
  `payments`, `preview`, `search`, `statuses`, `templates`, `types`, `{id}` are all
  documented and all work; `distribute`/`send` appear nowhere in it, while every other
  endpoint this app actually uses does. Conclusion: `/distribute` is an internal,
  browser-session-only endpoint behind Morning's own web UI "Send" button, not a supported
  partner/API-key integration point — no amount of payload tweaking would fix this.
  **Decision**: drop `send_invoice` entirely rather than ship a tool that can never work, or
  redefine it as a thin "assemble info" wrapper — a wrapper would only recombine
  `get_invoice_details` + `download_invoice_pdf`, which the calling MCP client can already
  compose itself. Removed the in-progress (uncommitted) `tools.send_invoice`,
  `MorningClient.distribute_invoice`, `contracts/send_invoice.json`, and the corresponding
  test file. `spec.md`/`user-stories.md`/`plan.md` updated to 7 tools.

### US7 — `download_invoice_pdf` (new)
- [ ] **T012a** [US7] Failing real-sandbox test `test_morning_sandbox_download_pdf_tool.py`
  (returns PDF URL or Base64).
- [ ] **T012b** [US7] Add `MorningClient.get_invoice_pdf` and the `download_invoice_pdf`
  tool in `tools.py`.

**Checkpoint**: all 7 tools callable end-to-end against the sandbox; every tool's test was
RED before its implementation.

---

## Phase 3 — FastMCP server + E2E dispatch

- [ ] **T013** Implement `src/denidin_mcp_morning/server.py`: FastMCP server registering all
  7 tools via `@mcp.tool()`, served over **streamable-HTTP** on configured host/port;
  `MorningClient` injected; startup gated by `feature_flags.enable_mcp_server`.
- [ ] **T014a** E2E test `tests/integration/test_mcp_server_e2e.py`: start the FastMCP
  server, connect an MCP client, list tools (assert all 8 present) and invoke one against
  the sandbox — proves registration/dispatch (CONSTITUTION §V routing). Real, no mocks.
- [ ] **T014b** Make T014a pass (wire server ↔ tools ↔ client).

**Checkpoint**: an OpenAI-style remote MCP client can discover + call the tools locally.

---

## Phase 4 — Polish & cross-cutting

- [ ] **T015** Structured logging + friendly error mapping (spec §Error Handling;
  `artifacts/error_codes.json`), correlation IDs, secret masking. No mocks.
- [ ] **T016** Finalize Hebrew i18n in `formatters.py` (asserted within the real-sandbox
  tool tests, not separate mock unit tests).
- [ ] **T017** [P] Update `Dockerfile` `CMD` to run the server; document local run in
  `../.../quickstart.md` and `src/denidin_mcp_morning/README.md`.
- [ ] **T018** [P] Update `../.../checklists/comprehensive.md` residual items as they land.

---

## Dependencies

- Phase 1 (T001–T005) before Phase 2.
- Per story: `a` (approved failing test) **before** `b` (implementation).
- Phase 3 (server) after the 7 tools exist. Phase 4 last.

## MVP

T001, T003, T004, T005, T006a/b (config + models + formatters + `create_invoice` tool with
real-sandbox test), then T013 + T014 for a minimal callable MCP server.

## Out of scope (see spec §Future Work)

WhatsApp delivery via denidin-app (architecture TBD); receipt-parsing/file-upload/webhook
product (`specs/in-definition/017-mcp-morning-receipt-parsing/`); Redis multi-worker token
store; multi-tenant scale; performance-SLA work.
