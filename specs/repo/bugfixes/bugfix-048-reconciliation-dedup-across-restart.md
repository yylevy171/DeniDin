# Bugfix Spec: Feature 025 reconciliation dedup guard re-persists every document after a process restart

## Bug ID
bugfix-048-reconciliation-dedup-across-restart

## Title
`LedgerEventManager.add_ledger_event`'s חשבונית duplicate guard keyed on an **exact
timestamp** match. The in-memory cache holds `local_dt` at seconds precision (parsed from
Morning's ISO `creation_date`), but `scan_accounting_documents` — which rebuilds that cache
from disk on every process start — can only recover minute precision from the persisted
`event_datetime` string. After any restart, `16:35:30 != 16:35:00`, so every already-captured
Morning document seen by a later reconciliation sweep was misclassified as an "anomaly",
persisted **again** as a new event file, and flagged into a write-only `pending_review.json`
that nothing ever reads.

## Priority
**P1** — silent, unbounded ledger corruption: the hourly reconciliation sweep re-lists every
document from the watermark date on each tick, so a single Morning document accumulated a fresh
duplicate ledger event on every sweep following a restart.

## Status
**Done — implemented, tested, validated in dev, Merged to master (PR #267).** Root cause presented; human chose the fix directly:
"dedup on date+display number — since there can be multiple entries on same date, but never
same display number. also order is never guaranteed for the listed items within a given date."
Human also directed removal of the `pending_review` mechanism outright ("WTF is 'pending
review'?! There is no review!") and cleanup of the accumulated dev duplicates.

Shipped together with bugfix-047 on branch `bugfix/047-048-reconciliation-sweep-timeout-and-dedup`
— bugfix-047 removes the 30s timeout that was incidentally throttling the buggy re-capture
loop, so deploying it alone would have made the duplication worse.

## Date Opened
2026-08-30

## Reported By
yaronlev171 — while reviewing dev impact of the bugfix-047 deploy: "Current dev has the
watermark a few days ago, but it took only 1 of 16 events from that date. What will happen
when we make the changes and restart dev?"

## Symptom (observed)
In `apps/denidin-app/dev_data/events/`, every 27/08/2026 חשבונית display number had 2–3
identical ledger event files (21 extra files across 16 display numbers).
`apps/denidin-app/dev_data/accounting_reconciliation/pending_review.json` held 23 entries,
**every one** a false positive — `prior_creation_date == new_creation_date` to the minute.

## Root Cause
`add_ledger_event` (source_type `"חשבונית"`):
- `local_dt = _parse_iso_local(event.pop("_source_creation_ts_raw"))` → full precision, e.g.
  `2026-08-27 16:35:30+03:00`.
- Guard: `if local_dt in seen_timestamps: return None` (true duplicate) else
  `if seen_entries: <anomaly — persist new + _append_pending_review>`.

`scan_accounting_documents` (runs once per process, rebuilds `_accounting_document_cache`):
- `creation_dt = datetime.strptime(record["event_datetime"], "%d/%m/%Y %H:%M")` → minute
  precision, e.g. `2026-08-27 16:35:00+03:00`.

Within one process run the guard worked (the cache still held the seconds-precision value it
had just written). Across a restart, the rebuilt cache value never equalled a fresh capture's
`local_dt`, so the `if seen_entries:` anomaly branch fired for every re-listed document.

`_append_pending_review` was a write-only dead-letter file — its own docstring: "Never reads
back/resolves entries — no consumer of this file exists yet within this feature's own scope."

## Test-Gap Analysis
`TestAccountingDocumentTriState` and `TestUS2DedupAcrossTwoSweepTicks` both exercised dedup
**only within a single process** — the cache was never dropped/rebuilt between the two
captures, so the seconds-vs-minute mismatch was never reproduced. No test simulated a restart
mid-reconciliation.

Failing tests added before the fix:
- `test_ledger_event_manager.py::TestAccountingDocumentTriState::test_same_date_duplicate_survives_a_cache_rebuild_restart`
  — persist a doc with a seconds-precision `creation_date`, set
  `manager._accounting_document_cache = None`, re-add the same doc → must return `None` and
  leave exactly one file.
- `test_accounting_reconciliation_service.py::TestUS2DedupAcrossTwoSweepTicks::test_second_tick_capturing_the_same_document_persists_nothing_new`
  — now nulls `ai_handler.ledger_event_manager._accounting_document_cache` between the two
  sweep ticks.

## The Fix (minimal)
`src/managers/ledger_event_manager.py` only:
- The חשבונית guard now keys on **(date, display_number)**: if any cached entry for that
  display number has `entry.timestamp.strftime("%d/%m/%Y") == local_dt.strftime("%d/%m/%Y")`,
  the capture is a duplicate → `return None`. Date strings are precision-immune, so the guard
  behaves identically whether the cache came from a live write or a disk rebuild.
- The "anomaly" third state and `prior_entries_for_anomaly` are removed. A same-display-number
  capture on a genuinely different calendar date is simply a new event (no warning, no review
  file) — a legitimate, rare case (`scan_accounting_documents` still lists both).
- `_append_pending_review` is deleted entirely; the call site is removed. The cache append
  (`AccountingDocumentCacheEntry(local_dt, event_id)`) stays — the watermark
  (`get_accounting_document_watermark`) depends on it.
- Docstrings/comments referencing "tri-state new/duplicate/anomaly" and `pending_review.json`
  updated in `ledger_event_manager.py` and the two test files.

No change to the watermark logic, the safety caps, `apps/morning-mcp-app`, or any config key.

## Dev data cleanup (one-time, per human directive #1)
- Deleted 21 duplicate `dev_data/events/H2708*.json` files — for each (date, display_number)
  group with >1 file, kept the lowest `event_id` (earliest same-minute sequence), deleted the
  rest.
- Deleted `dev_data/accounting_reconciliation/pending_review.json` (23 false-positive entries).
- The `events/` index and the accounting-document cache are both purely disk-derived with no
  separate persisted file, so a restart rebuilds both cleanly from the deduped set.
- Caveat: the running dev container keeps its stale in-memory index/cache until it is
  restarted (i.e. until the bugfix-047+048 deploy). A reconciliation sweep firing on the old
  code before that restart could re-create some duplicates; the deploy's startup sweep, on the
  new code, will then re-list 27/08 (3 days back, inside the 5-day cap) and dedup by date.

## Files Changed
- `apps/denidin-app/src/managers/ledger_event_manager.py`
- `apps/denidin-app/tests/unit/test_ledger_event_manager.py`
- `apps/denidin-app/tests/unit/test_accounting_reconciliation_service.py`

## Verification
- `pytest tests/unit/` — 1228 passed.
- `pytest tests/unit/test_ledger_event_manager.py tests/unit/test_accounting_reconciliation_service.py` — 214 passed.
- pylint / mypy: no new findings (all remaining mypy errors pre-exist on `master`).
- Post-deploy: after the startup reconciliation sweep, confirm each 27/08 display number has
  exactly one file under `dev_data/events/` and no `pending_review.json` is recreated.
- Dev validation (2026-08-30): 10 of the 16 27/08 חשבונית events were deleted, then both dev
  apps were rebuilt+restarted on this branch. First startup sweep captured **12** events (the
  10 re-listed 27/08 docs, deduped by date and re-persisted with their original timestamps +
  2 genuinely-new sandbox docs 52246/52247). A second restart (colima recovered after a Mac
  sleep) ran another startup sweep that captured **0** events — the disk-rebuilt cache deduped
  every re-listed document by `(date, display_number)`. No `pending_review.json` recreated;
  watermark advanced from `27/08 16:35` to `30/08 11:14`.
