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
- [ ] **T006a** [US1] Write failing real-sandbox test
  `tests/integration/test_morning_sandbox_create_invoice_tool.py` driving the MCP tool
  (input mapping → `MorningClient.create_invoice` → sandbox document created).
- [ ] **T006b** [US1] Implement `create_invoice` tool in `src/denidin_mcp_morning/tools.py`
  (validate vs `contracts/create_invoice.json`, map friendly inputs → Morning payload,
  format response).

### US2 — `list_invoices` (client method exists)
- [ ] **T007a** [US2] Failing real-sandbox test `test_morning_sandbox_list_invoices_tool.py`
  (filters, ≤10 items + continuation token).
- [ ] **T007b** [US2] Implement `list_invoices` tool in `tools.py`.

### US3 — `get_invoice_details` (client method exists) + `update_invoice_status` (new)
- [ ] **T008a** [US3] Failing real-sandbox test `test_morning_sandbox_invoice_status_tools.py`
  (get details returns status/payments; update status via `PUT /documents/{id}`).
- [ ] **T008b** [US3] Add `MorningClient.update_invoice_status` (`PUT /documents/{id}`) and
  implement `get_invoice_details` + `update_invoice_status` tools in `tools.py`.

### US4 — `add_client` (new)
- [ ] **T009a** [US4] Failing real-sandbox test `test_morning_sandbox_add_client_tool.py`
  (required `name`; creates client, returns id).
- [ ] **T009b** [US4] Add `MorningClient.add_client` (`POST /clients`) and the `add_client`
  tool in `tools.py`.

### US5 — `get_financial_summary` (new)
- [ ] **T010a** [US5] Failing real-sandbox test `test_morning_sandbox_financial_summary_tool.py`
  (period → totals/counts).
- [ ] **T010b** [US5] Add `MorningClient.get_financial_summary` (`POST /documents/search`
  aggregation) and the tool in `tools.py`.

### US6 — `send_invoice` (new; Morning-native send, NO denidin-app dependency)
- [ ] **T011a** [US6] Failing real-sandbox test `test_morning_sandbox_send_invoice_tool.py`
  (send via `POST /documents/{id}/send`; missing-contact error path).
- [ ] **T011b** [US6] Add `MorningClient.send_invoice` and the `send_invoice` tool in
  `tools.py`. Must not import/call `denidin-app`.

### US7 — `download_invoice_pdf` (new)
- [ ] **T012a** [US7] Failing real-sandbox test `test_morning_sandbox_download_pdf_tool.py`
  (returns PDF URL or Base64).
- [ ] **T012b** [US7] Add `MorningClient.get_invoice_pdf` and the `download_invoice_pdf`
  tool in `tools.py`.

**Checkpoint**: all 8 tools callable end-to-end against the sandbox; every tool's test was
RED before its implementation.

---

## Phase 3 — FastMCP server + E2E dispatch

- [ ] **T013** Implement `src/denidin_mcp_morning/server.py`: FastMCP server registering all
  8 tools via `@mcp.tool()`, served over **streamable-HTTP** on configured host/port;
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
- Phase 3 (server) after the 8 tools exist. Phase 4 last.

## MVP

T001, T003, T004, T005, T006a/b (config + models + formatters + `create_invoice` tool with
real-sandbox test), then T013 + T014 for a minimal callable MCP server.

## Out of scope (see spec §Future Work)

WhatsApp delivery via denidin-app (architecture TBD); receipt-parsing/file-upload/webhook
product (`specs/in-definition/017-mcp-morning-receipt-parsing/`); Redis multi-worker token
store; multi-tenant scale; performance-SLA work.
