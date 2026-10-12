# Tasks: Realistic Message Handling — Conversation Without "Turns"

**Feature Branch**: `feature/067-realistic-message-handling` | **Spec**: `./spec.md` | **Plan**: `./plan.md`

**Format**: `- [ ] Txxx [P?] [USn?] Description with file path` — `[P]` = parallelizable (different
files, no unfinished dependency). Paths are relative to `apps/denidin-app/` unless they start with
`specs/`, `apps/`, `.github/` or `scripts/`.

## Ground rules for every task (binding — CONSTITUTION/METHODOLOGY/CLAUDE.md)

- **Tests**: never a bare `pytest`. Unit/integration: `scripts/run_unit_integration_tests.sh <path>`.
  `billed`: `scripts/run_single_test.sh <node_id>` (no approval needed, sound off each result
  live). `expensive` (A8 only): fresh human approval each run, one at a time.
- **Task A / Task B pairing (unit + integration)**: *Task A* writes the tests and must be **RED**;
  **the human approves Task A** before *Task B* (implementation) starts. Approved tests are immutable.
- **`billed`/`expensive` acceptance tests (A1–A8)**: their plain-language scenarios are already
  approved (`user-stories.md`); the **code is written and run once, together, in the final
  Acceptance phase** — nothing before it. Tests that seed state wipe it before and after.
- **Config is code**: new config keys are added to `config/config.example.json` and
  `AppConfiguration` (defaults); adding them to `config.dev.json`/`config.prod.json`/`config.test.json`
  is a **human-approved step done before any run**, never mid-run.
- **Never** start dev/prod, cut a release, deploy, or bump `CURRENT_SCHEMA_VERSION` (human-only).
- No `os.getenv`, `now_local()` for time, `pathlib.Path`, no monkey-patching, no lock outside `queue.Queue`.
- Do not use the word "turn" in any new code, comment, test name or doc (REQ-RMH-030).
- Commit per phase on this branch; never to `master`; no worktrees.

---

## Phase 1: Setup

- [ ] T001 Add a `message_queues` config block with defaults to `config/config.example.json` and `src/models/config.py` (`AppConfiguration` + `validate()`): `intake_max_per_chat` 500, `intake_max_total` 2000, `session_max` 200, `warn_fraction` 0.5, `stall_seconds` 30, `monitor_interval_seconds` 10, `supervisor_interval_seconds` 5, `supervisor_max_restarts` 3, `supervisor_window_seconds` 600, `session_call_timeout_seconds` 60, `slow_call_seconds` 5. Absent block = these defaults (existing configs keep working)
- [ ] T002 **[HUMAN GATE]** Ask the human to approve adding those keys to `config/config.dev.json`, `config/config.prod.json`, `config/config.test.json` (gitignored) *before any test run*; do not edit them without that approval
- [ ] T003 [P] Create package skeletons `src/intake/__init__.py`, `tests/unit/intake/__init__.py`, `tests/integration/intake/__init__.py`

## Phase 2: Foundational (blocks every user story)

### 2a — Gate Zero: verify third-party assumptions with real responses (`billed`, text only, run freely)

- [ ] T004 [P] Write and run one `billed` probe `tests/billed/test_067_gate_zero.py::test_responses_api_accepts_user_item_beside_function_call_output` — chain two `responses.create` calls and put a user message item after a `function_call_output` in the second call's `input` (research V1). Record the real result in `specs/repo/features/067-realistic-message-handling/research.md`. **If it fails → plan fallback D4 (separate follow-up call); tell the human before continuing.**
- [ ] T005 [P] Inspect an existing real logged `mcp_call` response (or one billed run of an existing Morning-tool test) and record whether all server-side calls are in `response.output` on return and nothing is still running (research V2) in `research.md`
- [ ] T006 [P] Read `_run_post_turn_ledger_recognition` in `denidin.py` (and `LedgerEventRecognizer`) and record in `research.md` whether one reply covering several user messages is handled correctly (V6); if not, add a corrective task here before US1

### 2b — Queue safety (REQ-RMH-025/033/034/035/036)

- [ ] T007 [P] **Task A** Unit tests for `BoundedQueue` in `tests/unit/test_bounded_queue.py`: full queue raises `QueueLimitExceeded` and the item is dropped; every further put fails until room; `last_get_at`, `size`, high-water mark, dropped counter; ERROR log content (RED) — **await human approval**
- [ ] T008 **Task B** Implement `src/utils/bounded_queue.py` (`BoundedQueue` wrapping `queue.Queue(maxsize)`, `put_or_raise`, `get`, `get_nowait`, `QueueLimitExceeded`) until T007 is GREEN
- [ ] T009 [P] **Task A** Unit tests for `QueueMonitor` in `tests/unit/test_queue_monitor_service.py`: WARNING at warning size; WARNING when `size>0` and no `get` for the stall seconds; rate-limited repeats; periodic INFO depths when non-empty (RED) — **await human approval**
- [ ] T010 **Task B** Implement `src/services/queue_monitor_service.py` (scheduler job in the style of `reminder_delivery_service.py`; reads registered queues) and add boolean report-only fields `queues_within_limits` / `queues_not_stalled` via `build_health_info_fns` in `src/services/health_server.py` (its fields are pass/fail strings); numeric depths/limits/dropped/last-taken are INFO log lines
- [ ] T011 [P] **Task A** Unit tests for `ThreadSupervisor` in `tests/unit/test_thread_supervisor.py`: a dead thread is logged CRITICAL and restarted; the in-flight item's future is failed, not left hanging; more than N deaths in the window makes the health info report non-ok; a per-item exception never ends a loop (RED) — **await human approval**
- [ ] T012 **Task B** Implement `src/services/thread_supervisor.py` and add a `threads_alive` check to `build_health_check_fns` in `src/services/health_server.py` (flips `status`) so the existing prober restarts the container on repeated deaths

### 2c — `SessionManager` as an actor (REQ-RMH-029)

- [ ] T013 **Task A** Unit tests in `tests/unit/test_session_manager_actor.py`: every public method still returns what it returned before (parametrised over the full public surface: `get_session`, `set_active_capabilities`, `set_active_flows`, `set_approval_message_id`, `add_message`, `add_message_with_tokens`, `get_conversation_history`, `get_conversation_history_for_session`, `load_message`, `append_ledger_event_ids`, `get_rolling_window`, `update_message`, `has_whatsapp_id_message`, `get_messages_for_local_date`, `known_chats`, `archive_aged_and_backstopped_messages`, `count_tokens`, `calculate_session_tokens`, `get_session_token_count`); calls execute one at a time on one thread; an exception in the actor thread reaches the caller; a call that times out raises loudly; `close()` stops the thread; a full queue raises `QueueLimitExceeded` (RED) — **await human approval**
- [ ] T014 **Task A** Concurrency integration test `tests/integration/test_session_manager_concurrency.py`: two threads hammer `add_message` and `set_approval_message_id`/`set_active_capabilities` on one chat — assert no lost update, no duplicate `order_num`, no half-read `session.json` (RED against the current class, GREEN after T016) — **await human approval**
- [ ] T015 **Task B** Move the current `SessionManager` body to `src/managers/session_store.py` as `SessionStore` (behavior unchanged, single-thread-only; internal calls stay direct)
- [ ] T016 **Task B** Rewrite `src/managers/session_manager.py` as the actor facade: same constructor `SessionManager(denidin)` and public signatures, explicit forwarding methods (no `__getattr__`), one `BoundedQueue` of `(operation, args, kwargs, Future)`, one daemon thread, bounded wait, slow-operation WARNING, `close()`; register its queue with the monitor and its thread with the supervisor
- [ ] T017 Route every other direct session-file reader/writer through the facade: `src/managers/message_integrity.py` (reads `session.json` directly → use `get_session`), and audit `src/services/daily_summary_roll_service.py`, `src/services/capability_reset_service.py`, `player/`, backfill/migration scripts under `scripts/`; list findings in `research.md`. (`apps/webapp/backend` is a separate read-only process, out of scope.)
- [ ] T018 [P] Make sure every place that constructs `SessionManager` (`denidin.py:554`, tests' fixtures in `conftest.py`, `BackfillDeniDin`, `WebappDeniDin`) starts/stops the thread cleanly (`close()` in `DeniDin.shutdown`, fixtures' teardown)
- [ ] T019 Run the full unit + integration suite through `scripts/run_unit_integration_tests.sh` and fix regressions caused by T015–T018 only (stop and report at the first failure)

**Checkpoint**: sessions are safe to use from several threads; every queue is bounded, warned on and visible; threads are supervised.

---

## Phase 3: User Story 1 — Additive burst is understood as one request (P1) 🎯 MVP

**Goal**: several quick messages are stored individually at once, and the model gets the later ones at its next hand-back.
**Independent test**: feed three webhook bodies for one chat while a fake model client is mid-way through a tool-call round; the follow-up `responses.create` input contains the `function_call_output` **and** the other two messages, timestamped; history holds three user messages in order.

- [ ] T020 [P] [US1] **Task A** Unit tests `tests/unit/intake/test_intake_coordinator.py`: `submit`/`drain_attachable` order; text types attachable, taps/edited/deleted/contactsArray/blocked sender deferred; media parked in the backlog; per-chat isolation; a full chat queue or `arrival` raises `QueueLimitExceeded` (RED) — **await human approval**
- [ ] T021 [P] [US1] **Task A** Unit tests `tests/unit/intake/test_denidin_dispatcher.py`: calls only the injected `dispatch(type, notification)`; sets the pre-stored message before dispatch; an exception is logged, sleeps 5 s, loop continues; never exits on an item error (RED) — **await human approval**
- [ ] T022 [P] [US1] **Task A** Unit tests `tests/unit/test_pending_messages.py`: item text format with timestamp and "before"/"after" the model's last output; group `[sender]` prefix; media note line; empty list → no items (RED) — **await human approval**
- [ ] T023 [US1] **Task A** Integration test `tests/integration/intake/test_producer_dispatcher_flow.py`: real webhook bodies through the real producer (`DeniDinGreenAPIBot.run_forever` with a local fake Green API HTTP layer), coordinator, dispatcher and router: order preserved, message stored **before** `deleteNotification`, a failed store is **not** acknowledged, a full intake drops the message **without storing**, nothing lost, the player path (no coordinator) unchanged (RED) — **await human approval**
- [ ] T024 [US1] **Task A** Integration test `tests/integration/test_backbone_hand_back_merge.py`: an OpenAI-SDK-boundary fake (the only mock; CONSTITUTION §I/§V) returns a tool call then `send_to_user`; messages queued after the first call appear in the follow-up `input` after the `function_call_output`; none are attached on the `send_to_user` round; nothing attached when no coordinator (RED) — **await human approval**
- [ ] T025 [US1] **Task B** Implement `src/intake/intake_coordinator.py` (`IntakeCoordinator(denidin)`; per-chat `BoundedQueue`s + `arrival`; classification per D5) until T020 is GREEN
- [ ] T026 [US1] **Task B** Implement `src/intake/denidin_dispatcher.py` (`DeniDinDispatcher`; thread; supervised) until T021 is GREEN
- [ ] T027 [US1] **Task B** Implement `DeniDin.prestore(notification)` (same content rules each handler uses today), make `DeniDin.receive()` return the pre-stored message instead of storing twice, add `DeniDin.receive_pending(chat_id)` and the `denidin.intake` attribute — in `denidin.py`
- [ ] T028 [US1] **Task B** Implement the producer path in `DeniDinGreenAPIBot.run_forever` (`src/utils/green_api_bot.py`): room check → hook → build `Notification(body, bot.api, state_manager)` → `prestore` → `deleteNotification` → `intake.submit`; the `intake is None` path stays byte-identical
- [ ] T029 [US1] **Task B** Wire it up: `src/sources/green_api_source.py` and `denidin.py` `__main__`/`initialize_app` build `IntakeCoordinator(denidin)` and `DeniDinDispatcher(coordinator, dispatch)`, attach `bot.intake` and `denidin.intake`, start the dispatcher before the poll loop; register queues and threads with the monitor/supervisor; `shutdown` stops them
- [ ] T030 [US1] **Task B** Implement `src/backbone/pending_messages.py` (item formatting, REQ-RMH-007/008) until T022 is GREEN
- [ ] T031 [US1] **Task B** Hand-back merge in `src/backbone/backbone.py` `_run_resolution_loop`: after a non-final round, `denidin.intake` → `receive_pending(chat_id)` → append items after `outputs`; record `last_output_at`; re-fire the typing indicator when anything is attached; `send_to_user`/approval rounds attach nothing (REQ-RMH-013); until T023/T024 are GREEN
- [ ] T032 [US1] Run the unit + integration suites for `tests/unit/intake`, `tests/integration/intake`, `tests/integration/test_backbone_hand_back_merge.py` via the wrapper; report each result as it lands

**Checkpoint**: US1 works end to end; MVP.

## Phase 4: User Story 2 — A long burst (P1)

**Goal**: ten messages in a row, first handled at once, none lost, each with its timestamp.
**Independent test**: integration — ten bodies in quick succession; the first reaches the model at once; later ones are attached at successive hand-backs; ten stored messages in order.

- [ ] T033 [US2] **Task A** Integration test `tests/integration/intake/test_long_burst.py`: ten bodies for one chat while the fake model makes several rounds; first dispatched immediately (no debounce); every later message attached at some hand-back, in order, exactly once; messages arriving after the final `send_to_user` become the next handling, not dropped (RED or GREEN-already — report which) — **await human approval**
- [ ] T034 [US2] **Task B** Fix whatever T033 reveals (expected: little or nothing beyond US1)
- [ ] T035 [P] [US2] **Task A** Unit test `tests/unit/test_session_manager_rolling_window_timestamps.py`: opt-in timestamp prefix on user items (`[HH:MM:SS dd/mm]`, Israel local via stored timestamps), default output unchanged (legacy path byte-identical) (RED) — **await human approval**
- [ ] T036 [US2] **Task B** Add the opt-in timestamp parameter to `get_rolling_window`/`_render_history_item` in `src/managers/session_store.py` + facade, `AIManager.load_rolling_window` in `src/core/ai_manager.py`, and use it from the backbone's `_load_conversation_history` and first-round user content (REQ-RMH-007)

## Phase 5: User Story 3 — "Do X", then "stop" (P2)

**Goal**: a correction reaches the model at its next hand-back; an approval-gated write never runs without approval.
**Independent test**: integration — a proposed approval-gated write, then a "stop" message; no write call is made; the stop is in the model's next input.

- [ ] T037 [US3] **Task A** Integration test `tests/integration/test_stale_tap_guard_and_stop.py`: approval buttons stay live across unrelated messages (D14); cleared when answered (typed or tapped) and when superseded by a newer approval; a "stop" message does not execute anything (RED against current clearing at `backbone.py:501`) — **await human approval**
- [ ] T038 [US3] **Task B** D14 in `src/backbone/backbone.py` `handle_message` (rename later): stop clearing `Session.approval_message_id` on every new message; clear only when the incoming message answers it or a newer approval is sent (`record_sent_message_id`); matching rule in `resolve_button_tap` unchanged

## Phase 6: User Story 4 — Something was already done (P2)

**Goal**: results of side effects the model already caused are visible to it and reported truthfully, not repeated.

- [ ] T039 [US4] **Task A** Integration test `tests/integration/test_hand_back_keeps_tool_results.py`: after a hand-back that attaches messages, the model's own `mcp_call` results remain in the chain (`previous_response_id` retained, outputs not dropped) (RED/GREEN — report) — **await human approval**
- [ ] T040 [US4] **Task B** Fix only what T039 reveals; confirm the "already done" journal from the old design is not built anywhere (REQ-RMH-012)

## Phase 7: User Story 5 — Timeline and confusion (P2)

**Goal**: timestamps and before/after markers are visible; the model may ask when confused; it finishes a pending approval before the next request.

- [ ] T041 [US5] **Task A** Unit test `tests/unit/test_backbone_prompt_boundaries.py` asserting the backbone section and cross-references exist (RED) — **await human approval**
- [ ] T041b [US5] **Task B** Write the "Messages that arrive while you work" section in `config/prompts/backbone.md` (REQ-RMH-009/026/028: read timestamps and before/after, combine messages, ask when confusing, finish a pending approval before the next request, short replies answer the most recent pending question)
- [ ] T042 [P] [US5] **Task B** Add one-line cross-references in `config/prompts/capabilities/cap_invoicing_write.md`, `cap_reminders_write.md`, `cap_ledger_query.md`, `cap_approval_with_buttons.md`, `cap_send_to_user.md` (REQ-RMH-027)

## Phase 8: User Story 6 — A single image fits in (P2)

**Goal**: an image arriving mid-work is stored, noted to the model, then analyzed on its own right after; otherwise unchanged.

- [ ] T044 [US6] **Task A** Unit/integration tests `tests/integration/intake/test_media_fits_in.py`: media while idle → handled at once as today; media during work → stored, a note item attached at the next hand-back, parked in the backlog, dispatched after the current work, once; text arriving during media analysis attached at the next hand-back; two images in a row handled one after another; `analyze_media` untouched (RED) — **await human approval**
- [ ] T045 [US6] **Task B** Implement the media backlog dispatch in `src/intake/denidin_dispatcher.py`/`intake_coordinator.py` and make `_process_media_message` in `denidin.py` use the pre-stored message (no second `receive`)

## Phase 9: User Story 7 — Group chats, per chat (P3)

- [ ] T046 [US7] **Task A** Integration test `tests/integration/intake/test_group_stream.py`: two senders in one group — both messages stored individually, attached at a hand-back with `[sender]` prefixes; RBAC role resolution unchanged (`GroupMembershipResolver`) (RED/GREEN — report) — **await human approval**
- [ ] T047 [US7] **Task B** Fix only what T046 reveals

## Phase 10: User Story 8 — Approval execution is protected (P3)

- [ ] T048 [US8] **Task A** Integration test `tests/integration/test_approved_write_not_interrupted.py`: when the message is an affirmative reply to a pending approval (typed "כן" or button tap) hand-back draining is off; messages arriving meanwhile are handled afterwards; a "לא" still drains (RED) — **await human approval**
- [ ] T049 [US8] **Task B** Disable draining when `_turn_is_approved_write` (rename pending) in `src/backbone/backbone.py` (D7, REQ-RMH-014)

## Phase 11: User Story 9 — Guards stay put (P3)

- [ ] T050 [US9] **Task A** Integration test `tests/integration/test_guards_unchanged.py`: idle reset (`capability_reset_service`) still clears loaded capabilities after `capabilities_reset_minutes`; the model loads/unloads capabilities itself; button tap honored once after unrelated chatter, ignored on second tap (RED/GREEN — report) — **await human approval**
- [ ] T051 [US9] **Task B** Fix only what T050 reveals

---

## Phase 12: Acceptance (final — written AND run once, together, after every task above is GREEN)

Scenarios A1–A8 in `user-stories.md` are approved; this phase turns them into code and runs each once. Tests wipe seeded state before and after (autouse fixtures in the tier's `conftest.py`).

- [ ] T052 Write `tests/billed/test_realistic_message_handling_billed.py` with A1–A7 exactly as approved (A3/A4 use the real Morning sandbox via MCP; A6 uses a group fixture)
- [ ] T053 Write `tests/expensive/test_realistic_message_handling_expensive.py` with A8 exactly as approved
- [ ] T054 Run A1–A7 one at a time via `scripts/run_single_test.sh`, sounding off each result live; **stop at the first failure and report** (no fix-and-continue without fresh human input)
- [ ] T055 **[HUMAN GATE]** Request approval, then run A8 once via `scripts/run_single_test.sh`; read existing logs before any re-run
- [ ] T056 Re-run the full unit + integration suite and the Feature 043 player test (must pass without a coordinator)

## Phase 13: Polish & cross-cutting

- [ ] T057 [P] Update existing documentation to this model (REQ-RMH-031): `CLAUDE.md` (message flow, Architecture, test notes), `.github/ARCHITECTURE.md`, `.github/CONSTITUTION.md`/`METHODOLOGY.md` mentions of "turn" and the "no locks / queue" rule, `apps/denidin-app/README.md` and `docs/`
- [ ] T058 **Rename "turn"** (REQ-RMH-030; renaming inside approved tests is covered by the product owner's explicit 2026-10-12 instruction, names only, no assertion changes) in separate, reviewable steps, running the suite after each: (a) `handle_message`→`handle_message`, `mark_chat_busy`/`mark_chat_idle`→`mark_chat_busy`/`mark_chat_idle`, `_busy_chats`→`_busy_chats` in `src/` + `denidin.py`; (b) the backbone's `_turn_*` attributes → descriptive per-message names; (c) `turn_context` and other identifiers; (d) test names, fixtures and comments across `tests/` (111 files); (e) prompts under `config/prompts/` and `config/*.md`; (f) remaining docs. **Not** touched: `specs/done/`, `CHANGELOG.md`/`RELEASES.md`, logs, persisted data, git history. Final check: `grep -rniw turn` over code, tests, prompts and docs returns only the exclusions above
- [ ] T059 [P] Run lint and type checks (`python3 -m pylint src/ --fail-under=7.0 --rcfile=.pylintrc`, `python3 -m mypy src/ --config-file=mypy.ini`) and fix findings in the new modules
- [ ] T059b Guard test `tests/unit/test_067_no_flag_no_abort.py` (REQ-RMH-010/015/020): no 067 feature flag in `AppConfiguration`/`config.example.json`; no cancel/abort of a model call and no end-of-handling marker in the backbone/dispatcher modules — **human approval of the test**
- [ ] T060 Re-check the spec's requirement list (REQ-RMH-001…036) against the implementation; mark any gap; update `spec.md` Status and the "Required Files" line
- [ ] T061 Close out per the finish-up flow **only when the human says "haleluya"** (never on my own): spec symlink moves, PR, merge — no release, no deploy

---

## Requirement traceability

| Requirements | Tasks |
|---|---|
| RMH-001/002/003/004/005 | T020–T031 |
| RMH-006 | T046–T047 |
| RMH-007/008 | T022, T030, T035–T036 |
| RMH-009/026/027/028 | T041–T042 |
| RMH-010/015/020 | T059b |
| RMH-011/012 | T039–T040 |
| RMH-013/018 | T024, T031 |
| RMH-014 | T048–T049 |
| RMH-016 | T050–T051 |
| RMH-017 | T037–T038 |
| RMH-019/019a/019b | T044–T045 |
| RMH-021/022/023/024/032 | T021, T023, T026–T029, T056 |
| RMH-025/029 | T013–T019 |
| RMH-033/034/035/036 | T007–T012, T020–T021 |
| RMH-030 | T058 |
| RMH-031 | T057 |

Plan phases → task phases: 0 → 2a, 0b → 2c, 0c → 2b, 1 → 3, 2 → 3/4, 3 → 5/10/11, 4 → 8, 5 → 7, 5b → 13, 6 → 12.

## Dependencies & order

- Phase 1 → Phase 2 (2a, 2b, 2c can proceed in parallel after Phase 1; **2c blocks everything after it**; T004 blocks T031).
- US1 (Phase 3) needs Phase 2; **US2 needs US1** (shares the merge) plus T036; US3 needs US1 and T038; US4 needs US1; US5 needs US1; US6 needs US1; US7, US8 need US1; US9 needs T038.
- Phase 12 (Acceptance) needs every story phase GREEN; Phase 13's rename (T058) goes **last** so it never muddies behavior diffs.

## Parallel opportunities

T003, T004–T006, T007/T009/T011 (independent test files), T020–T022, T035, T042, T057, T059.

## Implementation strategy

1. MVP = Phases 1, 2 and 3 (US1). Stop and demonstrate after the Checkpoint.
2. Then US2 → US3 → US4/5/6 → US7/8/9, each independently tested and committed.
3. Acceptance A1–A8 once at the end; rename and docs last.

## Counts

61 tasks — Setup 3 · Foundational 16 (Gate Zero 3, queue safety 6, SessionManager actor 7) · US1 13 · US2 4 · US3 2 · US4 2 · US5 3 · US6 2 · US7 2 · US8 2 · US9 2 · Acceptance 5 · Polish 5.
