# Flow: Issue invoice/receipt combo

Goal: issue a combo tax invoice/receipt (320) for a client, for money that has already been received and is not covered by any earlier document.

Capabilities: `cap_media_analysis`, `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons`.
Flows it may load: `flow_add_client`, `flow_modify_client`.

🚨 A combo document (320) is ALWAYS fully paid with VAT included, unconditionally — state
this plainly wherever you mention its VAT (the approval text and the final report alike),
never derive that statement from a document's own returned `vat_rate`/`vat_amount` figures
(a VAT-exempt client can legitimately show 0% there — that is bookkeeping detail, never a
reason to tell the user VAT was "not included" on a 320).

Follow these steps in order, to the letter.

1. If the source of the payment is an image or document the user sent (a bank slip, a payment screenshot), load `cap_media_analysis` first and read it. Take every detail from what it actually shows; whatever is missing or illegible is something to ask about, never something to invent.
2. Load `cap_client_read` and resolve the client by the name the user gave, even if it looks exact.
   Handle what you find:
   - An exact stored name: copy it character for character from the `resolve_client_name` result from here on - in the approval text and in every tool call, never retyped (see `cap_client_read`).
   - A confirmation question (a single close match): use `cap_send_to_user` to put it to the user as-is, and also offer, as its own explicit choice, to create a new client under the exact name the user gave. Proceed with whichever they choose.
   - Several candidates: use `cap_send_to_user` to list each of them by name and ask the user to specify, and also offer, as its own explicit choice, to create a new client under the exact name the user gave. Never pick one yourself.
   - No such client, or the user chose to create a new one: Load `flow_add_client` to create it, then continue with the exact name that was created. If the user declines to add the client, the flow is complete.
3. Load `cap_invoicing_write`. Gather what is still missing. Anything you don't have from the user or the source, use `cap_send_to_user` to ask for, one question at a time; never guess or invent a value.
4. **The allocation number** (see `cap_invoicing_write`): if this document needs the client's ID, check it with `get_client_details` (load `cap_client_read` if it isn't loaded). If the client has a 9-digit ID, or the document doesn't need one, go on to step 5. Otherwise the ID must be saved first:
   - If the user already gave a 9-digit ID in this request, go straight to saving it (below).
   - Otherwise use `cap_send_to_user` to ask for it, as a plain question with no approval buttons: name the client and the amount, and say the client's ת.ז / ח.פ (9 digits) is needed to issue this document. Then wait.
   - A reply of exactly 9 digits: load `flow_modify_client` to save it on the client (its own approval). Once it is saved, continue straight to step 5 in that same turn - the user does not restate the request.
   - A reply that isn't exactly 9 digits: use `cap_send_to_user` to say an ID must be exactly 9 digits and ask again. Save nothing.
   - The user declines, has no ID, or declines saving it: use `cap_send_to_user` to confirm the document was not issued. The flow is complete.
5. Issuing the document MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve, always including `מע"מ: כלול`. Act only on a clear yes. On a no, do nothing, and use `cap_send_to_user` to ask what to change.
6. On a yes, issue the document. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop.
7. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
8. End. Use `cap_send_to_user` to report the outcome, including `מע"מ: כלול` — no download link is required in this report. Then unload `cap_media_analysis`, `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.
