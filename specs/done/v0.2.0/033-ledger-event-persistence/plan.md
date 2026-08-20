# Implementation Plan: Ledger Event Persistence

**Branch**: `feature/033-ledger-event-persistence` | **Date**: 2026-07-29 | **Spec**: `./spec.md`
**Input**: Feature specification from `specs/in-progress/033-ledger-event-persistence/spec.md`
**Estimated Duration**: 2-3 days (persistence layer + wiring + migration; no new external
integrations, no UI, small surface area)

---

**IMPORTANT**: This plan complies with:
- **CONSTITUTION.md** (§I-III): No env vars (all paths from `AppConfiguration.data_root`),
  UTC timestamps internally (`message_timestamp`/`captured_at` always UTC; local-time
  conversion is output-formatting only), feature branch + merge-commit workflow.
- **METHODOLOGY.md** (§II, IV, VII): Template structure, phased planning, Integration
  Contracts (`contracts/ledger-event-manager.md`, already written).

---

## Summary

Replace `SessionManager.add_pending_ledger_event`/`Session.pending_ledger_events` (session-
scoped, temporary, 16-field shape) with a new `LedgerEventManager` (sibling to
`MemoryManager`/`MediaFileManager`) that persists each captured ledger event as its own
file under `data/events/{event_id}.json`, in a 29-column schema matching the real
downstream `Events.csv` exactly, with a code-generated collision-free `event_id`, message-
level traceability in both directions, and a one-off migration of the one historical
session that predates this feature.

## Technical Context

**Language/Version**: Python 3.9+ (existing project floor, `apps/denidin-app`)
**Primary Dependencies**: stdlib only — `pathlib`, `json`, `dataclasses`, `zoneinfo`
(Asia/Jerusalem conversion), `re` (amount parsing), `uuid` (not needed here — `event_id`
is deterministic, not random)
**Storage**: Flat JSON files, `{data_root}/events/{event_id}.json` (see Technology Choices
in spec.md)
**Testing**: `pytest` — `tests/unit/` (new `test_ledger_event_manager.py`, updated
`test_session_manager.py`), component-integration tests for `AIHandler`/`MediaHandler`
wiring (real objects, no mocks, per CONSTITUTION §V)
**Target Platform**: Same as rest of `apps/denidin-app` — Docker container, Linux
**Project Type**: Single project (existing `apps/denidin-app` structure)
**Performance Goals**: N/A — single-digit events per day at current usage; no perf targets
**Constraints**: MUST NOT read `data/events/Events.csv` at runtime (explicit instruction);
MUST NOT do AI/LLM calls anywhere in the persistence layer
**Scale/Scope**: One new manager class (~150-200 LOC), 2 existing files modified
(`ai_handler.py`, `media_handler.py`), 2 existing models modified (`Message`, `Session` in
`session_manager.py`), 1 one-off migration script

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

- ✅ **§I No env vars**: `LedgerEventManager(storage_dir=...)` constructed from
  `AppConfiguration.data_root` in `denidin.py`'s `initialize_app`, same pattern as
  `MemoryManager`/`MediaFileManager`. No `feature_flags` needed (see spec.md Edge Cases —
  this is a storage-shape change to always-on behavior, not new gradually-rolled-out
  behavior).
- ✅ **§II UTC timestamps**: `message_timestamp`/`captured_at` remain
  `datetime.now(timezone.utc)`-sourced throughout; Asia/Jerusalem conversion via
  `zoneinfo` happens only at the point of formatting `event_date`/`event_time`/`event_id`
  for output — never stored as the canonical internal timestamp.
- ✅ **§III Git workflow**: On `feature/033-ledger-event-persistence`, off `master`.
- ✅ **§V Integration tests, no mocking**: New component-integration tests exercise real
  `AIHandler`/`MediaHandler`/`LedgerEventManager`/`SessionManager` objects together; no
  `unittest.mock` anywhere in `tests/integration/` or the new manager's own tests. The one
  external-service boundary this feature touches (none — no OpenAI/Green API calls
  introduced) needs no service mocking either.
- ✅ **§XIV pathlib**: `LedgerEventManager` uses `pathlib.Path` exclusively, matching
  `MediaFileManager`/`SessionManager`.
- ✅ **§XV JSON/file format**: `json.dump(..., sort_keys=True, ensure_ascii=False, indent=2)`.
- ✅ **§XVII No monkey-patching**: New manager injected via constructor (dependency
  injection), same as every existing manager — no runtime patching anywhere.
- **Re-check after Phase 1 (data-model.md/contracts/ written)**: No new violations
  introduced by the detailed design — `add_ledger_event` returning `Optional[str]` is a
  plain, ordinary return value, not a new pattern requiring justification.

No Complexity Tracking entries needed — no violations to justify.

## Project Structure

### Documentation (this feature)

```text
specs/in-progress/033-ledger-event-persistence/
├── user-stories.md      # MANDATORY, Given-When-Then (done)
├── spec.md               # This feature's spec (done)
├── plan.md               # This file
├── research.md           # Phase 0 output (done)
├── data-model.md          # Phase 1 output (done)
├── quickstart.md          # Phase 1 output (done)
├── contracts/
│   └── ledger-event-manager.md   # Phase 1 output (done)
└── tasks.md               # Phase 2 output (/speckit.tasks — next)
```

### Source Code (repository root, single project — `apps/denidin-app/`)

```text
apps/denidin-app/
├── src/
│   ├── managers/
│   │   ├── ledger_event_manager.py     # NEW — LedgerEventManager
│   │   └── session_manager.py          # MODIFIED — remove pending_ledger_events/
│   │                                    #   add_pending_ledger_event; add
│   │                                    #   Message.ledger_event_ids
│   ├── handlers/
│   │   ├── ai_handler.py               # MODIFIED — _handle_ledger_event_capture calls
│   │   │                               #   LedgerEventManager, threads ledger_event_ids
│   │   │                               #   into add_message calls
│   │   ├── media_handler.py            # MODIFIED — new message_id param, reordered
│   │   │                               #   capture-before-store, docstring fix
│   │   └── whatsapp_handler.py         # MODIFIED — threads message.message_id through
│   └── ...                             # (denidin.py: wire LedgerEventManager into
│                                        #   initialize_app, same pattern as MemoryManager)
├── scripts/
│   └── migrate_stray_ledger_events.py  # NEW — one-off, US4/REQ-MIGRATE-001
└── tests/
    ├── unit/
    │   ├── test_ledger_event_manager.py         # NEW
    │   ├── test_session_manager.py               # MODIFIED — TestPendingLedgerEvents replaced
    │   ├── test_ai_handler_ledger_events.py       # MODIFIED — new capture/wiring test classes added
    │   ├── test_media_handler.py                  # MODIFIED — message_id threading tests added
    │   └── test_migrate_stray_ledger_events.py    # NEW
    └── expensive/
        └── test_ledger_event_capture_e2e.py       # MODIFIED — see tasks.md Phase 8
```

**Structure Decision**: Single project, following `apps/denidin-app`'s existing
`src/managers/`+`src/handlers/` layout exactly — `LedgerEventManager` is a peer of
`MemoryManager`/`MediaFileManager` in `src/managers/`, not a new top-level module.
