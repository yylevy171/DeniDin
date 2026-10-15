# Tasks: 102 - Calendar Reminders as WhatsApp Events (.ics)

Convention (METHODOLOGY §VI.b): per phase, Task A = unit/integration tests written FIRST and seen RED;
Task B = implementation to GREEN. Billed tests are authored in the final Acceptance phase and are NOT run
without the user's go-ahead. All runs go through `scripts/run_unit_integration_tests.sh`.

## Phase 1 - Builder and storage (foundation for every story)
- [x] T001A Tests `tests/unit/test_reminder_ics.py`: UID/SEQUENCE/prefix/zero-duration/no VALARM/no VTIMEZONE/TZID, one-time, recurring `RRULE`, `EXDATE` for CANCELLED exceptions, override `VEVENT` with `RECURRENCE-ID`, `METHOD:CANCEL`+`STATUS:CANCELLED`, multi-entry file, file names, `ValueError` cases, DST-crossing series keeps wall-clock time. (REQ-102-02/04, UAT 1.1/2.x)
- [x] T001B Implement `src/utils/reminder_ics.py` (contracts/ics-file-format.md).
- [x] T002A Tests `tests/unit/test_reminder_manager_ics.py`: the `reminders` table is untouched, a pre-feature DB (no sequence table) works and keeps its rows, repeated starts never reset the counter; `claim_ics_sequence` returns 0,1,2... per reminder; `get_for_calendar` returns cancelled reminders + exceptions; `list_for_calendar` active-only in the given order; unknown id -> None/omitted.
- [x] T002B Implement the `ReminderManager` additions (`data-model.md`).

## Phase 2 - Delivery (US1, US2, US4, UAT 3.3)
- [x] T003A Tests `tests/unit/test_whatsapp_handler_calendar_file.py`: `sendFileByUpload` called once with the right arguments; retry once on 5xx; no retry on 4xx; False with no bot; never raises; wire-audited.
- [x] T003B Implement `WhatsAppHandler.send_calendar_file`.
- [x] T004A Tests `tests/unit/test_denidin_send_calendar_file.py`: temp file written under `{data_root}/tmp/reminder_ics/`, deleted after success AND after failure; outbound note stored on success only; False on failure.
- [x] T004B Implement `DeniDin.send_calendar_file`.

## Phase 3 - Automatic file with every create/modify/delete (US1, US2)
- [x] T005A Tests `tests/unit/test_capability_reminders_calendar_file.py` (queue part): successful create/modify/delete queue `PUBLISH`/`PUBLISH`/`CANCEL`; failed (`ReminderError`), unresolvable and no-op modify queue nothing; recurring creates queue too.
- [x] T005B Implement the queueing in `src/capabilities/reminders/handler.py` + `Backbone.queue_reminder_calendar_file`.
- [x] T006A Tests `tests/unit/test_backbone_reminder_calendar_flush.py`: file sent only AFTER the last `send_to_user` of the turn; one combined PUBLISH file + separate CANCEL; delete after create in one turn -> one CANCEL; send failure -> notice sent, reminder untouched; queue empty at the next turn; flush still runs when the conversation raises; a flush error never propagates.
- [x] T006B Implement `src/capabilities/reminders/calendar_file.py` and the backbone flush.
- [x] T007A Integration `tests/integration/test_reminder_calendar_file_102.py`: a real Green API webhook JSON through the router with a scripted AI client (create_reminder then confirmation) -> the confirmation is sent before the `.ics`; a decline ("לא") sends no file (UAT 1.2); recurring creation sends one file carrying `RRULE` (UAT 1.3); modify and delete send update/cancel (UAT 2.1-2.5); a non-godfather client never gets a file (UAT 3.2).
- [x] T007B Make T007A green (wiring only; fix gaps found).
- [x] T007C Tests (inside T007A's file): the approval answered by an `interactiveButtonsResponse` tap sends the file exactly like a typed "כן"; `ReminderDeliveryService` still delivers the text nudge at due time and sends no `.ics` (UAT 1.4).

## Phase 4 - On demand and offered (US4, US5)
- [x] T008A Tests (extend `test_capability_reminders_calendar_file.py`): tool schema; one/several ids -> one file; unknown id -> `⚠️` and nothing sent; duplicate ids deduped; no manager; send failure; the tool is attached with `REMINDERS_READ` and not in `WRITE_TOOL_NAMES`; extend `test_capability_toolsets.py` expectations; a role that is not godfather/admin never gets the tool (REQ-102-06).
- [x] T008B Implement the tool schema, toolset attach, dispatch.
- [x] T009A Tests `tests/unit/test_reminders_calendar_prompts.py`: the prompt files carry the required scope/boundary text (when applies / when NOT / ask when ambiguous / automatic-never-requested / offer after listing with the exact question), `FlowTag.REMINDERS_CALENDAR_FILE` exists with a `FLOW_INFO` entry and a prompt file, the catalog renders it, `backbone.md` boundary line present; EVERY other tool-bearing capability prompt (`cap_agreements_read/write`, `cap_client_read/write`, `cap_docx_write`, `cap_invoicing_read/write`, `cap_ledger_capture`, `cap_ledger_query`, `cap_media_analysis`) carries the calendar-files-are-out-of-scope line (both-directions rule).
- [x] T009B Write the prompts, the new flow, the `FlowTag`/`FLOW_INFO` entry, the `backbone.md` line and the one-line exclusion in each other tool-bearing capability prompt.

## Phase 5 - Quality gates
- [x] T010 Run the full unit + integration suite through the wrapper; lint (`pylint src/ --fail-under=7.0`, mypy) clean for touched files.
- [x] T011 Docs: `CLAUDE.md` architecture note for Feature 102 (reminders section), `.github/ARCHITECTURE.md`: grep it for reminder flows/capabilities and update every mention.

## Phase 6 - Acceptance (billed, authored here, NOT run)
- [x] T012 Author `tests/billed/test_reminder_calendar_file_102.py` - one test per approved scenario:
  UAT 1.1 create+approve -> `.ics` parses (summary prefix, zero duration, no VALARM, no VTIMEZONE) and the reminder is in `reminders.db`; 1.2 decline -> nothing; 1.3 recurring -> one file with `RRULE`; 1.4 the due-time nudge path still delivers (invoked through `ReminderDeliveryService`);
  2.1 modify -> update file with a higher `SEQUENCE`; 2.2 delete -> `METHOD:CANCEL`; 2.3 one occurrence -> master + override; 2.4 skip one -> `EXDATE` and earlier override kept; 2.5 delete series -> CANCEL;
  3.2 client refused, no file; 3.3 forced send failure -> reminder kept and the user told;
  4.1 ask for the file of an existing reminder -> file, no approval step; 4.2 two matches -> asks which, sends nothing; 4.3 no such reminder -> says so, no file;
  5.1 list -> offer; 5.2 accept -> file; 5.3 decline -> nothing; 5.4 unrelated question -> no offer.
  UAT 3.1 stays a manual on-device check (Android, done in Gate Zero 2). The manual checklist (UAT 3.1 and the untested
  unchanged-re-send import) lives in `quickstart.md` under "Manual device checks".
- [x] T013 STOP and report to the user; the first billed run needs their explicit permission.
