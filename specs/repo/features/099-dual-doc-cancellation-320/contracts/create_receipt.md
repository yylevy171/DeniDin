# Contract: `create_receipt` (extended by Feature 099)
`create_receipt(original_internal_morning_id, payment_date?, amount?, client_name?, description?, name_resolved?, payment_method?, bank_number?, bank_branch?, bank_account?, vat_included?)`
- original type 305: unchanged. original None: standalone (Feature 056), unchanged.
- original type **320**: cancelling receipt. `amount` must be omitted (full cancellation); `payment_method`/bank args ignored (copied from the 320's first payment); the payment date is today (cancellation date). Result: JSON of the new 400 (negative amount), or a Hebrew refusal if already credited / not linked to a client. Raises `ValueError` if `amount` is passed.
- any other type: `ValueError` as today.
