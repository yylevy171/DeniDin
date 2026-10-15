# Flow: Issue transaction account

Goal: issue a new transaction account (300) for a client. Only when the user's own wording names this document type.

Capabilities: `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons`, `cap_ledger_capture`.
Flows it may load: `flow_add_client`.

Follow these steps in order, to the letter.

Progress updates (`cap_send_progress_update`) can be sent between the steps, in plain words, so the user understands what is going on.

🚨 A Morning document that was created or cancelled successfully is final and cannot be undone. Never create or cancel it again because of anything that happens afterwards - an error, a failed step, a failed reaction, a confusing message. Duplicate tax documents have legal consequences. If you are not sure whether the write happened, check Morning first, and if you still cannot tell, ask the user.

1. Use this flow only if the user explicitly named a transaction account (חשבון עסקה). Never infer it from context; if the request is only for an invoice, use `flow_issue_invoice_for_payment_due`.
2. Load `cap_client_read` and resolve the client by the name the user gave, even if it looks exact.
   Handle what you find:
   - An exact stored name: copy it character for character from the `resolve_client_name` result from here on - in the approval text and in every tool call, never retyped (see `cap_client_read`).
   - A confirmation question (a single close match): use `cap_send_to_user` to put it to the user as-is, and also offer, as its own explicit choice, to create a new client under the exact name the user gave. Proceed with whichever they choose.
   - Several candidates: use `cap_send_to_user` to list each of them by name and ask the user to specify, and also offer, as its own explicit choice, to create a new client under the exact name the user gave. Never pick one yourself.
   - No such client, or the user chose to create a new one: Load `flow_add_client` to create it, then continue with the exact name that was created. If the user declines to add the client, the flow is complete.
3. Load `cap_invoicing_write`. Gather what is still missing. Anything you don't have from the user or the source, use `cap_send_to_user` to ask for, one question at a time; never guess or invent a value.
4. Issuing the transaction account MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Act only on a clear yes. On a no, do nothing, and use `cap_send_to_user` to ask what to change.
5. On a yes, issue the transaction account. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop. 🚨 **Right after each document is created, record it in the ledger - once per document, before you report.** Load `cap_ledger_capture` if it is not loaded and call `report_ledger_recognition` with `verdict` `complete` and an `event` whose `source_type` is `חשבונית`, `event_subtype` `הפקה`, and `accounting_document_json` the successful `create_*` result copied verbatim (see `cap_ledger_capture`). A call that failed records nothing.
6. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome — no download link is required in this report. Then unload `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons`, `cap_ledger_capture` and this flow, keeping any that other work still in progress needs.
