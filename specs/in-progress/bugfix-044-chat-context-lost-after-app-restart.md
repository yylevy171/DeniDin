# Bugfix Spec: Chat context lost after app restart

## Bug ID
bugfix-044-chat-context-lost-after-app-restart

## Title
After `denidin-app-prod` was restarted (during the 2026-08-25 production incident response, see
bugfix-043), an in-progress WhatsApp conversation lost its context entirely — the bot behaved as
if the conversation had never happened, and the user had to manually re-provide context that had
already been given earlier in the same conversation.

## Priority
**Not yet triaged.** Reported directly by yaronlev171 as a real production symptom observed
during/after the bugfix-043 restart. Treating as high-attention pending root cause, given it
affects the core session/memory system every conversation depends on — but not stating a formal
priority until root cause is understood (some possible causes below are P0-shaped, others are
more narrowly scoped).

## Status
**Open — root cause NOT YET investigated.** Per Bug-Driven Development (METHODOLOGY.md §VII),
this spec currently only records the reported symptom and available evidence. No code has been
read or changed for this bug yet. Next step is root-cause investigation, to be presented for
human approval before any test-gap analysis or fix work begins — this spec is being filed first,
deliberately, rather than folding investigation and fix together the way bugfix-043 did (a
process mistake corrected in real time, same session).

*(2026-09-02: In progress via Feature 070 — moved from `specs/bugfixes/` to `specs/in-progress/`.
Per explicit user direction 2026-09-01, this is NOT worked as a standalone Bug-Driven Development
track. Feature 070 structurally eliminates the failure mode by design: one long-lived `Session`
per chat resolved through a durable SQLite chat index (`_reconcile_chat_index` rebuilds it from
disk on every restart), so there is no losable in-memory `chat_to_session` state and no
orphan-recovery step to forget to populate; `remove_from_index` and the whole 4-step cleanup are
deleted. Proven by Feature 070 US1 restart scenario + AC-2. See
`specs/done/070-rolling-memory-window/spec.md` §"Legacy Defects". Final closure status note
is added at Feature 070 haleluya.)*

## Date Opened
2026-08-25

## Reported By
yaronlev171, live during the bugfix-043 production incident response.

## Symptom (as reported, verbatim)
> "chat context not loading after restart as seen in production. evidence is the whole conv going
> on since this started. after restart of the app the chat context was completely lost and I
> needed to provide it manually."

## Evidence (pulled 2026-08-25, from real prod logs + real session files — read-only)

The affected chat is `120363210094632983@g.us` ("$$ גבייה אילה $$" group), the same chat as
bugfix-045's evidence — the user's own working conversation with the bot, active right up to and
across the `denidin-app-prod` restart performed during bugfix-043's mitigation (~09:41–09:48
Israel time).

**A session for this exact chat WAS successfully recovered after the restart** — `denidin-app-prod` log:
```
2026-08-25 10:02:46+0300 - __main__ - INFO - Starting orphaned session recovery...
2026-08-25 10:02:46+0300 - src.handlers.ai_handler - INFO - Found 3 orphaned sessions - starting recovery
2026-08-25 10:02:46+0300 - src.handlers.ai_handler - INFO - Recovered active session to short-term: 99d0129e-b60a-458b-9647-d59d51be104f
2026-08-25 10:02:46+0300 - src.handlers.ai_handler - INFO - Session recovery complete: 0 transferred, 3 loaded, 0 failed
```
Confirmed via the real session file on disk (read via the sshfs prod-data mount,
`~/denidin-winprod-data/sessions/99d0129e-.../session.json`):
```
chat: 120363210094632983@g.us
last_active: 2026-08-25T09:29:56.832800+03:00     ← ~12 min before the restart completed
message_counter: 14                                ← real, substantial conversation content
```
So the recovery mechanism *did* reload the right session, with real content, from just before
the restart. **But `99d0129e` is never mentioned again anywhere in the logs after that one
recovery line** — no further activity, no transfer, no removal, nothing.

**The next real incoming message for the same chat, ~5 minutes later, did not use it:**
```
2026-08-25 10:07:28+0300 - AUDIT-IN ... chatId='120363210094632983@g.us' ... textMessage: 'בעעעע…\nתפיק חשבונית מס קבלה:\n\n• לקוחה: גלית סיטבון ...'
...
2026-08-25 10:07:51+0300 - src.managers.session_manager - INFO - Created new session b1cb04eb-4fc8-476c-82e3-89c8c7e8c6b5 for chat 120363210094632983@g.us
```
A **brand-new, empty** session was created for this chat instead of continuing `99d0129e` —
discarding its 14 messages of real, just-recovered context. This is the concrete mechanism behind
the reported symptom: the recovery ran, logged success, and then was never actually used.

**Root cause hypothesis (unconfirmed — needs code review, not yet done):** `run_startup_reminder_sweep`-style
orphaned-session recovery (`ai_handler.py`'s "Session recovery" path, triggered from
`denidin.py`'s `initialize_app`) reloads a session's data into memory and marks it recovered, but
does not appear to register it into whatever index/lookup `SessionManager` consults when a new
inbound message asks "is there already an active session for this chat?" — so the very next
message for that chat falls through to "no active session found → create new one," silently
discarding the just-recovered content. This is a plausible mechanism, not yet verified against
the actual code.

**Secondary, separate finding — a session schema-migration bug** (contributes to the general
health of restart/cleanup, may or may not be part of this specific symptom): one specific old
session repeatedly fails to load at all:
```
2026-08-25 09:49:59+0300 - src.managers.session_manager - ERROR - Failed to load session 0f5eaa04-6277-46ec-8e86-c9cae932170a: __init__() got an unexpected keyword argument 'pending_ledger_events'
2026-08-25 10:02:46+0300 - src.managers.session_manager - ERROR - Failed to load orphaned session 0f5eaa04-...: __init__() got an unexpected keyword argument 'pending_ledger_events'
```
Confirmed via the real session file: `whatsapp_chat: 972522968679@c.us` (a 1:1 chat, **not** the
group chat above), `created_at: 2026-08-03`, `pending_ledger_events: []` present in the persisted
JSON but rejected by the current `Session.__init__` signature — a field that was apparently
removed/renamed in code without a migration path for already-persisted session files. This
session is 3 weeks old and unrelated to the specific incident reported, but it's a real,
reproducible bug in its own right, and is why the "43 expired session(s)" startup count can never
fully clear.

**Related, already-filed, still-open bug actively contributing:** `specs/bugfixes/bugfix-035-hourly-maintenance-bugs.md`
(H1) describes this *exact* symptom — group-chat memory collection names keep the raw `@g.us`
suffix, so `get_collection` always throws `NotFoundError` and long-term-memory transfer can never
complete for any group chat. That bug's `Status` is still **"Open — backlogged. No fix
designed."** and it is actively firing right now, dozens of times, for this exact chat:
```
2026-08-25 10:07:03+0300 - src.handlers.ai_handler - ERROR - Failed to transfer session c18fa3e8-...: Collection [memory_120363210094632983@g.us] does not exist
2026-08-25 10:07:15+0300 - ... Failed to transfer session 6983b990-...: Collection [memory_120363210094632983@g.us] does not exist
2026-08-25 10:07:26+0300 - ... Failed to transfer session dbd3a4f2-...: Collection [memory_120363210094632983@g.us] does not exist
[... repeats for every session cleanup processes for this chat, 09:50:16 "Found 43 expired session(s)" onward]
```
This means: even when a session *does* correctly expire (not the recovery-bug above), its content
can never actually reach long-term memory for this chat either — so context that ages out of the
24h short-term window is not recoverable via memory recall as a fallback. This is not a new bug
being filed here; it's existing evidence that bugfix-035 is unfixed and actively degrading this
exact chat's memory reliability, worth surfacing alongside bugfix-044 since they may compound.

## Affected Area
- `apps/denidin-app/src/handlers/ai_handler.py` — orphaned-session recovery path (primary
  suspect: recovered session not registered as the chat's active session)
- `apps/denidin-app/src/managers/session_manager.py` — active-session-for-chat lookup;
  `Session.__init__`/deserialization (the `pending_ledger_events` schema mismatch)
- `apps/denidin-app/src/managers/memory_manager.py` / `apps/denidin-app/src/services/cleanup_service.py`
  — the already-filed bugfix-035 collection-naming bug, contributing but not new

## Next Steps
1. Present these findings for explicit human approval (this step) before any code is read for a
   fix or any test-gap analysis begins.
2. Once approved: locate the actual code responsible for "recovered session not found by the next
   message's active-session lookup" and confirm the hypothesis against the real implementation
   (not yet done — the above is inferred from logs + session files, not from reading the
   relevant source).
3. Only after that: test-gap analysis → failing test → human approval → minimal fix → verify,
   per METHODOLOGY.md §VII.
4. Separately, flag to the human that bugfix-035 remains open and is actively causing damage
   right now (43+ stuck expired sessions, unbounded retry cost) — worth prioritizing regardless
   of this bug's own resolution.
