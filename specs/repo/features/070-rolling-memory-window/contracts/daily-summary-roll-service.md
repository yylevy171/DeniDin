# Contract: `daily_summary_roll_service`

**Module (new)**: `apps/denidin-app/src/services/daily_summary_roll_service.py`
**Pattern**: mirrors `src/services/reminder_delivery_service.py` /
`src/services/accounting_reconciliation_service.py` verbatim — bare `BackgroundScheduler`, one
`add_job` with `max_instances=1`, a `trigger: Any = None` testability seam, a
`_sweep_*(global_context, *, now=None, lookback_days=None, log_prefix="")` worker with a
synchronous `run_startup_*_sweep(global_context)` twin, **wired in `denidin.py __main__` only**,
errors never escape the job.

`global_context` is the `DeniDin` instance. Reaches components via:
- `global_context.session_manager` (`= ai_handler.session_manager`, set on `DeniDin.__init__`)
- `global_context.ai_handler.roll_marker_store` (new — set in `AIHandler.__init__`)
- `global_context.ai_handler.memory_manager`
- `global_context.ai_handler.openai_client` / `config.ai_model` for the summarizer call

---

## `start_daily_roll_scheduler(global_context, *, roll_hour=2, trigger=None) -> BackgroundScheduler`

- `scheduler = BackgroundScheduler()`
- `scheduler.add_job(func=lambda: _sweep_daily_roll(global_context, lookback_days=2),
  trigger=trigger or CronTrigger(hour=roll_hour, minute=0, timezone=LOCAL_TZ),
  id="daily_summary_roll", max_instances=1)`
  - `CronTrigger(hour=2, minute=0, timezone=LOCAL_TZ)` is valid and wall-clock-aligned;
    `CronTrigger(minute="*/60")` is **not** (raises `ValueError` — real bug 2026-08-21). Do not use
    an interval form.
- `scheduler.start()`; return it.
- `roll_hour` from `config.memory['roll']['hour']` (default 2). `trigger` is production-`None`;
  tests pass a short `IntervalTrigger`.
- The periodic tick uses `lookback_days=2` (yesterday + a 1-day slack for a tick that slips past
  midnight), narrow on purpose (blast-radius cap if a marker write ever fails).

## `run_startup_daily_roll_sweep(global_context) -> None`

- Synchronous, main-thread, called in `__main__` **before** `start_daily_roll_scheduler`.
- `_sweep_daily_roll(global_context, lookback_days=config.memory['roll']['catchup_lookback_days'],
  log_prefix="[STARTUP] ")` (default 21).
- Days older than the lookback are **not** rolled here — they are the US4 backfill's responsibility
  (REQ-MEM-028). Logs a single INFO if any un-rolled (chat, date) predates the lookback, pointing
  at the backfill.
- Must not block message handling indefinitely: bounded by `catchup_lookback_days × n_chats`
  (≤ ~42 (chat, date) pairs at prod scale); each `_roll_one_chat_day` is independently
  try/excepted.

## `_sweep_daily_roll(global_context, *, now=None, lookback_days=None, log_prefix="") -> None`

- `now = now or now_local()`; `today = local_calendar_date(now)`.
- Candidate dates: `[today - k for k in range(1, lookback_days + 1)]` (never today itself — the
  current day is still in the verbatim window and not yet complete).
- Enumerate chats from `SessionManager` (all sessions on disk, live + `expired/`).
- For each (chat, date): `_roll_one_chat_day(...)`, wrapped in `try/except Exception` →
  `logger.error(exc_info=True)` + continue. One poison chat never aborts the sweep (REQ-MEM-027).
- After the roll loop, once per chat: `session_manager.archive_aged_and_backstopped_messages(
  session, now=now, window_days=config.memory['session']['window_days'], max_backstop_tokens=100000)`
  (Phase 3). Also try/excepted per chat.

## `_roll_one_chat_day(global_context, chat, date, *, source, log_prefix) -> None`

1. `roll_marker_store.is_rolled(chat, date_str)` → return (skip).
2. `roll_marker_store.try_claim(chat, date_str, source)` → `False` → return (another racer / fresh
   claim owns it).
3. `messages = session_manager.get_messages_for_local_date(session, date)`.
4. **Empty** → `roll_marker_store.commit(chat, date_str, message_count=0, memory_id=None)`. No
   OpenAI call. Return. (REQ-MEM-023)
5. **Non-empty**:
   a. `summary = summarize_conversation(client, config.ai_model, messages)` (Contract: summarizer —
      includes the raw-transcript fallback, so this does not raise on an OpenAI failure; but if it
      *does* raise, propagate → the outer try/except logs it and **no `commit`** happens →
      retried next run, REQ-MEM-025 / sc6).
   b. `collection = collection_name_for_chat(chat)` (Contract: memory-collections — the **only**
      way the name is derived; **no** `client.get_collection()` anywhere in this path).
   c. `memory_manager.get_or_create_collection(collection).delete(where={"type":"daily_summary",
      "chat":chat,"date":date_str})` — idempotent overwrite on a manual reset.
   d. `memory_id = memory_manager.remember(summary, collection, metadata={"type":"daily_summary",
      "chat":chat,"date":date_str,"scope":"PRIVATE","user_phone":chat,
      "message_count":len(messages),"source":source})`.
   e. `roll_marker_store.commit(chat, date_str, message_count=len(messages), memory_id=memory_id)`.

## Retry semantics (REQ-MEM-025, REQ-MEM-027 — "bounded retry budget", resolved)

There is **no per-item retry counter**. A (chat, date) that fails to `commit` (summary call
raised, `remember` raised, or the process died between `try_claim` and `commit`) is simply left
un-`committed`:

- its row is either absent or `status='claimed'`; a `claimed` row is re-takeable once
  `claimed_at` is older than `memory.roll.stale_claim_minutes` (120);
- it is retried on **every** subsequent nightly tick (`lookback_days=2`) and **every** startup
  catch-up sweep (`lookback_days=catchup_lookback_days`, 21);
- once the date ages past `catchup_lookback_days` from "today", the sweeps no longer look at it —
  it is then the **US4 backfill's** responsibility (REQ-MEM-028). `run_startup_daily_roll_sweep`
  logs one INFO if it sees an un-`committed` (chat, date) that has aged out, naming the backfill.

**The bound is the lookback window, not a count.** This is deliberate: at prod scale a persistently
failing day means a persistent external problem (OpenAI down for weeks, or a genuinely broken
session) that a retry counter would mask rather than fix, and the backfill is the explicit,
human-approved recovery path for anything older.

## Shutdown

`denidin.py` MUST call `global_context.daily_roll_scheduler.shutdown(wait=False)` in all three
existing shutdown sites (`DeniDin.shutdown()`, the SIGINT/SIGTERM handler, the `finally`),
alongside the reminder + accounting scheduler shutdowns.

## Wiring (`denidin.py __main__`, after `initialize_app` + reminder + accounting sweeps)

```python
run_startup_daily_roll_sweep(denidin)
denidin.daily_roll_scheduler = start_daily_roll_scheduler(
    denidin, roll_hour=denidin.config.memory.get("roll", {}).get("hour", 2)
)
# ... then message_source.start(dispatch_notification)
```

`DeniDin.__init__` gains `daily_roll_scheduler=None` (parallel to
`accounting_reconciliation_scheduler`).

**Never** wired in `initialize_app` (D1).
