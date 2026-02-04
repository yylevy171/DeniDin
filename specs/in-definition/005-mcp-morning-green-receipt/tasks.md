```markdown
# tasks.md — Implementation tasks for Feature 005 (MCP → Morning)

Phase 1: Setup
- [ ] T001 [P] Create package skeleton `src/denidin_mcp_morning/` with files: `__init__.py`, `server.py`, `tools.py`, `client.py`, `models.py`, `config.py`, `utils.py` (paths: `src/denidin_mcp_morning/`)
- [ ] T002 [P] Add example config file based on schema: `config/config.example.json` (use `specs/in-definition/005-mcp-morning-green-receipt/artifacts/config.schema.json` as source)
- [ ] T003 [P] Add feature README and quickstart: `specs/in-definition/005-mcp-morning-green-receipt/quickstart.md` (create quickstart that documents `config/config.example.json`, running locally, webhook example)
- [ ] T004 [P] Ensure `specs/in-definition/005-mcp-morning-green-receipt/contracts/` contains JSON schemas for all 8 tools (create missing files): path `specs/in-definition/005-mcp-morning-green-receipt/contracts/`

Phase 2: Foundational (blocking prerequisites)
- [ ] T005  Create Pydantic models: `src/denidin_mcp_morning/models.py` (Invoice, Client, Payment, ExpenseDraft) — implement schema fields and validation per `specs/.../data-model.md`
- [ ] T006a [P] [TEST-Plan] Draft test plan for token lifecycle: list test cases (request token, refresh when TTL<=refresh_before_seconds, missing token responses), map to CHKs, and specify expected failing behaviors.
- [ ] T006b [P] [TEST-Write] Write failing unit tests for token lifecycle behavior: `tests/unit/test_token_lifecycle.py` (should fail initially).
- [ ] T006c [P] [TEST-Approve] Human approval gate: present test plan and failing tests for sign-off before implementation.
- [ ] T007 [P] Implement token manager and HTTP client skeleton in `src/denidin_mcp_morning/client.py` (use `requests`; implement token caching and `get_token()` method) — make tests pass
- [ ] T008  Add rate-limiter utility `src/denidin_mcp_morning/utils.py` (token-bucket with default 3 req/s) and unit tests `tests/unit/test_rate_limiter.py`
- [ ] T009  Add config loader `src/denidin_mcp_morning/config.py` that reads `config/config.json` and validates against `specs/.../artifacts/config.schema.json`

Phase 3: User Stories (priority order)

US1 — Invoice Creation
Independent test criteria: given a valid `create_invoice` input, the MCP tool calls Morning `/documents` and returns the created document JSON (mocked). Files: `src/denidin_mcp_morning/tools.py`, `src/denidin_mcp_morning/client.py`, tests in `tests/unit/test_create_invoice.py`
- [ ] T010a [P] [US1][TEST-Plan] Draft test plan for `create_invoice`: enumerate cases, CHK mappings, mock behavior, expected failures.
- [ ] T010b [P] [US1][TEST-Write] Write failing unit tests for `create_invoice` tool (path: `tests/unit/test_create_invoice.py`).
- [ ] T010c [P] [US1][TEST-Approve] Human approval gate: present test plan and failing tests for sign-off.
- [ ] T011 [US1] Implement `create_invoice` tool function in `src/denidin_mcp_morning/tools.py` and wiring in `server.py` to accept tool input

US2 — Invoice Query / List
Independent test criteria: `list_invoices` accepts filters and returns list JSON; pagination handled if present.
- [ ] T012a [P] [US2][TEST-Plan] Draft test plan for `list_invoices`: filters, pagination, edge cases, CHK mappings.
- [ ] T012b [P] [US2][TEST-Write] Write failing unit tests for `list_invoices` (path: `tests/unit/test_list_invoices.py`).
- [ ] T012c [P] [US2][TEST-Approve] Human approval gate: present test plan and failing tests for sign-off.
- [ ] T013 [US2] Implement `list_invoices` in `src/denidin_mcp_morning/tools.py` and client mapping in `client.py`

US3 — Payment Tracking / Status
Independent test criteria: `get_invoice_details` returns status and payments; `update_invoice_status` updates status via Morning API.
- [ ] T014a [P] [US3][TEST-Plan] Draft test plan for invoice status tools: get details, update status, partial failure scenarios, CHK mappings.
- [ ] T014b [P] [US3][TEST-Write] Write failing tests for `get_invoice_details` and `update_invoice_status` (path: `tests/unit/test_invoice_status.py`).
- [ ] T014c [P] [US3][TEST-Approve] Human approval gate: present test plan and failing tests for sign-off.
- [ ] T015 [US3] Implement `get_invoice_details` and `update_invoice_status` in `tools.py` and client calls in `client.py`

US4 — Client Management
Independent test criteria: `add_client` creates a client and returns the client object; validation on required fields.
- [ ] T016a [P] [US4][TEST-Plan] Draft test plan for `add_client`: required fields, validation, disambiguation flows, CHK mappings.
- [ ] T016b [P] [US4][TEST-Write] Write failing tests for `add_client` tool (path: `tests/unit/test_add_client.py`).
- [ ] T016c [P] [US4][TEST-Approve] Human approval gate: present test plan and failing tests for sign-off.
- [ ] T017 [US4] Implement `add_client` in `tools.py` and client call in `client.py`

US5 — Financial Summaries / Reports
Independent test criteria: `get_financial_summary` returns summary based on period; uses Morning endpoints or aggregates returned data.
- [ ] T018a [P] [US5][TEST-Plan] Draft test plan for `get_financial_summary`: periods, aggregations, edge cases, CHK mappings.
- [ ] T018b [P] [US5][TEST-Write] Write failing tests for `get_financial_summary` (path: `tests/unit/test_financial_summary.py`).
- [ ] T018c [P] [US5][TEST-Approve] Human approval gate: present test plan and failing tests for sign-off.
- [ ] T019 [US5] Implement `get_financial_summary` in `tools.py`

US6 — Send Invoice (WhatsApp)
Independent test criteria: `send_invoice` returns success when publish to WhatsApp stub succeeds; uses DeniDin outbound send service (mocked) to send message with invoice link.
- [ ] T020a [P] [US6][TEST-Plan] Draft test plan for `send_invoice`: WhatsApp integration points, message formatting, failure modes, CHK mappings.
- [ ] T020b [P] [US6][TEST-Write] Write failing tests for `send_invoice` (path: `tests/unit/test_send_invoice.py`).
- [ ] T020c [P] [US6][TEST-Approve] Human approval gate: present test plan and failing tests for sign-off.
- [ ] T021 [US6] Implement `send_invoice` in `tools.py` including `download_invoice_pdf` helper and integration point with DeniDin send API (mocked)

US7 — Download Invoice PDF
Independent test criteria: `download_invoice_pdf` returns a pre-signed URL or Base64 PDF payload from Morning API.
- [ ] T022a [P] [US7][TEST-Plan] Draft test plan for `download_invoice_pdf`: presigned URL vs base64, size limits, CHK mappings.
- [ ] T022b [P] [US7][TEST-Write] Write failing tests for `download_invoice_pdf` (path: `tests/unit/test_download_pdf.py`).
- [ ] T022c [P] [US7][TEST-Approve] Human approval gate: present test plan and failing tests for sign-off.
- [ ] T023 [US7] Implement `download_invoice_pdf` in `tools.py` and client mapping in `client.py`

US8 — Expense Drafts / File Upload Flow
Independent test criteria: `Get File Upload URL` flow returns presigned POST fields and subsequent webhook `expense-draft/parsed` is validated by HMAC using partner auth token and canonicalization rules.
- [ ] T024a [P] [US8][TEST-Plan] Draft test plan for file-upload & webhook verification: presigned POST flow, webhook canonicalization test vectors, replay-window tests, CHK mappings.
- [ ] T024b [P] [US8][TEST-Write] Write failing tests for file-upload flow & webhook verification (path: `tests/unit/test_file_upload_and_webhook.py`). Tests must include:
    - happy path presigned POST -> upload -> webhook delivered and verified
    - canonicalization unit tests (whitespace/key-order variants produce the same canonical payload)
    - signature mismatch rejection
    - replay-window tests using `X-Data-Timestamp` (accept within 5 minutes, reject older)
    - use test vectors kept in `specs/005-mcp-morning-green-receipt/webhook_canonicalization.md`
- [ ] T024c [P] [US8][TEST-Approve] Human approval gate: present test plan and failing tests for sign-off.
    - happy path presigned POST -> upload -> webhook delivered and verified
    - canonicalization unit tests (whitespace/key-order variants produce the same canonical payload)
    - signature mismatch rejection
    - replay-window tests using `X-Data-Timestamp` (accept within 5 minutes, reject older)
    - use test vectors kept in `specs/005-mcp-morning-green-receipt/webhook_canonicalization.md`
- [ ] T025 [US8] Implement presigned upload helper and webhook handler in `src/denidin_mcp_morning/server.py` and `tools.py` (use canonicalization per `specs/005-mcp-morning-green-receipt/webhook_canonicalization.md`)

Phase Final: Polish & Cross-cutting concerns
- [ ] T026  Add logging and monitoring hooks: `src/denidin_mcp_morning/utils.py` (structured logging, error codes mapping from `specs/.../artifacts/error_codes.json`)
- [ ] T027  Add CI job skeleton (pytest runs) and pre-commit hooks (path: `.github/workflows/ci.yml` and `.pre-commit-config.yaml`)
- [ ] T028  Documentation: finalize `specs/in-definition/005-mcp-morning-green-receipt/quickstart.md`, `README.md` under `src/denidin_mcp_morning/` and include sample `config/config.example.json`

- [ ] T029  [INFRA] Design & implement shared token store for multi-worker deployment (Phase‑2): add design doc `specs/005-mcp-morning-green-receipt/token_store.md`, implement Redis-backed token cache adapter and distributed lock pattern (SETNX + short expiry). Add unit tests `tests/unit/test_token_store_redis.py` and integration test scaffolding.
- [ ] T030  [DOC] Consolidate contract schemas: merge `specs/in-definition/005-mcp-morning-green-receipt/contracts/*.json` into `specs/in-definition/005-mcp-morning-green-receipt/artifacts/mcp_tools_schema.json` (or add cross-references). Update `specs/in-definition/005-mcp-morning-green-receipt/README.md` to describe the canonical contract location used by the implementation and CI.

New Cross-cutting Tasks
- [ ] T031  [I18N] Localization / i18n: implement Hebrew templates, number/currency formatting, and RTL handling. Add unit tests for formatting and message templates (tests/unit/test_i18n.py).
- [ ] T032  [PERF] Performance & Monitoring: add metrics instrumentation (p95 latency, error-rate), a CI perf job skeleton, and a performance test plan. Add tests: `tests/perf/test_p95_latency.py` (works with local mock server).
- [ ] T033  [RETRY] Retry & Rate-limit tests: add tests simulating 429 and 5xx responses to validate exponential backoff + jitter and max-retries behavior. Tests: `tests/unit/test_retry_backoff.py`.
- [ ] T034  [US8] Bulk ops confirmation & idempotency: implement confirmation flow for bulk updates and idempotency keys. Add tests: `tests/unit/test_bulk_confirmation.py` and integration scenario in `tests/integration/test_bulk_ops.py`.

Dependencies (story completion order)
- MUST complete: T005 → T006 → T007 → T008 → T009 before implementation tasks (T010..T025)
- Per-story: tests (write failing tests) must precede implementation tasks for that story (e.g., T010 before T011). This enforces TDD requirements from `METHODOLOGY.md`.

Parallel execution examples
- While T005 (models) is in-progress, teams can parallelize: T006 (token tests) and T008 (rate-limiter) and T002 (config example) — mark these tasks with `[P]` above.
- Story-level parallelism: individual stories (US1..US8) are mostly independent after foundational tasks complete; e.g., implement `create_invoice` (US1) and `list_invoices` (US2) in parallel.

Task counts & summary
# tasks.md — Implementation tasks for Feature 005 (MCP → Morning)

Phase 1 — Setup
- [ ] T001 [P] Create package skeleton `src/denidin_mcp_morning/` with files: `__init__.py`, `server.py`, `tools.py`, `client.py`, `models.py`, `config.py`, `utils.py` (path: `src/denidin_mcp_morning/`)
- [ ] T002 [P] Add example config file `config/config.example.json` based on `specs/in-definition/005-mcp-morning-green-receipt/artifacts/config.schema.json`
- [ ] T003 [P] Add feature quickstart `specs/in-definition/005-mcp-morning-green-receipt/quickstart.md` and feature README `specs/in-definition/005-mcp-morning-green-receipt/README.md`
- [ ] T004 [P] Populate `specs/in-definition/005-mcp-morning-green-receipt/contracts/` with 8 JSON schema stubs: `authorize.json`, `receipt_parse.json`, `upload_file.json`, `get_status.json`, `list_receipts.json`, `webhook.json`, `health.json`, `metrics.json` (path: `specs/in-definition/005-mcp-morning-green-receipt/contracts/`)

Phase 2 — Foundational (blocking prerequisites)
- [ ] T005  Create Pydantic models file `src/denidin_mcp_morning/models.py` (Invoice, Client, Payment, ExpenseDraft) per `specs/in-definition/005-mcp-morning-green-receipt/data-model.md`
- [ ] T006  [P] [TEST-Plan] Draft token-lifecycle test plan `specs/in-definition/005-mcp-morning-green-receipt/test-plans/token_lifecycle_test_plan.md`
- [ ] T007  [P] [TEST-Write] Write failing unit tests for token lifecycle: `tests/unit/test_token_lifecycle.py` (cases: request token, refresh when TTL<=refresh_before_seconds, handle missing token)
- [ ] T008  Implement token manager skeleton and HTTP client `src/denidin_mcp_morning/client.py` (token caching + `get_token()`), make tests pass
- [ ] T009  Add rate-limiter utility `src/denidin_mcp_morning/utils.py` (token-bucket default 3 req/s) and unit tests `tests/unit/test_rate_limiter.py`
- [ ] T010  Add config loader `src/denidin_mcp_morning/config.py` that reads `config/config.json` and validates against `specs/in-definition/005-mcp-morning-green-receipt/artifacts/config.schema.json`

Phase 3 — User Stories (priority order)

US1 — Invoice Creation
Independent test criteria: given valid input, MCP tool calls Morning `/documents` and returns created document JSON (mocked).
- [ ] T011 [P] [US1] [TEST-Plan] Draft test plan for `create_invoice` (file: `specs/in-definition/005-mcp-morning-green-receipt/test-plans/create_invoice_test_plan.md`)
- [ ] T012 [P] [US1] [TEST-Write] Write failing unit tests for `create_invoice`: `tests/unit/test_create_invoice.py`
- [ ] T013 [US1] Implement `create_invoice` tool in `src/denidin_mcp_morning/tools.py` and wiring in `src/denidin_mcp_morning/server.py`

US2 — Invoice Query / List
Independent test criteria: filters handled, pagination supported.
- [ ] T014 [P] [US2] [TEST-Plan] Draft test plan for `list_invoices` (`specs/.../test-plans/list_invoices_test_plan.md`)
- [ ] T015 [P] [US2] [TEST-Write] Write failing unit tests: `tests/unit/test_list_invoices.py`
- [ ] T016 [US2] Implement `list_invoices` in `src/denidin_mcp_morning/tools.py` and client mappings in `src/denidin_mcp_morning/client.py`

US3 — Payment Tracking / Status
- [ ] T017 [P] [US3] [TEST-Plan] Draft test plan for `get_invoice_details` and `update_invoice_status`
- [ ] T018 [P] [US3] [TEST-Write] Write failing unit tests: `tests/unit/test_invoice_status.py`
- [ ] T019 [US3] Implement `get_invoice_details` and `update_invoice_status` in `src/denidin_mcp_morning/tools.py` and `client.py`

US4 — Client Management
- [ ] T020 [P] [US4] [TEST-Plan] Draft test plan for `add_client`
- [ ] T021 [P] [US4] [TEST-Write] Write failing unit tests: `tests/unit/test_add_client.py`
- [ ] T022 [US4] Implement `add_client` in `src/denidin_mcp_morning/tools.py` and client call in `client.py`

US5 — Financial Summaries / Reports
- [ ] T023 [P] [US5] [TEST-Plan] Draft test plan for `get_financial_summary`
- [ ] T024 [P] [US5] [TEST-Write] Write failing unit tests: `tests/unit/test_financial_summary.py`
- [ ] T025 [US5] Implement `get_financial_summary` in `src/denidin_mcp_morning/tools.py`

US6 — Send Invoice (WhatsApp)
- [ ] T026 [P] [US6] [TEST-Plan] Draft test plan for `send_invoice`
- [ ] T027 [P] [US6] [TEST-Write] Write failing unit tests: `tests/unit/test_send_invoice.py`
- [ ] T028 [US6] Implement `send_invoice` (uses DeniDin send API integration) in `src/denidin_mcp_morning/tools.py`

US7 — Download Invoice PDF
- [ ] T029 [P] [US7] [TEST-Plan] Draft test plan for `download_invoice_pdf`
- [ ] T030 [P] [US7] [TEST-Write] Write failing unit tests: `tests/unit/test_download_pdf.py`
- [ ] T031 [US7] Implement `download_invoice_pdf` in `src/denidin_mcp_morning/tools.py` and `client.py`

US8 — File Upload Flow & Webhook Verification
- [ ] T032 [P] [US8] [TEST-Plan] Draft test plan for file-upload & webhook verification (`specs/.../test-plans/file_upload_webhook_test_plan.md`)
- [ ] T033 [P] [US8] [TEST-Write] Write failing unit tests for presigned upload flow & webhook canonicalization: `tests/unit/test_file_upload_and_webhook.py` (use `specs/in-definition/005-mcp-morning-green-receipt/artifacts/webhook_test_vectors.json`)
- [ ] T034 [US8] Implement presigned upload helper and webhook handler in `src/denidin_mcp_morning/server.py` and `tools.py` (use canonicalization per `specs/in-definition/005-mcp-morning-green-receipt/webhook_canonicalization.md`)

Phase Final — Polish & Cross-cutting concerns
- [ ] T035  Add structured logging and error-code mapping in `src/denidin_mcp_morning/utils/logging.py`
- [ ] T036  Add CI job skeleton and test runner `.github/workflows/ci.yml` (pytest runs) and `.pre-commit-config.yaml`
- [ ] T037  Expand and finalize contract schemas: update `specs/in-definition/005-mcp-morning-green-receipt/contracts/*.json` into full JSON Schemas and merge references into `specs/in-definition/005-mcp-morning-green-receipt/artifacts/mcp_tools_schema.json`
- [ ] T038  Implement Redis-backed token store adapter `src/denidin_mcp_morning/token_store/redis_adapter.py` and tests `tests/unit/test_token_store_redis.py` (T029 in original plan)
- [ ] T039  Documentation: finalize `specs/in-definition/005-mcp-morning-green-receipt/quickstart.md` and `src/denidin_mcp_morning/README.md` and `config/config.example.json`
- [ ] T040  Add CI/Repo guard: add a lint job to detect spec files recommending environment variables for runtime config and fail the job if found (`.github/workflows/ci.yml`)

Dependencies & Notes
- MUST complete foundational tasks T005 → T007 → T008 → T009 → T010 before story implementation tasks T011..T034
- Story-level rule: For each US, write failing tests (TEST-Write) and get human approval (where required) before implementing the feature code.

MVP suggestion
- Implement MVP = T001, T002, T005, T006, T007, T012, T013 (package skeleton + config + models + token lifecycle + create_invoice tests + implementation).
