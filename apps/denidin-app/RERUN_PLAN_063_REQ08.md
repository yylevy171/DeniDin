# Test run plan after REQ-063-08 (Feature 063, backbone flag ON)

Rebuilt 2026-10-03, after commits b7c1956 + 95db86c. Every earlier result predates that refactor,
which sits under every turn (manager construction, message storage, sending, the @ rewrite,
progress updates, media, group resolver, post-turn recognition, schedulers) - so everything reruns.
Billed run freely; expensive need approval each, one at a time.

| List | Tests | Billed | Expensive |
|---|---|---|---|
| CS | 11 | 9 | 2 |
| ST | 36 | 36 | 0 |
| STE | 8 | 0 | 8 |
| IMP | 30 | 26 | 4 |
| - IMPA (run) | 10 | 8 | 2 |
| - IMPB (only if IMPA fails) | 20 | 18 | 2 |
| THKH | 12 | 10 | 2 |
| THKM | 12 | 12 | 0 |
| THKL | 20 | 18 | 2 |
| **Total** | **129** | **111** | **18** |

THKL includes 1 billed test in apps/rolling-memory-backfill. 70 denidin billed/expensive tests
are on no list (RBAC roles, extra ledger-query/list-invoice/capture/classification variants, raw
connectivity, reconciliation US3/US5/cap, extra reminder variants) - same prompts/tools, paths already
covered above.

## CS - Cap Sanity (T1-T11)

| ID | Old id | Tier | Last result (pre-refactor) | Node id |
|---|---|---|---|---|
| T1 | ST78 | exp | PASS before the refactor and before the 10-02 deposit-flow merge | tests/expensive/test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_bank_deposit_image_then_full_fields_correctly_persisted |
| T2 |  | billed | PASS 10-01 | tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_add_client_requires_approval |
| T3 |  | billed | PASS 09-30 | tests/billed/test_reminder_lifecycle_billed.py::TestReminderLifecycleBilled::test_godfather_creates_one_time_reminder_button_approval |
| T4 |  | billed | PASS 09-30 | tests/billed/test_reminder_lifecycle_billed.py::TestReminderLifecycleBilled::test_modify_single_occurrence_of_recurring_reminder |
| T5 |  | billed | PASS 09-30 | tests/billed/test_denidin_morning_list_invoices_e2e.py::test_godfather_lists_invoices_via_whatsapp |
| T6 |  | billed | PASS 09-30 | tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_hours_by_client_last_month |
| T7 | ST58 | billed | PASS 10-01 | tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_creates_invoice_via_whatsapp_button_tap |
| T8 |  | billed | PASS 10-01 | tests/billed/test_ledger_event_capture_text_billed.py::TestLedgerEventCaptureTextBilled::test_given_real_gilyan_davidian_agreement_text_when_processed_then_captured_per_component |
| T9 |  | exp | PASS before the refactor and before the 10-02 deposit-flow merge | tests/expensive/test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_multi_component_agreement_image_then_components_correctly_persisted |
| T10 | ST50 | billed | PASS 10-01 | tests/billed/test_denidin_morning_document_creation_e2e.py::test_godfather_creates_combo_document_via_whatsapp |
| T11 | ST70 | billed | PASS 10-01 | tests/billed/test_group_b_reference_approval_billed.py::TestGroupBReferenceApprovalBilled::test_receipt_against_existing_invoice_shows_reference_data |

## ST - Sanity billed

| ID | Old id | Tier | Last result (pre-refactor) | Node id |
|---|---|---|---|---|
| ST01 |  | billed | PASS 10-01 | tests/billed/test_real_api_connectivity.py::TestRealGreenAPIConnectivity::test_greenapi_real_connection |
| ST02 |  | billed | PASS 10-01 | tests/billed/test_real_api_connectivity.py::TestRealEndToEndFlow::test_complete_real_api_flow |
| ST03 |  | billed | PASS 10-01 (failed once, then passed) | tests/billed/test_simple_text_e2e.py::TestSimpleTextE2E::test_e2e_simple_text_message_hebrew |
| ST04 |  | billed | PASS 10-01 | tests/billed/test_ai_handler_real_api.py::TestBotExceptionHandlingWithRealAPI::test_openai_error_handling_real_api |
| ST05 |  | billed | PASS 10-01 | tests/billed/test_denidin_version_query_e2e.py::test_godfather_role_gets_accurate_version_answer |
| ST06 |  | billed | PASS 10-01 | tests/billed/test_denidin_morning_client_management_e2e.py::test_godfather_gets_client_details_via_whatsapp |
| ST07 |  | billed | PASS 10-01 (on retry) | tests/billed/test_denidin_morning_client_management_e2e.py::test_godfather_finds_client_via_hebrew_vowel_variant |
| ST08 |  | billed | PASS 10-01 (on retry) | tests/billed/test_denidin_morning_client_management_e2e.py::test_godfather_get_client_details_resolves_ambiguous_first_name_prefix_after_confirmation |
| ST09 |  | billed | PASS 10-01 | tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_add_client_missing_field_is_asked_for |
| ST10 |  | billed | **FAIL 10-02 (2 attempts, open)** - re-spelled Morning's candidate name | tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_add_client_near_duplicate_name_is_asked_before_creating |
| ST11 |  | billed | PASS 10-02 | tests/billed/test_denidin_morning_document_flows_e2e.py::test_create_document_for_existing_client_happy_path |
| ST12 |  | billed | PASS 10-02; PASS 10-04 rerun (blind VAT "כן" removed, explicit add-client turn - bugfix-065) | tests/billed/test_denidin_morning_document_flows_e2e.py::test_create_document_for_new_client_full_flow_happy_path |
| ST13 |  | billed | PASS 10-02; PASS 10-05 (operator-marked after blind "כן" removal, not rerun) | tests/billed/test_denidin_morning_document_flows_e2e.py::test_create_document_for_new_client_asked_for_missing_info_then_provided |
| ST14 |  | billed | PASS 10-01 (before the 10-02 doc-write prompts) | tests/billed/test_denidin_morning_document_creation_e2e.py::test_godfather_creates_transaction_account_via_whatsapp |
| ST15 |  | billed | PASS 10-01 (on retry; before doc-write prompts) | tests/billed/test_denidin_morning_document_creation_e2e.py::test_godfather_creates_credit_note_against_real_invoice |
| ST16 |  | billed | PASS 10-01 (on retry; before doc-write prompts) | tests/billed/test_denidin_morning_document_creation_e2e.py::test_godfather_creates_receipt_against_unpaid_invoice |
| ST17 |  | billed | PASS 10-02 (2nd attempt) | tests/billed/test_standalone_receipt_billed.py::test_godfather_records_a_deposit_as_a_standalone_receipt |
| ST18 |  | billed | PASS 10-02 | tests/billed/test_denidin_morning_invoice_lifecycle_e2e.py::test_godfather_gets_invoice_details_via_whatsapp |
| ST19 |  | billed | PASS 10-01 (on retry) | tests/billed/test_denidin_morning_list_invoices_e2e.py::test_client_all_payments_gets_the_complete_picture |
| ST20 |  | billed | PASS 10-01 (on retry; before doc-write prompts) | tests/billed/test_group_b_reference_approval_billed.py::TestGroupBReferenceApprovalBilled::test_combo_document_against_existing_transaction_account_shows_reference_data |
| ST21 |  | billed | PASS 10-01 | tests/billed/test_group_etiquette_billed.py::TestGroupEtiquetteBilled::test_case1_default_address_gets_substantive_reply |
| ST22 |  | billed | PASS 10-01 | tests/billed/test_group_etiquette_billed.py::TestGroupEtiquetteBilled::test_case2_clearly_for_someone_else_gets_no_reply |
| ST23 |  | billed | PASS 10-01 (on retry) | tests/billed/test_ledger_event_capture_billed.py::TestLedgerEventCaptureBilled::test_given_clear_fee_agreement_text_when_processed_then_ledger_event_captured |
| ST24 |  | billed | PASS 10-01 (on retry) | tests/billed/test_ledger_event_capture_billed.py::TestLedgerEventCaptureBilled::test_given_ordinary_chatter_when_processed_then_no_ledger_event_captured |
| ST25 |  | billed | PASS 10-02 | tests/billed/test_ledger_event_capture_text_billed.py::TestLedgerEventCaptureTextBilled::test_given_real_single_day_hours_message_then_hours_and_date_correctly_persisted |
| ST26 |  | billed | PASS 10-01 (single run after a failed retry) | tests/billed/test_ledger_event_capture_text_billed.py::TestLedgerEventCaptureTextBilled::test_given_real_conditional_fee_text_then_trigger_condition_captured |
| ST27 |  | billed | PASS 10-01 | tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_explicit_date_lookup |
| ST28 |  | billed | PASS 10-01 | tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_four_way_multi_criterion_with_date_range |
| ST29 |  | billed | PASS 10-01 (on retry) | tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_or_across_two_identities_single_turn |
| ST30 |  | billed | PASS 10-01 (on retry) | tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_broad_threshold_who_owes_above_amount |
| ST31 |  | billed | PASS 10-01 (on retry) | tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_typo_variant_name_resolved_or_clarified_never_silently_dropped |
| ST32 |  | billed | PASS 10-02 | tests/billed/test_fee_agreement_generation_flow.py::TestFeeAgreementGenerationFlow::test_multi_component_arbitrary_n[4] |
| ST33 |  | billed | PASS 10-01 (single run after a failed retry) | tests/billed/test_reminder_lifecycle_billed.py::TestReminderLifecycleBilled::test_godfather_creates_recurring_reminder |
| ST34 |  | billed | PASS 10-01 (on 2nd retry) | tests/billed/test_e2e_ledger_069_text_billed.py::TestLedgerPostTurnCaptureText::test_us4_new_client_agreement_full_detour |
| ST35 |  | billed | PASS 10-01 (on retry) | tests/billed/test_e2e_ledger_069_text_billed.py::TestLedgerPostTurnCaptureText::test_us5_ambiguous_agreement_operator_picks |
| ST36 |  | billed | PASS 10-01 | tests/billed/test_e2e_ledger_069_text_billed.py::TestLedgerPostTurnCaptureText::test_us6_exact_match_captures_without_a_question |

## STE - Sanity expensive

| ID | Old id | Tier | Last result | Node id |
|---|---|---|---|---|
| STE01 | ST37 | exp | PASS 10-04 (before 4c1d8b8, which changed media_analysis/handler.py and the deposit/fee-agreement flows; needs a rerun) | tests/expensive/test_image_classification_e2e.py::test_bank_test_image_is_classified_as_a_bank_deposit |
| STE02 | ST38 | exp | PASS 10-04 (before 4c1d8b8, which changed media_analysis/handler.py and the deposit/fee-agreement flows; needs a rerun) | tests/expensive/test_image_classification_e2e.py::test_six_component_agreement_is_classified_as_an_agreement |
| STE03 | ST39 | exp | PASS 10-04 (before 4c1d8b8, which changed media_analysis/handler.py and the deposit/fee-agreement flows; needs a rerun) | tests/expensive/test_image_classification_e2e.py::test_personal_note_is_neither_bank_nor_agreement |
| STE04 | ST40 | exp | PASS 10-04 (before 4c1d8b8, which changed media_analysis/handler.py and the deposit/fee-agreement flows; needs a rerun) | tests/expensive/test_e2e_media_client_resolution.py::TestMediaClientResolutionE2E::test_us7a_deposit_image_zero_matches_new_client |
| STE05 | ST41 | exp | PASS 10-04 (before 4c1d8b8, which changed media_analysis/handler.py and the deposit/fee-agreement flows; needs a rerun) | tests/expensive/test_e2e_media_client_resolution.py::TestMediaClientResolutionE2E::test_us9_photographed_multi_component_agreement |
| STE06 | ST42 | exp | PASS 10-04 (before 4c1d8b8, which changed media_analysis/handler.py and the deposit/fee-agreement flows; needs a rerun) | tests/expensive/test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_six_component_agreement_image_mor_ben_shaya_then_all_components_correctly_persisted |
| STE07 | ST43 | exp | PASS 10-04 (before 4c1d8b8, which changed media_analysis/handler.py and the deposit/fee-agreement flows; needs a rerun) | tests/expensive/test_e2e_media_client_resolution.py::TestMediaClientResolutionE2E::test_us7d_deposit_image_exact_match_no_question |
| STE08 | ST44 | exp | PASS 10-04 (before 4c1d8b8, which changed media_analysis/handler.py and the deposit/fee-agreement flows; needs a rerun) | tests/expensive/test_image_classification_e2e.py::test_kehunai_deposit_is_classified_as_a_bank_deposit |

## IMP - doc-write impacted

Split 2026-10-04 (random draw): **IMPA** = 8 billed + 2 expensive, run first; **IMPB** = the
other 20, run only if any IMPA test fails.

| ID | Set | Old id | Tier | Last result (pre-refactor) | Node id |
|---|---|---|---|---|---|
| IMP01 | IMPB | ST45 | billed | PASS 10-05 | tests/billed/test_cancel_transaction_account_billed.py::test_godfather_cancels_a_transaction_account_via_whatsapp |
| IMP02 | IMPB | ST46 | billed | PASS 10-05 | tests/billed/test_denidin_approval_content_and_vat_e2e.py::test_vat_included_transaction_account_is_stored_at_the_approved_amount |
| IMP03 | IMPA | ST47 | billed | PASS 10-04 | tests/billed/test_denidin_approval_content_and_vat_e2e.py::test_unstated_vat_is_asked_about_rather_than_assumed |
| IMP04 | IMPB | ST48 | billed | PASS 10-05 | tests/billed/test_denidin_approval_content_and_vat_e2e.py::test_the_approval_states_every_mandatory_element |
| IMP05 | IMPB | ST49 | billed | PASS 10-05 rerun (JSON-parsed client check) | tests/billed/test_denidin_approval_content_and_vat_e2e.py::test_a_client_qualified_by_its_tax_id_still_resolves |
| IMP06 | IMPA | ST51 | billed | PASS 10-04 | tests/billed/test_denidin_morning_document_creation_e2e.py::test_credit_note_request_with_invalid_invoice_number_fails_gracefully |
| IMP07 | IMPB | ST52 | billed | PASS 10-05 | tests/billed/test_denidin_morning_document_creation_e2e.py::test_receipt_request_with_exact_invoice_amount_resolves_correctly |
| IMP08 | IMPB | ST53 | billed | PASS 10-05 | tests/billed/test_denidin_morning_document_creation_e2e.py::test_receipt_request_for_already_paid_invoice_handled_sensibly |
| IMP09 | IMPA | ST54 | billed | PASS 10-04; PASS 10-05 (operator-marked after blind "כן" removal, not rerun) | tests/billed/test_denidin_morning_document_flows_e2e.py::test_create_document_for_new_client_declines_client_creation |
| IMP10 | IMPA | ST55 | billed | PASS 10-04 rerun (blind VAT "כן" removed; one explicit add-client turn - bugfix-065) | tests/billed/test_denidin_morning_document_flows_e2e.py::test_create_document_for_new_client_creates_client_but_declines_document |
| IMP11 | IMPA | ST56 | billed | PASS 10-04; PASS 10-05 rerun (blind "כן" removed; backbone rule 6 - check a tool's requirements by loading it; no-claim-without-details asserts) | tests/billed/test_denidin_morning_document_flows_e2e.py::test_create_document_for_new_client_missing_info_not_provided_stops_flow |
| IMP12 | IMPB | ST57 | billed | PASS 10-05 rerun (request states 'במזומן') | tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_creates_invoice_via_whatsapp |
| IMP13 | IMPB | ST59 | billed | PASS 10-05 | tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_declines_invoice_creation |
| IMP14 | IMPB | ST60 | billed | PASS 10-05 | tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_ignores_pending_approval_with_unrelated_message |
| IMP15 | IMPB | ST61 | billed | PASS 10-05 | tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_approval_survives_intervening_small_talk |
| IMP16 | IMPB | ST62 | billed | PASS 10-05 rerun 3 (planning note now records IDs - cap_record_planning_status; earlier: wrong id after date turn) | tests/billed/test_denidin_morning_invoice_lifecycle_e2e.py::test_godfather_marks_invoice_paid_via_whatsapp |
| IMP17 | IMPB | ST63 | billed | PASS 10-05 rerun (JSON-parsed type check; credit amount 32.03 vs 27.14 = bugfix-071) | tests/billed/test_denidin_morning_invoice_lifecycle_e2e.py::test_godfather_cancels_invoice_via_whatsapp |
| IMP18 | IMPB | ST64 | billed | PASS 10-05 | tests/billed/test_denidin_morning_invoice_lifecycle_e2e.py::test_godfather_declines_invoice_cancellation |
| IMP19 | IMPB | ST65 | billed | PASS 10-06 rerun 5 (earlier: test read only get_invoice_details - fixed; then Morning sandbox 403/400 + OpenAI timeout) | tests/billed/test_denidin_morning_invoice_lifecycle_e2e.py::test_godfather_marks_transaction_account_invoice_paid_via_whatsapp |
| IMP20 | IMPB | ST66 | billed | PASS 10-05 rerun (decline now lands on approval; per-document status check) | tests/billed/test_denidin_morning_invoice_lifecycle_e2e.py::test_godfather_declines_marking_transaction_account_invoice_paid |
| IMP21 | IMPA | ST67 | billed | PASS 10-04 (operator-marked: VAT seed fixed; refusal was correct, negation check widened with "אי אפשר") | tests/billed/test_denidin_morning_invoice_lifecycle_e2e.py::test_godfather_marks_already_paid_credit_invoice_as_paid_is_rejected |
| IMP22 | IMPB | ST68 | billed | PASS 10-05 | tests/billed/test_denidin_morning_list_invoices_e2e.py::test_godfather_searches_invoice_by_number_finds_it |
| IMP23 | IMPB | ST69 | billed | PASS 10-05 | tests/billed/test_e2e_ledger_069_morning_create_billed.py::TestLedgerPostTurnCaptureMorningCreate::test_us2_morning_create_is_captured_synchronously |
| IMP24 | IMPA | ST71 | billed | PASS 10-04 rerun (single match now goes straight to the approval, 4 flows) | tests/billed/test_group_b_reference_approval_billed.py::TestGroupBReferenceApprovalBilled::test_credit_note_against_existing_invoice_shows_reference_data |
| IMP25 | IMPA | ST72 | billed | PASS 10-04 | tests/billed/test_group_b_reference_approval_billed.py::TestGroupBReferenceApprovalBilled::test_multi_turn_clarification_uses_the_real_internal_id_not_the_display_number |
| IMP26 | IMPB | ST73 | billed | PASS 10-05 | tests/billed/test_small_bugfixes_027_032_054_058_061_billed.py::test_bugfix_027_client_stored_with_ascii_apostrophe_can_get_a_document |
| IMP27 | IMPB | ST74 | exp | PASS 10-04 | tests/expensive/test_e2e_media_client_resolution.py::TestMediaClientResolutionE2E::test_us7b_deposit_image_one_partial_match |
| IMP28 | IMPA | ST75 | exp | PASS 10-04 (operator-marked: 16:21 run asked + recorded הדס; payer_name now optional free text) | tests/expensive/test_e2e_media_client_resolution.py::TestMediaClientResolutionE2E::test_us7c_deposit_image_two_plus_matches |
| IMP29 | IMPB | ST76 | exp | PASS 10-05 | tests/expensive/test_group_b_reference_approval_e2e.py::TestGroupBReferenceApprovalE2E::test_given_a_deposit_matching_an_existing_tax_invoice_then_a_receipt_closes_it |
| IMP30 | IMPA | ST77 | exp | PASS 10-04 | tests/expensive/test_image_classification_e2e.py::test_whatsapp_email_screenshot_is_never_a_bank_deposit |

## THKH - think, high

| ID | Old id | Tier | Why | Node id |
|---|---|---|---|---|
| THKH01 | RX1 | billed | Reactions now go through DeniDin.send_reaction; last: PASS 10-06 | tests/billed/test_reaction_judgment_tuning.py::TestReactionJudgmentTuningHardAssertions::test_ambient_group_chatter_lunch_makes_zero_reaction_calls |
| THKH02 | RX3 | billed | Reactions now go through DeniDin.send_reaction; last: **PASS 10-06 (operator-marked: the bot flipped the final message correctly; the test compares reactions across turns)** | tests/billed/test_reaction_judgment_tuning.py::TestReactionJudgmentTuningHardAssertions::test_flip_earlier_message_targets_the_same_id_message |
| THKH03 | RX4 | billed | Reactions now go through DeniDin.send_reaction; last: PASS 10-06 | tests/billed/test_reaction_judgment_tuning.py::TestAgreementCreationReactionsBilled::test_agreement_creation_via_text_reacts_on_ask_and_resolution |
| THKH04 | THK07 | billed | ChatLog deleted / SessionManager rebuilt - restart continuity; last: **PASS 10-06** (test now sends both turns through denidin.handle_text_message, since REQ-063-08 moved storing to DeniDin) | tests/billed/test_rolling_memory_billed.py::TestAC2RestartContinuity::test_a_fresh_process_continues_the_same_conversation |
| THKH05 | THK11 | billed | AccountingReconciler on DeniDin + new LedgerEventManager ctor; last: **KNOWN BUG 10-06 (reconciliation is broken; not fixed in 063).** Skipped 10-06: the cap check now reads the JSON too_many shape and the lookback is 1 day, but the sandbox had 474 docs since 10-05 | tests/billed/test_accounting_reconciliation_billed.py::TestUS1CapturesDocumentsNeverSeenInConversation::test_sweep_captures_real_sandbox_documents_with_faithful_fields |
| THKH06 | THK16 | billed | message queued while down, answered after startup (startup changed); last: PASS 10-06 | tests/billed/test_small_bugfixes_027_032_054_058_061_billed.py::test_bugfix_054_message_queued_while_bot_was_down_is_answered_after_startup |
| THKH07 | THK17 | billed | error reply persisted (send_text = send then store); last: PASS 10-06 | tests/billed/test_small_bugfixes_027_032_054_058_061_billed.py::test_bugfix_058_error_reply_sent_to_user_is_persisted_in_session |
| THKH08 | THK18 | billed | docx delivery (send_document moved to DeniDin); last: PASS 10-06 | tests/billed/test_fee_agreement_generation_flow.py::TestFeeAgreementGenerationFlow::test_stage4_delivery_and_cleanup |
| THKH09 | THK20 | billed | recognizer back-links event ids to the stored message; last: PASS 10-06 | tests/billed/test_e2e_ledger_069_text_billed.py::TestLedgerPostTurnCaptureText::test_us1_mechanism_move_agreement_text_exact_client |
| THKH10 | THK24 | billed | DOCX read on the backbone (was marked "not adjusted"; extractor now uses ai_manager.single_prompt_text); last: PASS 10-06 | tests/billed/test_e2e_ledger_069_docx_billed.py::TestLedgerPostTurnCaptureDocx::test_us10_docx_multi_component_agreement_two_hop |
| THKH11 | THK36 | exp | media path changed (begin_turn, _handle_media_message, MediaHandler on DeniDin); last: **PASS 10-06** | tests/expensive/test_media_e2e.py::TestWhatsAppE2E::test_e2e_image_no_caption |
| THKH12 | THK38 | exp | DOCX on the backbone; last: **PASS 10-06 (operator-marked; the code was OK and the 10-06 failure was the helper reading the internal stash message. assert_extracted_text_persisted now takes the latest user message carrying the media file. Not rerun)** | tests/expensive/test_media_e2e.py::TestWhatsAppE2E::test_e2e_docx_no_caption |

## THKM - think, medium

| ID | Old id | Tier | Why | Node id |
|---|---|---|---|---|
| THKM01 | THK04 (was THKM03) | billed | @DeniDin overrides; last: **PASS 10-06** | tests/billed/test_group_etiquette_billed.py::TestGroupEtiquetteBilled::test_case6_at_denidin_overrides_ambiguous_content |
| THKM02 | THK10 (was THKM07) | billed | legacy session load; last: **PASS 10-06** | tests/billed/test_rolling_memory_billed.py::TestAC5PendingLedgerEventsFixture::test_legacy_pending_ledger_events_session_loads_and_rolls |
| THKM03 | THK21 (was THKM10) | billed | no capture on an ordinary turn; last: **PASS 10-06** | tests/billed/test_e2e_ledger_069_text_billed.py::TestLedgerPostTurnCaptureText::test_us3_regression_guard_ordinary_turn_no_capture |
| THKM04 | THK22 (was THKM11) | billed | store-anyway marks the record; last: **PASS 10-06** | tests/billed/test_e2e_ledger_069_text_billed.py::TestLedgerPostTurnCaptureText::test_us8_store_anyway_marks_the_record |
| THKM05 | THK23 (was THKM12) | billed | don't-store persists nothing; last: **PASS 10-06** | tests/billed/test_e2e_ledger_069_text_billed.py::TestLedgerPostTurnCaptureText::test_us8_dont_store_persists_nothing |
| THKM06 | THK26 (was THKM13) | billed | list reminders; last: **PASS 10-06** | tests/billed/test_reminder_lifecycle_billed.py::TestReminderLifecycleBilled::test_list_reminders_filtered_by_day_in_conversation |
| THKM07 | THK27 (was THKM14) | billed | delete; last: **PASS 10-06** | tests/billed/test_reminder_lifecycle_billed.py::TestReminderLifecycleBilled::test_delete_one_time_reminder |
| THKM08 | THK28 (was THKM15) | billed | delete series; last: **PASS 10-06** | tests/billed/test_reminder_lifecycle_billed.py::TestReminderLifecycleBilled::test_delete_whole_series |
| THKM09 | THK31 (was THKM18) | billed | flow_add_client changed 10-02 (ST10 fix); last: **PASS 10-06** | tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_declines_add_client |
| THKM10 | THK32 (was THKM19) | billed | same; last: **PASS 10-06** | tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_add_client_rejects_malformed_email |
| THKM11 | RX2 (was THKM21) | billed | Reactions now go through DeniDin.send_reaction; last: **PASS 10-06** | tests/billed/test_reaction_judgment_tuning.py::TestReactionJudgmentTuningHardAssertions::test_ambient_group_chatter_debate_makes_zero_reaction_calls |
| THKM12 | THK01 (was THKM22) | billed | Native @-mention by own number - exactly the moved @ rewrite; last: **PASS 10-06** (the earlier 10-06 failures came from a stale config.test.json, which pointed at old Green API instance 710722700313; switched to 7105257767 from the dev creds) | tests/billed/test_group_etiquette_billed.py::TestGroupEtiquetteBilled::test_case7_native_mention_by_own_phone_number_gets_substantive_reply |

## THKL - think, low

| ID | Old id | Tier | Why | Node id |
|---|---|---|---|---|
| THKL01 | THK19 | billed | docx generation, simple template | tests/billed/test_fee_agreement_generation_flow.py::TestFeeAgreementGenerationFlow::test_stage1_template_selection[simple_regular_agreement] |
| THKL02 | THK33 | billed | client update approval | tests/billed/test_denidin_morning_client_management_e2e.py::test_godfather_updates_client_via_whatsapp |
| THKL03 | THK34 | billed | client update decline | tests/billed/test_denidin_morning_client_management_e2e.py::test_godfather_declines_client_update |
| THKL04 | THK35 | billed | AIHandler(denidin) ctor - long prompt truncation | tests/billed/test_ai_handler_real_api.py::TestMessageLengthValidation::test_long_prompt_truncated_to_10000 |
| THKL05 | THK39 | exp | negative control, no ledger event from a non-agreement image | tests/expensive/test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_non_agreement_image_when_processed_then_no_ledger_event_captured |
| THKL06 | THK02 (was THKM01) | billed | @someone-else must not be rewritten | tests/billed/test_group_etiquette_billed.py::TestGroupEtiquetteBilled::test_case5a_at_name_not_denidin_real_name_gets_no_reply |
| THKL07 | THK03 (was THKM02) | billed | same | tests/billed/test_group_etiquette_billed.py::TestGroupEtiquetteBilled::test_case5b_at_name_not_denidin_arbitrary_text_gets_no_reply |
| THKL08 | THK05 (was THKM04) | billed | group resolver rebuilt | tests/billed/test_group_etiquette_billed.py::TestGroupEtiquetteBilled::test_case3_genuinely_unclear_gets_clarifying_question |
| THKL09 | THK06 (was THKM05) | billed | group resolver rebuilt | tests/billed/test_group_etiquette_billed.py::TestGroupEtiquetteBilled::test_case4_ordinary_message_negative_control |
| THKL10 | THK09 (was THKM06) | billed | token backstop / archive | tests/billed/test_rolling_memory_billed.py::TestAC3TokenBackstop::test_newest_context_wins_and_trimmed_messages_are_archived |
| THKL11 | THK12 (was THKM08) | billed | dedup across ticks | tests/billed/test_accounting_reconciliation_billed.py::TestUS2NeverRecapturesTheSameDocument::test_second_identical_tick_adds_no_new_events |
| THKL12 | THK13 (was THKM09) | billed | conversational turn unaffected by the sweep | tests/billed/test_accounting_reconciliation_billed.py::TestUS4ConversationalTurnsAreUnaffected::test_morning_question_answers_and_creates_no_ledger_event |
| THKL13 | THK29 (was THKM16) | billed | flow_add_client changed 10-02 (ST10 fix) | tests/billed/test_denidin_morning_document_flows_e2e.py::test_create_document_t1_single_letter_added_to_stored_name |
| THKL14 | THK30 (was THKM17) | billed | same | tests/billed/test_denidin_morning_document_flows_e2e.py::test_create_document_t2_single_letter_removed_from_stored_name |
| THKL15 | THK37 (was THKM20) | exp | media + caption question | tests/expensive/test_media_e2e.py::TestWhatsAppE2E::test_e2e_pdf_with_caption_user_question |
| THKL16 | THK08 (was THKM23) | billed | roll + recall through rebuilt managers | tests/billed/test_rolling_memory_billed.py::TestAC1RollThenRecall::test_out_of_window_day_is_answered_from_its_daily_summary |
| THKL17 | THK14 (was THKM24) | billed | contact card goes through receive(content=...) | tests/billed/test_denidin_vcf_contact_e2e.py::test_godfather_shares_contact_card_complete_requires_approval |
| THKL18 | THK15 (was THKM25) | billed | same, missing field | tests/billed/test_denidin_vcf_contact_e2e.py::test_godfather_shares_contact_card_missing_email_is_asked_for |
| THKL19 | THK25 (was THKM26) | billed | typed-text approval (not buttons) - reminders | tests/billed/test_reminder_lifecycle_billed.py::TestReminderLifecycleBilled::test_godfather_creates_one_time_reminder_text_approval |
| THKL20 | (was THKM27) | billed | rolling-memory-backfill on the new stand-in DeniDin (blocker B4 fixed) | apps/rolling-memory-backfill/tests/billed/test_backfill_billed.py |
