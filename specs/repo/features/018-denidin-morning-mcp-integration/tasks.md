# Tasks: DeniDin ↔ Morning MCP Integration — Feature 018

**Spec**: `./spec.md` · **Plan**: `./plan.md` · **User stories**: `./user-stories.md`
**Apps**: `apps/denidin-app/` (+ small `apps/morning-mcp-app/` status-file change)
**Branch**: `feature/018-denidin-morning-mcp-integration`

## Conventions

- Task ID `T###`. `[P]` = parallelizable. `[US#]` = user story.
- **TDD gate (METHODOLOGY §VI)**: the test task (A) is written first, must **fail** (RED), and
  needs **explicit human approval** before the implementation task (B). Approved tests are
  **immutable** (CONSTITUTION §VIII, decision #5).
- **Testing rule (CONSTITUTION §V, ZERO-MOCKING, project real-E2E preference)**: real-API E2E
  tests only, entry point = a real Green API webhook through `@bot.router.message`;
  `@pytest.mark.expensive` (real OpenAI billing); independent Morning **sandbox** verification
  via a direct `MorningClient`. No mocks, no mock-based unit tests.
- **Expensive-test discipline (CLAUDE.md / CONSTITUTION §VII)**: human approval before **every**
  run, run **one at a time** (never a bare `-m expensive` sweep), read `logs/test_logs/` before
  re-running, only re-run after a confident fix.
- Paths relative to `apps/denidin-app/` unless noted.

---

## Phase 1 — Foundation (plumbing the E2E tests need)

Per the project's real-E2E-only preference (no unit tests), this foundation is **validated by
the Phase 3 E2E tests**, not by isolated unit tests.

- [x] **T001** Add `mcp: Dict = field(default_factory=dict)` to `AppConfiguration`
  (`src/models/config.py`); register it in the `from_file` `defaults` dict and the inline
  field filter in `initialize_app` (`denidin.py`) so the block isn't stripped. Add the `mcp`
  block to `config/config.example.json` (`morning_auth_token`, `morning_status_file`,
  `morning_server_label`, `url_max_age_seconds`). Add a `validate()` sanity check.
- [x] **T002** Implement `src/handlers/morning_mcp_locator.py` — `MorningMcpLocator(config)`
  with `current_server_url() -> Optional[str]`: read `mcp.morning_status_file` via
  `pathlib.Path`, parse JSON, apply `url_max_age_seconds` freshness (UTC), return `server_url`
  or `None`; never raise (internal errors → None + WARNING log, masked). Inject into
  `AIHandler` via `initialize_app` (dependency injection, no globals).
- [x] **T003** [morning-mcp-app] Publish the status file: new `mcp.status_file` config field
  (both `config.schema.json` copies + `config.example.json`); `run_morning_mcp.sh` /
  `docker-entrypoint.sh` write `{"server_url": "<https>/mcp", "updated_at": "<UTC ISO>"}` after
  the tunnel URL is fetched, and clear it on stop (mirror the existing `.ngrok.pid` handling).
  Reuse the existing ngrok URL fetch. No server-code change.

**Checkpoint**: denidin loads the `mcp` config; the locator returns a URL when the Morning app
is up (with a real status file) and `None` when it's absent/stale; Morning writes/clears the
file on start/stop.

---

## Phase 2 — Responses API migration (replace Chat Completions)

- [x] **T004a** [US1] Write the first failing E2E test (see **T010a**) — it is RED because no
  Responses/MCP reply path exists yet. **This is the RED gate for the whole reply slice.**
- [x] **T004b** [US1] Migrate the **reply path** in `ai_handler.py`:
  `_call_openai_api` → `client.responses.create(model, instructions=constitution,
  input=history+user, max_output_tokens, temperature)`; update `get_response` extraction to
  `output_text` + `usage.input_tokens/output_tokens/total_tokens`; keep the tenacity retry and
  friendly-error fallbacks. Attach the Morning MCP tool when role ∈ {godfather, admin} **and**
  `locator.current_server_url()` is not None (bearer header + `require_approval:"never"` +
  `server_label`). Makes T010a GREEN.
- [x] **T005** Migrate **session summarization** (`ai_handler.py` transfer-to-long-term) to
  `responses.create` (no tools). Validated by existing/adapted expensive memory tests.
- [x] **T006** Migrate **image/vision extraction** (`extractors/image_extractor.py`) to
  `responses.create` with an `input_image` item; preserve the extractor output contract
  (`extracted_text`, `document_analysis`, `extraction_quality`, `warnings`, `model_used`).
- [x] **T007** One-time §VIII-approved migration of any **pre-existing test** coupled to the
  Chat-Completions surface (e.g. expensive vision/summarization tests) to the Responses
  surface. Human-approved; then immutable.

**Checkpoint**: all denidin OpenAI calls go through the Responses API; embeddings unchanged;
default (non-expensive) suite green; pylint/mypy pass.

---

## Phase 3 — Runtime constitution + E2E matrix (real API, TDD)

- [x] **T008** Add the runtime-constitution tool section
  (`data/constitution/runtime_constitution.md`): the 7 Morning tools, their scope
  (invoicing/clients/finance only; answer unrelated requests normally), Hebrew output, and
  confirm-before-state-change guidance (decision #4). Prompt-only.
- [x] **T009** Implement `tests/expensive/denidin_mcp_e2e_helpers.py`: ephemeral ngrok tunnel
  (re-implemented denidin-side, mirroring Feature 005's `e2e_helpers.ngrok_tunnel`), a fixture
  that spawns the **real Morning MCP server as a subprocess** (morning app dir, sandbox
  `config.test.json`, bearer token set) + writes the status file, and a helper to build + POST
  a real Green API `textMessage` webhook JSON through denidin's `bot.router`. Skip if
  ngrok/OpenAI/Morning creds absent.

Each of the following is an **A (write failing/first-run test → approval) / B (verify GREEN, or
implement any gap)** pair. Most B's need **no new denidin code** once T004b lands (the model
just invokes a different remote tool) — those tests are additional coverage; still written and
approved before running. All in `tests/expensive/test_denidin_morning_mcp_e2e.py`.

- [x] **T010** [US1] `create_invoice`: positive (godfather webhook → invoice exists in sandbox)
  + negative (missing amount → AI asks, no malformed call).
- [x] **T011** [US2] `list_invoices`: positive (seed 2 → list shows both) + negative (no match →
  readable "אין תוצאות").
- [x] **T012** [US2] `get_invoice_details`: positive (seed → status/dates) + negative (bad id →
  friendly error).
- [x] **T013** [US2] `update_invoice_status` paid: positive (mark paid → linked Receipt, status
  flips) + negative (reopen paid → graceful Hebrew rejection).
- [x] **T014** [US2] `update_invoice_status` cancel: positive (cancel → linked Credit Invoice
  type 330 in sandbox) + negative (cancel nonexistent → friendly error).
- [x] **T015** [US3] `add_client`: positive (add with valid ח.פ → client in sandbox) + negative
  (invalid tax id → friendly error; missing name → AI asks).
- [x] **T016** [US2] `get_financial_summary`: positive (seed → totals/counts) + negative (custom
  period w/o dates → AI asks).
- [x] **T017** [US2] `download_invoice_pdf`: positive (seed → real download URL) + negative (bad
  id → friendly error).
- [x] **T018** [US4] RBAC-negative: client webhook invoicing prompt → no MCP tool attached →
  nothing created in sandbox → bot still replies.
- [x] **T019** [US5] Scope-negative: godfather unrelated prompt (haiku) → no `mcp_call`.
- [x] **T020** [US6] Graceful degrade: status file missing/stale → godfather invoicing prompt →
  normal reply, no crash, nothing created.
- [x] **T021** Scenario A — full lifecycle: add client → create → list → cancel (multi-turn);
  verify client + original invoice + linked Credit Invoice in sandbox.
- [x] **T022** Scenario B — conversational slot-filling: "צור חשבונית" (no details) → AI asks →
  supply → created; no premature/garbage call in between.
- [x] **T023** Scenario C — confirm-before-act: create prompt → AI asks to confirm (no call) →
  "כן" → created. Asserts the no-code confirmation model (decision #4).

**Checkpoint**: every Morning action is covered by a passing real-API E2E test through the
WhatsApp webhook router; RBAC, scope, degrade, and multi-turn scenarios pass.

---

## Phase 4 — Polish

- [x] **T024** Audit logging (REQ-SEC-002): every reply attaching MCP tools logs role,
  correlation id, masked token, URL host.
- [x] **T025** [P] Docs: README/quickstart for running both apps together (docker-compose:
  shared bearer token + status file + tunnel); note the config `mcp` block.

---

## Dependencies

- Phase 1 before Phase 2/3 (config + locator + status file are prerequisites).
- **T004a (RED) before T004b** — the reply-path RED gate.
- Per E2E task: `a` (approved test) **before** `b`.
- T008 (runtime constitution) before the scope/confirmation tests (T019, T023) can pass.

## MVP

T001–T003 (foundation) + T004a/b (Responses reply + MCP attach) + T009 (harness) + T010
(create_invoice E2E) = a godfather creating a real sandbox invoice from WhatsApp, verified.

## Out of scope (see spec §Scope)

Morning tool changes; embeddings migration; invoice delivery from denidin's number; receipt
parsing (Feature 017).
