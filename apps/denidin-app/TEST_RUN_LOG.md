# Billed & Expensive Test Run Log

Manually-updated ground truth for every `billed`/`expensive` test's last real run —
started 2026-08-02 because chat narration of "N/M passed" isn't a trustworthy enough
record on its own. Update this file (never just report status in chat) immediately
after every real run: date, result, and the exact commit hash the code was at.

**Rules**: one row per test. `Result` is only ever what a real run actually produced -
never inferred, never "should still pass since nothing touched it." A test whose
underlying code changed since its last row must be treated as unverified until re-run,
regardless of what its last recorded result was. `Commit` is the short hash of
`git rev-parse --short HEAD` at run time, so a result can always be tied to an exact
version of the code.

Legend: PASS / FAIL / SKIP (marked `@pytest.mark.skip`, not run) / UNVERIFIED (never
run since this file started, or invalidated by a later code change).

## billed (48 tests)

| # | Test | Last Run | Result | Commit | Notes |
|---|------|----------|--------|--------|-------|
| 1 | test_ai_handler_real_api.py::TestBotExceptionHandlingWithRealAPI::test_openai_error_handling_real_api | 2026-08-02 | PASS | 5bec668 | |
| 2 | test_ai_handler_real_api.py::TestMessageLengthValidation::test_long_prompt_truncated_to_10000 | 2026-08-02 | PASS | 5bec668 | |
| 3 | test_ai_handler_real_api.py::TestMessageLengthValidation::test_short_messages_pass_through | 2026-08-02 | PASS | 5bec668 | |
| 4 | test_denidin_morning_document_creation_e2e.py::test_godfather_creates_transaction_account_via_whatsapp | 2026-08-02 | PASS | 5bec668 | |
| 5 | test_denidin_morning_document_creation_e2e.py::test_godfather_creates_combo_document_via_whatsapp | 2026-08-02 | PASS | cbfb093 | Was FAIL at 5bec668 - root cause (Morning-suppression missed `mcp_approval_request`) fixed in 52d6f8e, re-run confirms fix works for real. |
| 6 | test_denidin_morning_document_creation_e2e.py::test_godfather_creates_credit_note_against_real_invoice | 2026-08-02 | PASS | cbfb093 | |
| 7 | test_denidin_morning_document_creation_e2e.py::test_credit_note_request_with_invalid_invoice_number_fails_gracefully | 2026-08-02 | PASS | cbfb093 | |
| 8 | test_denidin_morning_document_creation_e2e.py::test_godfather_creates_receipt_against_unpaid_invoice | 2026-08-02 | PASS | cbfb093 | |
| 9 | test_denidin_morning_document_creation_e2e.py::test_receipt_request_with_exact_invoice_amount_resolves_correctly | 2026-08-02 | PASS | cbfb093 | |
| 10 | test_denidin_morning_document_creation_e2e.py::test_receipt_request_for_already_paid_invoice_handled_sensibly | 2026-08-02 | PASS | cbfb093 | |
| 11 | test_denidin_morning_mcp_e2e.py::test_godfather_creates_invoice_via_whatsapp | 2026-08-02 | PASS | cbfb093 | |
| 12 | test_denidin_morning_mcp_e2e.py::test_godfather_declines_invoice_creation | 2026-08-02 | PASS | cbfb093 | |
| 13 | test_denidin_morning_mcp_e2e.py::test_godfather_ignores_pending_approval_with_unrelated_message | 2026-08-02 | PASS | cbfb093 | |
| 14 | test_denidin_morning_mcp_e2e.py::test_godfather_approval_survives_intervening_small_talk | 2026-08-02 | PASS | cbfb093 | |
| 15 | test_denidin_morning_mcp_e2e.py::test_godfather_add_client_requires_approval | 2026-08-02 | PASS | cbfb093 | |
| 16 | test_denidin_morning_mcp_e2e.py::test_godfather_add_client_missing_field_is_asked_for | 2026-08-02 | PASS | cbfb093 | |
| 17 | test_denidin_morning_mcp_e2e.py::test_godfather_add_client_rejects_malformed_email | 2026-08-02 | PASS | cbfb093 | |
| 18 | test_denidin_morning_mcp_e2e.py::test_godfather_declines_add_client | 2026-08-02 | PASS | cbfb093 | |
| 19 | test_denidin_morning_mcp_e2e.py::test_godfather_lists_clients_via_whatsapp | 2026-08-02 | PASS | cbfb093 | |
| 20 | test_denidin_morning_mcp_e2e.py::test_godfather_gets_client_details_via_whatsapp | 2026-08-02 | PASS | cbfb093 | |
| 21 | test_denidin_morning_mcp_e2e.py::test_godfather_gets_client_details_not_found_via_whatsapp | 2026-08-02 | FAIL | cbfb093 | Fixture generates client name "לקוח לא קיים {random}" (literally "client doesn't exist" + a number) - model asked for clarification (name vs number) instead of calling get_client_details directly. Under investigation - likely a fixture-naming issue, not related to this session's ledger-event work. |
| 22 | test_denidin_morning_mcp_e2e.py::test_godfather_updates_client_via_whatsapp | - | UNVERIFIED | - | |
| 23 | test_denidin_morning_mcp_e2e.py::test_godfather_declines_client_update | - | UNVERIFIED | - | |
| 24 | test_denidin_morning_mcp_e2e.py::test_godfather_update_client_ambiguous_name_creates_no_pending_approval | - | UNVERIFIED | - | |
| 25 | test_denidin_morning_mcp_e2e.py::test_godfather_finds_client_via_hebrew_vowel_variant | - | UNVERIFIED | - | |
| 26 | test_denidin_morning_mcp_e2e.py::test_godfather_get_client_details_discloses_first_name_prefix_match | - | UNVERIFIED | - | |
| 27 | test_denidin_morning_mcp_e2e.py::test_godfather_update_client_discloses_family_name_prefix_match_before_approval | - | UNVERIFIED | - | |
| 28 | test_denidin_morning_mcp_e2e.py::test_client_role_gets_no_client_management_tools | - | UNVERIFIED | - | |
| 29 | test_denidin_morning_mcp_e2e.py::test_blocked_role_gets_no_client_management_tools | - | UNVERIFIED | - | |
| 30 | test_denidin_morning_mcp_e2e.py::test_godfather_lists_invoices_via_whatsapp | - | UNVERIFIED | - | |
| 31 | test_denidin_morning_mcp_e2e.py::test_godfather_asks_analytical_debtor_question_via_whatsapp | - | UNVERIFIED | - | |
| 32 | test_denidin_morning_mcp_e2e.py::test_zehavit_client_name_transcribed_exactly | - | UNVERIFIED | - | |
| 33 | test_denidin_morning_mcp_e2e.py::test_no_date_mentioned_omits_date_range | - | UNVERIFIED | - | |
| 34 | test_denidin_morning_mcp_e2e.py::test_client_all_payments_gets_the_complete_picture | - | UNVERIFIED | - | |
| 35 | test_denidin_morning_mcp_e2e.py::test_client_explicit_everything_request_gets_the_complete_picture | - | UNVERIFIED | - | |
| 36 | test_denidin_morning_mcp_e2e.py::test_godfather_gets_invoice_details_via_whatsapp | - | UNVERIFIED | - | |
| 37 | test_denidin_morning_mcp_e2e.py::test_godfather_marks_invoice_paid_via_whatsapp | - | UNVERIFIED | - | |
| 38 | test_denidin_morning_mcp_e2e.py::test_godfather_cancels_invoice_via_whatsapp | - | UNVERIFIED | - | |
| 39 | test_denidin_morning_mcp_e2e.py::test_godfather_declines_invoice_cancellation | - | UNVERIFIED | - | |
| 40 | test_denidin_morning_mcp_e2e.py::test_godfather_marks_transaction_account_invoice_paid_via_whatsapp | - | UNVERIFIED | - | |
| 41 | test_denidin_morning_mcp_e2e.py::test_godfather_declines_marking_transaction_account_invoice_paid | - | UNVERIFIED | - | |
| 42 | test_denidin_morning_mcp_e2e.py::test_godfather_marks_already_paid_credit_invoice_as_paid_is_rejected | - | UNVERIFIED | - | |
| 43 | test_denidin_vcf_contact_e2e.py::test_godfather_shares_contact_card_complete_requires_approval | - | UNVERIFIED | - | Ledger false-positive guard added 2026-08-02 (f285de7), never run. |
| 44 | test_denidin_vcf_contact_e2e.py::test_godfather_shares_contact_card_missing_email_is_asked_for | - | UNVERIFIED | - | Ledger false-positive guard added 2026-08-02 (f285de7), never run. |
| 45 | test_ledger_event_capture_billed.py::TestLedgerEventCaptureBilled::test_given_clear_fee_agreement_text_when_processed_then_ledger_event_captured | - | UNVERIFIED | - | File fully rewritten 2026-08-02 (f285de7) from the broken pending_ledger_events version - never run since. |
| 46 | test_ledger_event_capture_billed.py::TestLedgerEventCaptureBilled::test_given_ordinary_chatter_when_processed_then_no_ledger_event_captured | - | UNVERIFIED | - | Same rewrite as above - never run since. |
| 47 | test_session_transfer.py::test_session_transfer_and_recall_after_expiration | 2026-07-31 | PASS | (pre-merge) | Passed pre-merge under the old `expensive` marker, before the file moved to billed/. Unverified in its new location. |
| 48 | test_simple_text_e2e.py::TestSimpleTextE2E::test_e2e_simple_text_message_hebrew | 2026-07-31 | PASS | (pre-merge) | Same as above - unverified in its new billed/ location. |

## expensive (21 tests)

| # | Test | Last Run | Result | Commit | Notes |
|---|------|----------|--------|--------|-------|
| 1 | test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_agreement_image_when_processed_then_ledger_event_captured_via_image_path | 2026-07-31 | PASS | (pre-merge) | Unverified since merge. |
| 2 | test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_bank_deposit_screenshot_when_processed_then_captured_as_bank_deposit | 2026-07-31 | PASS | (pre-merge) | Unverified since merge. |
| 3 | test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_non_agreement_image_when_processed_then_no_ledger_event_captured | 2026-07-31 | PASS | (pre-merge) | Unverified since merge. |
| 4 | test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_gilyan_davidian_agreement_text_when_processed_then_captured_per_component | 2026-07-31 | PASS | (pre-merge) | Unverified since merge. |
| 5 | test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_new_agreement_flat_fee_then_all_fields_correctly_persisted | 2026-07-31 | PASS | (pre-merge) | Unverified since merge. |
| 6 | test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_agreement_correction_then_replaced_placeholder_correct | 2026-07-31 | PASS | (pre-merge) | Unverified since merge. |
| 7 | test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_agreement_cancellation_then_subtype_and_amount_correct | - | SKIP | - | `@pytest.mark.skip`, blocked on feature/032 (amount-sign decision). |
| 8 | test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_agreement_payment_confirmation_then_subtype_correct | 2026-07-31 | PASS | (pre-merge) | Unverified since merge. |
| 9 | test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_agreement_percent_based_fee_then_percent_fields_correct | 2026-07-31 | PASS | (pre-merge) | Unverified since merge. |
| 10 | test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_multi_component_agreement_image_then_components_correctly_persisted | 2026-07-31 | PASS | (pre-merge) | Unverified since merge. |
| 11 | test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_bank_deposit_image_then_full_fields_correctly_persisted | 2026-07-31 | PASS | (pre-merge) | Unverified since merge. |
| 12 | test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_six_component_agreement_image_mor_ben_shaya_then_all_components_correctly_persisted | 2026-08-02 | PASS | 402bd1e | Confirmed twice for real (component_count fix). Unverified since merge. |
| 13 | test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_single_day_hours_message_then_hours_and_date_correctly_persisted | 2026-08-02 | PASS | 402bd1e | Unverified since merge. |
| 14 | test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_two_day_hours_message_then_split_per_day_with_correct_dates | 2026-08-02 | PASS | 402bd1e | Unverified since merge. |
| 15 | test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_hours_message_with_payer_reference_then_payer_name_captured | 2026-08-02 | PASS | f285de7 | Confirmed for real (payer_name + hours fixes). Unverified since merge with subsequent commits. |
| 16 | test_media_e2e.py::TestWhatsAppE2E::test_e2e_image_no_caption | 2026-08-02 | PASS | (pre-merge) | Unverified since merge. |
| 17 | test_media_e2e.py::TestWhatsAppE2E::test_e2e_docx_no_caption | 2026-08-02 | PASS | (pre-merge) | Unverified since merge. |
| 18 | test_media_e2e.py::TestWhatsAppE2E::test_e2e_hebrew_pdf_from_you | 2026-08-02 | PASS | (pre-merge) | Unverified since merge. |
| 19 | test_media_e2e.py::TestWhatsAppE2E::test_e2e_pdf_with_caption_user_question | 2026-08-02 | PASS | (pre-merge) | Unverified since merge. |
| 20 | test_media_e2e.py::TestWhatsAppE2E::test_e2e_unsupported_audio_file | 2026-08-02 | PASS | (pre-merge) | Unverified since merge. |
| 21 | test_media_e2e.py::TestWhatsAppE2E::test_e2e_pdf_multipage_no_caption | 2026-08-02 | PASS | (pre-merge) | Unverified since merge. |

## Current sweep status (this session)

Resuming the `billed` sweep at **#5** (combo document - fix just applied, needs re-run),
sequential, stop on first failure, per standing instruction.
