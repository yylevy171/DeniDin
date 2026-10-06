# Flow: Issue payment received with reference document

Goal: record a payment against a Morning document that already exists: a receipt on an invoice (305), or a combo document that closes a transaction account (300).

Capabilities: `cap_invoicing_write`, `cap_approval_with_buttons`, and `cap_client_read` when the allocation-number step needs it.
Flows it may load: `flow_invoicing_query`, `flow_modify_client`.

Follow these steps in order, to the letter.

1. Load `flow_invoicing_query` and find the ONE real document the user means. Reuse an id and exact name you already have from earlier in this conversation. Otherwise search using only what the current request gives you (a client name, an amount, a date), and add a filter only if this request itself states one.
   - Exactly one plausible match: do not ask about it separately. Carry it straight into the approval, which shows its details; the user's yes or no there is the confirmation.
   - Several, or none: use `cap_send_to_user` to say what you found and ask what identifies the right one. Never guess and never ask the user for an internal id.
   A wrong match is a real, incorrect payment or cancellation, so be certain.
   Then fetch that document's own current details in this same turn. The approval must show real, fresh data, never memory from an earlier turn.
2. Load `cap_invoicing_write`. Gather what is still missing. Anything you don't have from the user or the source, use `cap_send_to_user` to ask for, one question at a time; never guess or invent a value.
3. **The allocation number** (see `cap_invoicing_write`): if this is a 320 closing a transaction account that needs the client's ID (a receipt on an invoice never does), check it with `get_client_details` (load `cap_client_read` if it isn't loaded). If the client has a 9-digit ID, or the document doesn't need one, go on to step 4. Otherwise the ID must be saved first:
   - If the user already gave a 9-digit ID in this request, go straight to saving it (below).
   - Otherwise use `cap_send_to_user` to ask for it, as a plain question with no approval buttons: name the client and the amount, and say the client's ת.ז / ח.פ (9 digits) is needed to issue this document. Then wait.
   - A reply of exactly 9 digits: load `flow_modify_client` to save it on the client (its own approval). Once it is saved, continue straight to step 4 in that same turn - the user does not restate the request.
   - A reply that isn't exactly 9 digits: use `cap_send_to_user` to say an ID must be exactly 9 digits and ask again. Save nothing.
   - The user declines, has no ID, or declines saving it: use `cap_send_to_user` to confirm the document was not issued. The flow is complete.
4. Recording the payment MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Act only on a clear yes. On a no, do nothing, and use `cap_send_to_user` to ask what to change.
5. On a yes, issue the document. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome — no download link is required in this report. Then unload `flow_invoicing_query`, `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.
