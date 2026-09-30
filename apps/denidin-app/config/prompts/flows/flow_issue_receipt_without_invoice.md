# Flow: Issue receipt without invoice

Goal: record a receipt (400) for a client with no linked invoice, such as a refundable deposit.

Capabilities: `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons`.
Flows it may load: `flow_add_client`.

Follow these steps in order, to the letter.

1. Load `cap_client_read` and resolve the client by the name the user gave, even if it looks exact.
   Handle what you find:
   - An exact stored name: use it verbatim from here on.
   - A confirmation question (a single close match): use `cap_send_to_user` to put it to the user as-is, and proceed once they confirm.
   - Several candidates: use `cap_send_to_user` to list them and ask the user to specify. Never pick one yourself.
   - No such client: Load `flow_add_client` to create it, then continue with the exact name that was created. If the user declines to add the client, the flow is complete.
2. Load `cap_invoicing_write`. Gather what is still missing. Anything you don't have from the user or the source, use `cap_send_to_user` to ask for, one question at a time; never guess or invent a value.
3. Issuing the receipt MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Act only on a clear yes. On a no, do nothing, and use `cap_send_to_user` to ask what to change.
4. On a yes, issue the receipt. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
5. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
6. End. Use `cap_send_to_user` to report the outcome — no download link is required in this report. Then unload `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.
