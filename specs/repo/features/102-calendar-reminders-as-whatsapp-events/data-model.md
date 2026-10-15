# Data Model: 102 - Calendar Reminders as WhatsApp Events (.ics)

## Schema change (the only one)

`reminders.ics_sequence INTEGER NOT NULL DEFAULT 0`

- Added by an idempotent migration in `ReminderManager._init_schema` (`PRAGMA table_info(reminders)`; `ALTER TABLE ... ADD COLUMN` only
  when missing). Existing rows get 0. A fresh DB creates the column in `CREATE TABLE`.
- Semantics: the `SEQUENCE` the **next** file for that reminder will carry.
  `claim_ics_sequence(reminder_id)` returns the stored value and stores value+1 (one transaction).
- No other table changes. `reminder_exceptions` and `fired_occurrences` are unchanged.

## Calendar entry (in-memory value object passed to the builder)

| Field | Source |
| :-- | :-- |
| `reminder_id` -> `UID` | `reminders.reminder_id` |
| `message_text` -> `SUMMARY` (prefixed) | `reminders.message_text` |
| `dtstart` -> `DTSTART` = `DTEND` | `reminders.dtstart` (ISO local) converted to `Asia/Jerusalem` |
| `rrule` -> `RRULE` | `reminders.rrule` (None for one-time) |
| `sequence` -> `SEQUENCE` | claimed `ics_sequence` |
| `exceptions[]` | `reminder_exceptions` rows: `recurrence_id`, `dtstart_override`, `summary_override`, `status` |

Exception mapping (verified on Android, Gate Zero 2):
- `status == "CANCELLED"` -> `EXDATE` on the master (recurrence_id converted to `Asia/Jerusalem`);
- otherwise -> an override `VEVENT` (same `UID`, `RECURRENCE-ID`, new `DTSTART`/`DTEND`, `SUMMARY` =
  prefix + (`summary_override` or master text), `SEQUENCE` = the file's sequence).

## Pending calendar file (per turn, in memory on the `Backbone`)

`_turn_pending_calendar_files: Dict[reminder_id, method]` with `method in {"PUBLISH", "CANCEL"}`.
Cleared at turn start; last operation per reminder wins (a delete turns it into `CANCEL`); flushed after
the conversation pauses. Never persisted.

## State of a reminder vs its file

| Reminder operation | File |
| :-- | :-- |
| create | PUBLISH, master only (+ none) |
| modify whole | PUBLISH, master + all existing overrides, claimed sequence |
| modify one occurrence / skip one | PUBLISH, master (with `EXDATE`s) + overrides |
| delete (one-time or whole series) | CANCEL, master with `STATUS:CANCELLED` |
| on-demand / offered | PUBLISH of the current state (active reminders only) |
