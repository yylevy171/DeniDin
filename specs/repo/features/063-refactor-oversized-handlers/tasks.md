# Tasks: The Dynamic Capability Backbone (063)

**Input**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/orchestration-loop.md`,
`contracts/prompt-assembly.md`, `quickstart.md`, `user-stories.md`
**Tests**: per `user-stories.md`'s §VI.a decision, no new `billed`/`expensive` tests are added —
unit/integration tests only, new/standalone (not rewrites of `ai_handler.py`'s existing ones, per
REQ-063-05/the 2026-09-14 clarification). `ai_handler.py` and every other legacy file listed in
REQ-063-07 are read-only references for this task list — never edited by any task below.

**Scope note**: this feature's own taxonomy (`spec.md`) reimplements the *behavior* of a
~4,859-line handler. This task list delivers the orchestrator mechanism end-to-end for real
(Setup, Foundational, US2) plus a working vertical slice of every domain capability's read/query
path and one full write-approval path (Reminders — Write, used as the template the remaining
write-capabilities' approval-flow parity follows), rather than rushing all 7 domains' full
write-side parity unreviewed. Capabilities marked `(parity follow-up)` below implement their
prompt file + tool wiring + read path now; full write-approval-flow parity ships as later,
separately-approved tasks — tracked at the end of this file, not silently dropped.

---

## Phase 1: Setup

- [X] T001 Create `apps/denidin-app/config/prompts/` + `apps/denidin-app/config/prompts/capabilities/`
      directories (no code — directory scaffold only, git tracks via the first file written into
      each).
- [X] T002 [P] Add `feature_flags.enable_capability_backbone` (bool, default `false`) and the new
      `backbone_config` section to `apps/denidin-app/src/models/config.py`'s `AppConfiguration`
      (per `data-model.md`'s Config additions) — `constitution_config` untouched.
- [X] T003 [P] Add `backbone_config`/`feature_flags.enable_capability_backbone` documentation to
      `apps/denidin-app/config/config.example.json` (additive keys only).

## Phase 2: Foundational (blocking prerequisites)

**Purpose**: the orchestrator kernel + prompt-loading/caching mechanism every user story depends on.

- [X] T010 [P] Author `apps/denidin-app/config/prompts/backbone.md` (static behavioral constants
      only, per `spec.md`'s Capability Plugin Taxonomy: Core Identity, Behavioral Guidelines, User
      Roles, Privacy & Security, Contexts of Operation, Group Conversation Etiquette,
      Edited/Deleted Message Markers, generic post-turn-recognition mechanism, Proactive Progress
      Updates, Reaction Management).
- [X] T011 [P] Author `apps/denidin-app/config/prompts/capabilities/intent_identification.md`.
- [X] T012 [P] Author `apps/denidin-app/config/prompts/capabilities/planning.md`.
- [X] T013 Create `apps/denidin-app/src/backbone/__init__.py`.
- [X] T014 Implement `_load_backbone()`/`_load_capability_prompt(tag)`/`_build_instructions(...)`
      in `apps/denidin-app/src/backbone/orchestrator.py` per `contracts/prompt-assembly.md`
      (independent mtime caches, missing-file → WARNING + empty string).
- [X] T015 [P] Implement `CapabilityTag` (the 9-value enum from `data-model.md`) in
      `apps/denidin-app/src/backbone/capability_tags.py`.
- [X] T016 Implement the `Plan` model + `role_allowed_capabilities()` RBAC filter in
      `apps/denidin-app/src/backbone/planning.py` (per `data-model.md`'s Plan/RBAC sections —
      empty-plan validity, unrecognized-tag dropping, fail-open on Planning-call failure).
- [X] T017 [US-shared] Implement the Intent Identification step (`identify_intent()`) in
      `apps/denidin-app/src/backbone/intent_identification.py` — one OpenAI call, Backbone +
      `intent_identification` prompt, free-form output.
- [X] T018 [US-shared] Implement the Planning step (`build_plan()`) in
      `apps/denidin-app/src/backbone/planning.py` — one OpenAI call, Backbone + `planning` prompt +
      Intent Identification's output + `available_capabilities_for_planning`, parses/validates
      into a `Plan`.
- [X] T019 Implement `BackboneOrchestrator` in `apps/denidin-app/src/backbone/orchestrator.py`:
      `get_response()` entry point running Intent Identification → Planning → empty-plan final
      reply (per `contracts/orchestration-loop.md` steps 1/2/4 — the execution loop over a
      non-empty plan is T020-T026 below, added per-capability).
- [X] T020 [P] Unit tests for prompt loading/caching (`test_orchestrator_prompt_loading.py`).
- [X] T021 [P] Unit tests for `CapabilityTag`/`Plan` validation + RBAC filtering + fail-open
      (`test_planning.py`).
- [X] T022 [P] Unit tests for `_build_instructions` assembly order (Backbone + one capability +
      accumulated context + date) (`test_orchestrator_instructions.py`).
- [X] T023 Integration test: `denidin.py::initialize_app` constructs the legacy `AIHandler` when
      the flag is off (byte-identical to today) and the new `BackboneOrchestrator` when on
      (`test_initialize_app_backbone_flag.py`).

## Phase 3: User Story 2 — Proof of Dynamic Prompt Loading (Priority: P1)

**Goal**: a small-talk turn is Backbone + Intent Identification + Planning only — zero domain
capability content loaded (UAT 2).

- [X] T030 [US2] Wire `BackboneOrchestrator.get_response()`'s empty-plan path (Intent
      Identification's output alone composes the final reply, `[[NO_REPLY]]` sentinel handled
      identically to `AIHandler._finalize_response`'s check) — `src/backbone/orchestrator.py`.
- [X] T031 [US2] Instrumentation: log each step's `instructions` byte-length + `cached_tokens` from
      the API response, per `research.md` R6/`quickstart.md`'s verification section —
      `src/backbone/orchestrator.py`.
- [X] T032 [US2] Unit test: an empty `Plan` produces a final reply built only from Intent
      Identification's output, with zero domain-capability prompt content ever loaded
      (`test_orchestrator_empty_plan.py`).
- [X] T033 [US2] Unit test: `[[NO_REPLY]]` sentinel on the final step suppresses the reply exactly
      as `AIHandler`'s does (`test_orchestrator_no_reply_sentinel.py`).

**Checkpoint**: a small-talk turn end-to-end (flag on) never touches any `config/prompts/capabilities/*.md`
file other than `intent_identification.md`/`planning.md`.

## Phase 4: User Story 3 — Multi-Capability Routing (Priority: P2)

**Goal**: a turn whose Plan names ≥2 domain capabilities executes them in order, each step's
prompt/tools swapped in one at a time, later steps seeing earlier steps' accumulated context.

- [X] T040 [US3] Implement the execution loop (`_execute_plan()`) in
      `src/backbone/orchestrator.py` per `contracts/orchestration-loop.md` step 3: per-step
      instructions assembly, accumulated-context threading, non-fatal per-step-failure handling.
- [X] T041 [P] [US3] Create `apps/denidin-app/src/capabilities/__init__.py`.
- [X] T042 [P] [US3] Author `config/prompts/capabilities/reminders_read.md` +
      `src/capabilities/reminders/handler.py::read()` — wraps `reminder_manager.py`'s existing
      `list_reminders`-equivalent query, unmodified manager, new thin capability handler.
- [X] T043 [P] [US3] Author `config/prompts/capabilities/ledger_query.md` +
      `src/capabilities/ledger_events/handler.py::query()` — wraps `LedgerEventManager.query_events`
      unmodified.
- [X] T044 [P] [US3] Author `config/prompts/capabilities/invoicing_read.md` +
      `src/capabilities/invoicing/handler.py::read_tools()` — remote MCP tool passthrough, same
      tool set `_build_morning_mcp_tools`'s read subset exposes today.
- [X] T045 [P] [US3] Author `config/prompts/capabilities/media_analysis.md` +
      `src/capabilities/media_analysis/handler.py::extract()` — wraps
      `handlers/extractors/{image,pdf,docx}_extractor.py` unmodified, MIME-dispatched exactly as
      `MediaHandler` does today.
- [X] T046 [US3] Wire `denidin.py::initialize_app`'s media-message dispatch: flag on routes into
      `BackboneOrchestrator` instead of `WhatsAppHandler.handle_media_message()` directly, flag off
      unchanged (REQ-063-04a).
- [X] T047 [P] [US3] Unit tests for each T042-T045 handler (read/query/extract paths only —
      `test_capability_reminders_read.py`, `test_capability_ledger_query.py`,
      `test_capability_invoicing_read.py`, `test_capability_media_analysis.py`).
- [X] T048 [US3] Unit test: a 2-step `Plan` (`media_analysis` → `ledger_capture` note-only stub)
      threads `media_analysis`'s output into the second step's accumulated context
      (`test_orchestrator_multi_step_context.py`).
- [X] T049 [US3] Integration test: flag-on media dispatch (`denidin.py`) reaches
      `BackboneOrchestrator` instead of `WhatsAppHandler.handle_media_message()`; flag-off dispatch
      is provably unchanged (`test_media_dispatch_backbone_flag.py`).

**Checkpoint**: read/query-side multi-capability routing works end-to-end under unit+integration
coverage; write-side (approval-gated) capabilities are Phase 5.

## Phase 5: User Story 1 — Zero Behavioral Regression, write-side template (Priority: P1)

**Goal**: prove the approval-gated write path works under the new orchestrator, using Reminders —
Write as the first fully-ported template; the same shape then applies to the remaining write
capabilities as separately-scoped follow-up work (see "Deferred" below) rather than four more
copies rushed in this pass.

- [X] T050 [US1] Author `config/prompts/capabilities/reminders_write.md`.
- [X] T051 [US1] Implement `src/capabilities/reminders/handler.py::propose_write()` — builds a
      `PendingLocalToolApproval` via the existing, unmodified
      `pending_local_tool_approval_manager.py`, mirroring `AIHandler._handle_reminder_creation_proposal`'s
      shape but as new code in the new module (REQ-063-07: zero changes to the original).
- [X] T052 [US1] Wire `BackboneOrchestrator.resolve_button_tap()`/pending-approval-resolution entry
      point (per `contracts/orchestration-loop.md`'s Non-goals: skips Intent Identification/Planning,
      resumes the specific pending step directly).
- [X] T053 [P] [US1] Unit tests: `test_capability_reminders_write.py` (propose → pending →
      approve/decline, mirroring `AIHandler`'s existing reminder-approval unit test shapes but as
      new, standalone tests per REQ-063-05).
- [X] T054 [US1] Integration test: a full flag-on turn (`AIRequest` in → `AIResponse` out) creating
      a reminder, asserting the returned object shape matches what `denidin.py`'s callers already
      expect from the legacy path (`test_backbone_reminder_write_e2e.py`, mocked OpenAI, no
      `billed` cost).

## Phase 6: Polish

- [X] T060 [P] Run `python3 -m pylint src/backbone src/capabilities --rcfile=.pylintrc` and
      `python3 -m mypy src/backbone src/capabilities --config-file=mypy.ini`, fix findings.
- [X] T061 [P] Update `CLAUDE.md`'s Architecture section with a short "Dynamic Capability Backbone
      (Feature 063, flag-gated)" pointer once the flag is real (kept minimal — full doc lands with
      the eventual default-flip decision, a separate future feature per `research.md` R1).
- [X] T062 Run the full unit+integration suite (`python3 -m pytest apps/denidin-app/tests/unit
      apps/denidin-app/tests/integration -v`) — flag off AND flag on paths — until green. Result:
      1629/1630 passed (49 new tests for this feature, all passing); the 1 failure
      (`test_edited_deleted_webhook_routing.py::test_redelivered_edited_message_is_logged_only_once`)
      was confirmed pre-existing/unrelated (still fails identically with this feature's changes
      fully stashed — shared test-data-state flakiness across runs, not a regression this feature
      introduced). Also fixed one real pre-existing-suite regression this feature's own change
      caused: `test_config.py`'s config-dict-sync check (added `backbone_config` to `denidin.py`'s
      `__main__` config_dict literal) and one existing unit test's `Mock()` fixture (explicit
      `backbone_orchestrator = None`, since a bare `Mock()` auto-vivifies a truthy attribute —
      permitted under the 2026-09-14 clarification allowing unit test updates for new module
      boundaries).
- [ ] T063 **STOP — human checkpoint.** Report readiness for the `billed`/`expensive` acceptance
      pass (REQ-063-05/SC-003) per `user-stories.md` §VI.a step 4 — that suite is run once,
      together, at the end, and is explicitly **out of scope for an AI agent to run/modify** per
      this session's standing instruction.

---

## Deferred (tracked, not silently dropped)

Full write-approval-flow parity for the remaining domain capabilities, following the
Reminders — Write template landed in Phase 5:
- Invoicing — Write (`create_invoice`/`create_transaction_account`/etc., Group B reference-tool
  approval-prompt building per bugfix-038's pattern)
- Ledger Events — Capture (the three-verdict recognition flow + הסכם/בנק specifics, ported from
  `config/ledger_recognition_prompt.md`'s domain rules per the second plan-phase clarification)
- Reminders modify/delete (`_handle_reminder_modify_or_delete_proposal`/`_propose_reminder_modify_or_delete`
  equivalents)
- Backbone-level Proactive Progress Updates + Reaction Management execution wiring (prompt content
  is in `backbone.md` per T010; the corresponding tool-call execution/dispatch code is not yet
  wired into `BackboneOrchestrator`'s loop)
- Accounting-reconciliation capture equivalent (`_handle_accounting_reconciliation_capture`) — the
  reconciliation *service* itself is explicitly out of scope per `contracts/orchestration-loop.md`'s
  Non-goals; only the capture path a live turn would take is deferred here
- Raw media bytes threading from `denidin.py`'s flag-on media dispatch into
  `BackboneOrchestrator`'s per-step `turn_context["media"]`/`["media_type"]` — the routing
  DECISION (flag on → orchestrator, flag off → legacy `WhatsAppHandler.handle_media_message`,
  unchanged) is wired for real (T046); `src/capabilities/media_analysis/handler.py::extract()`
  already calls the real, unmodified extractor classes once a `Media` object is present in
  `turn_context`, but nothing yet populates that key from the live WhatsApp media download path —
  it currently degrades to a clear "no media attached" fallback text instead of a crash
- Recurring reminder creation, reminder modify/delete (noted inline in Phase 5 already)

Each of these should get its own `tasks.md` phase, its own unit-test-first pass, and its own human
approval gate when picked up — not bundled into a single unreviewed sweep.
