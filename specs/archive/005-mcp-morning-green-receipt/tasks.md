```markdown
# tasks.md — Implementation tasks for Feature 005 (MCP → Morning)

Phase 1: Setup
- [ ] T001 [P] Create package skeleton `src/denidin_mcp_morning/` with files: `__init__.py`, `server.py`, `tools.py`, `client.py`, `models.py`, `config.py`, `utils.py` (paths: `src/denidin_mcp_morning/`)
- [ ] T002 [P] Add example config file based on schema: `config/config.example.json` (use `specs/in-definition/005-mcp-morning-green-receipt/artifacts/config.schema.json` as source)
- [ ] T003 [P] Add feature README and quickstart: `specs/in-definition/005-mcp-morning-green-receipt/quickstart.md` (create quickstart that documents `config/config.example.json`, running locally, webhook example)
- [ ] T004 [P] Ensure `specs/in-definition/005-mcp-morning-green-receipt/contracts/` contains JSON schemas for all 8 tools (create missing files): path `specs/in-definition/005-mcp-morning-green-receipt/contracts/`

Phase 2: Foundational (blocking prerequisites)
- [ ] T005  Create Pydantic models: `src/denidin_mcp_morning/models.py` (Invoice, Client, Payment, ExpenseDraft) — implement schema fields and validation per `specs/.../data-model.md`
- [ ] T006 [P] [TEST] Write failing unit tests for token lifecycle behavior: `tests/unit/test_token_lifecycle.py` (describe: request token, refresh when TTL<=refresh_before_seconds, handle missing token responses)
- [ ] T007 [P] Implement token manager and HTTP client skeleton in `src/denidin_mcp_morning/client.py` (use `requests`; implement token caching and `get_token()` method) — make tests pass
- [ ] T008  Add rate-limiter utility `src/denidin_mcp_morning/utils.py` (token-bucket with default 3 req/s) and unit tests `tests/unit/test_rate_limiter.py`
- [ ] T009  Add config loader `src/denidin_mcp_morning/config.py` that reads `config/config.json` and validates against `specs/.../artifacts/config.schema.json`

Phase 3: User Stories (priority order)

US1 — Invoice Creation
Independent test criteria: given a valid `create_invoice` input, the MCP tool calls Morning `/documents` and returns the created document JSON (mocked). Files: `src/denidin_mcp_morning/tools.py`, `src/denidin_mcp_morning/client.py`, tests in `tests/unit/test_create_invoice.py`
- [ ] T010 [P] [US1] [TEST] Write failing unit tests for `create_invoice` tool behavior (path: `tests/unit/test_create_invoice.py`)
- [ ] T011 [US1] Implement `create_invoice` tool function in `src/denidin_mcp_morning/tools.py` and wiring in `server.py` to accept tool input

US2 — Invoice Query / List
Independent test criteria: `list_invoices` accepts filters and returns list JSON; pagination handled if present.
- [ ] T012 [P] [US2] [TEST] Write failing unit tests for `list_invoices` (path: `tests/unit/test_list_invoices.py`)
- [ ] T013 [US2] Implement `list_invoices` in `src/denidin_mcp_morning/tools.py` and client mapping in `client.py`

US3 — Payment Tracking / Status
Independent test criteria: `get_invoice_details` returns status and payments; `update_invoice_status` updates status via Morning API.
- [ ] T014 [P] [US3] [TEST] Write failing tests for `get_invoice_details` and `update_invoice_status` (path: `tests/unit/test_invoice_status.py`)
- [ ] T015 [US3] Implement `get_invoice_details` and `update_invoice_status` in `tools.py` and client calls in `client.py`

US4 — Client Management
Independent test criteria: `add_client` creates a client and returns the client object; validation on required fields.
- [ ] T016 [P] [US4] [TEST] Write failing tests for `add_client` tool (path: `tests/unit/test_add_client.py`)
- [ ] T017 [US4] Implement `add_client` in `tools.py` and client call in `client.py`

This tasks document was consolidated into `specs/in-definition/005-mcp-morning-green-receipt/tasks.md`.

Please make edits in the `in-definition` folder; the prerequisite checker will read from `in-definition` when canonical files are not present.
- [ ] T019 [US5] Implement `get_financial_summary` in `tools.py`

```
