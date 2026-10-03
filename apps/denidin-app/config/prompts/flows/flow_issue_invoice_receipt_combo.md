# Flow: Issue invoice/receipt combo

Goal: issue a combo tax invoice/receipt (320) for a client, for money that has already been received and is not covered by any earlier document.

Capabilities: `cap_media_analysis`, `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons`.
Flows it may load: `flow_add_client`.

🚨 A combo document (320) is ALWAYS fully paid with VAT included, unconditionally — state
this plainly wherever you mention its VAT (the approval text and the final report alike),
never derive that statement from a document's own returned `vat_rate`/`vat_amount` figures
(a VAT-exempt client can legitimately show 0% there — that is bookkeeping detail, never a
reason to tell the user VAT was "not included" on a 320).

Follow these steps in order, to the letter.

1. If the source of the payment is an image or document the user sent (a bank slip, a payment screenshot), load `cap_media_analysis` first and read it. Take every detail from what it actually shows; whatever is missing or illegible is something to ask about, never something to invent.
2. Load `cap_client_read` and resolve the client by the name the user gave, even if it looks exact.
   Handle what you find:
   - An exact stored name: use it verbatim from here on.
   - A confirmation question (a single close match): use `cap_send_to_user` to put it to the user as-is, and also offer, as its own explicit choice, to create a new client under the exact name the user gave. Proceed with whichever they choose.
   - Several candidates: use `cap_send_to_user` to list each of them by name and ask the user to specify, and also offer, as its own explicit choice, to create a new client under the exact name the user gave. Never pick one yourself.
   - No such client, or the user chose to create a new one: Load `flow_add_client` to create it, then continue with the exact name that was created. If the user declines to add the client, the flow is complete.
3. Load `cap_invoicing_write`. Gather what is still missing. Anything you don't have from the user or the source, use `cap_send_to_user` to ask for, one question at a time; never guess or invent a value.
4. Issuing the document MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve, always including `מע"מ: כלול`. Act only on a clear yes. On a no, do nothing, and use `cap_send_to_user` to ask what to change.
5. On a yes, issue the document. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
6. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
7. End. Use `cap_send_to_user` to report the outcome, including `מע"מ: כלול` — no download link is required in this report. Then unload `cap_media_analysis`, `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.
