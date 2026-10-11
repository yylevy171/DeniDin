# Implementation Plan: Realistic Message Handling — Multiple Interfering Messages

**Branch**: `feature/067-realistic-message-handling` | **Date**: 2026-08-30 | **Spec**: `./spec.md`
**Input**: Feature specification from `specs/in-progress/067-realistic-message-handling/spec.md`

---

**IMPORTANT**: This plan complies with:
- **CONSTITUTION.md** (§I–III, §V, §XVII, §XVIII, NO UNVERIFIED THIRD-PARTY ASSUMPTIONS): No env
  vars (the one new setting is `config.feature_flags.realistic_message_handling`), Israel local
  time throughout (no new timestamps are introduced; any diagnostic time uses `now_local()`),
  feature-branch workflow, real-external-call integration tests, no monkey-patching (the
  producer/consumer split is a Template-Method refactor of `DeniDinGreenAPIBot.run_forever`
  plus a new dependency-injected `IntakeCoordinator` — no runtime patching of
  `whatsapp_chatbot_python`, `AIHandler`, or any manager), bounded-retry posture preserved on
  the existing external handshakes (this feature adds none).
- **METHODOLOGY.md** (§II, VI, VII, XXI-style constitution boundary): Integration Contracts
  written (`contracts/*.md`); the 2026-08-18 "TDD" redefinition is followed exactly (Tier 1
  unit/integration RED→GREEN per story during `speckit.implement`; Tier 2 `billed` acceptance
  described in plain language in `tasks.md` and written+run once at the end); a dedicated
  `runtime_constitution.md` boundary section is mandatory (REQ-RMH-026/027).

---

## Summary

When the feature flag is ON, DeniDin's live WhatsApp path stops being one strictly-serial loop.
A **background producer thread** continuously drains the Green API queue, fires the existing
read-receipt hook, **acknowledges each notification immediately**, and hands the raw body to a
new in-memory **`IntakeCoordinator`** (state keyed by `chat_id`). A **single consumer thread**
pulls coalesced work items and runs exactly today's `dispatch_notification` → handler →
`ai_handler.get_response` → `send_response` path, one turn at a time.

The coordinator's job is text coalescing + interruption: a text message that arrives while a
turn is in flight for the same chat raises that turn's one-way `cancelled` `threading.Event` and
is appended to the chat's burst buffer; the consumer, when the cancelled turn unwinds, folds the
whole buffer into **one merged turn** whose prompt is the concatenation of every burst message
and whose model call also receives an **"already done" journal** (via a new dedicated
`AIRequest.system_note` field, assembled into `instructions` *after* the per-call date line so
the constitution prefix stays byte-stable for prompt caching). `get_response` gains a
`cancel_check: Callable[[], bool]` parameter (default `lambda: False`) and checks it only at
**round boundaries** — before the first model call, at the top of each local-tool loop
iteration, before `_finalize_response`. On a positive check it stops: no local tool dispatched,
no further OpenAI call, no `PendingApproval`/`PendingLocalToolApproval` committed, reply never
sent; it returns an `AIResponse` with `cancelled=True` and a `side_effects_journal` built from
the server-side MCP calls already in the returned response plus any ledger event files already
written mid-turn.

Media messages break the burst but never discard or interrupt an in-flight text turn — they run
on the existing `_process_media_message` path unchanged. The "כן"/"לא" approval-**execution**
turn is non-interruptible (`cancel_check` is *not* threaded into `_resolve_pending_approval` /
`_call_openai_approval_api`). When the flag is OFF, `run_forever()` keeps its current single-loop
body verbatim, no coordinator is constructed, and behaviour is byte-for-byte identical to today.

## Technical Context

**Language/Version**: Python 3.9+ (existing project floor, `apps/denidin-app`)
**Primary Dependencies (new)**: none. `threading` (stdlib) `Thread` + `Event` only — no `Lock`,
`RLock`, `Semaphore`, or `queue.Queue` (REQ-RMH-025; see `research.md` for the lock-free design
and the accepted residual risks). `collections.deque` (stdlib) is used as the consumer's work
handoff — a `deque` with `append`/`popleft` is atomic under CPython's GIL for single-producer/
single-consumer use, which is the exact topology here; this is documented, not assumed
(`research.md`).
**Storage**: none. All coordinator state (`pending_text`, `active_turn`, `carryover`) is
in-memory, per `chat_id`, non-persistent, rebuilt empty on restart — same justification as
`GroupMembershipResolver._cache` and `RecentNotificationDeduper`.
**Testing**: `tests/unit/` covers the `IntakeCoordinator` state machine in isolation and the
`get_response` cancellation branch (round-boundary checks, journal assembly, no side effects on
cancel). `tests/integration/` drives `initialize_app` with a fake message source feeding a
scripted burst and a deliberately-slow fake OpenAI client, asserting the merged-reply and
flag-OFF behaviours end to end through the real coordinator + real `dispatch_notification` +
real handlers. `tests/billed/` covers the real-OpenAI acceptance scenarios (US1/US2/US3). No
`tests/expensive/` — this feature is text-only.
**Target Platform**: no container/runtime change — no `requirements.txt` change; existing
rebuild-on-merge process applies.
**Constraints**: no debounce window (process immediately); interrupt allowed at any round
boundary until `send_response` succeeds; only the last burst message is replied to; per-chat
scope including groups; single-threaded per chat (REQ-RMH-023); player path stays synchronous
(REQ-RMH-022); flag read once at process start (REQ-RMH-021).
**Scale/Scope**: one new class (`IntakeCoordinator`); `DeniDinGreenAPIBot.run_forever` refactored
into `_produce_forever` + `_consume_forever` (flag-ON path only); `GreenAPIMessageSource.start`
threads the flag/coordinator through; `denidin.py` `_process_conversational_message` accepts a
merged work item + `cancel_check` and threads both into `get_response`; `ai_handler.py` gains the
`cancel_check` parameter, round-boundary checks, the cancelled-return branch, and journal
assembly; `AIRequest` gains `system_note`, `AIResponse` gains `cancelled` + `side_effects_journal`;
`config/runtime_constitution.md` gains one new section + three cross-references.

## Constitution Check

*GATE: Must pass before Phase 0 research is closed. Re-checked after Phase 1 design (this
document) — see "Post-design re-check" at the end.*

- ✅ **§I No env vars**: the only new setting is `config.feature_flags.realistic_message_handling`,
  read via `AppConfiguration` and passed by dependency injection. `config.example.json` and
  `config.test.json` gain a `feature_flags` block (they currently have none); `config.dev.json`/
  `.prod.json`/`.player_prod.json` already have one and gain the new key (default `false`;
  `config.dev.json` may set `true` for manual verification, as a local uncommitted edit — config
  is code, so the committed default is `false` everywhere).
- ✅ **§II Israel local time**: no new persisted timestamps. Any diagnostic/log time uses
  `now_local()` from `utils/time_utils.py`. The `RecentNotificationDeduper` TTL and the worker's
  `time.sleep(5.0)` on exception are durations, not wall-clock timestamps — unchanged.
- ✅ **§III Git workflow**: on `feature/067-realistic-message-handling`, off `master`.
- ✅ **§V no mocking of internal components**: `tests/integration/` exercises the real
  `IntakeCoordinator`, real `dispatch_notification`, real handlers, real `AIHandler` — only the
  message source (a fake that feeds scripted notifications) and the OpenAI client (a fake slow
  client) are substituted, both third-party network boundaries, both already the established
  pattern for this codebase's source-level integration tests (Feature 043). `tests/billed/`
  makes real OpenAI calls. No `unittest.mock` in `tests/integration/`.
- ✅ **§XVII No monkey-patching**: `run_forever` is overridden in `DeniDinGreenAPIBot` already
  (Template Method over the upstream library); this feature extends that same subclass with
  `_produce_forever`/`_consume_forever` and composes in a new injected `IntakeCoordinator`. No
  attribute injection onto library objects, no runtime method replacement.
- ✅ **§XVIII bounded-retry external handshakes**: this feature adds no new external handshake.
  Ack-immediately (`deleteNotification` moved ahead of the turn) is a *reordering* of an existing
  call, not a new handshake; its failure mode and the crash-window it introduces are analysed in
  `research.md` and accepted as residual risk per the clarify decision (REQ-RMH-021a).
- ✅ **NO UNVERIFIED THIRD-PARTY ASSUMPTIONS**: `research.md` lists the third-party behaviours this
  design leans on and their verification status — chiefly (a) that a server-side MCP tool call
  that OpenAI already executed is fully represented in the returned `response.output` (so nothing
  is "in flight" server-side once `responses.create` returns) and (b) Green API's behaviour when a
  notification is *not* `deleteNotification`-ed (redelivery timing). Any item not already
  confirmed by a real call in this codebase's history is marked **OPEN** and gated to a real check
  before the dependent code is considered done.
- **Explicit deviation, not a violation** — `threading` primitives: the design uses
  `threading.Thread` + `threading.Event` + `collections.deque` and *deliberately avoids*
  `threading.Lock`/`RLock`/`Semaphore`/`queue.Queue` per the user's explicit standing instruction
  (spec Clarifications; memory `feedback_tdd_gate_only_billed_no_locks`). The residual races this
  leaves (a burst message landing in the exact instant a turn transitions from "in flight" to
  "reply sent"; producer appending to a `deque`/list the consumer is draining) are enumerated in
  `research.md` with their accepted outcomes — matching the precedent set by
  `send_proactive_message`'s documented shared-`requests.Session` race (explicit user decision
  2026-08-16).
- **Explicit deviation, not a violation** — feature flag: this feature *does* ship behind
  `config.feature_flags`, honouring the CLAUDE.md convention; the OFF path is byte-for-byte the
  current code (REQ-RMH-021). No deviation here; noted only for completeness against Feature 054's
  precedent of the opposite choice.

## Integration Contracts

Per METHODOLOGY §VII (multi-component feature: `green_api_bot.py`, `green_api_source.py`,
`denidin.py`, `ai_handler.py`, two model classes all gain new responsibilities). Full contracts
in `contracts/`:

1. **`contracts/producer-consumer.md`** — the `run_forever` refactor into `_produce_forever`
   (daemon thread: poll → read-receipt hook → `deleteNotification` immediately → hand body to
   coordinator) + `_consume_forever` (blocking, main thread, so `KeyboardInterrupt` shutdown is
   unchanged); the `IntakeCoordinator` public API (`submit(raw_body)`, `next_work_item()`,
   `on_turn_finished(chat_id)`); the flag-OFF fast path; the worker's log-sleep-continue posture.
2. **`contracts/turn-cancellation.md`** — `get_response(..., cancel_check=lambda: False)`; the
   exact round-boundary check points in `get_response` and `_run_local_tool_dispatch_loop`; the
   cancelled-return `AIResponse` shape; what is and is not done on a positive check; the
   non-interruptibility of the approval-execution path (`cancel_check` NOT passed to
   `_resolve_pending_approval` / `_resolve_pending_local_tool_approval` /
   `_call_openai_approval_api`).
3. **`contracts/journal-delivery.md`** — the `AIRequest.system_note` field; how the journal is
   built from structured side-effect records (`mcp_calls` items + persisted ledger event ids);
   the assembly point in `ai_handler.py` (`instructions` = constitution + memories + `---` +
   date line + **then** `system_note`); the clear-on-reply lifecycle; the
   `runtime_constitution.md` section the model is instructed by.

## Project Structure

### Documentation (this feature)

```text
specs/in-progress/067-realistic-message-handling/
├── spec.md                # done — fully clarified 2026-08-30 (initial + speckit.clarify)
├── user-stories.md        # done — 6 prioritized stories, routing/dispatcher requirements
├── checklists/
│   └── requirements.md    # done — all boxes checked
├── plan.md                # this file
├── research.md            # this phase's output — ack-immediately crash-window, lock-free
│                          #   design + residual races, server-side-MCP-call detection,
│                          #   system_note prompt-cache rationale, OPEN third-party checks
├── data-model.md          # this phase's output — IntakeCoordinator in-memory state,
│                          #   new AIRequest/AIResponse fields, side-effect record shape
├── quickstart.md          # this phase's output — manual dev verification steps
├── contracts/
│   ├── producer-consumer.md      # this phase's output
│   ├── turn-cancellation.md      # this phase's output
│   └── journal-delivery.md       # this phase's output
└── tasks.md               # NOT yet run (/speckit.tasks)
```

### Source Code (repository root, single project — `apps/denidin-app/`)

```text
apps/denidin-app/
├── denidin.py                              # MODIFIED —
│                                            #   • __main__: read config.feature_flags
│                                            #     .realistic_message_handling once; pass it (and
│                                            #     the constructed coordinator, when ON) into
│                                            #     GreenAPIMessageSource.
│                                            #   • _process_conversational_message: accept a merged
│                                            #     work item (ordered notifications + combined text
│                                            #     + optional carryover journal) and a cancel_check;
│                                            #     persist each burst message as its own user entry;
│                                            #     thread cancel_check + system_note into
│                                            #     ai_handler.get_response; re-fire typing on a
│                                            #     merged turn; on cancelled result, persist the
│                                            #     user message(s), send nothing, stash journal.
│                                            #   • HANDLER_REGISTRY: UNCHANGED (still 8 types).
│                                            #   • dispatch_notification: UNCHANGED signature; the
│                                            #     coordinator sits upstream of it.
├── config/
│   ├── config.example.json                 # MODIFIED — add `feature_flags` block with
│   │                                        #   `realistic_message_handling: false`
│   ├── config.test.json                    # MODIFIED — add `feature_flags` block (false)
│   ├── config.dev.json / .prod.json        # MODIFIED — add the new key (false) to the existing
│   │   / .player_prod.json                  #   `feature_flags` block
├── src/
│   ├── models/
│   │   ├── message.py                      # MODIFIED — AIRequest gains `system_note: str = ""`;
│   │   │                                    #   AIResponse gains `cancelled: bool = False` and
│   │   │                                    #   `side_effects_journal: List[Dict] = field(
│   │   │                                    #   default_factory=list)`; AIResponse.__post_init__
│   │   │                                    #   must NOT raise for a cancelled (no-text) response.
│   │   └── config.py                       # MODIFIED (maybe) — `feature_flags` field already
│   │                                        #   exists as Dict[str,bool]; no code change needed,
│   │                                        #   but add a defensive `.get(...)` helper usage note.
│   ├── sources/
│   │   ├── green_api_source.py             # MODIFIED — GreenAPIMessageSource.__init__ gains
│   │   │                                    #   `realistic_message_handling: bool = False` and
│   │   │                                    #   `intake_coordinator=None`; start(dispatch) passes
│   │   │                                    #   them to the bot before run_forever(); player
│   │   │                                    #   source and the MessageSource contract UNCHANGED.
│   │   └── intake_coordinator.py           # NEW — the per-chat text-coalescing + interruption
│   │                                        #   state machine (see data-model.md / contracts/
│   │                                        #   producer-consumer.md). No AI/WhatsApp imports;
│   │                                        #   pure state + threading.Event + deque.
│   ├── utils/
│   │   └── green_api_bot.py                # MODIFIED — DeniDinGreenAPIBot: run_forever() keeps
│   │                                        #   its current body when the flag is OFF; when ON it
│   │                                        #   delegates to _produce_forever() (daemon Thread) +
│   │                                        #   _consume_forever() (blocking). New attrs
│   │                                        #   `realistic_message_handling` and
│   │                                        #   `intake_coordinator`, set by the source before
│   │                                        #   run_forever(). deleteNotification moved ahead of
│   │                                        #   the turn on the ON path.
│   └── handlers/
│       └── ai_handler.py                   # MODIFIED — get_response(..., cancel_check=lambda:
│                                            #   False); round-boundary checks (before initial
│                                            #   _call_openai_api, top of each _run_local_tool_
│                                            #   dispatch_loop iteration, before _finalize_
│                                            #   response); early cancelled-return building
│                                            #   AIResponse(cancelled=True, side_effects_journal=
│                                            #   [...]); journal built from response.output
│                                            #   mcp_call items + ledger event ids persisted this
│                                            #   turn; system_note assembled into instructions
│                                            #   AFTER the date line; approval-resolution paths
│                                            #   NOT given cancel_check.
└── tests/
    ├── unit/
    │   ├── test_intake_coordinator.py                 # NEW — the state machine in isolation
    │   ├── test_ai_handler_cancellation.py            # NEW — round-boundary checks, journal,
    │   │                                               #   no side effects on cancel
    │   └── test_message_models.py                     # MODIFIED (if it exists) / NEW — new field
    │                                                   #   defaults; cancelled AIResponse allowed
    ├── integration/
    │   ├── test_realistic_message_handling.py         # NEW — initialize_app + fake slow OpenAI +
    │   │                                               #   scripted burst; flag ON (one merged
    │   │                                               #   reply, N user entries) and OFF (three
    │   │                                               #   replies); IT-2 journal; IT-2b
    │   │                                               #   non-interruptible approval turn; IT-3
    │   │                                               #   media breaks burst; IT-4 reset
    │   ├── test_message_source.py                     # MODIFIED — add IT-5 assertion that
    │   │                                               #   PlayerExportSource.start(dispatch) is
    │   │                                               #   still one synchronous call per
    │   │                                               #   notification, in order (existing tests
    │   │                                               #   untouched)
    │   └── test_denidin_dispatch.py                   # UNCHANGED — TestHandlerRegistryCompleteness
    │                                                   #   must stay green with no edit (IT-6)
    └── billed/
        └── test_realistic_message_handling_billed.py  # NEW — see "Testing Strategy" (US1/US2/US3)
```

**Structure Decision**: Single project. The new `IntakeCoordinator` lands in `src/sources/`
next to `green_api_source.py` and `player_export_source.py` because it is strictly a live-source
concern (it never runs on the player path). The threading refactor stays inside the existing
`DeniDinGreenAPIBot` subclass in `src/utils/green_api_bot.py` — the class that already owns the
polling loop. No new top-level module.

## Phased Implementation Order

Ordered so the lowest-risk, most isolated pieces land and are proven first, and so the
flag-OFF equivalence is established before any ON-path behaviour is built.

1. **Phase 0 — Research**: close `research.md`'s OPEN third-party items — chiefly the
   server-side-MCP-call representation in a returned Responses API response (can be confirmed from
   existing `billed`/`expensive` test logs that already exercised a real MCP tool call, or a
   single fresh `billed` run) and Green API redelivery timing for an un-acked notification
   (already partly documented via `RecentNotificationDeduper`'s ~32s figure — confirm it still
   holds). Lock-free-design and crash-window analysis are written here too. Does not block
   Phases 1–2.
2. **Phase 1 — Model + config plumbing (flag OFF still the only behaviour)**: `AIRequest
   .system_note`, `AIResponse.cancelled` / `.side_effects_journal` + `__post_init__` relaxation;
   `feature_flags` block added to `config.example.json` / `config.test.json`, new key added to
   the rest; `get_response` gains the `cancel_check` parameter with a default that makes it a
   no-op. Full existing suite stays green — nothing observable changes.
3. **Phase 2 — `IntakeCoordinator`**: the per-chat state machine, fully unit-testable in
   isolation with no AI/WhatsApp/threading-of-real-work dependency (the tests drive `submit` /
   `next_work_item` / `on_turn_finished` directly and assert buffer/active-turn/carryover
   transitions and that the `cancelled` Event is set). Highest-value, lowest-risk — build and
   prove first.
4. **Phase 3 — `get_response` cancellation branch**: round-boundary `cancel_check` calls; the
   early cancelled-return; journal assembly from `response.output` mcp_call items + ledger ids
   persisted this turn; guarantee no `PendingApproval`/`PendingLocalToolApproval` is committed on
   a cancelled turn. Unit-tested against a fake OpenAI client. Approval-resolution paths left
   untouched (non-interruptible).
5. **Phase 4 — `system_note` assembly + `runtime_constitution.md` section**: wire `system_note`
   into `instructions` after the date line; write the new "Interrupted / Merged Turns" section
   and the three cross-references (REQ-RMH-026/027).
6. **Phase 5 — producer/consumer refactor in `DeniDinGreenAPIBot`**: `_produce_forever` /
   `_consume_forever`, ack-immediately on the ON path, `run_forever` branches on the flag. Wire
   the coordinator through `GreenAPIMessageSource.start` and `denidin.py __main__`.
7. **Phase 6 — `_process_conversational_message` merged-item handling**: accept the merged work
   item, persist each burst message, thread `cancel_check` + `system_note`, re-fire typing, stash
   the journal on a cancelled result, clear all per-chat state on a successful send / silent turn
   / error fallback.
8. **Phase 7 — Integration tests** (IT-1 … IT-6) against `initialize_app` + fake slow OpenAI.
9. **Phase 8 — Billed acceptance tests + `quickstart.md` manual verification** — written AND run
   once, together, after every Tier-1 task is green (per METHODOLOGY §VI).

## Testing Strategy

Per METHODOLOGY §VI (2026-08-18 "TDD" redefinition):

**Tier 1 — unit/integration (RED→GREEN per story, Task A frozen before Task B, immutable once
approved) — §VI.b.** Written incrementally during `speckit.implement`.

- **Unit — `test_intake_coordinator.py`**: no in-flight turn + text → single-message work item,
  `active_turn` marked; in-flight turn + text → `cancelled` Event set, message buffered; buffer
  present + no active turn → append; media / non-text / `interactiveButtonsResponse` → own work
  item, no merge, does NOT set `cancelled`; `on_turn_finished` clears buffer + active turn +
  carryover; carryover set by a cancelled result is delivered to the next merged item and cleared
  after the following `on_turn_finished`; group (per-chat) → a second sender's message merges the
  same `chat_id` turn.
- **Unit — `test_ai_handler_cancellation.py`**: `cancel_check` true before the initial call → no
  OpenAI call, `AIResponse(cancelled=True)`, empty journal; true between local-tool rounds → no
  further tool dispatch, no follow-up `responses.create`, journal contains the ledger event
  already persisted this turn; a completed `mcp_call` item in the returned response + `cancel_check`
  true → that call is in the journal; no `PendingApproval`/`PendingLocalToolApproval` exists for
  the chat after a cancelled turn; `system_note` present → `instructions` contains it after the
  date line and the constitution prefix bytes are unchanged.
- **Unit — models**: new field defaults; a `cancelled=True` `AIResponse` with no text does not
  raise.
- **Integration — `test_realistic_message_handling.py`** (real coordinator + real dispatch + real
  handlers, fake message source + fake slow OpenAI client):
  - IT-1: flag ON → one outbound send with all three messages, three user history entries, one
    assistant entry; flag OFF → three outbound sends in order, no coordinator constructed.
  - IT-2: fake first response carries a completed server-side MCP call + a proposed local ledger
    action; interfere before the local action runs → no ledger file for the discarded turn, no
    pending approval, merged request's `system_note` names the MCP document and sits after the
    date line, one final send.
  - IT-2b: burst during a "כן"-approval execution turn → approval turn completes and sends its
    own reply uninterrupted; burst then processed as one following turn.
  - IT-3: text, then media notification, then text, with a slow first response → media went
    through the media handler, the two texts coalesced into one reply, the text turn was not
    discarded.
  - IT-4: two messages separated by a completed send → two independent turns, no carryover.
- **Immutability**: `test_message_source.py` IT-5 (player contract unchanged);
  `test_denidin_dispatch.py::TestHandlerRegistryCompleteness` IT-6 (8 types, no edit).

**Tier 2 — billed acceptance ("TDD" under the new definition) — §VI, Acceptance phase.**
Recorded in `tasks.md` in plain user-experience language only during `speckit.tasks`; the test
code is written **and run, once, together**, as the final step of `speckit.implement` after all
Tier-1 is green. Run via `scripts/run_multiple_billed_tests.sh`, sounding off each result. No
`expensive` tier (text-only feature).

- `test_benign_additive_burst_gets_one_reply` (US1) — "קבע פגישה" / "עם דנה" / "מחר ב-3" faster
  than reply latency → exactly one reply reflecting all three.
- `test_flag_off_burst_gets_three_replies` (US2) — same burst, flag disabled → three replies in
  order.
- `test_create_then_retract_burst_is_truthful` (US3) — "צור קבלה ללקוח X על 500 שקל" then "בעצם
  תבטל" before the approval prompt returns → one final reply reflecting the retraction, no stale
  pending approval, and if the external system created the document server-side the reply names
  it.

**Manual / `quickstart.md`-only**: a real dev run (separate explicit approval to start dev)
sending a live 3-message burst; a live create-then-cancel burst; a post-reply fresh turn; a
mid-burst image.

## Complexity Tracking

No Constitution Check violations requiring justification. Two items recorded above as **explicit
deviations, not violations**: (1) the deliberate use of `threading.Event`/`deque` and avoidance
of `Lock`/`queue.Queue` per standing user instruction, with residual races enumerated and
accepted in `research.md`; (2) ack-immediately's crash-window, accepted per the clarify decision
(REQ-RMH-021a) and documented in `research.md`.

## Post-design re-check (after Phase 1)

Re-run after `data-model.md` + `contracts/` were written:

- §I/§II/§III/§V/§XVII/§XVIII — still ✅; the design added no env var, no timestamp, no mock of an
  internal component, no monkey-patch, no unbounded external handshake.
- The `deque`/`Event` lock-free handoff is the single concurrency mechanism; `research.md`
  enumerates every shared-state access and its accepted outcome. No `Lock` was needed for
  correctness given single-producer/single-consumer topology — confirmed, not assumed.
- The `HANDLER_REGISTRY` and player `MessageSource` contract are untouched — the coordinator is
  strictly upstream of `dispatch_notification` and strictly inside the live source.
- Prompt-cache prefix stability is preserved: `system_note` is appended *after* the per-call
  date line, which already breaks the cache prefix, so the constitution + memories portion is
  byte-identical to today.

**Command ends after Phase 2 planning.** Branch: `feature/067-realistic-message-handling`.
IMPL_PLAN: `specs/in-progress/067-realistic-message-handling/plan.md`. Generated artifacts:
`research.md`, `data-model.md`, `contracts/producer-consumer.md`,
`contracts/turn-cancellation.md`, `contracts/journal-delivery.md`, `quickstart.md`.
Next: `speckit.tasks`.
