# Quickstart: Manual Verification — Reminders

**Feature**: 054-reminders-functionality-mgmt · **Date**: 2026-08-16

Manual scenarios complementing (not replacing) the automated suite — run against a real `dev`
environment with real WhatsApp/Green API/OpenAI traffic, per this project's usual E2E verification
discipline. Each scenario needs its own explicit approval to run, per CLAUDE.md's environment-start
rules — this document does not itself authorize starting anything.

## 0. Gate Zero — live proactive send (blocking prerequisite, see `research.md`)

Before any scenario below that depends on real delivery: confirm `bot.api.sending.sendMessage()`
actually delivers a message to a real device when called outside a webhook-response context.
Capture the raw request/response in `research.md`.

## 1. Create a one-time reminder (text approval)

As the godfather, from their own 1:1 chat: *"remind me to call the accountant in 10 minutes"* →
confirm the AI presents an approval summary with the **rounded** time (nearest 5 minutes) → reply
`כן` → confirm a confirmation message, phrased naturally (not a hardcoded template) → wait for the
sweep tick → confirm the reminder text (prefixed "תזכורת: ") arrives in the same chat it was
created from (`delivery_chat_id`), and the underlying `fired_occurrences` row exists.

## 2. Create a one-time reminder (button approval)

Same as above, but tap the "כן" button instead of typing it. Confirm identical behavior.

## 3. Decline a proposed reminder

Propose a reminder, reply `לא` (or tap "לא") → confirm nothing was persisted (no new row in
`reminders`).

## 4. Past-dated request rejected

*"remind me to call the accountant yesterday at 5pm"* → confirm a friendly rejection, re-prompt
for a valid date, no reminder created.

## 5. Cap enforcement

With 20 already-active reminders (script/manually seed the DB for this — creating 20 by hand via
conversation is impractical): attempt a 21st → confirm friendly decline naming the cap.

## 6. Recurring reminder — weekly

*"remind me every Monday and Thursday at 10am to check invoices"* → confirm the approval summary
states the cadence in plain language → approve → inspect the `reminders` row's `RRULE`
(`FREQ=WEEKLY;BYDAY=MO,TH`) directly in the SQLite file.

## 7. Recurring reminder — monthly, Nth weekday

*"remind me the first Monday of every month at 9am"* → confirm correct `RRULE`
(`FREQ=MONTHLY;BYDAY=1MO`) and that the computed first occurrence lands on the actual next first-
Monday.

## 8. Recurring reminder — end conditions

Create one with "for 3 occurrences" (`COUNT=3`) and one with "until end of the year"
(`UNTIL=...`) → let the count-bounded one fire 3 times across real sweep ticks → confirm no 4th
ever fires.

## 9. Modify a one-time reminder

Create a one-time reminder, then *"actually make that 3pm instead"* → confirm the system
identifies it (no scope question, since it's not recurring), applies the change, re-approval gate
applies.

## 10. Delete a one-time reminder

Same setup, *"cancel that reminder"* → confirm deletion after approval.

## 11. Modify a single occurrence of a recurring reminder

With the weekly reminder from #6 active: *"push this Thursday's to 5pm instead"* → confirm the
system asks/confirms scope = single occurrence → approve → inspect `reminder_exceptions` for the
new row (`RECURRENCE-ID` = the original Thursday date, `dtstart_override` = the new 5pm time) →
confirm next Monday's occurrence is unaffected.

## 12. Modify a whole series (the "Monday→Tuesday, 17:00→18:00" case)

With the same weekly reminder: *"actually move the whole thing to Tuesdays at 18:00"* → confirm
scope = whole series → approve → inspect the `reminders` row's updated `RRULE`/`DTSTART` →
confirm the Thursday exception from #11 is **untouched** (still present, still overriding its own
original date) — this is the single most important assertion in this whole document, since it's
the one most likely to silently regress.

## 13. Delete a single occurrence

*"skip next week's"* → confirm only that one `reminder_exceptions` row (`status=CANCELLED`) is
created, the rest of the series continues.

## 14. Delete a whole series

*"cancel the whole recurring reminder"* → confirm `reminders.status='cancelled'`, all pending
exceptions marked cancelled, `fired_occurrences` history untouched.

## 15. Ambiguous target disambiguation

With 2+ active reminders sharing a similar phrase in their message text, ask to modify/delete "it"
vaguely → confirm the AI calls `list_reminders` and asks which one, rather than guessing.

## 16. Client/blocked role denied

From a CLIENT or BLOCKED-role number, attempt to create/list/modify/delete a reminder → confirm
declined the same way other godfather/admin-only tools are.

## 17. Admin acts on the godfather's behalf

From the ADMIN number, in the admin's own 1:1 chat, create a reminder → confirm it fires to the
**admin's own** 1:1 chat (`delivery_chat_id` = the chat it was created from), not the godfather's.
Then simulate a failed send to the admin's chat and confirm the fallback goes to the admin's own
1:1 too (`created_by_phone` = the admin, not the godfather) — never the godfather's chat, since the
admin performed the action.

## 18. Restart-survives-and-catches-up

With a reminder due imminently: stop the `denidin-app-dev` container just before it's due, wait
past the due time, restart → confirm `run_startup_reminder_sweep()` catches it and it fires late
rather than being silently skipped.

## 19. Group-chat creation fires back to the group

Create a reminder from a group chat DeniDin is in (as the godfather or admin) → confirm it fires
to that **same group** (`delivery_chat_id`), not the creator's 1:1 chat. Then simulate the group
being unreachable (e.g. temporarily block delivery) and confirm the fallback goes to the actual
creator's own 1:1 chat.
