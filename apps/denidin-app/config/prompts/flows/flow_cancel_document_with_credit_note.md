# Flow: Cancel document with credit note

Goal: cancel or credit an existing Morning document by issuing a credit note (330) against it. Cancelling a חשבונית מס / קבלה (320) in full takes TWO documents: the 330 (reverses the revenue) and then a negative receipt (reverses the cash).

Capabilities: `cap_invoicing_write`, `cap_approval_with_buttons`.
Flows it may load: `flow_invoicing_query`.

Follow these steps in order, to the letter.

1. Load `flow_invoicing_query` and find the ONE real document the user means. Reuse an id and exact name you already have from earlier in this conversation. Otherwise search using only what the current request gives you (a client name, an amount, a date), and add a filter only if this request itself states one.
   - Exactly one plausible match: do not ask about it separately. Carry it straight into the approval, which shows its details; the user's yes or no there is the confirmation.
   - Several, or none: use `cap_send_to_user` to say what you found and ask what identifies the right one. Never guess and never ask the user for an internal id.
   A wrong match is a real, incorrect payment or cancellation, so be certain.
   Then fetch that document's own current details in this same turn. The approval must show real, fresh data, never memory from an earlier turn.
   Note the document's type from that fresh lookup. 🚨 **If it is a 320:** if its linked documents already include a 330 or a negative receipt, it is already cancelled - use `cap_send_to_user` to say so and stop; create nothing. A partial credit of a 320 is not covered by this flow's two-document rule: it stays a 330 only.
2. Load `cap_invoicing_write`. Gather what is still missing. Anything you don't have from the user or the source, use `cap_send_to_user` to ask for, one question at a time; never guess or invent a value.
3. Issuing the credit note MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve. Act only on a clear yes. On a no, do nothing, and use `cap_send_to_user` to ask what to change.
4. On a yes, issue the credit note. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
   🚨 **If the cancelled document is a 320 (full cancellation), the work is not done yet:** the cash side still has to be reversed. Record with `cap_record_planning_status` that the 330 was created and the cancelling receipt is next. Then ask a SECOND approval with `cap_approval_with_buttons`, in the form `cap_invoicing_write` defines for a document that acts on an existing one, saying plainly that this is the negative receipt that cancels the cash side of the same 320: its type (`סוג מסמך: קבלה (400) מבטלת`), the 320's number, the client, the amount (shown as the negative of the 320's total), and the payment method taken from the 320's first payment (all from the fresh lookup). On a yes, call `create_receipt` with the 320's internal id (nothing else). On a no, create nothing and use `cap_send_to_user` to tell the user plainly that the credit note was created but the cash side of the 320 is still NOT reversed. If `create_receipt` fails, tell the user plainly that the 330 was created and the receipt was not, and offer to try again. Never create the negative receipt before the 330, and never both on a single approval.
5. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
6. End. Use `cap_send_to_user` to report the outcome — for a 320, say that both a credit note and a cancelling receipt were created (or exactly which one was not) — no download link is required in this report. Then unload `flow_invoicing_query`, `cap_invoicing_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.
