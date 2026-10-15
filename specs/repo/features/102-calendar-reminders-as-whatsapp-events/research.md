# Research: 102 - Calendar Reminders as WhatsApp Events (.ics)

All decisions below are grounded in the Gate Zero results (`spec.md` section 2) or in the current code.

## R1 - Native WhatsApp event card
- **Decision**: not used. **Evidence**: Gate Zero 1 (no send method found among 25 names + docs; an incoming
  event produced no webhook). **Alternatives**: other gateway (rejected: a WhatsApp-layer migration).

## R2 - File format and delivery
- **Decision**: `.ics` via the existing `sendFileByUpload` path (the same call Feature 083 uses for docx).
- **Evidence**: Gate Zero 2 on the PM's Android phone - opens, creates, updates, cancels.

## R3 - Event shape
- **Decision**: `DTEND == DTSTART`, no `VALARM`, `SUMMARY = "דנידין תזכורת: " + message_text`,
  `UID = reminder_id`, `METHOD:PUBLISH` (create/update/on-demand) or `METHOD:CANCEL` + `STATUS:CANCELLED`
  (delete), times as `TZID=Asia/Jerusalem` with **no embedded `VTIMEZONE`**.
- **Evidence**: PM inputs 1-3; the embedded `icalendar`-generated `VTIMEZONE` shifted recurring updates by
  one hour on Android, its absence did not (Gate Zero 2, D3 vs D5).

## R4 - `SEQUENCE` bookkeeping
- **Problem**: update/cancel only work if `SEQUENCE` increases per file for the same `UID`; a re-sent
  unchanged file (on-demand) is untested on the phone.
- **Decision**: a persisted per-reminder counter in its own table `reminder_ics_sequences` (absent row = 0; a separate table, not a column, so the approved `reminders` schema test and every existing database stay untouched). Every file generated for a
  reminder *claims* the current value and increments the stored one, so every file for a reminder carries a
  strictly higher `SEQUENCE` than any before - including on-demand re-sends and reminders that pre-date this
  feature (their first file carries 0, as a fresh entry would). Monotonic by construction, so no
  "same sequence, different content" ambiguity.
- **Alternatives**: derive from a change counter only on writes (rejected: on-demand re-send of an unchanged
  reminder would repeat a sequence, behavior unverified); timestamp-based sequence (rejected: opaque, not
  an RFC-5545-style small integer).

## R5 - When the automatic file is sent (after the confirmation text)
- **Problem**: the model writes the confirmation text with `send_to_user` *after* the write tool returns, so
  a send inside the tool would arrive before it.
- **Decision**: the write handler only *queues* `(reminder_id, method)` on the backbone for the current turn;
  `Backbone` flushes the queue when `_run_conversation` returns (the app pauses = the model is done), in a
  `finally` so a failed turn still delivers files for writes that already happened. Last operation per
  reminder wins (a delete after a create in the same turn sends one CANCEL).
- **Alternatives**: have the model call a send tool as a flow step (rejected: non-deterministic, REQ-01 says
  every reminder); send inside the tool (rejected: wrong order).

## R6 - Which chat receives the file
- **Decision**: the chat of the current turn. For a create it *is* the reminder's `delivery_chat_id`
  (REQ-102-01); for modify/delete/on-demand it is where the user is asking.

## R7 - Temp-file handling ("same as docx authoring", PM decision 2)
- **Decision**: write to `{data_root}/tmp/reminder_ics/<uuid>_<name>.ics`, upload, delete in `finally`
  (docx's `_cleanup` pattern). File names are ASCII: `reminder_<id8>.ics` / `reminders_<YYYYMMDD>.ics`.

## R8 - On-demand and offer (REQ-09/10)
- **Decision**: a read-only local tool `send_reminders_calendar_file(reminder_ids)` attached with
  `cap_reminders_read` (so it inherits that capability's RBAC); no approval step (read-only). The offer is the
  existing stateless `approval_with_yes_no_buttons` capability, driven by a new flow
  `flow_reminders_calendar_file`. One file with several events for several ids (verified, Gate Zero H1/H2).
- **Not a write**: the tool is deliberately not in `WRITE_TOOL_NAMES`, so the approved-turn guard does not
  count it.

## R9 - Pre-feature reminders (PM decision 5)
- Modify/delete of a reminder that never had a file simply sends the update/cancel file as usual; the
  a reminder with no `reminder_ics_sequences` row starts at 0 (no migration needed).

## R10 - Boundaries in the prompts
- `runtime_constitution.md` is gone; `config/prompts/` is the constitution. The new capability behavior needs
  explicit scope: when the file is automatic, when it is requested/offered, and that it is **never**
  produced for anything but reminders (invoices, ledger, agreements are out of scope), per CLAUDE.md's
  tool-bearing-feature rule.

## R11 - Risks carried forward
- `.ics` behavior on iOS/other calendar apps and on a re-imported unchanged file is unverified; covered by a
  manual billed-checklist step, not by automation.
- The dev Green API instance is over its monthly `readchat` quota; sends were unaffected in Gate Zero.
