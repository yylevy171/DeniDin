# Flow: Payment received by bank slip image

Goal: a bank slip image arrived: read it, record its payer, and get the payment recorded in Morning the right way.

Capabilities: `cap_media_analysis`.
Flows it may load: `flow_deposit_provided_by_user`, `flow_issue_invoice_receipt_combo`, `flow_issue_payment_received_with_reference_doc`, `flow_invoicing_query`.

Follow these steps in order, to the letter.

1. Load `cap_media_analysis` and read the slip. Use `cap_send_to_user` to report what it contains (payer, amount, date, bank details) so the user can see what you understood. If the image is not a bank slip, stop using this flow and decide what it is from its content.
2. Load `flow_deposit_provided_by_user` for the payer named on the slip.
3. Load `flow_invoicing_query` and check whether an existing Morning document already covers this payment (same client, similar amount).
   - No document covers it: load `flow_issue_invoice_receipt_combo`.
   - An existing document covers it: load `flow_issue_payment_received_with_reference_doc`.
   - It is unclear: use `cap_send_to_user` to ask the user which applies. Never guess, and never fall back to a bare tax invoice; money already received is never a bare tax invoice.
4. Follow the flow you loaded through to its end.
5. If the user drops the request or changes the subject mid-way, do nothing further and treat the flow as complete.
6. End. Use `cap_send_to_user` to report the outcome. Then unload `cap_media_analysis`, `flow_invoicing_query` and this flow, keeping any that other work still in progress needs.
