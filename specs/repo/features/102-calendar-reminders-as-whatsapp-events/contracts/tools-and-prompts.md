# Contract: tool, delivery methods and prompt changes

## New local tool: `send_reminders_calendar_file`  (attached with `cap_reminders_read`)

```json
{
  "type": "function", "name": "send_reminders_calendar_file", "strict": true,
  "parameters": {
    "type": "object",
    "properties": {"reminder_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1}},
    "required": ["reminder_ids"], "additionalProperties": false
  }
}
```
- Read-only, needs no approval. Not in `WRITE_TOOL_NAMES`.
- Sends ONE `.ics` (PUBLISH, current state, claimed sequence per reminder) with an event per id, to the current chat.
- Result (string, JSON): `{"sent": true, "reminders": <n>, "file_name": "..."}`.
- Failure results begin with `⚠️` (the dispatcher counts those as failures): unknown/inactive id
  (`⚠️ לא נמצאה תזכורת פעילה עם המזהה ...`), no manager (`⚠️ שירות התזכורות אינו זמין כרגע.`), send failed
  (`⚠️ לא הצלחתי לשלוח את קובץ היומן.`). Nothing is sent when any id is unknown.
- Dedupes repeated ids. More ids than the active-reminder cap is simply rejected as unknown.

## Delivery methods
- `WhatsAppHandler.send_calendar_file(chat_id, path, file_name) -> bool`: `sendFileByUpload` through the existing
  `_send_file_with_retry` (retry once on 5xx/timeout, never on 4xx), wire-audited as an outbound file; never raises.
- `DeniDin.send_calendar_file(chat_id, file_name, content: bytes) -> bool`: writes the temp file under
  `{data_root}/tmp/reminder_ics/`, sends, deletes the temp file in `finally`, stores a `[קובץ יומן: <name>]`
  outbound note in the chat's conversation; False (never raises) on any failure.

## Reminder manager additions
- `claim_ics_sequence(reminder_id) -> int`
- `get_for_calendar(reminder_id) -> Optional[dict]`: the row for ANY status (so a cancelled reminder can still produce its CANCEL file) + `exceptions` + `ics_sequence`.
- `list_for_calendar(reminder_ids) -> List[dict]`: ACTIVE reminders only, preserving the given order.

## Backbone
- `Backbone.queue_reminder_calendar_file(reminder_id, method)` - called by the reminders handler after a
  **successful** create/modify/delete only (never for a ReminderError / validation failure / no-op modify).
- `Backbone._flush_reminder_calendar_files(chat_id)` - called in a `finally` after `_run_conversation`; one
  file per pending reminder (CANCEL ones separately, PUBLISH ones combined into one file); on a send
  failure sends the model-independent notice `⚠️ התזכורת נשמרה, אבל לא הצלחתי לשלוח את קובץ היומן.` via
  `DeniDin.send_to_user`. Best effort - never raises. Queue cleared at turn start and after flushing. The call sits in a `finally` inside
  the same `try` that wraps `_run_conversation`, so it runs BEFORE any error reply is produced for that turn.

## Prompt changes (the constitution boundaries, CLAUDE.md "every new tool-bearing feature")
- `cap_reminders_read.md`: documents the new tool; lists WHEN to use it (the user asks for the calendar file of
  reminders; after the user accepts the offer) and WHEN NOT (never for invoices/documents/ledger/agreements;
  never to answer a confirmation reply; ambiguity - several matches - is resolved by asking); after listing
  reminders (any question about reminders, or an explicit list) ask `לייצא את התזכורות שלך לקובץ יומן (ics)?`
  through `approval_with_yes_no_buttons`, send nothing until a yes.
- `cap_reminders_write.md` + `flow_create_reminder.md` + `flow_modify_reminder.md`: state that the calendar
  file is sent automatically after the confirmation text and must never be requested, mentioned as
  pending, or produced by hand.
- New `flow_reminders_calendar_file.md` (+ `FlowTag.REMINDERS_CALENDAR_FILE`, `FLOW_INFO` entry): list -> answer
  -> offer -> on yes call the tool with the chosen ids; on no or silence do nothing more.
- Every other tool-bearing capability prompt (`cap_agreements_read/write`, `cap_client_read/write`, `cap_docx_write`,
  `cap_invoicing_read/write`, `cap_ledger_capture`, `cap_ledger_query`, `cap_media_analysis`) gets one line:
  calendar files (.ics) belong only to the reminders capabilities and are never produced here.
- `config/prompts/backbone.md`: a short line in the boundaries listing that calendar files belong only to the
  reminder capabilities.
