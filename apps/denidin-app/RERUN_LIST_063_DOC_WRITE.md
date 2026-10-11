# Item-17 / Morning doc-write rerun list (Feature 063, backbone flag ON)

Tests to rerun after the flow_morning_document_write + deposit-flow + bank-transfer-only changes.
54 tests: 41 billed, 13 expensive (expensive = approval required, one at a time).
Created 2026-10-02. None run yet.

## 1. Failed sanity (ST-F)

| ST | Tier | Node id |
|---|---|---|
| ST10 | billed | `tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_add_client_near_duplicate_name_is_asked_before_creating` |
| ST11 | billed | `tests/billed/test_denidin_morning_document_flows_e2e.py::test_create_document_for_existing_client_happy_path` |
| ST12 | billed | `tests/billed/test_denidin_morning_document_flows_e2e.py::test_create_document_for_new_client_full_flow_happy_path` |
| ST13 | billed | `tests/billed/test_denidin_morning_document_flows_e2e.py::test_create_document_for_new_client_asked_for_missing_info_then_provided` |
| ST17 | billed | `tests/billed/test_standalone_receipt_billed.py::test_godfather_records_a_deposit_as_a_standalone_receipt` |
| ST18 | billed | `tests/billed/test_denidin_morning_invoice_lifecycle_e2e.py::test_godfather_gets_invoice_details_via_whatsapp` |
| ST25 | billed | `tests/billed/test_ledger_event_capture_text_billed.py::TestLedgerEventCaptureTextBilled::test_given_real_single_day_hours_message_then_hours_and_date_correctly_persisted` |
| ST32 | billed | `tests/billed/test_fee_agreement_generation_flow.py::TestFeeAgreementGenerationFlow::test_multi_component_arbitrary_n[4]` |

## 2. Expensive sanity, not yet run

| ST | Tier | Node id |
|---|---|---|
| ST37 | expensive | `tests/expensive/test_image_classification_e2e.py::test_bank_test_image_is_classified_as_a_bank_deposit` |
| ST38 | expensive | `tests/expensive/test_image_classification_e2e.py::test_six_component_agreement_is_classified_as_an_agreement` |
| ST39 | expensive | `tests/expensive/test_image_classification_e2e.py::test_personal_note_is_neither_bank_nor_agreement` |
| ST40 | expensive | `tests/expensive/test_e2e_media_client_resolution.py::TestMediaClientResolutionE2E::test_us7a_deposit_image_zero_matches_new_client` |
| ST41 | expensive | `tests/expensive/test_e2e_media_client_resolution.py::TestMediaClientResolutionE2E::test_us9_photographed_multi_component_agreement` |
| ST42 | expensive | `tests/expensive/test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_six_component_agreement_image_mor_ben_shaya_then_all_components_correctly_persisted` |
| ST43 | expensive | `tests/expensive/test_e2e_media_client_resolution.py::TestMediaClientResolutionE2E::test_us7d_deposit_image_exact_match_no_question` |
| ST44 | expensive | `tests/expensive/test_image_classification_e2e.py::test_kehunai_deposit_is_classified_as_a_bank_deposit` |

## 3. Sanity that passed but creates Morning documents

| ST | Tier | Node id |
|---|---|---|
| ST14 | billed | `tests/billed/test_denidin_morning_document_creation_e2e.py::test_godfather_creates_transaction_account_via_whatsapp` |
| ST15 | billed | `tests/billed/test_denidin_morning_document_creation_e2e.py::test_godfather_creates_credit_note_against_real_invoice` |
| ST16 | billed | `tests/billed/test_denidin_morning_document_creation_e2e.py::test_godfather_creates_receipt_against_unpaid_invoice` |
| ST20 | billed | `tests/billed/test_group_b_reference_approval_billed.py::TestGroupBReferenceApprovalBilled::test_combo_document_against_existing_transaction_account_shows_reference_data` |

## 4. Billed tests that create/cancel Morning documents

| ST | Tier | Node id |
|---|---|---|
| ST45 | billed | `tests/billed/test_cancel_transaction_account_billed.py::test_godfather_cancels_a_transaction_account_via_whatsapp` |
| ST46 | billed | `tests/billed/test_denidin_approval_content_and_vat_e2e.py::test_vat_included_transaction_account_is_stored_at_the_approved_amount` |
| ST47 | billed | `tests/billed/test_denidin_approval_content_and_vat_e2e.py::test_unstated_vat_is_asked_about_rather_than_assumed` |
| ST48 | billed | `tests/billed/test_denidin_approval_content_and_vat_e2e.py::test_the_approval_states_every_mandatory_element` |
| ST49 | billed | `tests/billed/test_denidin_approval_content_and_vat_e2e.py::test_a_client_qualified_by_its_tax_id_still_resolves` |
| ST50 | billed | `tests/billed/test_denidin_morning_document_creation_e2e.py::test_godfather_creates_combo_document_via_whatsapp` |
| ST51 | billed | `tests/billed/test_denidin_morning_document_creation_e2e.py::test_credit_note_request_with_invalid_invoice_number_fails_gracefully` |
| ST52 | billed | `tests/billed/test_denidin_morning_document_creation_e2e.py::test_receipt_request_with_exact_invoice_amount_resolves_correctly` |
| ST53 | billed | `tests/billed/test_denidin_morning_document_creation_e2e.py::test_receipt_request_for_already_paid_invoice_handled_sensibly` |
| ST54 | billed | `tests/billed/test_denidin_morning_document_flows_e2e.py::test_create_document_for_new_client_declines_client_creation` |
| ST55 | billed | `tests/billed/test_denidin_morning_document_flows_e2e.py::test_create_document_for_new_client_creates_client_but_declines_document` |
| ST56 | billed | `tests/billed/test_denidin_morning_document_flows_e2e.py::test_create_document_for_new_client_missing_info_not_provided_stops_flow` |
| ST57 | billed | `tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_creates_invoice_via_whatsapp` |
| ST58 | billed | `tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_creates_invoice_via_whatsapp_button_tap` |
| ST59 | billed | `tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_declines_invoice_creation` |
| ST60 | billed | `tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_ignores_pending_approval_with_unrelated_message` |
| ST61 | billed | `tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_approval_survives_intervening_small_talk` |
| ST62 | billed | `tests/billed/test_denidin_morning_invoice_lifecycle_e2e.py::test_godfather_marks_invoice_paid_via_whatsapp` |
| ST63 | billed | `tests/billed/test_denidin_morning_invoice_lifecycle_e2e.py::test_godfather_cancels_invoice_via_whatsapp` |
| ST64 | billed | `tests/billed/test_denidin_morning_invoice_lifecycle_e2e.py::test_godfather_declines_invoice_cancellation` |
| ST65 | billed | `tests/billed/test_denidin_morning_invoice_lifecycle_e2e.py::test_godfather_marks_transaction_account_invoice_paid_via_whatsapp` |
| ST66 | billed | `tests/billed/test_denidin_morning_invoice_lifecycle_e2e.py::test_godfather_declines_marking_transaction_account_invoice_paid` |
| ST67 | billed | `tests/billed/test_denidin_morning_invoice_lifecycle_e2e.py::test_godfather_marks_already_paid_credit_invoice_as_paid_is_rejected` |
| ST68 | billed | `tests/billed/test_denidin_morning_list_invoices_e2e.py::test_godfather_searches_invoice_by_number_finds_it` |
| ST69 | billed | `tests/billed/test_e2e_ledger_069_morning_create_billed.py::TestLedgerPostTurnCaptureMorningCreate::test_us2_morning_create_is_captured_synchronously` |
| ST70 | billed | `tests/billed/test_group_b_reference_approval_billed.py::TestGroupBReferenceApprovalBilled::test_receipt_against_existing_invoice_shows_reference_data` |
| ST71 | billed | `tests/billed/test_group_b_reference_approval_billed.py::TestGroupBReferenceApprovalBilled::test_credit_note_against_existing_invoice_shows_reference_data` |
| ST72 | billed | `tests/billed/test_group_b_reference_approval_billed.py::TestGroupBReferenceApprovalBilled::test_multi_turn_clarification_uses_the_real_internal_id_not_the_display_number` |
| ST73 | billed | `tests/billed/test_small_bugfixes_027_032_054_058_061_billed.py::test_bugfix_027_client_stored_with_ascii_apostrophe_can_get_a_document` |

## 5. Expensive deposit / bank-slip image tests

| ST | Tier | Node id |
|---|---|---|
| ST74 | expensive | `tests/expensive/test_e2e_media_client_resolution.py::TestMediaClientResolutionE2E::test_us7b_deposit_image_one_partial_match` |
| ST75 | expensive | `tests/expensive/test_e2e_media_client_resolution.py::TestMediaClientResolutionE2E::test_us7c_deposit_image_two_plus_matches` |
| ST76 | expensive | `tests/expensive/test_group_b_reference_approval_e2e.py::TestGroupBReferenceApprovalE2E::test_given_a_deposit_matching_an_existing_tax_invoice_then_a_receipt_closes_it` |
| ST77 | expensive | `tests/expensive/test_image_classification_e2e.py::test_whatsapp_email_screenshot_is_never_a_bank_deposit` |
| ST78 | expensive | `tests/expensive/test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_bank_deposit_image_then_full_fields_correctly_persisted` |

## Notes

- Sanity-marked but missing from the original 44-test list: ST50, ST58, ST70, ST78 (and the add-client approval test). `scripts/verify_sanity_lists.sh` not yet run.
- Left out on purpose: ledger-query, contact-card, client add/update tests (no document flow).
