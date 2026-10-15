# Implementation Plan: 102 - Calendar Reminders as WhatsApp Events (.ics)

**Branch**: `feature/102-calendar-reminders-as-whatsapp-events` | **Spec**: `spec.md` | **Stories**: `user-stories.md` (scenarios approved 2026-10-15)
**Gate**: acceptance scenarios approved by the user 2026-10-15 (METHODOLOGY §VI.a) - satisfied.

## Summary

Every reminder DeniDin creates, changes or deletes (one-time or recurring) also produces an
iCalendar `.ics` file sent into the chat, after the model's confirmation text; the user can also ask
for the file of any existing reminder, and DeniDin offers it when reminders are listed. Native
WhatsApp event cards are impossible (Gate Zero 1); `.ics` behavior on Android was verified live
(Gate Zero 2, `spec.md` section 2). No new storage engine: `reminders.db` stays the source of truth and
the `.ics` is generated from it on demand.

## Technical Context

- **Language/stack**: Python 3.11, the existing `denidin-app` (Starlette-free bot; Green API via
  `whatsapp-api-client-python`; `icalendar` already a dependency, `recurring_ical_events` for occurrences).
- **Storage**: existing SQLite `reminders.db` (`reminders`, `reminder_exceptions`, `fired_occurrences`),
  plus ONE new column `reminders.ics_sequence`.
- **Testing**: pytest through `scripts/run_unit_integration_tests.sh`; billed tests authored only, run only
  with the user's go-ahead.
- **Constraints**: backbone only (the legacy `AIHandler` path is gone). No environment variables, no
  monkey-patching, `pathlib`, `now_local()`, no feature flag (PM decision 2026-10-15).
- **Unknowns**: none remaining (all NEEDS CLARIFICATION resolved in `research.md`).

## Constitution Check

| Rule | Status |
| :-- | :-- |
| No env vars; config via `AppConfiguration` | OK - no new config key; temp dir is a fixed subpath of `data_root` |
| Israel local time via `now_local()` | OK - the builder converts stored local ISO values to `Asia/Jerusalem` |
| No monkey-patching / DI | OK - new methods on existing classes, called through `DeniDin` |
| `pathlib.Path` | OK |
| Feature flag | None (explicit PM decision) |
| Tool-bearing feature needs explicit boundaries in the prompts (CLAUDE.md, METHODOLOGY §XXI) | OK - see `contracts/prompts.md`; `runtime_constitution.md` no longer exists, the prompts under `config/prompts/` are the constitution now |
| Unit/integration tests written first, RED then GREEN | OK - see `tasks.md` |
| Integration tests simulate a real entry point (webhook through the router) | OK - T-INT tasks |
| Ledger `CURRENT_SCHEMA_VERSION` untouched | OK - nothing here writes ledger events |
| Version/release decisions human-only | OK - no release is cut by this feature |

Re-check after design: still OK (no new violation introduced in Phase 1).

## Design (summary; detail in `research.md`, `data-model.md`, `contracts/`)

1. **`src/utils/reminder_ics.py`** (new, pure): builds the `.ics` bytes from reminder rows (REQ-102-02).
2. **`ReminderManager`**: `ics_sequence` column (idempotent migration), `claim_ics_sequence()`,
   `get_for_calendar()` (any status, with exceptions), `list_for_calendar()`.
3. **Delivery**: `WhatsAppHandler.send_calendar_file()` + `DeniDin.send_calendar_file()` (temp file under
   `{data_root}/tmp/reminder_ics/`, deleted in `finally`, outbound note stored).
4. **Automatic send (REQ-01/04, ordering REQ decision 3)**: the reminders handler *queues* a pending
   calendar file on every successful create/modify/delete; the backbone *flushes* the queue when the
   conversation pauses, i.e. after the model's confirmation text.
5. **On-demand and offered (REQ-09/10)**: new local tool `send_reminders_calendar_file(reminder_ids)` in
   `cap_reminders_read`; new flow `flow_reminders_calendar_file` (list -> offer with
   `approval_with_yes_no_buttons` -> send).
6. **Prompts**: `cap_reminders_read.md`, `cap_reminders_write.md`, `flow_create_reminder.md`,
   `flow_modify_reminder.md`, new flow file, `FlowTag`/`FLOW_INFO` entry, backbone boundary lines.

## Project Structure (touched files)

```text
apps/denidin-app/
  src/utils/reminder_ics.py                       NEW
  src/managers/reminder_manager.py                + ics_sequence, claim_ics_sequence, get_for_calendar, list_for_calendar
  src/handlers/whatsapp_handler.py                + send_calendar_file
  denidin.py                                      + DeniDin.send_calendar_file
  src/capabilities/reminders/handler.py           queue on write success; dispatch send_reminders_calendar_file
  src/capabilities/reminders/calendar_file.py     NEW (build + send one file for N reminders)
  src/tool_actions/tool_schemas.py                + SEND_REMINDERS_CALENDAR_FILE_TOOL
  src/capabilities/toolsets.py                    REMINDERS_READ also attaches the new tool
  src/backbone/backbone.py                        pending queue + flush after the conversation
  src/backbone/flow_tags.py                       + FlowTag.REMINDERS_CALENDAR_FILE, FLOW_INFO
  config/prompts/{capabilities,flows}/...         prompt updates + new flow + exclusion line in the 10 other tool-bearing capability prompts
  tests/unit/test_reminder_ics.py, test_reminder_manager_ics.py, test_whatsapp_handler_calendar_file.py,
        test_denidin_send_calendar_file.py, test_capability_reminders_calendar_file.py,
        test_backbone_reminder_calendar_flush.py, test_reminders_calendar_prompts.py           NEW
  tests/integration/test_reminder_calendar_file_102.py                                           NEW
  tests/billed/test_reminder_calendar_file_102.py                                                NEW (authored, not run)
```
