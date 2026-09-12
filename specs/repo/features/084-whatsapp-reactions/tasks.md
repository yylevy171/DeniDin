# Tasks: WhatsApp Reactions

**Input**: `plan.md`, `research.md`, `data-model.md`, `contracts/*.md`, `spec.md`, `user-stories.md`
**Branch**: `feature/084-whatsapp-reactions-impl`

Per METHODOLOGY.md §VI's redefinition: unit/integration tasks below keep the full RED→GREEN /
human-approval / test-immutable discipline. The reaction-judgment-tuning phase (Phase 6) is NOT a
fixed acceptance-test pass — see `contracts/reaction-judgment-tuning.md` — its "tasks" are the
harness plumbing (hard-assertion-tested) plus the AI-run tuning loop itself (not a test).

---

## Phase 1 — `send_reaction()` helper (`src/utils/green_api_bot.py`)

- **T001 [test]**: Add unit tests to `tests/unit/test_green_api_bot.py` for a not-yet-existing
  `send_reaction(bot, chat_id, id_message, reaction) -> bool`, stubbing `bot.api.request`:
  - correct payload shape (`POST`, `{{host}}/waInstance{{idInstance}}/sendReaction/{{apiTokenInstance}}`,
    body `{"chatId", "idMessage", "reaction"}`) and return `True` on a 200-shaped response.
  - a 5xx/timeout response is retried exactly once after 1s, then returns `False` if still failing.
  - a 4xx response is never retried, returns `False` immediately.
  - any raised exception from `bot.api.request` is caught, logged at WARNING, function returns
    `False` — never raises.
  - **Human approval required before implementation (T002) begins** — tests written, run RED,
    reported.
- **T002 [impl]**: Implement `send_reaction()` in `green_api_bot.py` per
  `contracts/green-api-reaction-client.md`, next to `mark_message_read`/`send_proactive_message`.
  Make T001 GREEN. No other file changes.

## Phase 2 — Data model additions (`src/managers/session_manager.py`, `src/models/message.py`)

- **T003 [test]**: Unit tests (`tests/unit/test_session_manager.py`, `tests/unit/test_message.py`)
  for the new optional fields:
  - `Message.whatsapp_id_message: Optional[str] = None` — round-trips through
    `SessionManager.add_message()`'s new `whatsapp_id_message` parameter and through
    save/load (tolerant load: absent in old JSON → `None`, no crash).
  - `Session.active_document_message_id: Optional[str] = None` — round-trips through
    `Session` save/load the same way.
  - `WhatsAppMessage.whatsapp_id_message` populated from `event.get('idMessage')` in
    `from_notification()` (distinct from the existing internal `message_id` UUID field, which is
    untouched — Feature 033's identity constraint on `message_id` is preserved).
  - **Human approval required before implementation (T004) begins.**
- **T004 [impl]**:
  - `src/models/message.py`: add `whatsapp_id_message: Optional[str] = None` to `WhatsAppMessage`,
    populate it in `from_notification()` from `event.get('idMessage')`.
  - `src/managers/session_manager.py`: add `whatsapp_id_message: Optional[str] = None` to
    `Message`; add `active_document_message_id: Optional[str] = None` to `Session`; extend
    `add_message()` with a `whatsapp_id_message: Optional[str] = None` parameter, threaded into the
    `Message(...)` constructor call; thread save/load for both new fields.
  - `src/handlers/ai_handler.py`: at the existing message-persistence call sites (`add_message`/
    `add_message_with_tokens`), pass `whatsapp_id_message=request.original_message.whatsapp_id_message`
    when `original_message` is present.
  - Make T003 GREEN.

## Phase 3 — Fast-path hook (`apps/denidin-app/denidin.py`)

- **T005 [test]**:
  - `tests/unit/test_fast_path_reaction_heuristic.py` (new): classification logic in isolation
    (media pool for `imageMessage`/`documentMessage`, action-verb pool for
    `textMessage`/`extendedTextMessage` matching the curated keyword list, "neither" for
    everything else including ambient chatter) — `send_reaction` stubbed, no network, no LLM call.
  - `tests/integration/test_reaction_dispatch_routing.py` (new): a real notification dispatched
    through `bot.router` — an actionable message (media or action-verb match) reaches a
    Green-API-boundary-stubbed `send_reaction`; an ambient/non-matching message (group or 1:1)
    produces **zero** calls. Confirms hook placement (after dedup, before `HANDLER_REGISTRY.get`)
    does not alter existing dispatch behavior for any of the 9 registered types
    (`test_denidin_dispatch.py` stays green, untouched).
  - **Human approval required before implementation (T006) begins.**
- **T006 [impl]**: Implement `_dispatch_fast_path_reaction(type_message, notification)` in
  `denidin.py` per `contracts/fast-path-reaction-heuristic.md` (classification IS the gate, no
  separate addressed-to-bot predicate — see `contracts/group-discretion-gating.md`'s Correction);
  call it inside `dispatch_notification()` right before `handler(notification)`, after the
  `HANDLER_REGISTRY.get(...)` lookup line, never touching `HANDLER_REGISTRY` itself. Never raises;
  catches/logs internally at WARNING. Make T005 GREEN.

## Phase 4 — `react_to_message` AI tool (`src/handlers/ai_handler.py`)

- **T007 [test]**: Unit tests for the `message_id` fallback-chain resolution (explicit arg →
  `Session.active_document_message_id` → current turn's `whatsapp_id_message`) in isolation,
  against a stubbed `send_reaction` — covers all three fallback levels winning in the documented
  order. **Human approval required before implementation (T008) begins.**
- **T008 [impl]**:
  - Add `REACT_TO_MESSAGE_TOOL` schema constant per `contracts/react-to-message-tool-schema.md`.
  - Attach it unconditionally to every role's tool list (no RBAC gate).
  - Add `_handle_react_to_message()` (mirrors `_handle_query_ledger_events`'s multi-call pattern
    via `extract_all_function_calls`, since a turn could call this more than once) + its
    `_call_openai_react_to_message_followup_api()` companion, reporting
    `{"status": "ok"|"failed"}` per call.
  - Wire both into `_run_local_tool_dispatch_loop()` alongside the existing immediate-dispatch
    tools (`list_reminders`, `query_ledger_events`).
  - Make T007 GREEN.

## Phase 5 — `runtime_constitution.md`

- **T009 [impl, no test-gate — config content, not code]**: Add the `## Reaction Management`
  section (classics table + when-applies/when-does-NOT-apply/ambiguity-resolution structure) per
  `contracts/group-discretion-gating.md`'s draft content, plus the required one-line
  cross-reference edits to `## Reminder Management`, `## Ledger Event Querying`, and the Morning
  MCP sections (per the CLAUDE.md "every new tool-bearing feature needs explicit constitution
  boundaries, cross-referenced everywhere" rule). **Flagged for explicit human review** once
  drafted, same review attention Feature 054's reminder section received.

## Phase 6 — Reaction judgment tuning harness (plumbing only — see `contracts/reaction-judgment-tuning.md`)

- **T010 [test+impl] — DONE**: `tests/billed/reaction_judgment_pool.py` +
  `tests/expensive/reaction_judgment_pool.py` — the scenario-pool data + the capture mechanism
  (`tests/_reaction_capture.py`: stubs `send_reaction` at the Green API boundary, writes one JSON
  judgment-log entry per scenario run). Hard assertions ONLY on: zero `send_reaction` calls for
  the two ambient-group scenarios, and flip-targeting correctness (second call's `id_message`
  matches the first's) for the flip scenario — implemented as real billed tests
  (`tests/billed/test_reaction_judgment_tuning.py`, run against the actual `AIHandler` pipeline)
  and confirmed green. No assertion anywhere on emoji choice itself; the flip test explicitly
  skips (never fails) when the model's own judgment doesn't produce a flip that round.
- **T011 [test+impl] — DONE**: `scripts/run_reaction_tuning.sh` + `logs/reaction_tuning/rotation_state.tsv`
  rotation logic (`tests/_reaction_tuning_rotation.py`), and its own unit tests
  (`tests/unit/test_reaction_tuning_harness.py` — least-recently-run selection,
  `--billed-only`/`--include-expensive N`/`--subset-size` flags, judgment-log write shape) — 20
  tests, all green. Smoke-verified end-to-end: two successive rounds correctly rotate through
  never-run-first scenarios and advance `rotation_state.tsv`.
- **T012 [AI-run loop, not a test] — RUN, not declared stable**: Ran the iterative tuning loop
  per `contracts/reaction-judgment-tuning.md`, in two later sessions (2026-09-12), session-capped
  each time by explicit instruction rather than run to the contract's own stopping condition:
  - **5 billed rounds** — all 12 billed pool scenarios exercised at least once. Found and fixed
    one real constitution gap (the model was embedding a reaction emoji inside its reply text
    instead of calling `react_to_message`); confirmed the fix worked and caused no regression.
    Documented in `logs/reaction_tuning/tuning_log.md`.
  - **2×3 expensive rounds** (fresh human approval each time) — found a real document-flip
    wording gap (❓ missing as a flip target), then, investigating why the fix looked ineffective,
    found and fixed a real bug in the tuning driver itself (`--followup`/mimeType), and finally
    confirmed the wording fix genuinely works once a document scenario has a real follow-up turn
    (`react_to_message` is only ever attached there — a document upload's own first reply is
    composed by deterministic code, `MediaHandler._compose_user_message`, with no tool access at
    all). Documented in `logs/reaction_tuning/tuning_log_expensive.md`.
  - **Not reached**: the contract's own stopping condition ("a couple of consecutive rounds
    across different rotated subsets, including expensive, with no real misses") — every round
    run so far found or chased something real. Held-out for a future round: a scenario giving
    `react_flip_earlier_message` a genuine 3rd turn (it's one turn short of ever completing a
    flip), and continued rotation through the remaining never-repeated scenarios.

## Phase 7 — `quickstart.md` manual verification

- **T013**: The two items the tuning harness deliberately doesn't cover — the <1000ms fast-path
  timing check against a real dev environment, and a real confirmation of the
  deleted-message-before-flip no-op. Deferred alongside Phase 6 (needs a running dev environment —
  out of scope for this session's checkpoint).

---

## Dependency order

T001→T002 → T003→T004 → T005→T006 → T007→T008 (depends on T002/T004's real fields existing) →
T009 (independent, can run anytime after T008 for accurate cross-references) → T010→T011→T012 →
T013.

## Checkpoint (this session)

Per explicit user instruction: implement and green Phases 1-5 (T001-T009), report back, and STOP
before Phase 6 (T010-T012, the reaction-judgment-tuning harness and loop) and Phase 7 (T013).

**Superseded (2026-09-12)**: per a later explicit user instruction ("continue until all is
implemented and unit and integration tests pass"), Phase 6's harness plumbing (T010, T011) was
also implemented and is green — see above. T012 (the AI-run tuning loop itself — not a test) and
Phase 7's T013 (manual quickstart verification, needs a live dev environment) remain deliberately
out of scope: neither is a "unit and integration test," and both need a separate, explicit human
decision to start (T012's iterative judgment review; T013's environment start, per CLAUDE.md).
