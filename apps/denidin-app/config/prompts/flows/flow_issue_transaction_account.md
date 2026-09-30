# Flow: Issue transaction account

Goal: issue a new transaction account (300) for a client. Only when the user's own wording names this document type.

Capabilities: `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons`.
Flows it may load: `flow_add_client`.

Follow these steps in order, to the letter.

1. Use this flow only if the user explicitly named a transaction account (חשבון עסקה). Never infer it from context; if the request is only for an invoice, use `flow_issue_invoice_for_payment_due`.
2. Load `cap_client_read` and resolve the client by the name the user gave, even if it looks exact.
   Handle what you find:
   - An exact stored name: use it verbatim from here on.
   - A confirmation question (a single close match): use `cap_send_to_user` to put it to the user as-is, and proceed once they confirm.
   - Several candidates: use `cap_send_to_user` to list them and ask the user to specify. Never pick one yourself.
   - No such client: Load `flow_add_client` to create it, then continue with the exact name that was created. If the user declines to add the client, the flow is complete.
3. Load `cap_invoicing_write`. Gather what is still missing. Anything you don't have from the user or the source, use `cap_send_to_user` to ask for, one question at a time; never guess or invent a value.
4. Issuing the transaction account MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Act only on a clear yes. On a no, do nothing, and use `cap_send_to_user` to ask what to change.
5. On a yes, issue the transaction account. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome — no download link is required in this report. Then unload `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.
