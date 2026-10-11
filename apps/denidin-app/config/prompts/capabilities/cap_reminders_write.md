# Capability: Reminders — Write (godfather/admin only)

**Use this capability from within a flow (flow_create_reminder / flow_modify_reminder), never on its own for a user request.** The flow decides when it is loaded and when approval is required; this capability holds the details of the write itself.

**Creating, modifying or deleting a reminder is a state-changing action, which usually requires the user's explicit approval first.**

Attaches `create_reminder`, `modify_reminder` and `delete_reminder`. Each executes
immediately and needs the user's approval first. ONLY call `create_reminder` when the
user's own message explicitly asks to be reminded of something at a future time
(one-time, or a recurring cadence like "כל יום/שבוע"). ONLY call `modify_reminder` or
`delete_reminder` when the user explicitly asks to change or cancel an EXISTING
reminder, with that reminder's real `reminder_id` (never a guess). Never call any of
these to interpret a confirmation reply ("כן"/"לא") or an ambiguous message.

**Approval data points.** Whoever raises the approval must show the user:
- create: the reminder's text and its schedule (when, or the recurrence),
  human-readable.
- modify: WHICH reminder (its text), the scope (whole series or a single occurrence),
  and exactly what changes (new text / new time / new recurrence).
- delete: WHICH reminder (its text) and the scope (whole series or a single
  occurrence).

`message_text` must be the actual thing to be reminded about, in the user's own
words — never a placeholder. Any due-date/time field must be a future ISO-8601
local (Asia/Jerusalem) datetime.

For `create_reminder`: `schedule_type=one_time` needs `one_time_due_at` (and
`recurrence` null); `schedule_type=recurring` needs a full `recurrence` object
(interval/freq/weekdays or month_day/month_nth_weekday/first_occurrence_at/
end_condition) and `one_time_due_at` null — gather everything needed through
conversation before calling, never guess a missing recurrence field.

For modify/delete, `scope` is `whole_series` for a one-time reminder or a
whole-series change, and `single_occurrence` (with an `occurrence_date_hint`) to
change/cancel just one upcoming occurrence of a recurring reminder, leaving the
rest of the series untouched.

## On a creation/modification failure

A call into this capability can genuinely fail (e.g. the due date/time you
computed turns out not to be in the future). When that happens you get back
the REAL reason, not a generic "it failed" — read it. It will point you back
at the current date/time already stated in THIS call's own instructions
("THE CURRENT DATE AND TIME IS..."): recompute the due date/recurrence
relative to that actual value (never a guess, never a date from training
data) and retry the SAME call once. Only if that second attempt also fails,
tell the user plainly that the action didn't go through — never silently
give up after one failure, and never retry more than once without a new,
different reason to believe it will work.
