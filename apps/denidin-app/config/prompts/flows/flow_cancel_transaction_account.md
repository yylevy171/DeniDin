# Flow: Cancel transaction account

Goal: cancel an open transaction account (300) in Morning. No document of any kind is created.

Capabilities: `cap_invoicing_write`, `cap_approval_with_buttons`.
Flows it may load: `flow_invoicing_query`.

Follow these steps in order, to the letter.

1. Load `flow_invoicing_query` and find the ONE real document the user means. Reuse an id and exact name you already have from earlier in this conversation. Otherwise search using only what the current request gives you (a client name, an amount, a date), and add a filter only if this request itself states one.
   - Exactly one plausible match: use `cap_send_to_user` to confirm it with the user rather than asking a generic question.
   - Several, or none: use `cap_send_to_user` to say what you found and ask what identifies the right one. Never guess and never ask the user for an internal id.
   A wrong match is a real, incorrect payment or cancellation, so be certain.
   Then fetch that document's own current details in this same turn. The approval must show real, fresh data, never memory from an earlier turn.
2. If the account is not open or is not a transaction account, use `cap_send_to_user` to tell the user plainly and stop; the flow is complete.
3. Cancelling the transaction account MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Act only on a clear yes. On a no, do nothing, and use `cap_send_to_user` to ask what to change.
4. On a yes, cancel it. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop. Say plainly that no document was created.
5. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
6. End. Use `cap_send_to_user` to report the outcome. Then unload `flow_invoicing_query`, `cap_invoicing_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.
