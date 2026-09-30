# Tasks: The Dynamic Capability Backbone (063)

> **Note 2026-09-24**: the task history below records the design as it evolved (two-call Intent Identification/Planning → `use_capability`/`note` → the current "resolution" loop). Only `contracts/capability-resolution-loop.md` describes the CURRENT design; older entries are historical and intentionally left as written.

**Input**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/intent-planning-loop.md`,
`contracts/prompt-assembly.md`, `quickstart.md`, `user-stories.md`
**Tests**: per `user-stories.md`'s §VI.a decision, no new `billed`/`expensive` tests are added —
unit/integration tests only, new/standalone (not rewrites of `ai_handler.py`'s existing ones, per
REQ-063-05/the 2026-09-14 clarification). `ai_handler.py` and every other legacy file listed in
REQ-063-07 are read-only references for this task list — never edited by any task below.

**Scope note**: this feature's own taxonomy (`spec.md`) reimplements the *behavior* of a
~4,859-line handler. This task list delivers the backbone mechanism end-to-end for real
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

**Purpose**: the backbone kernel + prompt-loading/caching mechanism every user story depends on.

- [X] T010 [P] Author `apps/denidin-app/config/prompts/backbone.md` (static behavioral constants
      only, per `spec.md`'s Capability Plugin Taxonomy: Core Identity, Behavioral Guidelines, User
      Roles, Privacy & Security, Contexts of Operation, Group Conversation Etiquette,
      Edited/Deleted Message Markers, generic post-turn-recognition mechanism, Proactive Progress
      Updates, Reaction Management).
- [X] T011 [P] Author `apps/denidin-app/config/prompts/capabilities/intent_identification.md`.
- [X] T012 [P] Author `apps/denidin-app/config/prompts/capabilities/planning.md`.
- [X] T013 Create `apps/denidin-app/src/backbone/__init__.py`.
- [X] T014 Implement `_load_backbone()`/`_load_capability_prompt(tag)`/`_build_instructions(...)`
      in `apps/denidin-app/src/backbone/backbone.py` per `contracts/prompt-assembly.md`
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
- [X] T019 Implement `Backbone` in `apps/denidin-app/src/backbone/backbone.py`:
      `get_response()` entry point running Intent Identification → Planning → empty-plan final
      reply (per `contracts/intent-planning-loop.md` steps 1/2/4 — the execution loop over a
      non-empty plan is T020-T026 below, added per-capability).
- [X] T020 [P] Unit tests for prompt loading/caching (`test_backbone_prompt_loading.py`).
- [X] T021 [P] Unit tests for `CapabilityTag`/`Plan` validation + RBAC filtering + fail-open
      (`test_planning.py`).
- [X] T022 [P] Unit tests for `_build_instructions` assembly order (Backbone + one capability +
      accumulated context + date) (`test_backbone_instructions.py`).
- [X] T023 Integration test: `denidin.py::initialize_app` constructs the legacy `AIHandler` when
      the flag is off (byte-identical to today) and the new `Backbone` when on
      (`test_initialize_app_backbone_flag.py`).

## Phase 3: User Story 2 — Proof of Dynamic Prompt Loading (Priority: P1)

**Goal**: a small-talk turn is Backbone + Intent Identification + Planning only — zero domain
capability content loaded (UAT 2).

- [X] T030 [US2] Wire `Backbone.get_response()`'s empty-plan path (Intent
      Identification's output alone composes the final reply, `[[NO_REPLY]]` sentinel handled
      identically to `AIHandler._finalize_response`'s check) — `src/backbone/backbone.py`.
- [X] T031 [US2] Instrumentation: log each step's `instructions` byte-length + `cached_tokens` from
      the API response, per `research.md` R6/`quickstart.md`'s verification section —
      `src/backbone/backbone.py`.
- [X] T032 [US2] Unit test: an empty `Plan` produces a final reply built only from Intent
      Identification's output, with zero domain-capability prompt content ever loaded
      (`test_backbone_empty_plan.py`).
- [X] T033 [US2] Unit test: `[[NO_REPLY]]` sentinel on the final step suppresses the reply exactly
      as `AIHandler`'s does (`test_backbone_no_reply_sentinel.py`).

**Checkpoint**: a small-talk turn end-to-end (flag on) never touches any `config/prompts/capabilities/*.md`
file other than `intent_identification.md`/`planning.md`.

## Phase 4: User Story 3 — Multi-Capability Routing (Priority: P2)

**Goal**: a turn whose Plan names ≥2 domain capabilities executes them in order, each step's
prompt/tools swapped in one at a time, later steps seeing earlier steps' accumulated context.

- [X] T040 [US3] Implement the execution loop (`_execute_plan()`) in
      `src/backbone/backbone.py` per `contracts/intent-planning-loop.md` step 3: per-step
      instructions assembly, accumulated-context threading, non-fatal per-step-failure handling.
- [X] T041 [P] [US3] Create `apps/denidin-app/src/capabilities/__init__.py`.
- [X] T042 [P] [US3] Author `config/prompts/capabilities/cap_reminders_read.md` +
      `src/capabilities/reminders/handler.py::read()` — wraps `reminder_manager.py`'s existing
      `list_reminders`-equivalent query, unmodified manager, new thin capability handler.
- [X] T043 [P] [US3] Author `config/prompts/capabilities/cap_ledger_query.md` +
      `src/capabilities/ledger_events/handler.py::query()` — wraps `LedgerEventManager.query_events`
      unmodified.
- [X] T044 [P] [US3] Author `config/prompts/capabilities/cap_invoicing_read.md` +
      `src/capabilities/invoicing/handler.py::read_tools()` — remote MCP tool passthrough, same
      tool set `_build_morning_mcp_tools`'s read subset exposes today.
- [X] T045 [P] [US3] Author `config/prompts/capabilities/cap_media_analysis.md` +
      `src/capabilities/media_analysis/handler.py::extract()` — wraps
      `handlers/extractors/{image,pdf,docx}_extractor.py` unmodified, MIME-dispatched exactly as
      `MediaHandler` does today.
- [X] T046 [US3] Wire `denidin.py::initialize_app`'s media-message dispatch: flag on routes into
      `Backbone` instead of `WhatsAppHandler.handle_media_message()` directly, flag off
      unchanged (REQ-063-04a).
- [X] T047 [P] [US3] Unit tests for each T042-T045 handler (read/query/extract paths only —
      `test_capability_reminders_read.py`, `test_capability_ledger_query.py`,
      `test_capability_invoicing_read.py`, `test_capability_media_analysis.py`).
- [X] T048 [US3] Unit test: a 2-step `Plan` (`cap_media_analysis` → `ledger_capture` note-only stub)
      threads `cap_media_analysis`'s output into the second step's accumulated context
      (`test_backbone_multi_step_context.py`).
- [X] T049 [US3] Integration test: flag-on media dispatch (`denidin.py`) reaches
      `Backbone` instead of `WhatsAppHandler.handle_media_message()`; flag-off dispatch
      is provably unchanged (`test_media_dispatch_backbone_flag.py`).

**Checkpoint**: read/query-side multi-capability routing works end-to-end under unit+integration
coverage; write-side (approval-gated) capabilities are Phase 5.

## Phase 5: User Story 1 — Zero Behavioral Regression, write-side template (Priority: P1)

**Goal**: prove the approval-gated write path works under the new backbone, using Reminders —
Write as the first fully-ported template; the same shape then applies to the remaining write
capabilities as separately-scoped follow-up work (see "Deferred" below) rather than four more
copies rushed in this pass.

- [X] T050 [US1] Author `config/prompts/capabilities/cap_reminders_write.md`.
- [X] T051 [US1] Implement `src/capabilities/reminders/handler.py::propose_write()` — builds a
      `PendingLocalToolApproval` via the existing, unmodified
      `pending_local_tool_approval_manager.py`, mirroring `AIHandler._handle_reminder_creation_proposal`'s
      shape but as new code in the new module (REQ-063-07: zero changes to the original).
- [X] T052 [US1] Wire `Backbone.resolve_button_tap()`/pending-approval-resolution entry
      point (per `contracts/intent-planning-loop.md`'s Non-goals: skips Intent Identification/Planning,
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
      `backbone = None`, since a bare `Mock()` auto-vivifies a truthy attribute —
      permitted under the 2026-09-14 clarification allowing unit test updates for new module
      boundaries).
- [ ] T063 **STOP — human checkpoint.** Report readiness for the `billed`/`expensive` acceptance
      pass (REQ-063-05/SC-003) per `user-stories.md` §VI.a step 4 — that suite is run once,
      together, at the end, and is explicitly **out of scope for an AI agent to run/modify** per
      this session's standing instruction.

---

## Deferred (tracked, not silently dropped) — CLOSED 2026-09-15

Every item originally listed here has since been implemented and verified (unit+integration
suite green, flag on and off, 1713/1713 passing) as of 2026-09-15's full spec-vs-code re-audit.
Kept as a record of what was closed, not as open work:

- **Invoicing — Write** — `src/capabilities/invoicing/handler.py::propose_write()`/
  `resolve_button_tap()`/`resolve_typed_reply()`, Group B reference-tool approval-prompt building
  per bugfix-038's pattern. Done.
- **Ledger Events — Capture** — NOT ported as an in-plan three-verdict flow (a deliberate design
  decision, not a gap): `denidin.py`'s pre-existing, unmodified `_run_post_turn_ledger_recognition`
  (Feature 069, calling `AIHandler.recognize_ledger_event`'s full proven flow) already runs for
  every godfather/admin turn under flag-on, text and media alike, once flag-on turns are
  persisted to the session (see the session-persistence item below). This step's own `capture()`
  is a documented no-op that defers to that shared mechanism entirely, to avoid double-capturing
  the same event. See `src/capabilities/ledger_events/handler.py::capture()`'s docstring.
- **Reminders modify/delete** — `src/capabilities/reminders/handler.py::_propose_modify_or_delete()`
  + `MODIFY_DELETE_REMINDER_TOOLS`, offered alongside create in the same `propose_write()` call.
  Done.
- **Recurring reminder creation** — `CREATE_REMINDER_TOOL`'s `schedule_type=recurring` branch,
  same call as one-time creation. Done.
- **Backbone-level Proactive Progress Updates + Reaction Management execution wiring** —
  `src/backbone/backbone_tools.py`'s `dispatch_send_progress_update`/`dispatch_react_to_message`,
  dispatched from `Backbone._resolve_backbone_tool_calls` after every capability-step
  call. Done.
- **Accounting-reconciliation capture equivalent** — turned out not to be a real gap on closer
  inspection: `_handle_accounting_reconciliation_capture` is called ONLY by
  `services/accounting_reconciliation_service.py`'s headless sweep, never by any live
  conversational turn (confirmed via a full-codebase grep for its only callers) — and
  `denidin.py::initialize_app` constructs `AIHandler` unconditionally regardless of the flag
  (the reconciliation service, reminder delivery, and daily-summary-roll schedulers all always
  run against that same shared `ai_handler` instance), so this was never actually routed through
  either `AIHandler.get_response` or `Backbone.get_response` in the first place.
  Nothing to build here.
- **Raw media bytes threading** — `denidin.py`'s flag-on media dispatch (split into
  `_process_media_message_via_backbone`) downloads/validates real media via the unmodified
  low-level `MediaFileManager` methods and threads the raw `Media` object into
  `Backbone.get_response(media=..., media_type=...)`; Planning decides whether the
  turn's plan even includes a `cap_media_analysis` step at all — REQ-063-04a's real design (corrects
  the earlier 2026-09-14 eager-extraction shortcut, per explicit human correction: media enters
  the backbone raw, like any other message, and the backbone chooses whether/when to
  extract). Done.

Additionally closed by the 2026-09-15 re-audit, not originally listed above (found via
cross-referencing every spec artifact against the actual code, not just this task list):
- **Session persistence** for flag-on turns (`Backbone._persist_turn`, wired into
  `_finalize_response` and into the pending-approval bypass paths in both reminders/invoicing
  handlers).
- **Long-term memory recall** for flag-on turns (`Backbone._recall_memory`, mirroring
  `AIHandler`'s own RBAC-filtered `recall_with_rbac_filter`/`recall` call).
- **mcp_calls tracking** through the turn (`call_capability_step` accumulates real Morning MCP
  tool calls into `AIResponse.mcp_calls` and the persisted assistant message), closing a gap where
  the post-turn ledger-recognition hook always saw an empty list under flag-on regardless of real
  Morning activity that turn.

---

## Next Up (approved design, not yet implemented) — opened 2026-09-16

The two-call Intent Identification → Planning design (this file's closed items above,
`contracts/intent-planning-loop.md`) is retired — see `spec.md`'s 2026-09-16 clarification session.
Two approved-but-unbuilt designs, not yet broken into tasks:

- **Tool-driven resolution loop** — `contracts/tool-driven-loop.md`. Deletes
  `intent_identification.py`/`planning.py`/`fail_open_plan`/`_execute_plan`'s step-list; replaces
  with one merged backbone call driven by four real function-calling tools
  (`load_capability`, `use_capability`, `record_planning_status`, `send_to_user`) on a
  generalized version of the existing chained (`previous_response_id`) tool-dispatch loop.
- **`cap_docx_write` capability** — `contracts/docx-write-capability.md`. Wraps Feature 083's
  `FeeAgreementToolHandler`/`DocTemplateEngine` unmodified; needs its own inner multi-round
  tool-dispatch loop (no approval gate), local to this one capability.

---

## Bug fix: `use_capability`'s original always-`call_capability_step` design — CLOSED 2026-09-23

Root cause: a real T3 sanity-test trace (`tests/billed/T3_rawlog_*.log`) showed
`cap_reminders_write`'s `create_reminder` computing a wrong `one_time_due_at` twice in a row
(different wrong years both times) despite the correct current date being present in
`instructions` on every call. Traced to `use_capability` *always* dispatching through
`call_capability_step` — a brand-new, non-chained Responses API call resending the full
Backbone + capability prompt and conversation history from scratch — giving the model two
fully disconnected chances to compute the same relative date (once composing `note`, once
independently re-deriving the ISO value from it). Explicit user correction: `use_capability`
was always meant to mean "the capability you just loaded is now live — its tools are attached
to THIS call" — never a second, disconnected AI call; see `contracts/tool-driven-
resolution.md`'s new "Dynamic tool-attachment" section for the full corrected contract.

- [X] T070 Update `contracts/tool-driven-loop.md`: corrected `use_capability`'s own
      description + new "Dynamic tool-attachment" section documenting the fix, the original
      flaw, and which capabilities are/aren't migrated. Done.
- [X] T071 `backbone.py`: `_dynamic_capability_tools` (allowlist — `cap_reminders_write` only
      so far), `_maybe_activate_dynamic_capability` (attaches domain tools to the SAME chained
      follow-up instead of spawning a new call), `_extract_dynamic_capability_calls` /
      `_dispatch_dynamic_capability_call` (recognizes and executes the domain tool call once it
      comes back on that same chain), `_turn_active_dynamic_capability` per-turn state
      (reset in `get_response`, one-shot per activation). Done.
- [X] T072 `src/capabilities/reminders/tools.py`: `extract_reminder_tool_calls` (same
      `(call_id, tool_name, args)` shape as `backbone_tools.extract_backbone_tool_calls`).
      `src/capabilities/reminders/handler.py`: `dispatch_direct_tool_call` (direct-execute entry
      point against `ReminderManager`, no `call_capability_step` involved). Done.
- [X] T073 Unit suite green (`tests/unit -k "backbone or reminders"`, 111/111 passed; full
      `tests/unit` run to confirm no unrelated regression). `reminders/handler.py`'s existing
      `write()`/`read()` (the old `call_capability_step`-based path) are left in place, unused by
      this new path for `cap_reminders_write` specifically but still directly unit-testable and still
      the live path for `cap_reminders_read` (not migrated — no strict-schema re-derivation risk
      there) — no removal, per minimal-diff scoping.
- [ ] T074 **Not done, explicitly scoped out for now**: migrating any other capability
      (`cap_invoicing_write`, `ledger_capture`, `cap_media_analysis`, `cap_docx_write`) to this same
      mechanism — each has its own protocol constraints worth reviewing on their own (see
      "Dynamic tool-attachment"'s own note on why). Tracked here, not silently dropped.
- [X] T075 Re-ran `tests/billed/test_reminder_lifecycle_billed.py::TestReminderLifecycleBilled::
      test_godfather_creates_one_time_reminder_button_approval` (T3) with
      `feature_flags.enable_capability_backbone` scope-toggled true for the run only, reverted
      immediately after (confirmed 0 `feature_flags` keys left in `config.test.json`). Found TWO
      real bugs in the T071 implementation via this re-run, both fixed same session:
      1. `_turn_active_dynamic_capability` was cleared after the FIRST domain-tool dispatch
         (success or failure) - broke `cap_reminders_write.md`'s own "retry the SAME call once on
         failure" contract, since a model retry calls `create_reminder` directly again with no
         fresh `use_capability` in between. The orphaned retry call went unanswered and the loop
         silently returned `NO_REPLY_SENTINEL`. Fixed: stays active for the rest of the turn,
         reset only at the top of the next `get_response` call.
      2. A model several rounds deep in one chained turn declined to call `create_reminder` at
         all, replying that "the system didn't supply the required current date" - even though
         the date WAS present, just several rounds back (a chained follow-up carries no
         `instructions` of its own). Fixed: `_current_date_time_line` factored out of
         `build_instructions` and restated verbatim in the dynamic-capability activation
         acknowledgment text itself, right next to where the strict-schema date field actually
         gets filled.
      Final re-run: **PASSED** - `one_time_due_at=2026-09-23T20:43:00+03:00` (correct date, first
      try, no retry needed), reminder actually created and verified via the active-reminder-set
      diff assertion, confirmed via log grep that `call_capability_step[cap_reminders_write]` was
      called zero times in this run's window. Unit suite re-confirmed green after both fixes
      (111/111 scoped, 1649/1649 full) with the flag reverted off.


## Resolution redesign — implemented 2026-09-24
See `contracts/capability-resolution-loop.md`. Unit + integration suites green (1753 passed). Remaining: the 10 billed capability tests (need explicit go-ahead via sanctioned scripts).
