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
- [x] **T012a** [US7] Wrote failing real-sandbox test `test_morning_sandbox_download_pdf_tool.py`
  (returns a real download URL; nonexistent invoice raises). Confirmed RED
  (`ImportError: download_invoice_pdf`) before implementation.
- [x] **T012b** [US7] Implemented `download_invoice_pdf` in `tools.py`. **No new client
  method needed** — `GET /documents/{id}` (the existing `MorningClient.get_invoice`) already
  returns a `url: {he, origin}` object with ready-to-use, pre-signed PDF download links
  (`GET /documents/download?d=...`); confirmed live on both a create response and a
  subsequent `get_invoice` fetch. 61/61 full suite green.

**Checkpoint**: ✅ met — all 7 tools callable end-to-end against the sandbox; every tool's
test was RED before its implementation.

---

## Phase 3 — FastMCP server + E2E dispatch

- [x] **T013** Implemented `src/denidin_mcp_morning/server.py`: FastMCP server registering
  all 7 tools via `@mcp.tool()`, served over **streamable-HTTP** on configured host/port;
  `MorningClient` injected via `create_server(config, client=...)` (no globals). Startup
  gated by `feature_flags.enable_mcp_server` — confirmed the process exits immediately with
  a clear message when the flag is `false` (default), and builds correctly when `true`.
  Each `@mcp.tool()` wrapper takes only caller-facing args (no `client` param) so FastMCP's
  auto-generated inputSchema matches the real tool contracts.
- [x] **T014a** Wrote E2E test `tests/integration/test_mcp_server_e2e.py`: starts the actual
  FastMCP server (via `uvicorn.Server` in a background thread, using
  `mcp.streamable_http_app()`), connects a real MCP client
  (`mcp.client.streamable_http.streamable_http_client` + `ClientSession`), lists tools, and
  invokes `create_invoice` against the live sandbox.
- [x] **T014b** Passed on first run: `list_tools()` returns exactly the 7 expected tool
  names, and the `create_invoice` call reaches the real sandbox end-to-end (client name +
  formatted amount confirmed in the tool's response) — proves registration/dispatch
  (CONSTITUTION §V routing), not just that `tools.py` functions work in isolation.
  63/63 full suite green (32 unit + 31 integration).

**Checkpoint**: ✅ met — an OpenAI-style remote MCP client can discover + call the tools
locally (verified against a real, running streamable-HTTP server).

---

## Phase 4 — Polish & cross-cutting

- [x] **T015** Implemented friendly error mapping: new `errors.py`
  (`friendly_error_message()` + `mask_secret()`), wired into `server.py` via a
  `_call_with_error_boundary()` wrapper applied to all 7 `@mcp.tool()` registrations.
  **Real finding driving this task**: empirically confirmed FastMCP's default behavior, with
  no mapping layer, surfaces the *raw* exception string to the MCP caller — e.g.
  `"Error executing tool get_invoice_details: 404 Client Error: Not Found for url:
  https://sandbox.d.greeninvoice.co.il/api/v1/documents/..."` — leaking the internal API URL
  and violating CONSTITUTION §X. New E2E test
  `test_mcp_tool_error_is_friendly_not_a_raw_stack_trace` in `test_mcp_server_e2e.py` (RED
  confirmed before the fix, now passes) plus 13 new unit tests in `tests/unit/test_errors.py`
  (real `requests.Response`/`HTTPError` objects, no mocking). Full technical detail still
  goes to logs (WARNING/ERROR) with a per-call correlation id. Correlation-ID/secret-masking
  plumbing here is deliberately minimal — the full logging *infrastructure*
  (dedicated app log file + per-test log files, mirroring denidin-app) is queued as Phase 5
  T019, not duplicated here.
- [x] **T016** Finalized Hebrew i18n. Success-path formatting (`formatters.py`) was already
  fully Hebrew and asserted within the real-sandbox tool tests. **Found and fixed a real
  inconsistency**: `errors.py`'s mapped messages, and `tools.py`'s raised `ValueError` text,
  were in English despite `REQ-I18N-001` ("Hebrew by default") — translated all 6 static
  error messages to Hebrew; business-rule `ValueError`s now return a generic Hebrew message
  to the caller (the specific English detail is logged, not echoed — see
  `test_value_error_never_echoes_raw_english_text`). `spec.md` §Error Handling table
  corrected to show the actual Hebrew text (it previously showed English placeholders despite
  its own column header promising Hebrew) and to stop claiming unimplemented richer UX (amount
  pre-validation, fuzzy client-match disambiguation, `send_invoice`-era messaging) as if it
  existed — those are now explicitly noted as deferred. 77/77 full suite green.
- [x] **T017** [P] `Dockerfile` `CMD` updated to run the real server (done in Phase 3, T013).
  Remaining scope: quickstart docs — **not yet done**, tracked below.
- [x] **T017-quickstart** [P] Rewrote `../.../quickstart.md` — it was fully stale (nested
  config, wrong flag name `enable_morning_integration`, FastAPI/uvicorn run pattern, and a
  webhook-HMAC example that belongs to the split-off 017 feature). Now: flat config, correct
  `enable_mcp_server` gate, real `python3 -m denidin_mcp_morning.server` start command, and a
  working MCP-client manual-check snippet — **verified live** (listed the 7 tools + created a
  real sandbox invoice via the exact documented snippet). README's "Running the MCP server"
  section (added Phase 3) already covers the same.
- [x] **T018** [P] Updated `../.../checklists/comprehensive.md`: added an Implementation
  Status section, corrected 8→7 tool references, and pointed observability items at
  T015 (done) vs Phase 5 T019 (queued).

---

## Phase 5 — Queued follow-up (after Phase 4; user-requested 2026-07-09)

Mirror denidin-app's own patterns exactly (inspected live from
`apps/denidin-app/` — `conftest.py`, `src/utils/logger.py`, `run_denidin.sh`,
`stop_denidin.sh`, `restart_denidin.sh`, `pytest.ini`, `tests/expensive/`).

- [x] **T019** [LOGGING] Application + per-test logging, mirroring denidin-app (verified,
  not just adapted):
  - `src/denidin_mcp_morning/utils/logger.py` — `setup_logger()`/`get_logger()`, ported
    line-for-line from denidin-app's `src/utils/logger.py` (only the default filename
    changed: `morning-mcp.log`). `RotatingFileHandler` (10MB, 5 backups) + console handler;
    `propagate=False` in production. 8 new unit tests in `tests/unit/test_logger.py`
    (adapted from denidin-app's own logger tests) — all pass.
  - Wired into `tools.py`, `errors.py`, `server.py` (previously used bare
    `logging.getLogger(__name__)`, which has no handler in production and silently drops
    everything) via `get_logger(__name__)`. **Verified live**: started the server with
    `feature_flags.enable_mcp_server=true` and confirmed a real line appeared in
    `logs/morning-mcp.log`.
  - `conftest.py` — added the `pytest_runtest_setup` hook, ported line-for-line from
    denidin-app's `conftest.py`. **Verified**: a full suite run produces one dedicated
    `logs/test_logs/{test_file}.log` per test file (14 files), each containing that file's
    own log lines (confirmed `denidin_mcp_morning.errors`/`.tools` correlation-id log lines
    appear correctly in `test_mcp_server_e2e.log`).
  - `logs/` already gitignored (was from the start); added `.morning_mcp.pid` to
    `.gitignore` (see T020) since it wasn't covered yet.
- [x] **T020** [SCRIPTS] `run_morning_mcp.sh` / `stop_morning_mcp.sh` /
  `restart_morning_mcp.sh` at `apps/morning-mcp-app/`, ported from denidin-app's PID-file
  scripts (same structure: PID-file + orphan-process guard, `nohup` background start,
  graceful `SIGTERM`→10s-wait→`SIGKILL` stop, `restart` = stop then start).
  **Real bug found and fixed during live testing**: the first draft called bare `python3`,
  which in a fresh shell (no venv activated) resolved to system Python 3.9 lacking the
  `mcp` package — the background process crashed immediately, **silently**, because
  `nohup ... >/dev/null 2>&1` swallowed the import error before any of our own logging
  even initialized. Fixed by having the script prefer `$SCRIPT_DIR/venv/bin/python3`
  explicitly (falling back to ambient `python3` with a warning if no local venv exists) —
  this is the deeper reason this class of bug matters: a script that "usually works" only
  because the operator happened to have the venv active is not actually robust. **Verified
  live end-to-end** (start → confirm PID/log → double-start correctly rejected → stop →
  confirm clean shutdown → restart → stop again), all against a temporarily-flag-enabled
  copy of the real `config.json` (restored to original afterward; no tool calls made during
  the test, since that config's `api_url` points at production, not sandbox).
- [x] **T021-auth** [SECURITY, prerequisite for T021] Bearer-token auth for the MCP server.
  **Why this became necessary**: T021 requires exposing the local server publicly (via a
  tunnel) for OpenAI's remote-MCP connector to reach it; the server had zero authentication,
  and its tools include state-changing operations (`create_invoice`, `update_invoice_status`
  which can cancel an invoice via a real credit note, `add_client`) — a permanently or even
  transiently public unauthenticated endpoint could be used by anyone who finds the URL.
  **Design decision**: FastMCP's built-in `auth`/`token_verifier` is full OAuth 2.1
  resource-server machinery (`AuthSettings` requires an `issuer_url` — a real external OAuth
  authorization server) — overkill for this server's actual usage model (one expected main
  consumer, denidin-app, plus ad hoc manual tests). Implemented a much simpler, opt-in
  shared bearer-token check instead:
  - New `mcp.auth_token` config field (`config.py`, both `config.schema.json` copies) —
    optional, defaults to unset/no-op (zero friction for local dev/tests, which is why this
    app's entire existing test suite needed no changes).
  - New `server.BearerTokenMiddleware` (Starlette `BaseHTTPMiddleware`): no-op if no token
    configured; otherwise rejects any request without a matching
    `Authorization: Bearer <token>` header (401). New `server.build_asgi_app()` wraps
    `mcp.streamable_http_app()` with it.
  - `main()` now bypasses `FastMCP.run()`'s built-in uvicorn runner for the streamable-http
    transport (the only one this project uses) so the middleware can actually be applied;
    falls back to `server.run()` unchanged for stdio/sse.
  - 5 new unit tests (`tests/unit/test_auth_middleware.py`, real Starlette `TestClient`, no
    mocking) + 3 new real-server E2E tests in `test_mcp_server_e2e.py` (raw HTTP 401 checks
    via `requests`, then a full real MCP tool-listing round trip with the correct token via
    `httpx.AsyncClient` + `streamable_http_client`). 2 new config tests. 95/95 full suite
    green.
- [x] **T021-tunnel-scripts** [prerequisite for T021] ngrok tunnel management in
  `run_morning_mcp.sh`/`stop_morning_mcp.sh`, per user decision 2026-07-09 (persistent
  reserved-domain tunnel, managed by the run script rather than per-test-run):
  - New config fields `mcp.ngrok_authtoken`/`mcp.ngrok_domain` (optional, default unset) —
    2 new unit tests.
  - `run_morning_mcp.sh`: after the server itself starts successfully, reads these via the
    app's own `load_config()`; if both set, runs `ngrok config add-authtoken` +
    `ngrok http --domain=<domain> <port>` in the background, tracks its PID in `.ngrok.pid`,
    verifies it started. If unset (the common case), this whole section no-ops — **verified
    live**: a full start/stop cycle with no ngrok config produces byte-identical output to
    before this change. If `ngrok_authtoken`/`ngrok_domain` ARE set but the `ngrok` CLI isn't
    installed (the actual case on this dev machine), prints a clear warning and continues —
    **verified live**: server still starts fine, warning shown, no crash.
  - `stop_morning_mcp.sh`: added a `trap ... EXIT` that stops the ngrok process (if
    `.ngrok.pid` exists) on every exit path.
  - Added `.ngrok.pid` to `.gitignore`; documented both fields in `config.example.json` and
    both `config.schema.json` copies.
  - **Still not testable end-to-end**: `ngrok` isn't installed on this machine, and no
    account authtoken/reserved domain has been provided yet — the actual tunnel
    start/reachability can't be verified until those exist (see T021 below).
  - 97/97 full suite green (no regressions).
- [x] **T021** [E2E-EXPENSIVE] Written (per explicit user instruction, **not yet run** —
  requires the approval gate below first). Real end-to-end test where an **external
  OpenAI call** actually drives the running MCP server as a remote-MCP tool source (not
  just our own MCP client, per T014).
  - **Design correction mid-task**: the user initially wanted a *persistent* reserved-domain
    tunnel (hence T021-tunnel-scripts), then clarified they don't want to pay for ngrok.
    ngrok's **free tier is genuinely sufficient** — a no-cost account + authtoken gives a
    tunnel, just with a *random* URL instead of a stable one; a paid plan is only needed for
    a *reserved* domain. Since the test only needs the URL for its own runtime (not
    indefinitely), this switched the design back to an **ephemeral, per-test-run tunnel**
    with the URL fetched dynamically from ngrok's local inspector API
    (`http://127.0.0.1:4040/api/tunnels`) — new `tests/expensive/e2e_helpers.py`
    (`ngrok_tunnel()` context manager: starts `ngrok http <port>`, polls the local API for
    the public HTTPS URL, tears the process down after). This is also strictly safer than a
    permanent tunnel (smaller exposure window for an unauthenticated-by-default server whose
    tools include state-changing operations).
  - **Verified the tunnel mechanism works, independent of OpenAI** (per explicit
    instruction — "not from openai, but any other way"): new
    `tests/integration/test_ngrok_tunnel.py` starts the real local server + a real ngrok
    tunnel, then hits the **public** ngrok URL directly with `requests` to prove real
    internet traffic reaches the local process (checked via the bearer-auth boundary: no
    token → 401, correct token → not 401). **Verified for real** (2026-07-09) once the user
    provided a free ngrok authtoken (registered via `ngrok config add-authtoken` and stored
    in `config/config.json`'s `mcp.ngrok_authtoken`) — passed on the first run in isolation.
    **Real finding + fix**: failed once inside a full-suite run with a `404` — not from our
    own `BearerTokenMiddleware` (which never returns 404), but from ngrok's own edge: the
    local agent reports a tunnel "active" slightly before the public edge network has fully
    propagated the route. Added a short bounded retry (`_post_once_tunnel_is_live`, up to
    8×1s) that only tolerates `404` specifically, not any other failure. Verified stable
    across two consecutive full-suite runs (100/100 both times).
  - **OpenAI API key**: copied from `apps/denidin-app/config/config.json`'s `ai_api_key`
    into this app's own `config/config.json` as `openai_api_key` (per user decision — own
    config, not shared/read from denidin-app). New schema field (both `config.schema.json`
    copies), read-only by the expensive test itself (not by `server.py`).
  - **`tests/expensive/test_openai_invokes_mcp_e2e.py`**: starts the real bearer-protected
    local server, opens the real ephemeral ngrok tunnel, calls the real OpenAI Responses API
    (`client.responses.create(tools=[{"type": "mcp", "server_url": ..., "headers":
    {"Authorization": "Bearer ..."}, "require_approval": "never"}])`) with a natural-language
    prompt, asserts an output item with `type == "mcp_call"` and `name == "create_invoice"`
    exists with no `error`, then **independently verifies** (not just trusting the model's
    textual claim) that a matching document actually landed in the Morning sandbox via
    `MorningClient.list_invoices`. The `McpCall` output-item schema (`.name`, `.arguments`,
    `.output`, `.error`, `.status`, discriminated by `type == "mcp_call"`) was confirmed by
    reading the installed `openai` SDK's own
    `openai.types.responses.response_output_item.McpCall` class directly — documentation
    coverage of this is thin, so the SDK's type definitions were treated as the authoritative
    source, not guessed.
  - `pytest.ini` updated: registered the `expensive` marker + `addopts = -m "not expensive"`
    (mirroring denidin-app), so this test is **excluded by default**. **Confirmed**: full
    default suite run collects 100/101 (1 correctly deselected), the expensive test collects
    fine under `-m expensive --collect-only` (imports/syntax valid), and has **not been
    executed** — no OpenAI billing has occurred.
  - **Resolved 2026-07-09 (was flagged above as a concern)**: per user decision — "we are
    not yet in production for this app, so until further notice use config.test.json and
    not config.json" — both `test_ngrok_tunnel.py` and `test_openai_invokes_mcp_e2e.py` now
    load `config/config.test.json` (sandbox `api_url`, confirmed unchanged), not
    `config/config.json` (which still points at production and was intentionally left
    untouched — out of scope for this app right now). A real `create_invoice` call from
    T021 therefore lands in the **sandbox**, not production.
  - **Secret-handling change 2026-07-09**: `openai_api_key` and `mcp.ngrok_authtoken` were
    added to `config/config.test.json` for this purpose. Since that file was previously
    **git-tracked** (holding real, if sandbox-tier, Morning credentials since the app's
    initial scaffold), adding a real billable OpenAI key / ngrok authtoken to it would have
    committed them to the repo. Instead: `config/config.test.json` was removed from git
    tracking (`git rm --cached`) and added to `.gitignore`, matching `config/config.json`'s
    existing treatment. The file's real content on disk is unchanged (existing Morning sandbox
    creds untouched); only its git status changed. (Prior git history still contains the one
    commit that originally added it — not purged, since that's a more drastic, separate
    action not requested.) Existing sandbox integration tests are unaffected since they read
    the same file by path, just no longer via git. Two Phase-1 unit tests
    (`test_load_config_defaults_ngrok_fields_to_none`,
    `test_load_config_defaults_openai_api_key_to_none`) asserted "these fields are absent in
    config.test.json" and broke as a direct, expected consequence — fixed by switching them
    to an isolated `tmp_path` config (matching their "reads X when present" sibling tests'
    existing pattern) instead of depending on `config.test.json`'s now-populated state.
  - **Model corrected 2026-07-09**: `OPENAI_MODEL` changed from the placeholder `"gpt-4.1"`
    to `"gpt-4o-mini"` — the same text model denidin-app itself uses
    (`apps/denidin-app/config/config.json`'s `ai_model`), per user decision.
  - **Shared `instructions` + negative-case test added 2026-07-12** (per explicit user
    instruction: "implement #2 for the expensive tests. use the same instructions for all
    expensive tests. add a new expensive test that calls openai with some prompt that is
    not related to morning at all, assert it does NOT do any morning mcp calls."). "#2"
    refers to OpenAI's own `instructions` parameter on `client.responses.create()`
    (confirmed as a real, distinct top-level SDK parameter — separate from the MCP
    server's own optional `instructions` field surfaced in `InitializeResult`).
    - New `OPENAI_ASSISTANT_INSTRUCTIONS` constant in `tests/expensive/e2e_helpers.py`:
      names all 7 Morning tools and explicitly scopes them to invoicing/client/financial
      requests only, telling the model to answer unrelated requests normally without
      calling any tool. Both tests in `test_openai_invokes_mcp_e2e.py` now pass this via
      `instructions=OPENAI_ASSISTANT_INSTRUCTIONS`, so every expensive OpenAI-driven test
      in this module runs under identical guidance.
    - New `test_openai_does_not_invoke_mcp_tools_for_unrelated_prompt` (same `config`/
      `running_server` fixtures, its own ephemeral ngrok tunnel, same `tools=[{"type":
      "mcp", ...}]` registration) sends an unrelated prompt (a haiku request) and asserts
      `response.output` contains **no** `type == "mcp_call"` items at all — the negative
      counterpart to T021's existing `create_invoice`-invocation assertion, proving the
      model doesn't reach for these tools indiscriminately just because they're available.
    - **Confirmed**: `pytest --collect-only -m expensive` collects both tests cleanly
      (2 selected, 100 deselected); full default-suite run still **100 passed, 2
      deselected** (up from 1, as expected) — nothing executed, no OpenAI billing.
  - **Before running**: ~~(1) provide a free ngrok authtoken~~ — **done** 2026-07-09, tunnel
    verified for real (see above); ~~(2) confirm/fix the OpenAI model~~ — **done**,
    `gpt-4o-mini`; ~~confirm sandbox vs production~~ — **done**, now reads
    `config.test.json`/sandbox; (3) explicit human approval per
    CONSTITUTION §VII/CLAUDE.md — human approval required before every single run, run alone
    (never batched), read `logs/test_logs/` before re-running, only re-run after a confident
    fix.
  - **First real run (2026-07-12) — `test_openai_invokes_create_invoice_via_remote_mcp`,
    approved individually**: failed on first attempt with `openai.APIStatusError: 424 -
    "Error retrieving tool list from MCP server ... Failed Dependency"`. Root cause found
    directly in the captured debug log, not guessed: `mcp.server.transport_security:
    Invalid Host header: <ngrok-hostname>`. FastMCP silently enables Host-header
    DNS-rebinding protection (allow-listing only `127.0.0.1`/`localhost`/`::1`) whenever
    `host` is loopback and no `transport_security` is explicitly given — this rejects
    *every* request forwarded through the ngrok tunnel (whose `Host` header is the tunnel's
    own public hostname), independent of and prior to `BearerTokenMiddleware` ever running.
    Confirmed against the MCP Python SDK's own published guidance (GitHub
    modelcontextprotocol/python-sdk issue #1798, "Resolving 421 Invalid Host Header", and
    security advisory GHSA-9h52-p55h-vw2f / CVE-2025-66416): the SDK's own docs call
    disabling this check acceptable "for local development or if you are managing security
    at a different layer" — which applies here, since `BearerTokenMiddleware`'s shared
    bearer token is this server's actual access boundary, not Host-header matching. The
    SDK-recommended alternative (allow-listing the exact tunnel host) doesn't fit this
    project's free-tier ephemeral tunnel: the SDK only supports exact-host + port-wildcard
    matching (`host:*`), not subdomain wildcards, and the ephemeral hostname is only known
    *after* the server is already constructed — properly allow-listing it would require
    reordering startup (tunnel first, then server), out of scope for this fix. **Fix**:
    `create_server()` in `src/denidin_mcp_morning/server.py` now passes
    `transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False)`
    explicitly to `FastMCP(...)`. This affects every ngrok-exposed use of the server (this
    test, `run_morning_mcp.sh`, `docker-entrypoint.sh`), not just this one test — flagged to
    and approved by the user before applying (a real security-control change, not a routine
    bug fix). Verified: full default-suite run still 100 passed/2 deselected after the fix;
    re-ran the same expensive test once (per the "only re-run after a confident fix" rule)
    and it **passed** — OpenAI's Responses API discovered and invoked `create_invoice` over
    the remote MCP tool via the real ngrok tunnel with no error, and the test independently
    confirmed the resulting invoice landed in the Morning sandbox. **T021 is now verified
    working end-to-end for real** (first successful run). Real OpenAI/Morning billing was
    incurred by this run (as expected/approved).
  - **Second real run (2026-07-12), separately approved —
    `test_openai_does_not_invoke_mcp_tools_for_unrelated_prompt`**: **passed** on its first
    attempt (the transport_security fix above applies to both tests, since both go through
    the same `create_server()`/`running_server` fixture). Given a haiku prompt with nothing
    to do with invoicing, OpenAI answered normally with zero `type == "mcp_call"` output
    items — confirming `OPENAI_ASSISTANT_INSTRUCTIONS`' scoping guidance actually holds in
    practice, not just in the prompt text. **Both expensive tests in this module have now
    been run for real and both pass.**

---

## Dependencies

- Phase 1 (T001–T005) before Phase 2.
- Per story: `a` (approved failing test) **before** `b` (implementation).
- Phase 3 (server) after the 7 tools exist. Phase 4, then Phase 5, last.

## MVP

T001, T003, T004, T005, T006a/b (config + models + formatters + `create_invoice` tool with
real-sandbox test), then T013 + T014 for a minimal callable MCP server.

## Out of scope (see spec §Future Work)

WhatsApp delivery via denidin-app (architecture TBD); receipt-parsing/file-upload/webhook
product (`specs/in-definition/017-mcp-morning-receipt-parsing/`); Redis multi-worker token
store; multi-tenant scale; performance-SLA work.
