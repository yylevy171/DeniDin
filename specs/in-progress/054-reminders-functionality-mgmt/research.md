# Phase 0 Research: Reminders — Functionality and Management

**Feature**: 054-reminders-functionality-mgmt · **Date**: 2026-08-16

Per CONSTITUTION's NO UNVERIFIED THIRD-PARTY ASSUMPTIONS rule, this feature has exactly one
genuine unverified-third-party-behavior gap. Everything else load-bearing (the `type: "function"`
local-tool pattern, the approval-gate UX, the background-thread pattern, the per-entity-file
storage pattern) is derived from reading this codebase's own already-running, already-verified
code — not a claim about third-party behavior that needs its own live confirmation.

## ⏳ Gate Zero — real proactive `sendMessage`, outside any webhook-response context (OPEN)

**Status**: NOT YET RUN. This is a hard blocker on Phase 5/6/7 of `plan.md` (the delivery
mechanism) being considered done — mirrors exactly how Feature 047's own Gate Zero blocked all
design/implementation work on that feature until a real button round-trip was captured. Nothing
about *this* feature's design is blocked on it (the data model, tool schemas, and approval-gate
mechanism are all independently correct regardless of the outcome) — but `send_proactive_message`
and the delivery thread that calls it must not be merged as "done" until this is closed.

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

## ✅ `icalendar`/`recurring_ical_events` — timezone-awareness preservation (non-live, pure-library sanity check)

**Status**: design confirmed 2026-08-16 to use real iCalendar (RFC5545) data — `icalendar` for
VEVENT (de)serialization and `recurring_ical_events` for resolving concrete due occurrences
(RRULE expansion + RECURRENCE-ID overrides + STATUS=CANCELLED suppression), superseding an
earlier design draft that called `dateutil.rrule` directly. Both are pure computation libraries,
not third-party *services* DeniDin integrates with at runtime, so neither is itself subject to
the "must be a live call" Gate Zero rule the way Green API/OpenAI/Morning are. Still recorded here
because this codebase has a hard, mandatory, previously-violated-once (bugfix-037's predecessor
issues) rule that every datetime everywhere is aware Asia/Jerusalem, never naive, never UTC — so
any new date-handling dependency's behavior on this specific point is worth a recorded, deliberate
check rather than an assumed one. (`dateutil.rrule`'s own tz-preservation behavior, checked prior
to this design revision, still applies transitively — both `icalendar` and `recurring_ical_events`
are built on `dateutil` internally — but is no longer this feature's own direct dependency.)

**Still to verify (cheap, non-live — before `ReminderManager`'s sweep-resolution code is written,
not blocking on Gate Zero R1)**:
1. That an `icalendar.Calendar`/`vDDDTypes` round-trip preserves an aware `Asia/Jerusalem`
   `DTSTART` (both winter `+02:00` and summer `+03:00` offsets, since Israel observes DST) without
   silently normalizing to UTC or dropping tzinfo — `icalendar` is known to support `VTIMEZONE`
   but the exact behavior when constructing VEVENTs programmatically (not parsed from a `.ics`
   file with an explicit `VTIMEZONE` block) needs a real snippet, not an assumption from docs.
2. That `recurring_ical_events.of(cal).between(window_start, window_end)` efficiently handles a
   `never`-ending RRULE queried against a narrow future window (e.g. the next 5 minutes) — i.e.
   that it does not internally enumerate the whole recurrence history from `DTSTART` forward every
   call, which would degrade over a long-lived `never`-ending reminder's lifetime. Both of these
   are ordinary `tests/unit/` coverage once written (constructing a calendar, asserting `.tzinfo`
   and timing behavior), not a live third-party call — just flagged here before the sweep code is
   written so nothing gets built on an unverified read of either library's documentation.
