# Implementation Plan: Reminders — Functionality and Management

**Branch**: `feature/054-reminders-functionality-mgmt` | **Date**: 2026-08-16 | **Spec**: `./spec.md`
**Input**: Feature specification from `specs/in-progress/054-reminders-functionality-mgmt/spec.md`

---

**IMPORTANT**: This plan complies with:
- **CONSTITUTION.md** (§I-III, §V, §XVII, NO UNVERIFIED THIRD-PARTY ASSUMPTIONS): No env vars
  (all new config lives in `config.*.json`'s new `reminders` section), Israel local time
  throughout (every stored datetime round-tripped through `time_utils`), feature branch workflow,
  real-external-call integration tests, no monkey-patching (new managers/services via dependency
  injection, matching this codebase's existing constructor-injection style).
- **METHODOLOGY.md** (§II, IV, VII): Integration Contracts written (`contracts/*.md`).

---

## Summary

Godfather/admin users can create, list, modify, and delete reminders through natural WhatsApp
conversation, gated by the existing approval-gate UX (Feature 022/047) and delivered as proactive
WhatsApp messages by a single shared background mechanism. There is exactly one reminder list
(owned by "the godfather"); ADMIN manages it too, via this app's existing blanket-access pattern,
not a new permission concept. Recurrence uses real iCalendar (RFC5545) data — `RRULE`/`DTSTART`
on a master record, single-occurrence edits/cancellations as real `RECURRENCE-ID`-keyed override
records — resolved by the `icalendar`/`recurring_ical_events` libraries rather than hand-rolled
date math. Delivery always targets the godfather's own 1:1 chat with DeniDin, regardless of what
chat the reminder was created/modified from. No feature flag — RBAC is the only gate, by explicit
user decision.

## Technical Context

**Language/Version**: Python 3.9+ (existing project floor, `apps/denidin-app`)
**Primary Dependencies (new)**:
- `icalendar` — RFC5545 VEVENT (de)serialization.
- `recurring_ical_events` — resolves concrete due occurrences from a VEVENT + RECURRENCE-ID
  overrides, for a given time window.
- `apscheduler` — `BackgroundScheduler` + one `CronTrigger(minute='*/5')` job for wall-clock-
  aligned sweep timing.
- `sqlite3` (stdlib, no install needed) — reminder storage.
**Storage**: SQLite (`{data_root}/reminders/reminders.db`) — `reminders` (master VEVENT fields),
`reminder_exceptions` (RECURRENCE-ID-keyed override VEVENTs), `fired_occurrences` (append-only
delivery history). Full schema: `data-model.md`.
**Testing**: `tests/unit/` covers `ReminderManager` (recurrence resolution via
`icalendar`/`recurring_ical_events`, cap enforcement, rounding, single-occurrence vs. whole-series
semantics) and the new `PendingLocalToolApprovalManager`/`AIHandler` dispatch logic in isolation.
`tests/billed/` covers real conversational create/modify/delete + approval flows (see "Testing
strategy" below for the concrete list). No `tests/expensive/` — nothing here calls vision.
**Target Platform**: N/A beyond the code change itself — no container/runtime change beyond a
`requirements.txt` update (existing rebuild-on-merge process applies).
**Constraints**: reminder times rounded to the nearest 5 minutes (ties round up); max 20 active
reminders for the one list; no yearly recurrence cadence; delivery always to the godfather's own
1:1 chat, never configurable per-reminder.
**Scale/Scope**: three new local function tools (`create_reminder`/`modify_reminder`/
`delete_reminder`) plus one read-only tool (`list_reminders`); one new manager
(`ReminderManager`); one new parallel approval manager (`PendingLocalToolApprovalManager`); one
new background service (`reminder_delivery_service.py`); `ai_handler.py`/`denidin.py` extended,
not restructured.

## Constitution Check

*GATE: Must pass before Phase 0 research is closed. Re-checked after Phase 1 design (this
document).*

- ✅ **§I No env vars**: all new settings (`max_active_reminders`, sweep cadence being fixed at 5
  minutes rather than configurable) live in `config.*.json`'s new `reminders` section, no env
  vars.
- ✅ **§II Israel local time**: every stored datetime (`DTSTART`, `RECURRENCE-ID`, override
  datetimes, `fired_occurrences.delivered_at`) is round-tripped through `time_utils` at the
  `ReminderManager` boundary — see `research.md`'s open sanity-check items for the
  `icalendar`/`recurring_ical_events` tz-preservation verification required before this is
  considered closed.
- ✅ **§III Git workflow**: on `feature/054-reminders-functionality-mgmt`, off `master`.
- ✅ **§V no mocking**: `tests/integration/` exercises real router dispatch (a real
  `textMessage`-shaped notification through `bot.router`) and real internal objects throughout;
  `tests/billed/` makes real OpenAI calls; the one third-party *service* dependency this feature
  adds (the proactive `sendMessage` call) is the subject of `research.md`'s Gate Zero — no mock
  ever substitutes for it.
- ✅ **§XVII No monkey-patching**: `ReminderManager`, `PendingLocalToolApprovalManager`, and the
  delivery scheduler are all new, separately-constructed, dependency-injected objects — no
  runtime patching of `whatsapp_chatbot_python`, `AIHandler`, or the existing
  `PendingApprovalManager`.
- **Explicit deviation, not a violation**: this feature ships without a `config.feature_flags`
  gate, by explicit user decision — CLAUDE.md's general "new behavior needs a flag" convention is
  overridden for this feature specifically (see spec.md Clarifications). Recorded here rather than
  silently applied, per the Complexity Tracking spirit even though it's not technically a
  Constitution violation (CONSTITUTION doesn't mandate feature flags itself — that's a CLAUDE.md
  project convention).

## Integration Contracts

Per METHODOLOGY §VII (multi-component feature: `ai_handler.py`, `denidin.py`, a new manager, a new
service all gain new responsibilities). Full contracts in `contracts/`:

1. **`contracts/reminder-tool-schemas.md`** — the four tool schemas (`list_reminders`,
   `create_reminder`, `modify_reminder`, `delete_reminder`) and their RBAC-gated attachment.
2. **`contracts/local-tool-approval-gate.md`** — `PendingLocalToolApproval`/
   `PendingLocalToolApprovalManager`, the dual-check dispatch added to `get_response()`/
   `resolve_button_tap()`, and `_resolve_pending_local_tool_approval`'s approve/decline handling.
3. **`contracts/reminder-delivery.md`** — the APScheduler job, `_sweep_due_reminders`'s
   iCalendar-based resolution logic, `send_proactive_message`, and the rounding contract.

## Project Structure

### Documentation (this feature)

```text
specs/in-progress/054-reminders-functionality-mgmt/
├── spec.md               # done — fully clarified, including the 2026-08-16 design-review round
├── user-stories.md       # done — 5 prioritized stories, updated for the ownership/delivery model
├── research.md           # done — Gate Zero (live proactive-send) OPEN/blocking; icalendar/
│                          #   recurring_ical_events tz + narrow-window-efficiency checks pending
├── plan.md                # this file
├── data-model.md          # done — SQLite schema (genuine iCalendar fields), sweep resolution logic
├── quickstart.md          # this phase's output
├── contracts/
│   ├── reminder-tool-schemas.md         # done
│   ├── local-tool-approval-gate.md      # done
│   └── reminder-delivery.md             # done
└── tasks.md                # NOT yet run (/speckit.tasks)
```

### Source Code (repository root, single project — `apps/denidin-app/`)

```text
apps/denidin-app/
├── denidin.py                              # MODIFIED — construct+start the reminder
│                                            #   BackgroundScheduler in initialize_app() (after
│                                            #   run_startup_reminder_sweep()), alongside the
│                                            #   existing SessionCleanupThread wiring; stop it in
│                                            #   both shutdown paths.
├── requirements.txt                        # MODIFIED — + icalendar, recurring_ical_events,
│                                            #   apscheduler
├── config/
│   ├── config.example.json                 # MODIFIED — new `reminders` section
│   ├── config.dev.json / .prod.json / .test.json   # MODIFIED — same
├── src/
│   ├── models/
│   │   └── config.py                       # MODIFIED — new `reminders: Dict` field +
│   │                                        #   defaults-merge block (mirrors the `mcp` section's
│   │                                        #   pattern)
│   ├── managers/
│   │   ├── reminder_manager.py             # NEW — SQLite storage, RFC5545 construction/
│   │   │                                    #   resolution, cap enforcement, rounding,
│   │   │                                    #   single-occurrence vs. whole-series logic
│   │   └── pending_local_tool_approval_manager.py   # NEW — see contracts/local-tool-approval-gate.md
│   ├── services/
│   │   └── reminder_delivery_service.py    # NEW — BackgroundScheduler wiring,
│   │                                        #   run_startup_reminder_sweep, _sweep_due_reminders
│   ├── utils/
│   │   └── green_api_bot.py                # MODIFIED — + send_proactive_message
│   └── handlers/
│       └── ai_handler.py                   # MODIFIED — 4 new tool schemas, RBAC-gated
│                                            #   attachment, dual-check dispatch in get_response()/
│                                            #   resolve_button_tap(), new
│                                            #   _resolve_pending_local_tool_approval() +
│                                            #   _call_openai_reminder_followup_api()
└── tests/
    ├── unit/
    │   ├── test_reminder_manager.py                    # NEW — modeled on test_ledger_event_manager.py
    │   ├── test_pending_local_tool_approval_manager.py # NEW
    │   ├── test_ai_handler_reminders.py                # NEW — modeled on test_ai_handler_ledger_events.py
    │   └── test_reminder_delivery_service.py           # NEW — sweep logic against a stub bot/sender
    ├── integration/
    │   └── test_reminder_conversation_routing.py       # NEW — real textMessage-shaped notification
    │                                                    #   through bot.router, real internal wiring,
    │                                                    #   exercising the create/approve flow up to
    │                                                    #   a pending approval being set
    └── billed/
        └── test_reminder_lifecycle_billed.py           # NEW — see "Testing strategy" below
```

**Structure Decision**: Single project, following the exact placement convention already used for
`LedgerEventManager` (`managers/`), `SessionCleanupThread` (`services/`), and
`mark_message_read`/`send_typing_indicator` (`utils/green_api_bot.py`) — no new top-level module,
every new file lands where its analog already lives.

## Phased Implementation Order

1. **Phase 0 — Research**: close `research.md`'s two non-live library sanity checks
   (`icalendar` tz-preservation, `recurring_ical_events` narrow-window efficiency) before writing
   `ReminderManager`'s sweep-resolution code. Gate Zero R1 (live proactive send) does NOT block
   this phase or Phases 1-4 below — only Phase 5 onward.
2. **Phase 1 — Config + dependencies**: `config.py`'s `reminders` section, config file updates,
   `requirements.txt`.
3. **Phase 2 — `ReminderManager`**: SQLite schema + RFC5545 construction/resolution + cap
   enforcement + rounding + single-occurrence/whole-series logic. Fully unit-testable in
   isolation, no AI/WhatsApp dependency — highest-value, lowest-risk phase, build and test first.
4. **Phase 3 — `PendingLocalToolApprovalManager`**: small, mechanical, no dependency on Phase 2.
5. **Phase 4 — Tool schemas + dual-check dispatch**: `ai_handler.py`'s RBAC-gated attachment,
   `get_response()`/`resolve_button_tap()` dual-check, `_resolve_pending_local_tool_approval`,
   the follow-up confirmation call.
6. **Phase 5 — `send_proactive_message`**: implementable and unit-testable (against a stubbed
   `bot`) immediately, but **not mergeable as "done" until Gate Zero R1 closes** (`research.md`) —
   a real live send, human-approved, human-present.
7. **Phase 6 — Delivery scheduling**: `reminder_delivery_service.py` (depends on Phases 2 and 5).
8. **Phase 7 — `denidin.py` wiring**: scheduler start/stop alongside the existing cleanup-thread
   block.
9. **Phase 8 — Billed E2E tests + `quickstart.md` manual verification**.

## Testing Strategy

**Unit** (`tests/unit/`, no network): `test_reminder_manager.py` (recurrence resolution across all
`freq`/end-condition combinations — the single highest-value test file, since correctness here is
the crux of the whole feature; cap enforcement; rounding, including the "rounds into the past"
edge case; single-occurrence vs. whole-series semantics; the permanence rule for
`reminder_exceptions`), `test_pending_local_tool_approval_manager.py` (get/set/clear/
attach_sent_message_id), `test_ai_handler_reminders.py` (tool attachment gated correctly by role;
dual-check dispatch order; approve/decline paths), `test_reminder_delivery_service.py` (sweep
due/not-due logic, failed-send-leaves-pending-for-retry, against a stub `bot`/
`send_proactive_message` — permitted at the unit tier per CONSTITUTION §I/§V's real-internal-
components-only rule applying to *integration* tests, not unit).

**Integration** (`tests/integration/`, real router dispatch, no mocking of internal components):
a real `textMessage`-shaped notification through `bot.router` exercising the full create-reminder
conversational flow through to a pending approval being set.

**Billed** (`tests/billed/`, cheap real OpenAI, no per-run approval needed): the corrected,
complete list from the design-review conversation —
`test_godfather_creates_one_time_reminder_text_approval`,
`test_godfather_creates_one_time_reminder_button_approval`,
`test_godfather_creates_recurring_reminder`, `test_modify_one_time_reminder`,
`test_delete_one_time_reminder`, `test_modify_single_occurrence_of_recurring_reminder`,
`test_modify_whole_series_pattern` (explicitly asserts a pre-existing Detached/exception
occurrence is untouched by the whole-series edit), `test_delete_whole_series`,
`test_client_role_denied_reminder_tools`, `test_cap_declined_at_21st_reminder`.

**Manual/`quickstart.md`-only**: the live proactive-send Gate Zero itself; a real
restart-survives-and-catches-up check; observing a real recurring reminder fire across multiple
5-minute sweep ticks.

## Complexity Tracking

No Constitution Check violations requiring justification, beyond the explicitly-recorded
no-feature-flag deviation (a CLAUDE.md project-convention override by user decision, not a
CONSTITUTION.md violation) noted above.
