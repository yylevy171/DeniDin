# Integration Contracts: Reminder Delivery

**Feature**: 054-reminders-functionality-mgmt · Per METHODOLOGY.md §VII format.

---

### Scheduling: APScheduler `BackgroundScheduler` + one `CronTrigger` job (new: `src/services/reminder_delivery_service.py`)

**MUST** register exactly **one** APScheduler job for the whole process — never one job per
reminder (the original design guardrail: a single shared delivery mechanism, not one per
reminder):

```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

scheduler = BackgroundScheduler()
scheduler.add_job(
    func=lambda: _sweep_due_reminders(global_context, bot),
    trigger=CronTrigger(minute="*/5"),   # wall-clock-aligned: :00, :05, :10, ..., :55
    id="reminder_sweep",
    max_instances=1,                      # a slow tick must not overlap the next one
)
scheduler.start()
```

Wall-clock alignment (not a `time.sleep(300)` loop drifting from an arbitrary process-start
offset) is the whole reason for using `CronTrigger` here rather than a hand-rolled loop — the
sweep always runs at `:00`/`:05`/.../`:55`, matching the 5-minute rounding applied to reminder
times at creation (see `data-model.md`), so a reminder is guaranteed to become due exactly on a
sweep tick, never between two ticks.

**`run_startup_reminder_sweep(global_context, bot)` (module-level function) MUST** run
synchronously on the main thread **before** `scheduler.start()` — mirrors `run_startup_cleanup()`'s
precedent (`services/cleanup_service.py`) for catching anything that became due while the process
wasn't running (container restart). Calls the exact same `_sweep_due_reminders` the periodic job
calls — one shared implementation, two call sites.

**`denidin.py` MUST** construct and start this scheduler unconditionally (no feature flag — RBAC
alone gates reminder *creation*, but the delivery mechanism itself has no reason to be conditional
beyond "does at least one active reminder exist," which the sweep query itself already handles as
a no-op when the answer is no), store it as `denidin.reminder_scheduler`, and call `.shutdown()`
on it in both the SIGINT/SIGTERM handler and the `__main__` `KeyboardInterrupt` block, alongside
the existing `denidin.cleanup_thread.stop()` calls.

**🚨 Correction, caught during implementation (2026-08-17)**: this wiring is deliberately placed in
the `if __name__ == "__main__":` block, **NOT** inside `initialize_app()` as an earlier draft of
this contract said. `initialize_app()` is the shared bootstrap `tests/integration/` calls directly
(a process-global `denidin_app` singleton reused across test files) — starting a real
`BackgroundScheduler` against the real `bot` object there would let an ordinary test run reach
`bot.api.sending.sendMessage` unattended, using `config.test.json`'s real (not sandboxed) Green
API credentials. No actual harm occurred (verified: `test_data/reminders/reminders.db` had zero
rows at the time this was caught), but the structural risk was real. Every other genuine
`bot.api` call in this codebase (`mark_message_read`, `send_typing_indicator`) is safe in tests
only because its trigger point (`bot.on_notification_received`, fired from `run_forever()`'s live
polling loop) is never reached by any test — they dispatch straight to router handler functions
instead. The reminder scheduler now follows that same discipline: started alongside
`bot.run_forever()` itself in `__main__`, never inside the shared test-reachable bootstrap.

---

### `_sweep_due_reminders(global_context, bot)` (shared worker, module-level function)

For every `reminders` row with `status = 'active'`:

1. Reconstruct an `icalendar.Calendar` for this reminder: the master VEVENT (`UID=reminder_id`,
   `RRULE` if recurring, `DTSTART`, `SUMMARY=message_text`), plus one override VEVENT per matching
   `reminder_exceptions` row (shared `UID`, `RECURRENCE-ID`, `DTSTART`/`SUMMARY` if overridden,
   `STATUS`).
2. **Correction, caught during implementation (2026-08-17)**: the window actually implemented is
   backward-looking, not the forward 5-minute window an earlier draft of this contract described —
   `window_start = now - lookback`, `window_end = now` (this tick's wall-clock time) — so a sweep
   run after any downtime (container restart) still catches anything that became due while the
   process wasn't running, which a fixed 5-minutes-forward window could never do.
   **Further correction (2026-08-18, user decision)**: `lookback` is NOT one constant - it's
   `STARTUP_SWEEP_LOOKBACK` (24h), used only by `run_startup_reminder_sweep`'s one-time boot call,
   vs. `PERIODIC_SWEEP_LOOKBACK` (1h), used by the recurring APScheduler tick. Splitting these
   closes a real risk the single-24h-bound design had: if `fired_occurrences` bookkeeping is ever
   wrong (a "sent" row that fails to persist correctly), a wide window on EVERY periodic tick would
   let the same already-delivered occurrence be silently re-picked-up and re-sent on every
   subsequent tick for up to 24h. The narrower periodic bound caps that blast radius to at most 1h
   of repeated resends, while the startup sweep - the one mechanism actually responsible for
   surviving real downtime - keeps the generous 24h margin.
   `ReminderManager.get_due_occurrences(window_start, window_end)` calls
   `recurring_ical_events.of(cal).between(...)` internally, passing `window_end + 1 microsecond` —
   `between()` is exclusive of its own end argument (live-verified 2026-08-17), so without this an
   occurrence due at exactly `now` would depend on incidental scheduler-vs-clock-read latency to be
   picked up on its own tick rather than the next one; `get_due_occurrences`'s own public contract
   is end-inclusive (`[window_start, window_end]`) precisely so callers never have to think about
   this. This resolves RRULE expansion and RECURRENCE-ID reschedule overrides; nothing about that
   math is hand-written (see `data-model.md`). It does **not** suppress `STATUS=CANCELLED`
   occurrences (live-verified 2026-08-16) — `ReminderManager` filters those out itself, one `if`
   check per returned occurrence, before anything is treated as due.
3. For each concrete non-cancelled occurrence returned as due:
   a. `message_text = occurrence's SUMMARY` (already resolved to the override text if this
      occurrence came from a `reminder_exceptions` row, else the master's `message_text`).
   b. `id_message = send_proactive_message(bot, godfather_chat_id, message_text)` — see below.
   c. If `id_message is not None` (send succeeded): insert a `fired_occurrences` row
      (`occurrence_datetime`, `delivered_at=now_local()`, `message_text_sent`); call
      `session_manager.add_message(chat_id=godfather_chat_id, role="assistant",
      content=message_text, user_role=<godfather's resolved role>, recipient=godfather_chat_id)`
      so the delivered reminder shows up in that chat's session history like any other assistant
      message (mirrors `ai_handler.py`'s existing outbound-message persistence call).
   d. If `id_message is None` (send failed): log at ERROR, do **not** insert a `fired_occurrences`
      row — the occurrence remains due and will be picked up again on the next sweep tick (the
      sweep interval itself is the retry cadence; no separate retry/backoff state).
4. `godfather_chat_id` is computed once per sweep tick as `f"{config.godfather_phone}@c.us"` —
   never read from a per-reminder field (none exists — see `data-model.md`'s Ownership section).

One-time reminders (`rrule IS NULL`) go through the identical code path — a VEVENT with no RRULE
is just a single-instance calendar event to `recurring_ical_events`, so there is no special-case
branch for "one-time vs. recurring" anywhere in the sweep logic.

**Concurrent due occurrences** (spec's edge case): the sweep is a plain sequential loop over all
active reminders within one tick, on one thread (`max_instances=1` on the APScheduler job
prevents two ticks ever running concurrently with each other too) — "no ordering guarantee" is
satisfied trivially since there is exactly one thread doing the sending.

---

### `send_proactive_message` (new function, `src/utils/green_api_bot.py`)

```python
def send_proactive_message(bot: Any, chat_id: str, message: str) -> Optional[str]:
    """Send an unprompted WhatsApp message (not a reply to any incoming notification).

    Returns the sent idMessage on success, None on failure (logged, never raised) - same
    best-effort convention as mark_message_read/send_typing_indicator in this module.
    """
```

Calls `bot.api.sending.sendMessage(chat_id, message)` directly on the shared module-level `bot`
object (never a second `GreenAPIBot` instance — its constructor drains pending notifications as a
side effect, must only ever happen once for the one real bot instance, per `denidin.py`'s existing
documented constraint). Checks `response.code == 200` (the library's `raise_errors` default is
`False`, so a failed send returns a `Response` rather than raising — same pattern
`WhatsAppHandler._send_approval_buttons` already uses).

**No lock** around this call, by explicit user decision — `bot.api.session` (a plain
`requests.Session()`) is shared with the existing polling loop's own concurrent HTTP calls, which
is not a proven-thread-safe pattern, but is an accepted, unmitigated residual risk (low
probability, low impact if it manifests — an occasional HTTP hiccup, not data corruption),
revisited only if the live Gate-Zero test (`research.md`) or real usage surfaces an actual
problem.

---

### Rounding (applied at `ReminderManager` creation/modification time, not in the sweep)

Every user-supplied due datetime (one-time `due_at`, recurring `dtstart`, and single-occurrence
override `due_at` alike) is rounded to the nearest 5 minutes (ties round up) **before** being
shown in the approval summary and **before** being persisted — so what the user approves is
exactly what will fire, and every stored `DTSTART`/`RECURRENCE-ID`/override datetime already lands
on a sweep-tick boundary by construction.
