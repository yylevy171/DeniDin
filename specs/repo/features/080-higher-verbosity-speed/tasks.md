# Tasks: Higher Verbosity, Active Feedback, and Latency Telemetry

**Input**: `plan.md`, `research.md`, `data-model.md`, `contracts/`, `user-stories.md` (Acceptance
Scenarios ✅ approved 2026-09-12)

## Phase 0: Setup
- T001 Add `feature_flags.verbosity_and_telemetry_080` (default `false`) to
  `AppConfiguration`/`config.example.json`/`config.test.json`.
- T002 [P] Create `apps/denidin-app/src/models/telemetry.py` — `RequestTelemetry` dataclass
  per `data-model.md`.
- T003 [P] Create `apps/denidin-app/src/managers/telemetry_manager.py` — `TelemetryBuilder` +
  `TelemetryManager` per `contracts/telemetry-recorder.md`.

## Phase 1: Foundational (blocks all user stories)
- T004 Unit tests for `TelemetryManager`/`TelemetryBuilder` (RED) — schema creation, `record()`
  write-once semantics, best-effort failure handling, field validation from `data-model.md`.
- T005 Implement `TelemetryManager`/`TelemetryBuilder` to pass T004 (GREEN). **Human approval
  gate before T005 per §VI.b (Task A/Task B pattern).**

## Phase 2: User Story 1 — The Patient Waiter (Keep-Alive) (P1)
- T006 [P] Unit tests for `start_typing_keepalive`/`stop_typing_keepalive`
  (`green_api_bot.py`) — job scheduled with immediate first tick, renewed every
  `interval_seconds`, cancelled on stop, capped at `max_duration_seconds`, `is_blocked` no-op,
  never raises (RED).
- T007 Implement `start_typing_keepalive`/`stop_typing_keepalive` on the existing
  `APScheduler` `BackgroundScheduler` per `contracts/keep-alive-renewal.md` (GREEN). **Human
  approval gate before T007.**
- T008 Wire the two call sites (`_process_conversational_message`, the shared media-message
  wrapper in `denidin.py`) to use the renewal functions instead of the single-shot
  `send_typing_indicator` when the feature flag is on; call `stop_typing_keepalive` at every
  outbound-send point (final reply, interim clarification, approval prompt) — mirrors feature
  048's Q4 "DeniDin's turn" semantics exactly.
- T009 **Unit test** (not integration — CLAUDE.md/CONSTITUTION forbid integration tests from
  setting feature flags, since they validate default production behavior with the flag off):
  construct `AIHandler`/the call-site wrapper directly with the flag forced on, mocking only
  the external Green API HTTP call, and confirm the renewal job starts at turn start and is
  cancelled at the turn's outbound send — no renewal calls fire after the turn ends.

## Phase 3: User Story 2 — AI-Driven Progress Updates (P1)
- T010 Add the "Proactive Progress Updates" section to `config/runtime_constitution.md` per
  `research.md` R4 — explicit scope (when to narrate / when NOT to), cross-references to
  existing tool-bearing sections per CLAUDE.md's constitution-boundaries rule, and a note that a
  progress update is a real outbound message subject to the same Group Etiquette judgment as
  any other reply.
- T011 Gate the constitution addition behind `feature_flags.verbosity_and_telemetry_080` (byte-
  identical prompt when off) — confirm via a unit test on system-prompt assembly.

## Phase 4: User Story 4 — Telemetry & Metrics Plumbing (P1)
- T012 Thread a `TelemetryBuilder` instance through `AIHandler.get_response()` and its call
  chain, constructed at webhook receipt (`denidin.py`) with `request_id`/`chat_id`/
  `timestamp_received`.
- T013 Instrument every `responses.create()` call site in `ai_handler.py` (7 as of this branch)
  with `record_llm_call()` (duration, input/output tokens from `response.usage`).
- T014 Instrument local function-tool dispatch and remote MCP tool-call result handling with
  `record_tool_call()` (name, duration, `is_morning_tool` flag for
  `morning_api_request_times_ms`).
- T015 Call `TelemetryBuilder.finalize()` + `TelemetryManager.record()` at the point the turn's
  outbound message is dispatched (or concludes with no reply) — best-effort, never raises into
  the request path.
- T016 Unit tests for the instrumentation wiring (RED before T012-T015, GREEN after) — call-count
  and duration accounting correctness using a fake/stub OpenAI client response shape (no real
  network call — unit tier).
- T017 **Unit test** (same feature-flag constraint as T009): with the flag forced on directly in
  the test's `AppConfiguration` construction, drive `AIHandler.get_response()` with a stubbed
  OpenAI client/tool responses and confirm exactly one `RequestTelemetry` row is produced with
  plausible field values.

## Phase 5: User Story 3 — Consolidated Final Delivery (P2, regression-only)
- T018 Confirm (via existing/extended unit test on `WhatsAppHandler.send_response()`) that
  nothing in T006-T017 introduces response chunking — single-message delivery unchanged.

## Phase 6: 🚨 Mandatory Cross-Cutting Sweep (per `user-stories.md`'s Cross-Cutting Risk, operator-mandated)
- T019 Audit every `billed`/`expensive` test/helper in `apps/denidin-app/tests/` (and
  `apps/morning-mcp-app/tests/` if applicable) that drives a multi-tool-call AI turn and assumes
  a single deterministic reply per turn (e.g. `_send_image`/`_drive_detour_until_captured` and
  siblings). Produce a written inventory (which tests, which helper, what assumption).
- T020 Adapt each identified helper/assertion to correctly distinguish an interim progress
  update from the real final answer (content/completion-signal based, not "whatever came back
  first"), gated so this logic is a no-op when `feature_flags.verbosity_and_telemetry_080` is
  off (existing test behavior must stay unchanged until the flag is actually on in test config).
  **Must complete before Phase 7's flag-on acceptance run is trusted.**

## Phase 7: Acceptance (§VI.a — approved 2026-09-12, code only, no run yet)
- T021 Add progress-update-sent + telemetry-row-written assertions to the 5 approved `billed`
  tests and 2 approved `expensive` tests listed in `user-stories.md`.
- T022 🛑 STOP — report back to operator before running any `billed`/`expensive` test (this
  document's own instruction, reiterated from the standing CLAUDE.md/METHODOLOGY approval
  gates).

**Phase 6/7 status (2026-09-13, explicit operator decision): DEFERRED, not executed.**
`verbosity_and_telemetry_080` was removed entirely later the same day (the feature became
always-on, unconditional — see the flag-removal commit) — the flag-off/flag-on gating T020
describes no longer exists, so T020 as written is moot. Rather than adapt this phase's plan to
match, real-WhatsApp manual live testing (repeated rounds against the dev environment, operator-
driven) was used instead to verify the feature end-to-end, and surfaced/fixed several real bugs
this phase's own written-inventory approach would not have caught on its own (a local-tool
dispatch-loop bug where a response carrying more than one pending tool call type failed
outright; a typing-indicator renewal gap; a rogue-language leak). The operator confirmed live
behavior as satisfactory and closed the feature on that basis. T019-T022 are left unchecked
above as an accurate historical record of what was planned but not done, not retroactively
marked complete.

## Dependencies
- T001-T003 before everything.
- T004→T005 (Task A/B gate) before Phase 2/3/4 use `TelemetryManager`.
- T006→T007→T008→T009 (Phase 2) independent of Phase 3.
- T010-T011 (Phase 3) independent of Phase 2/4.
- T012-T017 (Phase 4) depends on T005 (telemetry manager exists).
- T019-T020 (Phase 6) depends on Phase 2-4 being code-complete (needs to know the real
  interim-message shape to adapt against) but is otherwise independent of Phase 7.
- T021 depends on Phase 6 complete. T022 is the hard stop.
