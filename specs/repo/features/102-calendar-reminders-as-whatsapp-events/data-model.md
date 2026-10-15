# Data Model: 102 - Calendar Reminders as WhatsApp Events (.ics)

## Schema change (the only one): a new table, no change to `reminders`

```sql
CREATE TABLE IF NOT EXISTS reminder_ics_sequences (
    reminder_id TEXT PRIMARY KEY REFERENCES reminders(reminder_id),
    next_sequence INTEGER NOT NULL
);
```

- Created by `ReminderManager._init_schema` with `IF NOT EXISTS`: no `ALTER TABLE`, no migration step, and the
  `reminders` table (pinned exactly by the existing approved schema test) is untouched. A reminder with no row
  (every reminder that pre-dates this feature) starts at 0.
- Semantics: the `SEQUENCE` the **next** file for that reminder will carry.
  `claim_ics_sequence(reminder_id)` returns the stored value (0 when there is no row) and stores value+1.
- `get_for_calendar` reports the stored value as `ics_sequence` (read only).
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
