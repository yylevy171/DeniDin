# Analysis: 102 - consistency check across spec / user-stories / plan / research / contracts / tasks

Run 2026-10-15 after `speckit.plan` + `speckit.tasks`. Every finding below was fixed in the same pass
(the "Resolution" column); none is left open.

| # | Severity | Finding | Resolution |
| :-- | :-- | :-- | :-- |
| A1 | HIGH | `spec.md` REQ-102-08 requires updating `runtime_constitution.md`'s "Reminder Management" section; that file no longer exists (the backbone prompts under `config/prompts/` are the constitution now). | REQ-102-08 rewritten to the prompt files; `plan.md`/`research.md` R10 already match. |
| A2 | HIGH | CLAUDE.md requires boundaries "in both directions" for a tool-bearing feature: every *other* tool-bearing prompt must exclude the new feature too. The plan only touched the reminder prompts and `backbone.md`. | Plan, contract and tasks now add a one-line exclusion to every other capability prompt that has tools (invoicing read/write, client read/write, ledger query, agreements read/write, docx write, media analysis) and a test that asserts it (T009). |
| A3 | MED | REQ-102-01 says the file goes to the reminder's `delivery_chat_id`; the plan sends to the current turn's chat (identical for a create, different for modify/delete/on-demand from another chat). | REQ-102-01 states both cases. |
| A4 | MED | REQ-102-09 says an on-demand file carries "the current `SEQUENCE`"; REQ-102-02 says it "increases by 1 with every change". The design (R4) bumps on every generated file. | REQ-102-02 and REQ-102-09 aligned to "strictly higher than any earlier file for that reminder". |
| A5 | MED | REQ-102-09 asserts that importing an on-demand file onto a phone that already has the entry updates it, not duplicates it. Only a *changed* file with a higher sequence was verified; an unchanged re-send with a higher sequence was not. | Reworded as the design expectation, listed as an untested assumption (spec section 2 + research R11) and added to the billed/manual checklist (T012). |
| A6 | MED | UAT 1.4 (the due-time text nudge still delivered) had only a billed task, no fast regression test. | T007A now includes a regression test that `ReminderDeliveryService` still delivers the text nudge at due time and sends no `.ics`. |
| A7 | MED | REQ-102-06 (RBAC) had no explicit test for the new tool: it is attached with `REMINDERS_READ`, so the gate is the capability's role check - not asserted anywhere. | T008A adds a test that a non-godfather/admin never gets `send_reminders_calendar_file`. |
| A8 | MED | The approval-button path: a "כן" typed OR a button tap both lead to the write; the plan only tests a typed path. | T007A adds the tap path (`interactiveButtonsResponse` through the router). |
| A9 | MED | The flush runs after `_run_conversation`; exceptions there are caught later in `_handle_message_body`. Order of flush vs. error reply was unspecified. | Contract and T006A: the flush is in a `finally` inside the same `try`, runs before the error reply, never raises. |
| A10 | LOW | Spec section 4 "Decisions" numbering (`0b`, `0`, `1`-`6`) is untidy and out of order. | Renumbered 1-8 in order. |
| A11 | LOW | Spec has no requirement for file name / caption; contract defines them. | Added to REQ-102-01. |
| A12 | LOW | `tasks.md` T011 said "if ARCHITECTURE.md lists reminder flows" (conditional, unverifiable). | Made concrete: grep it during T011 and update every mention. |
| A13 | LOW | `tasks.md` T012 listed UAT 3.1 as manual but the billed file had no place to record the manual result. | T012 adds a `docs`-style manual checklist section in `quickstart.md` for UAT 3.1 and the unchanged-re-send check. |
| A14 | LOW | `user-stories.md` UAT 1.1 says the `.ics` carries "no alert" but does not mention the absence of an embedded timezone definition (a verified requirement). | UAT 1.1 asserts both. |

Coverage check (every requirement has at least one task and one story):
REQ-01 -> T005/T007 + UAT 1.1/1.3; REQ-02 -> T001 + UAT 1.1; REQ-03 -> T007 (no new approval); REQ-04 -> T001/T006/T007
+ UAT 2.1-2.5; REQ-05 -> T001/T007 + UAT 1.3; REQ-06 -> T007/T008 + UAT 3.2; REQ-07 -> T003/T004/T006 + UAT 3.3;
REQ-08 -> T009; REQ-09 -> T008 + UAT 4.1-4.3; REQ-10 -> T009 + UAT 5.1-5.4. No orphan tasks.
