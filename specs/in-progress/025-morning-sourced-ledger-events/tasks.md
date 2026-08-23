# Tasks: Morning-Sourced Ledger Events

**Input**: Design documents from `specs/in-progress/025-morning-sourced-ledger-events/`
**Prerequisites**: `plan.md` ✅ · `spec.md` ✅ · `user-stories.md` ✅ · `research.md` ✅ ·
`data-model.md` ✅ · `contracts/` ✅

**Revised 2026-08-21 (round 3 of `spec.md`'s Clarifications, mid-`speckit.implement` — T001 and
Phase 2's test-writing had already started against the old design when these changes landed)**:
supersedes the 2026-08-20 revision. Renumbers everything. Major design changes since the previous
revision:
- Dedup: hard-refusal → in-memory tri-state (new/duplicate/anomaly) cache inside
  `LedgerEventManager`, never a per-tick disk re-scan, never in `ai_handler.py`.
- Fields: 5 → 4 (`accounting_document_id`/`accounting_document_number` merged into
  `accounting_document_display_number`).
- New config field `config.accounting_ledger_update_freq` (minutes; `0` = inactive).
- New safety cap (5 days / 100 docs, whichever binds first) — skip-entire-tick on breach, checked
  by the service directly (non-AI) before ever calling OpenAI.
- New real scope addition: `apps/morning-mcp-app` needs a small change (map+expose Green
  Invoice's raw `creationDate`) — the "zero morning-mcp-app changes" conclusion from the previous
  revision is **no longer accurate** for this one field.
- A live probe against the real Morning dev sandbox already happened 2026-08-21 (documented in
  `research.md`) and resolved most, but not all, of what was previously task T020 — the remaining
  live-verification scope is narrower now (see T027 below).

---

**IMPORTANT**: This task list complies with:
- **CONSTITUTION.md** (§I-III): Config-only (no env vars), Israel local time throughout
  (bugfix-037), feature branch workflow.
- **METHODOLOGY.md** (§VI): every "a" (test) task requires human approval before its paired "b"
  (implementation) task; once approved, tests are IMMUTABLE without explicit re-approval.
  **§VI.a's 2026-08-18 TDD redefinition applies** (this feature is planned entirely after that
  date): the `billed`/`expensive` acceptance scenarios below are **descriptions only** — no test
  code is written, and nothing is run, until every unit/integration task (Phases 1-7's "a"/"b"
  pairs, plus the Gate-Zero task) is GREEN. At that point every 👤-marked task's description
  becomes real test code, written and run together, once, as the feature's actual acceptance
  pass.

**Tests**: TDD (§VI.b, unchanged) for all unit/integration work; §VI.a (redefined) for
`billed`/`expensive`.
**Organization**: Grouped by user story (`user-stories.md`'s priorities), after a shared
Foundational phase every story depends on (the extended `LedgerEvent` record shape + tool
schema + the small `morning-mcp-app` field-exposure change).

## Format: `[ID] [P?] [Story] Description`
- **[P]**: can run in parallel (different files, no dependency on each other)
- **[Story]**: which user story this task belongs to
- **[T###a]**: write tests (requires human approval before T###b)
- **[T###b]**: implement (blocked until T###a approved)
- 👤: acceptance-scenario definition — description only at this stage, per §VI.a above

---

## Phase 1: Setup

- [x] T001 Create `apps/denidin-app/src/services/accounting_reconciliation_service.py` module
  skeleton — docstring, imports, placeholder constants. **Already written** (before round 3) —
  needs a small revision alongside T009b below to add the safety-cap constants
  (`MAX_CATCHUP_LOOKBACK = timedelta(days=5)`, `MAX_CATCHUP_DOCUMENT_COUNT = 100`) and drop the
  now-unused `STARTUP_SWEEP_LOOKBACK`/`PERIODIC_SWEEP_LOOKBACK` split in favor of the single
  `FALLBACK_LOOKBACK` `research.md` describes (both only mattered for a per-tick re-scan design
  this feature no longer has — the cache-based watermark makes the startup/periodic distinction
  moot). No test (scaffolding).
- [x] T002a [P] Write a test in `apps/denidin-app/tests/unit/test_config.py` (or wherever
  `AppConfiguration`'s existing field tests live): `config.accounting_ledger_update_freq` parses
  as an int, defaults sensibly (TBD exact default — likely `0`/inactive, so an environment that
  doesn't yet have this key set in its config file doesn't accidentally start polling), and `0`
  is accepted as a valid value (not coerced to `None`/falsy-and-therefore-something-else).
- [x] T002b Add `accounting_ledger_update_freq` to `AppConfiguration`
  (`apps/denidin-app/src/models/config.py`) + `apps/denidin-app/config/config.example.json` (BLOCKED
  until T002a approved). **Does NOT touch `config.dev.json`/`config.prod.json`** (gitignored,
  human-owned real files) — a human adds the real per-environment value there separately, once a
  real interval is decided (T028 below).

---

## Phase 2: Foundational (blocks all user stories)

**⚠️ CRITICAL**: no user-story work begins until this phase is complete and approved — every
story depends on the extended persisted-record shape, the tool schema, and the small
`morning-mcp-app` field-exposure addition all existing.

- [x] T003a [P] **(`apps/morning-mcp-app`, separate app/test suite)** Write a unit test for the
  `Invoice` model's new `creation_timestamp` field in
  `apps/morning-mcp-app/tests/unit/test_models.py` (or wherever `Invoice`'s existing field-mapping
  tests live): given a raw response dict containing `creationDate` (a Unix epoch int — real
  example from the live probe: `1787241168`), `Invoice.creation_timestamp` parses to the correct
  UTC/aware `datetime`; missing `creationDate` leaves it `None` (never raises). **Unit-level only
  — a hand-crafted dict fixture, not a live sandbox call** (this is a plain Pydantic
  validator/mapping test, no external service involved, consistent with `Invoice`'s other
  existing field-mapping tests — not a CONSTITUTION.md no-mocking violation).
- [x] T003b **(`apps/morning-mcp-app`)** Implement `Invoice.creation_timestamp: Optional[datetime]`
  in `apps/morning-mcp-app/src/denidin_mcp_morning/models.py`, mapped from raw `creationDate`
  (BLOCKED until T003a approved).
- [x] T004a [P] **(`apps/morning-mcp-app`)** Write a unit test proving `get_invoice_details`'s tool
  output actually surfaces `creation_timestamp` (i.e. it isn't dropped somewhere between the
  `Invoice` model and the MCP tool's returned payload) — check `tools.py`/`formatters.py`'s
  relevant function.
- [x] T004b **(`apps/morning-mcp-app`)** Wire `creation_timestamp` through to `get_invoice_details`'s
  output (BLOCKED until T004a approved, depends on T003b). Real live-sandbox confirmation that
  this actually round-trips end-to-end happens later, as part of Gate Zero (T012) and T027, not
  here — T003a/T004a are unit-level only.
- [x] T005a [P] Write tests in `apps/denidin-app/tests/unit/test_ledger_event_manager.py` for the
  extended record shape (`data-model.md`, round 3 — **4 fields, not 5**):
  `source_type="חשבונית"` persists with `accounting_document_display_number`/`_type`/`_status`/
  `_creation_date` populated; `event_subtype="הפקה"` accepted for `חשבונית`; all four fields are
  forced `null` for `הסכם`/`בנק` regardless of what's passed; the usual non-applicable fields
  (`agreement_id`/`component_id`/`component_label`/`trigger_condition`/`percent`/`percent_base`/
  `hours`/`hourly_rate`/`bank_number`/`bank_branch`/`bank_account`/`payer_name`) are all forced
  `null` for `חשבונית`; `schema_version=2` on every new write regardless of `source_type`
  (including `הסכם`/`בנק` — proves the bump is global); the old reserved field names
  (`morning_document_id`/`invoice_number`/`invoice_type`/`invoice_status`/
  `invoice_actual_creation_date`) no longer appear anywhere in a persisted record; there is no
  separate `accounting_document_id` field at all (round 3's field-merge).
- [x] T005b Implement the record-shape changes in `add_ledger_event`
  (`apps/denidin-app/src/managers/ledger_event_manager.py`): field additions/renames per
  `contracts/ledger-event-manager-extension.md`, `_LETTER_BY_SOURCE_TYPE` gains `"חשבונית": "H"`,
  `event_subtype` enum extension, `CURRENT_SCHEMA_VERSION = 2` (BLOCKED until T005a approved).
  **Also update `_LETTER_BY_SOURCE_TYPE`'s own comment** (currently reads `"H"/חשבונית is
  Morning-invoice-sourced and never produced by capture_ledger_event (Feature 025)"`) — reword
  since this feature now produces it (via the new reconciliation handler, T009b), just never via
  the conversational path (`speckit.analyze` finding L1, carried over unchanged).
- [x] T006a [P] Write tests for `scan_accounting_documents`/`_ensure_accounting_document_cache` in
  `apps/denidin-app/tests/unit/test_ledger_event_manager.py`: empty `storage_dir` →
  `scan_accounting_documents()` returns `{}`; one `חשבונית` event → `{display_number:
  [creation_datetime]}`; two events sharing the same `display_number` with different timestamps →
  both timestamps present in that key's list; `הסכם`/`בנק` events ignored entirely; a
  malformed/unparseable JSON file is skipped with a WARNING, never raises. **Separately**: prove
  `_ensure_accounting_document_cache` only calls `scan_accounting_documents` **once** across
  multiple `add_ledger_event` calls on the same manager instance (e.g. via a spy/call-count
  assertion on `scan_accounting_documents` itself — not mocking any external service, just
  counting calls to this class's own method) — this is the "no reading and parsing of the ledger
  events... per tick" guarantee, and needs its own explicit test, not just an implied side effect
  of other tests passing.
- [x] T006b Implement `scan_accounting_documents` + `_ensure_accounting_document_cache` +ה
  `self._accounting_document_cache` instance attribute in `ledger_event_manager.py` (BLOCKED
  until T006a approved, depends on T005b). Needs new imports: `Dict`/`List` already present,
  `datetime` already present (no bare `date` needed anymore — round 3 uses full `datetime`
  throughout, not date-only).
- [x] T007a [P] Write tests for the tri-state new/duplicate/anomaly logic in
  `apps/denidin-app/tests/unit/test_ledger_event_manager.py`: a first `חשבונית` capture with a
  new `accounting_document_display_number` persists normally and populates the cache; a second
  capture with the SAME `display_number` and the SAME `creation_date` is silently discarded
  (returns `None`, no new file, cache unchanged, logged at INFO not WARNING/ERROR); a third
  capture with the SAME `display_number` but a DIFFERENT `creation_date` **is persisted as a new
  event** (own new `event_id`), logs a WARNING, and appends an entry to
  `{data_root}/accounting_reconciliation/pending_review.json` (assert the file's contents, not
  just that logging happened); the guard never fires for `הסכם`/`בנק` (their
  `accounting_document_display_number` is always `None`, and two `None`s must never be treated as
  a collision with each other).
- [x] T007b Implement the tri-state guard + `_append_pending_review` at the top of
  `add_ledger_event` (before `_next_seq`, per `contracts/ledger-event-manager-extension.md`)
  (BLOCKED until T007a approved, depends on T006b).
- [x] T008a [P] Write a test for `prune_accounting_document_cache` in
  `apps/denidin-app/tests/unit/test_ledger_event_manager.py`: an entry whose only timestamp is
  older than the 7-day (5-day cap + 2-day margin) boundary before a given `now` is dropped; an
  entry with at least one timestamp still within that boundary is kept in full (not partially
  trimmed); an empty cache is a no-op.
- [x] T008b Implement `prune_accounting_document_cache` (BLOCKED until T008a approved, depends on
  T007b).
- [x] T009a [P] Write tests for the extended `LEDGER_EVENT_TOOL` schema in
  `apps/denidin-app/tests/unit/test_ai_handler_ledger_events.py`: `source_type` enum includes
  `"חשבונית"`; `event_subtype` enum includes `"הפקה"`; the **four** new top-level properties exist
  (`accounting_document_display_number`/`_type`/`_status`/`_creation_date` — NOT a fifth `_id`
  field), are `["string", "null"]`, and are present in `required` (strict-mode compliance);
  `additionalProperties` stays `False`; tool `description` distinguishes the free-text-signal use
  case from the transcribe-given-structured-data use case.
- [x] T009b Implement the `LEDGER_EVENT_TOOL` schema extension in
  `apps/denidin-app/src/handlers/ai_handler.py` (BLOCKED until T009a approved).

---

## Phase 3: User Story 1 — A background sweep captures a Morning document DeniDin never saw (P1) 🎯 MVP core

**Goal**: the reconciliation sweep can list, detail, and persist a not-yet-known Morning
document as a `LedgerEvent`, end to end, without touching the conversational suppression path.

**Independent Test**: per `user-stories.md` US1.

- [x] T010a [P] [US1] Write tests for the NEW reconciliation-capture handler in
  `tests/unit/test_ai_handler_ledger_events.py`: given a synthetic Responses-API response object
  containing both `mcp_call` item(s) (`list_invoices`/`get_invoice_details`) and one
  `capture_ledger_event` call, the new handler persists it via
  `LedgerEventManager.add_ledger_events_from_call`, **unaffected** by
  `_handle_ledger_event_capture`'s same-turn-`mcp_call` suppression (proven by never calling that
  method); a malformed/unparseable `capture_ledger_event` call is rejected and logged, not
  silently dropped (mirrors REQ-DATA-008's existing discipline); persisted events use the
  `session_id="accounting-reconciliation"`/`message_id=None` sentinel (data-model.md). **This
  handler does NOT implement any dedup/anomaly logic itself (round 3)** — assert it calls
  `add_ledger_events_from_call` unconditionally and trusts the manager's own return value,
  never pre-filtering calls. **Also assert that no `WhatsAppHandler.send_response`/
  `send_proactive_message` call occurs anywhere in this path** (`speckit.analyze` finding M3).
- [x] T010b [US1] Implement the new handler method (e.g. `_handle_accounting_reconciliation_capture`)
  in `ai_handler.py` (BLOCKED until T010a approved, depends on T005b, T007b, T009b).
- [x] T011a [P] [US1] Write tests for the sweep worker's watermark derivation, safety-cap
  pre-check, and prompt construction in
  `apps/denidin-app/tests/unit/test_accounting_reconciliation_service.py`:
  - `since` derives from `ledger_event_manager.get_accounting_document_watermark()` (a thin new
    method — max timestamp across the cache), not any disk scan performed by the service itself.
  - Given no known `חשבונית` events, `since = now_local() - FALLBACK_LOOKBACK`.
  - **Safety cap**: given a (test-constructed, non-AI) candidate-document count/gap that exceeds
    5 days OR 100 documents, the sweep skips the entire tick — asserts NO OpenAI call is even
    attempted (mock/stub only the boundary — the direct, non-AI `list_invoices` count-check call
    itself is real-shaped but test-doubled at the HTTP boundary per this codebase's existing
    "mock external services only" convention) and the watermark is provably unchanged afterward.
  - Given a candidate count/gap within both bounds, the sweep proceeds and the built prompt text
    includes the correct `since` date/time and instructs one `capture_ledger_event` call per
    not-yet-known document.
- [x] T011b [US1] Implement `_sweep_accounting_documents`'s watermark/safety-cap/prompt-building
  logic in `services/accounting_reconciliation_service.py` (the real OpenAI call itself is
  exercised for real only in T012/T013) (BLOCKED until T011a approved, depends on T006b).
- [x] T012a [P] [US1] Write tests for scheduler wiring in
  `tests/unit/test_accounting_reconciliation_service.py`:
  `start_accounting_reconciliation_scheduler` registers exactly one job with `max_instances=1`
  when `config.accounting_ledger_update_freq > 0`; `run_startup_accounting_reconciliation_sweep`
  invokes the shared sweep function synchronously; passing `accounting_ledger_update_freq=0`
  means the scheduler is never started at all (no job registered) — assert this explicitly, not
  just that a 0-interval job would fire fast; a testability-seam `trigger` override (mirroring
  `reminder_delivery_service.py`'s own) proves the real `add_job()`+`BackgroundScheduler` wiring
  fires without waiting on a real `CronTrigger` boundary.
- [x] T012b [US1] Implement scheduler start/stop + the `accounting_ledger_update_freq == 0` inactive
  gate + `run_startup_accounting_reconciliation_sweep` in
  `services/accounting_reconciliation_service.py` (BLOCKED until T012a approved, depends on
  T011b, T002b).
- [x] T013 [US1] Wire the scheduler into `apps/denidin-app/denidin.py`'s
  `if __name__ == "__main__":` block — start alongside `bot.run_forever()`, store as
  `denidin.accounting_reconciliation_scheduler`, `.shutdown()` in the SIGINT/SIGTERM handler and
  the `KeyboardInterrupt` block, alongside the existing `cleanup_thread`/`reminder_scheduler`
  shutdowns. **NOT** inside `initialize_app()` (per contract's explicit constraint —
  `tests/integration/` calls that bootstrap directly against a real `bot`, same risk
  `reminder-delivery.md`'s own 2026-08-17 correction already documents). No dedicated automated
  test — this exact placement is what a test can't exercise without a real process; verified
  manually via `quickstart.md` instead, same as `reminder_scheduler`'s own wiring (BLOCKED until
  T012b approved).
- [ ] T014 [US1] 👤 **GATE ZERO** (`speckit.analyze` finding H1 — mirrors Feature 054's T014
  precedent): a real, minimal, standalone OpenAI Responses API call — Morning MCP tools +
  `LEDGER_EVENT_TOOL` attached, explicitly **no** session/`chat_id`/`AIRequest`, using the
  dedicated reconciliation prompt shape — succeeds live, once, against the real `dev` Morning
  sandbox + real OpenAI, AND confirms `get_invoice_details`'s tool output genuinely surfaces the
  new `creation_timestamp` field end-to-end (closing the loop on T003b/T004b's unit-level-only
  coverage with one real, live check). This proves the core novel mechanism this entire phase is
  built on actually works, **before** T015's full multi-scenario Acceptance pass is written. A
  single manual/live check is sufficient (does not need to be a formal pytest suite entry) — its
  purpose is early, cheap risk reduction. Run only after T010b/T011b/T012b/T013 all exist
  (needs the real tool-attachment plumbing to issue the call through), but explicitly **before**
  T015 is attempted.
- [ ] T015 [US1] 👤 **Acceptance scenario definition (`billed` tier — text-only OpenAI + Morning
  MCP round-trip, no vision/image calls involved)**: description only, per §VI.a — no test code
  yet. A document is created directly in the Morning **dev sandbox**, outside any DeniDin
  conversation. One reconciliation sweep tick is triggered for the test (via T012a's
  testability-seam trigger) against the real sandbox + real OpenAI. After it completes, a new
  `dev_data/events/H{DDMMYY}{HHMM}{seq}.json` file exists with `source_type="חשבונית"`, all four
  `accounting_document_*` fields matching the real sandbox document (cross-checked against the
  Morning sandbox UI, not just internal consistency — including the exact HH:MM creation time),
  `schema_version=2`. Validates User Story 1. Test code written and run together with every other
  👤 task below, once, only after Phase 7 is entirely GREEN.

**Checkpoint**: US1 fully functional and independently demoable (a genuinely new Morning
document gets captured), even without the dedup/multi-doc/regression guarantees below.

---

## Phase 4: User Story 2 — A document already captured is never re-captured (P1)

**Goal**: prove the tri-state dedup logic (now living in `LedgerEventManager`, Phase 2) actually
composes correctly with the sweep worker across two ticks — not re-testing the dedup logic
itself (already covered by T007a), but that the sweep doesn't do anything that would defeat it.

**Independent Test**: per `user-stories.md` US2. **Must ship together with US1** (per
`user-stories.md`'s own priority note — without this, US1 alone is actively harmful, not merely
incomplete).

- [x] T016a [P] [US2] Write a test in
  `apps/denidin-app/tests/unit/test_accounting_reconciliation_service.py` (fixed file — was
  left as an either/or before `speckit.analyze` finding M2) proving the composed flow: a first
  simulated sweep persists a synthetic document via the new handler (T010b); a second simulated
  sweep whose (synthetic) model response attempts to capture the SAME
  `accounting_document_display_number` **at the same creation timestamp** results in exactly one
  persisted file total (the manager's own tri-state guard fires transparently through the
  handler/sweep, nothing in the sweep needs its own duplicate-prevention code) — real
  `LedgerEventManager`/handler objects throughout, only the OpenAI response object itself is a
  test-constructed stand-in (no live network), matching this codebase's existing pattern for
  `ai_handler.py` unit tests. No real router/webhook entry point exists for this feature
  (CONSTITUTION §V) — `unit`, not `integration`, tier.
- [x] T016b [US2] Any glue code the test surfaces as missing (expected: none new — this proves
  T007b's guard and T011a/T011b's watermark logic already compose correctly together) (BLOCKED
  until T016a approved).
- [ ] T017 [US2] 👤 **Acceptance scenario definition (`billed`)**: description only. A second
  sweep tick, run with no new Morning documents created since T015's scenario, produces zero new
  `dev_data/events/` files, and the log shows the sweep actually ran (distinguishable from a
  silent no-op). Validates User Story 2.

**Checkpoint**: US1+US2 together are the MVP — a document is captured exactly once, ever (barring
the anomaly case, which is itself a deliberate, logged, reviewable exception — not a dedup
failure).

---

## Phase 5: User Story 4 — An ordinary conversational Morning question is unaffected (P1)

**Goal**: prove, not assume, that this feature introduces zero regression risk to the existing
(and previously-broken, then fixed) conversational suppression path.

**Independent Test**: per `user-stories.md` US4.

- [x] T018a [P] [US4] Extend the existing `_handle_ledger_event_capture` suppression tests in
  `tests/unit/test_ai_handler_ledger_events.py` (the ones covering the 2026-07-28/2026-08-02
  incidents) to run unchanged against the now-extended `LEDGER_EVENT_TOOL` schema: same-turn
  `mcp_call`/`mcp_approval_request` still suppresses every `capture_ledger_event` call; more
  than one call in a turn is still a protocol violation there — both completely independent of
  the new `source_type="חשבונית"` additions.
- [x] T018b [US4] Fix anything T018a's regression check surfaces (expected: none —
  `_handle_ledger_event_capture` is explicitly unmodified by this feature) (BLOCKED until T018a
  approved).
- [ ] T019 [US4] 👤 **Acceptance scenario definition (`billed`)**: description only. From a
  godfather/admin phone, a real Morning question that causes `list_invoices`/`get_invoice_details`
  to run in the same conversational turn (the original 2026-07-28 incident's shape — e.g. "list
  all payments for client X"). The reply is complete and correct (the original empty-reply
  symptom does not reproduce), and no new `dev_data/events/` file is created by that turn.
  Validates User Story 4 — the regression check for this entire feature's core assumption.

---

## Phase 6: User Story 3 — Multiple new documents in one window are all captured (P2)

**Goal**: the reconciliation handler's multi-call-per-turn path actually persists every call,
not just the first.

**Independent Test**: per `user-stories.md` US3.

- [x] T020a [P] [US3] Extend T010a's test file: given a synthetic response containing TWO
  `capture_ledger_event` calls in the same turn (two distinct
  `accounting_document_display_number`s), both are persisted as separate `LedgerEvent` files.
- [x] T020b [US3] Confirm/adjust the handler from T010b to support N calls per turn (expected:
  already correct by construction) (BLOCKED until T020a approved).
- [ ] T021 [US3] 👤 **Acceptance scenario definition (`billed`)**: description only. Two
  documents are created in the Morning sandbox before one sweep tick; after that tick, two new
  distinct `H...json` files exist, one per document. Validates User Story 3.

---

## Phase 7: User Story 5 — A sweep failure never silently skips a window (P2)

**Goal**: prove the watermark's cache-derived-not-counted design actually self-corrects after a
failure (or a safety-cap skip), not just in theory.

**Independent Test**: per `user-stories.md` US5.

- [x] T022a [P] [US5] Write tests in `tests/unit/test_accounting_reconciliation_service.py`:
  given the sweep worker raises partway through (simulated OpenAI/MCP failure) before persisting
  anything, the function catches it, logs at ERROR, and returns cleanly; a subsequent watermark
  derivation (`get_accounting_document_watermark()`) afterward returns exactly the same result as
  before the failed attempt. **Also**: given the safety-cap check trips (T011a already covers the
  skip itself — this test covers the *aftermath*), the watermark and cache are provably unchanged
  after the skipped tick, same as the exception case.
- [x] T022b [US5] Implement the try/except wrapper around the sweep tick's
  OpenAI-call-through-persist logic in `services/accounting_reconciliation_service.py` (BLOCKED
  until T022a approved, depends on T011b, T012b).
- [ ] T023 [US5] 👤 **Acceptance scenario definition (`billed`)**: description only. One sweep
  tick is made to fail (e.g. a temporarily unreachable Morning MCP URL for that single tick),
  then a subsequent successful tick still covers the full window back to the last real captured
  document — nothing silently skipped. Validates User Story 5.

---

## Phase 9: Full Document Capture (added 2026-08-23 — see `proposal-full-document-capture.md`)

**Decided 2026-08-23 (user)**: this EXTENDS Feature 025 rather than becoming Feature 026 — 025
does not ship until this lands. Goal: the ledger becomes a faithful local mirror of each Morning
document, so future queries run against the ledger instead of the Morning MCP.

**Decisions already locked in (do not re-litigate):**
- Transport: MCP read tools gain a `format="json"` parameter; **default stays today's Hebrew
  prose**, so conversational output is byte-for-byte unchanged. Model copies JSON verbatim;
  `LedgerEventManager` maps/derives in code.
- Line items (`income[]`): **use only the first entry**; log a WARNING if the array has more than
  one, so a multi-line document is never silently half-captured.
- Bank details: **lift** `ledger_event_manager.py`'s `בנק`-only force-null and reuse the existing
  `bank_number`/`bank_branch`/`bank_account` fields for `חשבונית` events.
- `get_invoice_details`' tool description: **reword** to cover both status-resolution and
  reconciliation (its current status-change-only scoping is what made the model never call it).
- `_DOCUMENT_TYPE_NAMES`: keep **only the 5 types actually seen** (user decision) — an unmapped
  type renders as a bare number, accepted.

**Ledger field list — decided field-by-field 2026-08-23 (all 13 candidates reviewed):**

CAPTURE — 2 new fields:
| Field | Source | Why |
|---|---|---|
| `accounting_document_status_code` | `status` (raw int) + Morning's own label | Guards the open/closed-vs-paid/unpaid mismatch — we map `מסמך סגור`→paid, but for a proforma "closed" may mean "converted to an invoice" |
| `accounting_document_payment_method` | `payment[].name` | `העברה בנקאית`/`מזומן`/... — otherwise the bank fields appear with no indication of what payment they belong to |

**Document linkage — NO new fields (user correction, 2026-08-23):** an earlier draft proposed
`accounting_document_linked_number`/`_linked_type`. The ledger **already models this**:
`reference_hint` (free text describing the relationship) + `reference` (the real prior
**event_id**, or `REFERENCE_PLACEHOLDER = "צריך למצוא"` until resolved). `resolve_reference`'s own
docstring names the case exactly: *"the real prior event id this event relates to (replaces,
**cancels**, or otherwise references)"*. Rules, per user:
- **`reference_hint` is ALWAYS written** when `linkedDocuments` is present, and must carry
  **everything known**: the linked document's number AND its type **translated to Hebrew**
  (`חשבונית מס`, never the raw `305`). Written **deterministically by code** from the JSON
  payload, never AI-authored. `morning-mcp-app` performs the type translation when building the
  JSON (it owns `_DOCUMENT_TYPE_NAMES`), so `denidin-app` never needs a type table.
  ⚠️ Since the type table stays at the 5 seen types (earlier decision), a linked document of an
  unmapped type will render as a bare number here — accepted.
- **Resolve at capture time only** — no end-of-sweep second pass. If a ledger event already exists
  whose `accounting_document_display_number` matches the linked number, write that event's real
  `event_id` into `reference`.
- **If resolution fails**, leave `reference = REFERENCE_PLACEHOLDER` (the existing machine-readable
  "needs to be found" marker) **and note the failure explicitly in `reference_hint`**. It goes in
  `reference_hint`, not `description`: Phase 11 removed the `notes` field and split its roles —
  unparseable-value text appends to `description` (the component's own content), relationship
  reasoning goes to `reference_hint`. A failed link is relationship metadata.
  Expected to be common: the list returns newest-first, so a credit note is often captured before
  the document it cancels (#70284 and #52203 were created in the same minute).

CAPTURE — via EXISTING fields, no new field:
- `bank_number`/`bank_branch`/`bank_account` ← `payment[].bankName/bankBranch/bankAccount`
  (requires lifting the `בנק`-only force-null, already agreed).
- **`txn_date` ← `payment[].date`** (user insight, 2026-08-23: *"is this not txn_date in the
  ledger?"* — confirmed: `txn_date`'s own schema is "the actual calendar date this component's
  content refers to… for `source_type=בנק`, the transaction/value date", persisting to Events.csv's
  `תאריך_ביצוע`. A Morning payment date is the same concept.) Add a third case to `txn_date`'s
  tool description for `source_type=חשבונית`. Formats already align: Morning gives ISO
  `YYYY-MM-DD`, which `_normalize_iso_date` converts to `DD/MM/YYYY`.
- `vat_status` — still **derived in code** from the JSON's `vat`/`amountExcludeVat`/`amount` at
  capture time. Unaffected by skipping the VAT fields below: we read them from the payload without
  persisting them.

SKIP — 8 candidates, deliberately not captured (plus linked_number/linked_type, folded into
`reference_hint` above rather than skipped):
`amount_open` (volatile snapshot), `amount_excl_vat` + `vat_rate` (derivable), `vat_amount`,
`issue_date` (matched the creation date on all 5 samples), `currency` (ILS-only today),
`morning_id` (strictest reading of "display number, never the internal id"), `issued_by`
(constant today).

**Note for the record**: this is a leaner set than the opening goal ("capture as much as
possible") implied — 2 new fields rather than 13. The skips are coherent (derivable, constant,
volatile, or redundant), but since a skipped field cannot be backfilled once a document is
captured, it is worth a deliberate second look before implementation begins rather than after.

**Reverses the round-5 deferral**: credit-note linkage IS now captured — via the existing
`reference`/`reference_hint` mechanism (see above), superseding "leave as-is for now".

### Phase 9a — the 2 sweep tools

- [ ] T032a/b **(`morning-mcp-app`)** Fix the pre-existing `Invoice.payments` bug (raw key
  `payment` vs field `payments`, no mapping, `Payment.invoice_id` required but absent) — it is
  dead for EVERY caller today, so `get_invoice_details`' "תשלומים:" block has never rendered for
  anyone. Add `bank_name`/`bank_branch`/`bank_account`/`payment_type`/`status` to `Payment`.
  **User approved fixing this here rather than as a separate bugfix spec.**
- [ ] T033a/b **(`morning-mcp-app`)** Add `format="json"` to `list_invoices` +
  `get_invoice_details`. Default unchanged (Hebrew prose). JSON carries native types and explicit
  `null`s — the prose format's "missing is invisible" property is what produced the fabricated
  `00:00` timestamp.
- [ ] T034a/b **(`morning-mcp-app`)** Reword `get_invoice_details`' description (see above).
- [ ] T035a/b **(`denidin-app`)** Extend the `LEDGER_EVENT_TOOL` schema + `LedgerEventManager`
  with the agreed new `accounting_document_*` fields; `schema_version` 2 → 3; lift the `בנק`-only
  bank-field restriction; derive `vat_status` in code from `vat`/`amountExcludeVat`/`amount`
  rather than asking the model.
- [ ] T036a/b **(`denidin-app`)** Sweep consumes `format="json"`; first-`income[]`-entry-only rule
  with the multi-entry WARNING.
- [ ] T037 Re-verify live in dev via `scripts/prompt_playground.py` before redeploying.

### Phase 9b — 🔜 WIDEN JSON TO ALL READ TOOLS (explicit user commitment, 2026-08-23)

**Recorded so it is not forgotten.** The `format="json"` shape introduced in 9a is scoped to the
2 sweep tools purely to keep 9a's blast radius small — the agreed end state is **uniformity across
the whole MCP server**. User's words: *"I want uniformity for the whole mcp server."*

- [ ] T038 Extend `format="json"` to the remaining read tools: `get_financial_summary`,
  `list_clients`, `get_client_details`, `resolve_client_name`, `download_invoice_pdf` — reusing
  9a's exact JSON shape/conventions, not a second dialect.
- [ ] T039 Re-run the `billed` E2E suite for the conversational Morning flows afterwards: this
  changes what the model sees on every existing Morning conversation, so the Hebrew replies need
  confirming, not assuming.
- [ ] T040 Decide (separately) whether the 6 `create_*`/`add_client`/`update_client` confirmation
  tools also move to JSON — deliberately NOT in scope here: they feed Feature 022's approval-gate
  flow, whose prompts quote what will happen, so they need their own verification pass.

---

## Phase 8: Polish & Cross-Cutting

- [x] T024 [P] Update `config/config.example.json` (already done by T002b — this task is the
  companion CLAUDE.md/quickstart.md documentation of the new field, not code).
- [x] T025 [P] Update `quickstart.md`'s manual scenarios to reflect the round-3 design (safety
  cap, no WhatsApp alerts, `pending_review.json`, config-gated activation) — the file currently
  describes the superseded round-1/2 design in places.
- [ ] T026 **Live-verify `apps/morning-mcp-app`'s `creation_timestamp` mapping end-to-end against
  the real Morning dev sandbox** (narrower than the old T020 — most of what that task covered was
  already resolved live 2026-08-21, see `research.md`) — confirm the full round-trip: real
  document → `get_invoice_details` tool call → `creation_timestamp` present and matching the
  document's real creation time as shown in the Morning UI. Overlaps with Gate Zero (T014) — if
  T014 already exercises this, T026 can be marked done by cross-reference rather than a second
  separate live call (never re-run a live check speculatively).
- [ ] T027 **Confirm Morning's `from_date` filter semantics** at the day/instant boundary (does
  `from_date=X` include documents created exactly at `X`, or strictly after?) — drives the exact
  correctness of the cache-pruning safety margin (`data-model.md`'s "Pruning" note) and the
  safety-cap's own day-boundary math. A real, live, read-only check against the dev sandbox
  (e.g. query with a `from_date` matching a known document's own date, confirm inclusion).
- [ ] T028 **Verify `source_type="חשבונית"`'s real-world usage** against the actual
  hand-maintained `Events.csv` (spec.md's flagged, still-open naming risk) — a real-data check,
  not code — document the finding (confirm the term, or revise it) **before** the Acceptance
  tasks (T015/T017/T019/T021/T023) run for real.
- [ ] T029 **Confirm `event_subtype="הפקה"`** reads correctly as real accounting terminology —
  same kind of real-world sanity check as T028, not code.
- [ ] T030 **Pick and document the real `accounting_ledger_update_freq` value** for `dev`
  (and, separately, whenever `prod` adopts this feature) — an explicit human tuning decision
  (cost/traffic tradeoff), not a default to silently pick. The human then adds the real value to
  `config.dev.json`/`config.prod.json` directly (T002b intentionally does not touch these
  gitignored files).
- [ ] T031 Update `CLAUDE.md`'s feature-summary section with a new "Accounting Document
  Reconciliation (Feature 025)" paragraph, mirroring the "Reminders (Feature 054)" section's
  shape — done as part of `haleluya`'s docs-update step, not here.

---

## Dependencies & Execution Order

1. **Phase 1 (Setup)** → **Phase 2 (Foundational)** — strictly sequential, blocks everything else.
   T003a/T003b/T004a/T004b (`morning-mcp-app`) are independent of T005-T009 (`denidin-app`) and
   can run in parallel with them — different apps, different test suites, different venvs.
2. **Phase 3 (US1)** depends on Phase 2 fully complete (both apps' pieces).
3. **Phase 4 (US2)** depends on Phase 3 — ships together with US1 as the MVP.
4. **Phase 5 (US4)** depends on Phase 2 only — independent of Phases 3-4/6-7, can run any time
   after Phase 2.
5. **Phase 6 (US3)** depends on Phase 3 — independent of Phases 4-5/7.
6. **Phase 7 (US5)** depends on Phase 3 — independent of Phases 4-6.
7. **T014 (Gate Zero)** depends on T010b/T011b/T012b/T013 all existing, and must complete
   **before** T015 (US1's Acceptance definition is written into real code).
8. **Phase 8 (Polish)** T026/T027/T028/T029 should happen before any 👤 Acceptance task actually
   runs; T030 before T012b/T013 are meaningfully exercised against a real, always-on environment
   (not needed for the unit-test-level work, since tests always pass an explicit
   `accounting_ledger_update_freq` value or a `trigger` override); T031 last (post-implementation).
9. **All 👤 Acceptance tasks (T015/T017/T019/T021/T023)**: written and run together, once, only
   after every other task in Phases 1-7 (including Gate Zero, T014) is GREEN (§VI.a).

## Parallel Example: Foundational Phase

```text
# Different apps/venvs entirely - safe to run fully in parallel:
Task: "morning-mcp-app: write+implement creation_timestamp mapping (T003a/T003b/T004a/T004b)"
Task: "denidin-app: write tests for extended LedgerEvent record shape (T005a)"

# Within denidin-app, T005a/T006a/T009a can be written in parallel (different concerns, though
# T005a/T006a/T007a/T008a share one file - coordinate within it; T009a is a separate file):
Task: "Write tests for extended LedgerEvent record shape in test_ledger_event_manager.py"
Task: "Write tests for scan_accounting_documents/cache in test_ledger_event_manager.py"
Task: "Write tests for the extended LEDGER_EVENT_TOOL schema in test_ai_handler_ledger_events.py"
```

---

## Implementation Strategy

### MVP First (Phases 1-4: Setup + Foundational + US1 + US2)

1. Complete Phase 1: Setup (including the new config field)
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories; includes the small
   `morning-mcp-app` addition)
3. Complete Phase 3: User Story 1 (including Gate Zero, T014, before T015)
4. Complete Phase 4: User Story 2 (dedup — ships with US1, not after it)
5. **STOP and VALIDATE**: T026/T027/T028/T029/T030 resolved, US1+US2's 👤 scenarios (T015/T017)
   written and run for real
6. This is the MVP — a genuinely new Morning document gets captured exactly once (or, in the rare
   anomaly case, flagged for human review rather than either silently dropped or silently
   overwritten), with zero regression to existing conversational behavior only once Phase 5 (US4)
   also lands

### Incremental Delivery

1. Setup + Foundational → foundation ready (both apps)
2. US1 (+ Gate Zero) + US2 → MVP demoable
3. US4 → regression safety net confirmed
4. US3 → multi-document correctness
5. US5 → failure/cap-skip resilience correctness
6. Each story adds value without breaking previous stories; Phase 8 closes remaining real-world
   verification/tuning gaps before Acceptance runs for real

## Notes

- [P] tasks = different files (or clearly separable concerns within one file), no dependency on
  each other.
- [Story] label maps task to specific user story for traceability.
- Verify each "a" task's tests fail before writing its paired "b" implementation.
- Commit after each approved task or logical group (per CLAUDE.md's "never merge without
  approval" — commits within the branch are fine; PR/merge to `master` is its own separate gate,
  handled by `haleluya`).
- Stop at each Checkpoint to validate that story independently before continuing.
- `apps/morning-mcp-app` needs exactly **one** small change for this feature — mapping/exposing
  `creationDate` (T003/T004) — everything else about its existing tools is already sufficient
  (live-confirmed 2026-08-21, `research.md`). This corrects the previous revision's "zero changes
  needed" note, which was accurate for every *other* aspect of this feature but not this one.
