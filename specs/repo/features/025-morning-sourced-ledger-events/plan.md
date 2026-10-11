# Implementation Plan: Morning-Sourced Ledger Events

**Branch**: `feature/025-morning-sourced-ledger-events` | **Date**: 2026-08-20 | **Spec**: `./spec.md`
**Input**: Feature specification from `specs/in-progress/025-morning-sourced-ledger-events/spec.md`
**Estimated Duration**: 3-5 days (new background service + scheduler wiring, `LedgerEventManager`/
`LEDGER_EVENT_TOOL` schema extension, a new non-conversational OpenAI+MCP call path, new dedup
scan logic; no new external integrations — reuses the existing Morning MCP tunnel and `Invoice`
model as-is)

---

**IMPORTANT**: This plan complies with:
- **CONSTITUTION.md** (§I-III): No env vars (all config from `AppConfiguration`), Israel local
  time everywhere (bugfix-037 — every timestamp `now_local()`-sourced, never bare
  `datetime.now()`/UTC), feature branch + merge-commit workflow.
- **METHODOLOGY.md** (§II, IV, VII): Template structure, phased planning, Integration Contracts
  (`contracts/accounting-reconciliation-service.md`, `contracts/ledger-event-manager-extension.md`,
  both written).

---

## Summary

Add a third, proactive source for `LedgerEvent` capture (alongside Feature 024's existing
conversational text/image sources): a new background service
(`services/accounting_reconciliation_service.py`) that periodically polls Morning for documents
created since the last known one, and — via a dedicated, non-conversational OpenAI + Morning-MCP
call — transcribes each not-yet-seen one into a `LedgerEvent` with `source_type="חשבונית"`, using
five newly-named `accounting_document_*` fields already reserved (under different, vendor-
specific names) since Feature 033. Dedup is derived entirely from already-persisted ledger events
(no new store); the existing conversational-turn suppression that made this exact case an
explicit non-goal (2026-08-02 user directive) stays completely unchanged for the reactive path —
this feature adds a structurally separate capture path, it does not loosen that one.

## Technical Context

**Language/Version**: Python 3.9+ (existing project floor, `apps/denidin-app`)
**Primary Dependencies**: `apscheduler` (already a dependency, via Feature 054's
`reminder_delivery_service.py`) for the poll scheduler; OpenAI Responses API + remote MCP tool
attachment (already used by every Morning-MCP-authorized conversational turn) for the actual
list/detail/capture calls — no new dependency introduced.
**Storage**: Flat JSON files, `{data_root}/events/{event_id}.json` — same files/format Feature
033 already owns, extended in place (renamed fields, `CURRENT_SCHEMA_VERSION` 1→2). No new
storage mechanism, no new persisted watermark/state file (derived from existing events instead —
research.md).
**Testing**: `pytest` — `tests/unit/` for `LedgerEventManager`'s new
`scan_accounting_documents`/duplicate-guard logic and the scheduler wiring's non-network parts;
`billed`/`expensive` acceptance tests (per METHODOLOGY.md's TDD redefinition, §VI) for the real
end-to-end sweep-against-the-real-Morning-sandbox scenario — written and run together, once, as
the final acceptance pass, not before.
**Target Platform**: Same as rest of `apps/denidin-app` — Docker container, Linux.
**Project Type**: Single project (`apps/denidin-app`) — this feature makes zero changes to
`apps/morning-mcp-app` (research.md's finding: `list_invoices`/`get_invoice_details` already
cover every document type via the real `/documents/search`/`/documents/{id}` endpoints with no
type filter — no new MCP tool needed).
**Performance Goals**: N/A — poll interval is a cost/traffic tuning knob (`tasks.md`), not a
latency target; single-digit-to-low-hundreds of documents at current/foreseeable scale.
**Constraints**: MUST NOT let the reconciliation sweep's `capture_ledger_event` calls interact
with `_handle_ledger_event_capture`'s existing conversational-turn suppression/one-call-per-turn
logic at all (research.md's "Critical" note) — a structurally separate handler, not a
conditionally-loosened existing one. MUST NOT start the new scheduler inside `initialize_app()`
(reachable by `tests/integration/`'s shared bootstrap) — `__main__`-only, mirroring
`reminder-delivery.md`'s own corrected precedent.
**Scale/Scope**: One new service module (~150-200 LOC, closely mirroring
`reminder_delivery_service.py`'s shape), one new `LedgerEventManager` method
(`scan_accounting_documents`) plus a duplicate-guard addition to `add_ledger_event`, one extended
tool schema (`LEDGER_EVENT_TOOL`), `denidin.py` wiring for scheduler start/shutdown alongside the
existing `cleanup_thread`/`reminder_scheduler` pattern.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

- ✅ **§I No env vars**: New service constructed with `AppConfiguration`-derived values
  (`LedgerEventManager` instance already exists via DI; poll interval/lookback constants live in
  code, same as `reminder_delivery_service.py`'s `STARTUP_SWEEP_LOOKBACK`/
  `PERIODIC_SWEEP_LOOKBACK`, not config — consistent with that precedent; revisit only if
  `tasks.md` finds a concrete reason a given environment needs a different interval). No
  `feature_flags` entry (per spec.md Clarifications — explicit user decision, schema-version
  bump instead).
- ✅ **§II Israel local time (bugfix-037)**: All new timestamps/date comparisons (watermark
  derivation, `accounting_document_creation_date` formatting) via `now_local()`/the existing
  `_normalize_iso_date` helper — never bare `datetime.now()`.
- ✅ **§III Git workflow**: On `feature/025-morning-sourced-ledger-events`, off `master`.
- ✅ **§V Integration tests, no mocking**: The reconciliation sweep's real acceptance test hits
  the real Morning sandbox + real OpenAI (billed/expensive tier, per METHODOLOGY.md §VI) — no
  `unittest.mock` for either external service anywhere in `tests/integration/`/`tests/billed/`/
  `tests/expensive/`. Unit tests for `scan_accounting_documents`/the duplicate guard use real
  `LedgerEventManager` instances against real temp-dir JSON files (no mocking of internal
  components, consistent with existing `test_ledger_event_manager.py`).
- ✅ **§XIV pathlib**: `scan_accounting_documents` uses `Path.glob`, matching every existing
  `LedgerEventManager` method.
- ✅ **§XV JSON/file format**: Unchanged — `json.dump(..., sort_keys=True, ensure_ascii=False,
  indent=2)`, same as every existing `LedgerEvent` write.
- ✅ **§XVII No monkey-patching**: New service function + scheduler, injected via
  `global_context`, same DI pattern `reminder_delivery_service.py` already establishes — no
  runtime patching.
- **Re-check after Phase 1 (data-model.md/contracts/ written)**: No new violations. The one
  design point requiring real care rather than a constitution rule — never letting the new
  reconciliation handler share code paths with `_handle_ledger_event_capture`'s conversational
  suppression logic — is documented explicitly in both contracts, not left implicit.

No Complexity Tracking entries needed — no violations to justify. This is additive to an
existing, already-DI'd manager and mirrors an already-shipped scheduler pattern; no new
architectural primitive is introduced.

## Project Structure

### Documentation (this feature)

```text
specs/in-progress/025-morning-sourced-ledger-events/
├── spec.md                # This feature's spec (done, incl. Clarifications)
├── user-stories.md        # MANDATORY, Given-When-Then — backfilled during this plan (see note)
├── plan.md                # This file
├── research.md            # Phase 0 output (done)
├── data-model.md          # Phase 1 output (done)
├── quickstart.md          # Phase 1 output (done)
├── contracts/
│   ├── accounting-reconciliation-service.md   # Phase 1 output (done)
│   └── ledger-event-manager-extension.md      # Phase 1 output (done)
└── tasks.md                # Phase 2 output (/speckit.tasks — next)
```

Note: `spec.md` predates the `user-stories.md`-mandatory convention (033/054-era) and had never
been backfilled — closed during this planning pass (not deferred) since `speckit.tasks` needs
Given-When-Then stories to derive tasks from; `user-stories.md` now exists with 5 stories
(US1-US5), matching `quickstart.md`'s manual-verification scenarios.

### Source Code (repository root, single project — `apps/denidin-app/`)

```text
apps/denidin-app/
├── src/
│   ├── managers/
│   │   └── ledger_event_manager.py       # MODIFIED — 5 fields renamed, source_type="חשבונית"
│   │                                      #   support, scan_accounting_documents (NEW method),
│   │                                      #   duplicate guard in add_ledger_event,
│   │                                      #   CURRENT_SCHEMA_VERSION 1->2
│   ├── handlers/
│   │   └── ai_handler.py                 # MODIFIED — LEDGER_EVENT_TOOL schema extended;
│   │                                      #   NEW handler method for the reconciliation
│   │                                      #   sweep's capture_ledger_event calls (separate
│   │                                      #   from _handle_ledger_event_capture, UNCHANGED)
│   ├── services/
│   │   └── accounting_reconciliation_service.py   # NEW — scheduler + sweep worker,
│   │                                      #   mirrors reminder_delivery_service.py's shape
│   └── ...                               # denidin.py: wire scheduler start/shutdown in
│                                          #   __main__ (NOT initialize_app), alongside
│                                          #   cleanup_thread/reminder_scheduler
└── tests/
    ├── unit/
    │   ├── test_ledger_event_manager.py             # MODIFIED — scan_accounting_documents,
    │   │                                             #   duplicate guard, renamed-field tests
    │   ├── test_ai_handler_ledger_events.py          # MODIFIED — schema extension tests
    │   └── test_accounting_reconciliation_service.py # NEW — non-network scheduler-wiring
    │                                                 #   unit tests (mirrors
    │                                                 #   reminder_delivery_service.py's own
    │                                                 #   unit-test split, if any)
    ├── billed/ or expensive/
    │   └── test_accounting_reconciliation_e2e.py     # NEW — real Morning sandbox + real
    │                                                 #   OpenAI acceptance test (tier TBD in
    │                                                 #   tasks.md; likely billed — no
    │                                                 #   vision/image calls involved)
    └── integration/
        └── (regression coverage for US4's "conversational turn unaffected" scenario, likely
             extending the existing test_denidin_morning_mcp_e2e.py-adjacent suite rather than
             a new file — tasks.md to decide)
```

**Structure Decision**: Single project, following `apps/denidin-app`'s existing
`src/managers/`+`src/handlers/`+`src/services/` layout exactly — the new service is a peer of
`services/reminder_delivery_service.py`/`services/cleanup_service.py`, not a new top-level
module or a new app. `apps/morning-mcp-app` is untouched (research.md).
