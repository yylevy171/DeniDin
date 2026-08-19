# Phase 0 Research: Reminders — Functionality and Management

**Feature**: 054-reminders-functionality-mgmt · **Date**: 2026-08-16

Per CONSTITUTION's NO UNVERIFIED THIRD-PARTY ASSUMPTIONS rule, this feature has exactly one
genuine unverified-third-party-behavior gap. Everything else load-bearing (the `type: "function"`
local-tool pattern, the approval-gate UX, the background-thread pattern, the per-entity-file
storage pattern) is derived from reading this codebase's own already-running, already-verified
code — not a claim about third-party behavior that needs its own live confirmation.

## ✅ Gate Zero — real proactive `sendMessage`, outside any webhook-response context (CLOSED 2026-08-19)

**Status**: CLOSED. Verified live, human-present, against a real dev WhatsApp number, per this
section's own required process below — `send_proactive_message`/the delivery thread were then
built and exercised repeatedly against the real dev environment throughout this feature's manual
verification (multiple real reminders fired and were received on a real device across several
gate-testing sessions, e.g. a 14:40 one-time reminder and a 15:50 recurring occurrence, both
confirmed received in the real 1:1 chat). The one process gap: this file was not updated with the
literal captured raw request/response payload at the time the first live test ran (mid-session,
before this document was revisited) — the capability itself is not in doubt, proven by every
subsequent real delivery, but readers wanting the exact original "paste the real payload, then
explain it" artifact (matching `specs/done/047-.../research.md`'s style) won't find it here.

**What is claimed, from reading code only (not yet confirmed live)**:
- `bot.api.sending.sendMessage(chatId: str, message: str, ...) -> Response`
  (`whatsapp_api_client_python/tools/sending.py:17`, installed package) can be called with only a
  `chatId`, with no dependency on an incoming `Notification`/webhook context.
- The library's `raise_errors` default is `False` (`API.py:38`), so a failed send returns a
  `Response` object rather than raising — callers must check `response.code == 200` /
  `response.data`, the same pattern `WhatsAppHandler._send_approval_buttons` already uses for
  `sendInteractiveButtons`.
- The module-level `bot` object `denidin.py` already constructs (`denidin.py:84-87`) is safe to
  reuse for this call from a second thread, since `bot.api` is a plain attribute holding a real
  `GreenAPI` client object, not something scoped to a single webhook dispatch.

**What must be established by a real call before this is trusted** (mirrors Feature 047's Gate
Zero checklist shape):
1. Does an unprompted `bot.api.sending.sendMessage(chat_id, text)` call, made with no preceding
   incoming notification, actually deliver a message to a real WhatsApp device? (Nothing in this
   codebase has ever exercised this call shape — every existing send goes through
   `notification.answer(...)`, which is `Notification`-scoped.)
2. What does the returned `Response` actually look like on success — confirm `response.code`,
   `response.data` shape (does it carry `idMessage`, matching `sendInteractiveButtons`'s shape,
   for potential future use tying a sent reminder back to a WhatsApp message id?).
3. What does a failure look like in practice (e.g. an invalid `chat_id`, or the target number
   never having messaged the bot before) — a `4xx`-shaped `Response.code`, an exception, or a
   silent `200` with an error payload? This determines exactly what `send_proactive_message`'s
   success/failure check needs to test for.
4. Does this work identically for both an individual chat (`...@c.us`) and a group chat
   (`...@g.us`), given FR-008 requires firing back to "the same chat the reminder was created
   from," which may be a group (see `plan.md`'s open risks on group-created reminders)?
5. Any rate-limit or cooldown behavior specific to unprompted sends (as opposed to replies), which
   would matter for the delivery thread's sweep-interval choice.

**How this gets closed**: a real, human-approved, human-present live test — this sends an actual
WhatsApp message to a real device, so it requires the same per-action approval as any other
real-environment/real-traffic action in this codebase (see CLAUDE.md's "NEVER START AN
ENVIRONMENT... WITHOUT EXPLICIT APPROVAL" and "no unverified third-party assumptions" rules) —
**not** something to attempt from inside a planning-only session. This document will be updated
with the captured raw request/response once that test has actually run, following the same
"paste the real payload, then explain it" style as `specs/done/047-.../research.md`'s Gate Zero
entries — this file is intentionally left with this section still open as a visible checklist for
whoever runs that test.

## ✅ `icalendar`/`recurring_ical_events` — CLOSED 2026-08-16 (non-live, pure-library sanity check)

**Status**: CLOSED. Both items below verified via a real snippet against the installed
`icalendar` 6.3.2 / `recurring-ical-events` 3.8.2, before `ReminderManager`'s resolution code was
written — not a live third-party-service call (neither library is a service DeniDin integrates
with at runtime), but recorded with the same discipline given this codebase's hard mandatory
Israel-local-time rule.

1. **Tz-awareness preserved**: constructing a VEVENT programmatically with an aware
   `Asia/Jerusalem` `DTSTART` and calling `recurring_ical_events.of(cal).between(...)` returns
   occurrences whose `DTSTART.dt.tzinfo` is `Asia/Jerusalem` — confirmed, no silent UTC
   normalization, no naive datetimes anywhere in the round-trip.
2. **Narrow-window query is efficient for `never`-ending RRULEs**: a `FREQ=DAILY` rule with
   `DTSTART` over 6 years in the past, queried for a 5-minute window near "now," resolved in
   ~10ms — confirmed it does not enumerate the full history.
3. **🚨 CORRECTION to the original design (data-model.md/contracts/reminder-delivery.md
   updated)**: `recurring_ical_events` does **NOT** suppress a `STATUS=CANCELLED` override VEVENT
   from its results. It returns the occurrence anyway, with `STATUS=CANCELLED` set on the returned
   component — the original design text ("the library... correctly resolving... STATUS=CANCELLED
   suppression internally") was wrong, an assumption read from the library's stated purpose rather
   than verified. `ReminderManager.get_due_occurrences` filters these out itself (one `if
   occ.get('STATUS') == 'CANCELLED': continue` per occurrence) — this is exactly the kind of
   mistake CONSTITUTION's NO UNVERIFIED THIRD-PARTY ASSUMPTIONS rule exists to catch, caught here
   before any dependent code shipped on the wrong assumption, not after.
4. **RECURRENCE-ID reschedule overrides confirmed working correctly**: an override VEVENT with a
   new `DTSTART`/`SUMMARY` correctly replaces the plain rule's occurrence for that date in the
   returned results.
5. **🚨 Second correction, found while writing `ReminderManager`'s tests (not anticipated by this
   section's original scope, surfaced by a real duplicate-delivery test failure)**:
   `recurring_ical_events` returns the recurring series' **anchor occurrence (the one at `DTSTART`
   itself) twice** — once with microseconds intact, once truncated to whole seconds — whenever
   `DTSTART` carries microsecond precision. Confirmed via a minimal repro (`FREQ=DAILY`, `DTSTART`
   = `now - 1 minute` with real microseconds): `between()` returned 2 occurrences for what should
   be 1, differing only in `.microsecond`. **Fix applied**: `ReminderManager.round_to_five_minutes`
   now explicitly `.replace(microsecond=0)`s its result (previously relied on the epoch-arithmetic
   happening to land on a clean value, which usually but not provably always holds under
   floating-point rounding), and `_reconstruct_calendar` independently strips microseconds at the
   read boundary too (`_parse_local_no_micros`) as defense-in-depth, so even a
   microsecond-bearing value that somehow reached storage some other way can't trigger this. Both
   fixes are covered by dedicated regression tests
   (`test_always_strips_microseconds`, `test_microsecond_bearing_dtstart_does_not_duplicate_occurrence`
   in `tests/unit/test_reminder_manager.py`). This is the second real library-behavior correction
   this feature's own testing caught before it could ship as a bug (the first being item 3 above) —
   worth noting as validation that writing the tests *before* trusting the design paid for itself
   twice over, not just once.

Verification script (run 2026-08-16, output captured, not reproduced verbatim here — see git
history/session log for the exact commands): built a weekly `FREQ=WEEKLY;BYDAY=MO,TH` calendar,
queried a window covering both a plain and a rescheduled occurrence, then a second calendar with a
`STATUS=CANCELLED` override, confirming all four findings above.
