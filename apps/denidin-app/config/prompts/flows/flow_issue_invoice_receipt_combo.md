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

🚨 This flow has several stages, and you are not done until every stage that applies has been completed. The client's ID is the typical case, but only for a document whose amount before VAT is above {{ALLOCATION_THRESHOLD_NIS}} ₪ (see `cap_invoicing_write`, "Allocation number"); for any other document there is no ID stage and nothing about the ID is asked. When the ID is required and the client has none, there is an extra stage before the document - the ID must be asked for, provided and saved. Saving the ID (through `flow_modify_client`) is NOT the end of the flow; it is the middle. Once it is saved, do not stop and do not report it as the outcome: carry on from where you were (the step after the ID step) and ask for the document's own approval, then issue the document, then report. The same goes for any other stage that turns out to be needed (a client that has to be created first, a missing detail that has to be asked for): finish it, then continue the flow from there. Only the last step ends the flow.

1. If the source of the payment is an image or document the user sent (a bank slip, a payment screenshot), load `cap_media_analysis` first and read it. Take every detail from what it actually shows; whatever is missing or illegible is something to ask about, never something to invent.
2. Load `cap_client_read` and resolve the client by the name the user gave, even if it looks exact.
   Handle what you find:
   - An exact stored name: copy it character for character from the `resolve_client_name` result from here on - in the approval text and in every tool call, never retyped (see `cap_client_read`).
   - A confirmation question (a single close match): use `cap_send_to_user` to put it to the user as-is, and also offer, as its own explicit choice, to create a new client under the exact name the user gave. Proceed with whichever they choose.
   - Several candidates: use `cap_send_to_user` to list each of them by name and ask the user to specify, and also offer, as its own explicit choice, to create a new client under the exact name the user gave. Never pick one yourself.
   - No such client, or the user chose to create a new one: Load `flow_add_client` to create it, then continue with the exact name that was created. If the user declines to add the client, the flow is complete.
3. Load `cap_invoicing_write`. Gather what is still missing. Anything you don't have from the user or the source, use `cap_send_to_user` to ask for, one question at a time; never guess or invent a value.
4. **The allocation number** (see `cap_invoicing_write`): if this document needs the client's ID, check it with `get_client_details` (load `cap_client_read` if it isn't loaded). If the document doesn't need one, or the client has a 9-digit ID and the user gave no other ID, go on to step 5. Otherwise:
   - **The user gave an ID in this request and the client already has a different one:** this is a conflict - maybe a typo, maybe a misunderstanding. Never pick one yourself. Use `cap_send_to_user` to show both (the ID on file and the one the user gave) and ask which is right. If the user confirms the new one, save it on the client (below) before issuing - the client's record is the only way the allocation number gets the right ID. If they keep the one on file, go on to step 5.
   - **The user gave a 9-digit ID in this request and the client has none:** go straight to saving it (below).
   - **Otherwise ask for it:** use `cap_send_to_user`, as a plain question with no approval buttons: name the client and the amount, and say the client's ת.ז / ח.פ (9 digits) is needed for the allocation number (מספר הקצאה), because the amount is above {{ALLOCATION_THRESHOLD_NIS}} ₪ before VAT. Then wait.
   The user's reply to that question:
   - **A decline, a postponement, or no ID** ("עזוב", "לא עכשיו", "אין לי"): use `cap_send_to_user` to confirm the document was not issued. Save nothing. The flow is complete.
   - **9 digits** - spaces or dashes between them are fine (e.g. "308-253-681"); keep the digits only. This is the client's ID (see `cap_invoicing_write`). Load `flow_modify_client` to save it on the client. Saving the ID and issuing the document are two separate writes, each with its own approval: the user's yes to saving the ID approves the save only - never issue the document on it. Once the ID is saved, continue straight to step 5 in that same turn and ask for the document's own approval - the user does not restate the request. If the user says no to saving the ID, use `cap_send_to_user` to confirm the document was not issued; the flow is complete.
   - **An attempt at an ID that isn't 9 digits** (8 or 10 digits, letters mixed in): use `cap_send_to_user` to say an ID must be exactly 9 digits and ask again. Save nothing.
5. Issuing the document MUST be approved by the user first. Load `cap_approval_with_buttons` and ask, with a message containing all the details the user needs to approve, always including the line `מע״מ: כולל מע״מ` (see `cap_invoicing_write`). Act only on a clear yes. On a no, do nothing, and use `cap_send_to_user` to ask what to change. If the client's ID was saved earlier in this flow, also say that the ID stays saved on the client and that no document was issued.
6. On a yes, issue the document. If the action fails, use `cap_send_to_user` to tell the user plainly what happened. Retry once only if the reason is fixable; otherwise stop. A refusal because the client's ID is missing is never a fixable reason: never retry it, never issue a different document type instead, and never split the amount into several smaller documents - go back to step 4 and ask for the ID.
7. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
8. End. Use `cap_send_to_user` to report the outcome, stating that VAT is included — no download link is required in this report. Then unload `cap_media_analysis`, `cap_client_read`, `cap_invoicing_write`, `cap_approval_with_buttons` and this flow, keeping any that other work still in progress needs.
