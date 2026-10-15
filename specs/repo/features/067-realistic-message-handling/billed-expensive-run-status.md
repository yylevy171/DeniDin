# Feature 067 - billed/expensive acceptance runs: groups and status

Updated as runs progress. Status: PASSED / FAILED / NOT RUN / RUNNING / PENDING-APPROVAL.
Billed/expensive tests run only on the user's explicit go-ahead.

Last updated: 2026-10-15

## G1 - cancel combo (billed)
- test_cancel_combo_099_billed.py::test_99_3_already_cancelled_320_is_refused - PASSED (2026-10-15, final code)

## G2 - cancel transaction account (billed)
- test_cancel_transaction_account_billed.py::test_godfather_cancels_a_transaction_account_via_whatsapp - PASSED (2026-10-15, final code)

## G3 - client management (billed)
- 5 client_management tests - PASSED (2026-10-14, BEFORE the prompt changes; not rerun)

## G4 - bugfix-071 VAT rules (billed)
- 5 bugfix_071 tests - PASSED (2026-10-14, BEFORE the prompt changes; not rerun)

## G5 - allocation, first two (billed)
- test_allocation_tax_id_billed.py::test_uat_1_1_combo_above_threshold_asks_for_id - PASSED (2026-10-14, before prompt changes)
- test_allocation_tax_id_billed.py::test_uat_1_2_tax_invoice_above_threshold_asks_for_id - PASSED (2026-10-14, before prompt changes)

## G6 - ledger_query sanity (billed), all PASSED 2026-10-15
- test_explicit_date_lookup - PASSED
- test_hours_by_client_last_month - PASSED
- test_four_way_multi_criterion_with_date_range - PASSED
- test_or_across_two_identities_handle_message - PASSED
- test_broad_threshold_who_owes_above_amount - PASSED
- test_typo_variant_name_resolved_or_clarified_never_silently_dropped - PASSED

## G7 - reminders (billed)
- test_reminder_lifecycle_billed.py button_approval and recurring_reminder - PASSED (2026-10-14, before prompt changes)

## G8 - group etiquette (billed) - cut from 8 to 4 tests
- test_case1_default_address_gets_substantive_reply - NOT RUN
- test_case2_clearly_for_someone_else_gets_no_reply - NOT RUN
- test_case3_genuinely_unclear_gets_clarifying_question - NOT RUN
- test_case6_at_denidin_overrides_ambiguous_content - NOT RUN
- (deleted: case4, case5a, case5b, case7)

## G9 - allocation, important ones (billed) - approved list of 3
- test_uat_1_3_closing_transaction_account_above_threshold_asks_for_id - FAILED twice (2026-10-15); dropped by the user (scenario never happens)
- test_uat_2_1_valid_id_saved_then_document_issued - NOT RUN (sequence stopped at 1_3)
- test_uat_3_3_client_already_has_an_id - NOT RUN (sequence stopped at 1_3)
- (not run, by decision: uat_2_2, 2_3, 3_1, 3_2, 3_4, 3_5, edge x2)

## G10 - Morning flows, one happy path per file (billed)
- invoice_creation: test_godfather_creates_invoice_via_whatsapp - NOT RUN (sequence stopped at G9 failure)
- document_creation: test_godfather_creates_combo_document_via_whatsapp - NOT RUN (sequence stopped at G9 failure)
- document_flows: test_create_document_for_existing_client_happy_path - NOT RUN (sequence stopped at G9 failure)
- invoice_lifecycle: test_godfather_marks_invoice_paid_via_whatsapp - NOT RUN (sequence stopped at G9 failure)
- list_invoices: test_godfather_lists_invoices_via_whatsapp - NOT RUN (sequence stopped at G9 failure)
- client_management: test_godfather_updates_client_via_whatsapp - NOT RUN (sequence stopped at G9 failure)
- standalone_receipt: test_godfather_records_a_deposit_as_a_standalone_receipt - NOT RUN (sequence stopped at G9 failure)
- approval_content: test_the_approval_states_every_mandatory_element - NOT RUN (sequence stopped at G9 failure)
- group_b: TestGroupBReferenceApprovalBilled::test_receipt_against_existing_invoice_shows_reference_data - NOT RUN (started by mistake for ~10s and killed, no result)

## G11 - expensive vision tests (each needs the user's approval, one at a time)
Chosen so far: the six-component agreement image (ledger capture).
- test_ledger_event_capture_e2e.py::test_given_real_six_component_agreement_image_mor_ben_shaya_then_all_components_correctly_persisted - PENDING-APPROVAL
- e2e_media_client_resolution.py::TestMediaClientResolutionE2E::test_us7a_deposit_image_zero_matches_new_client - PASSED 2026-10-15 (before the deposit flow rewrite)
- test_deposit_offer_064_e2e.py::TestDepositOffer064E2E::test_64_1_yes_starts_the_320_flow - FAILED 2026-10-15 (assertion read the summary message too); assertion fixed to the buttons message; rerun -> PASSED 2026-10-15 on the rewritten deposit flow
Dropped by decision: us7d, us9, allocation slip, A8 (already done).

## G12 - ledger capture (billed), approved list
- test_ledger_event_capture_billed.py: clear fee agreement captured - NOT RUN
- test_ledger_event_capture_billed.py: ordinary chatter captures nothing - NOT RUN
- test_ledger_event_capture_text_billed.py: Gilyan multi-component agreement per component - NOT RUN
- test_ledger_event_capture_text_billed.py: single-day hours message - NOT RUN
- test_ledger_event_capture_text_billed.py: conditional fee trigger captured - NOT RUN
- test_e2e_ledger_069_text_billed.py::test_us4_new_client_agreement_full_detour - NOT RUN
- test_e2e_ledger_069_morning_create_billed.py::test_us2_morning_create_is_captured_synchronously - NOT RUN
- test_e2e_ledger_069_docx_billed.py::test_us10_docx_multi_component_agreement_two_hop - NOT RUN
- (dropped by decision: cash deposit from text)

## Unit/integration
- 1711 passed, 1 failed (live Green API connectivity test, network SSL error; flaky) - 2026-10-14
