# Bugfix 068: Shared SQLite connections used across threads with no serialization

## Bug ID
bugfix-068

## Status
Open — root cause known, fix NOT yet chosen/implemented (explicit human direction: create the
placeholder now, solve later).

## Priority
P2 — currently only observed as a rare, intermittent integration-test flake, not (yet) a
confirmed production incident. Real risk is a `sqlite3.OperationalError` (or, worse, silent data
corruption) under the same race in production, since the affected managers are used the same way
there as in the test.

## Discovered
2026-09-27, during Feature 063 (Dynamic Capability Backbone) test-stabilization work — a background
`pytest` run hit:
```
sqlite3.OperationalError: cannot commit transaction - SQL statements in progress
```
in `tests/integration/test_backbone_capability_resolution.py::test_real_scheduler_fires_and_clears_idle_chat_but_not_active_one`.

## Root Cause
`src/managers/session_manager.py`'s `SessionManager` opens one long-lived SQLite connection for
`chat_index.db` in `__init__`, with `check_same_thread=False`, and reuses it from every caller for
the lifetime of the process — with no locking/serialization around it. Normally only one request
thread touches it at a time, but `services/capability_reset_service.py`'s idle-capability-reset
job runs on its own `APScheduler` `BackgroundScheduler` thread and can call into the very same
connection concurrently with the main thread (e.g. commit a write while another thread is
mid-read/mid-write). SQLite does not support concurrent use of one connection from multiple
threads without external synchronization; when the timing lines up wrong, a commit fails with the
error above. This is inherently timing-dependent, so it reproduces only intermittently.

A `threading.Lock` fix for this exact case was implemented and verified (all failures gone across
repeated flag-on/flag-off full unit+integration runs), then explicitly reverted at the user's
direction ("REMOVE THE LOCK!!!! I DID NOT APPROVE ANY LOCK") — no lock-based fix may be
reintroduced without fresh, explicit approval. `git log`/PR history for this bugfix's eventual fix
commit will show the revert; the lock implementation itself is not preserved anywhere as
prior art beyond this note.

## Scope: other shared connections with the same shape

A grep for `sqlite3.connect` under `src/` found three more managers built the same way (one
long-lived connection, `check_same_thread=False`, no locking) — each is a candidate for the same
race and needs the same look, not just `SessionManager`:

1. **`src/managers/reminder_manager.py`** (`self._conn`) — used by the main request thread
   (create/modify/delete/list_reminders, via `ai_handler.py` and the Feature 063 backbone) **and**
   by `services/reminder_delivery_service.py`'s `BackgroundScheduler` job
   (`CronTrigger(minute='*/5')`) on its own thread. Same two-thread shape (scheduler + request
   thread) as the confirmed `SessionManager` failure — the closest analog and the next most likely
   to actually reproduce.
2. **`src/managers/roll_marker_store.py`** (`self._conn`) — used by
   `services/daily_summary_roll_service.py`'s nightly `BackgroundScheduler` job and by its own
   startup catch-up sweep. Lower risk in practice (nightly cron vs. one-time startup rarely
   overlap), but the same unguarded-shared-connection shape, so a slow catch-up sweep overlapping
   the cron boundary is not provably impossible.
3. **`src/managers/telemetry_manager.py`** (`self._conn`) — used from `ai_handler.py`/
   `src/backbone/backbone.py`, both driven by the request thread. No background scheduler was
   found touching it, so it's likely single-threaded in practice — lowest priority of the three,
   but not yet confirmed either way.

## Fix options considered (none chosen yet — do not implement without discussing first)

1. **Per-thread connection** (e.g. via `threading.local()`) instead of one shared connection per
   manager. Each thread gets its own `sqlite3.connect(...)`, so there is no shared mutable
   connection object to race on. Closest to "remove the shared state" rather than "coordinate
   access to it." Standard fix for this exact SQLite usage pattern.
2. **Route the scheduler's work through the same single thread/queue the request path already
   uses**, instead of letting the scheduler call into the manager from its own background thread
   at all. Removes the second thread from the picture entirely for that one call site.
3. **WAL mode + retry-on-busy**: `PRAGMA journal_mode=WAL` for more tolerant concurrent
   read/write, plus a short bounded retry around the commit (catch `OperationalError`, retry once
   after a brief pause). Absorbs the rare race without adding a lock construct; less clean than
   #1 since it doesn't remove the underlying shared-connection race, just tolerates it.
4. **Short-lived connection per call** (open, do the one operation, close) instead of one
   long-lived connection. Removes the shared-state problem entirely; costs reopening the file
   each time, likely acceptable given how infrequently these DBs are touched per call.

## Next steps
- Decide which fix option (or combination, e.g. #1 for `reminder_manager.py` /
  `session_manager.py`, lower priority for the other two) to pursue — needs explicit human
  sign-off before any implementation, same as the reverted lock attempt.
- Bug-Driven Development applies (METHODOLOGY.md §VII): once a fix direction is approved, still
  needs a test-gap analysis and a real failing test before the fix, not just a spot patch.
