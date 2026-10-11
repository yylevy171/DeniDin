# bugfix-061 — VAT test categorization

Every test across the repo that either states VAT in its prompt/source text, or expects/answers
a VAT-related question, categorized per the scheme below. Read-only analysis, no code/test
changes made as part of this.

## Categories

- **C1a / C1b** — standalone `create_combo_document` (320) or standalone `create_receipt` (400):
  VAT must default to "included"; no clarifying question is ever expected.
  C1a = prompt/source text states VAT anyway; C1b = it doesn't (the common case — includes
  **bank-deposit events**, which are always assumed VAT-included from an image with no VAT
  text/prompt at all, and must never trigger a clarification).
- **C2a / C2b / C2c** — `create_transaction_account` (300) / `create_invoice` (305): VAT can be
  stated or left silent; if silent, a follow-up question IS expected.
  C2a = VAT stated in prompt text; C2b = not stated, follow-up expected;
  **C2c = fee-agreement ("הסכם") capture** — VAT is never required and no clarification is ever
  expected, whether or not the source text happens to mention it.
- **C3a / C3b** — by-reference actions: `create_credit_note` (330), `create_receipt` against an
  existing invoice (400 by-ref), `create_combo_document_as_reference` (320 by-ref). VAT can be
  stated (C3a) or not (C3b); no clarifying question is expected either way.

## Relevance rule (bugfix-061)

A test is **bug61-relevant** ("yes") when it demonstrates/guards against the actual defect —
a VAT question asked (or expected) where the rules say it shouldn't be, or missing where it
should be:
- **C1b with a VAT question** — should never ask, but does/might.
- **C2c with a VAT question** — should never ask, but does/might.
- **C2b without a VAT question** — should ask, but doesn't (or isn't verified to).
- **any C3 (a or b) with a VAT question** — should never ask, but does/might.

Everything else ("vat question" column = "no" for C1b/C3, "yes" for C2b, or C2a/N/A regardless)
is **not** relevant to this bug — it's either correct behavior or a different concern entirely
(e.g. VAT *stated* correctly, C2a).

## Full test list

| Test name | Category | VAT question (yes/no) | bug61 relevant (yes/no) |
|---|---|---|---|
| `test_denidin_morning_document_creation_e2e.py::test_godfather_creates_transaction_account_via_whatsapp` | C2b | Yes | No |
| `test_denidin_morning_document_creation_e2e.py::test_godfather_creates_combo_document_via_whatsapp` | C1b | No | No |
| `test_denidin_morning_document_creation_e2e.py::test_godfather_creates_credit_note_against_real_invoice` | C3b | No | No |
| `test_denidin_morning_document_creation_e2e.py::test_credit_note_request_with_invalid_invoice_number_fails_gracefully` | C3b | No | No |
| `test_denidin_morning_document_creation_e2e.py::test_godfather_creates_receipt_against_unpaid_invoice` | C3b | No | No |
| `test_denidin_morning_document_creation_e2e.py::test_receipt_request_with_exact_invoice_amount_resolves_correctly` | C3b | No | No |
| `test_denidin_morning_document_creation_e2e.py::test_receipt_request_for_already_paid_invoice_handled_sensibly` | C3b | No | No |
| `test_denidin_morning_invoice_creation_e2e.py::test_godfather_creates_invoice_via_whatsapp` | C1b | No | No |
| `test_denidin_morning_invoice_creation_e2e.py::test_godfather_creates_invoice_via_whatsapp_button_tap` | C2b | No (not verified either way) | **Yes** |
| `test_e2e_ledger_069_morning_create_billed.py::test_us2_morning_create_is_captured_synchronously` | C1b | No | No |
| `test_denidin_approval_content_and_vat_e2e.py::test_vat_included_transaction_account_is_stored_at_the_approved_amount` | C2a | No | No |
| `test_denidin_approval_content_and_vat_e2e.py::test_unstated_vat_is_asked_about_rather_than_assumed` | C2b | Yes | No |
| `test_denidin_approval_content_and_vat_e2e.py::test_the_approval_states_every_mandatory_element` | C2a | No | No |
| `test_denidin_approval_content_and_vat_e2e.py::test_a_client_qualified_by_its_tax_id_still_resolves` | C2a | No | No |
| `test_group_b_reference_approval_billed.py::test_receipt_against_existing_invoice_shows_reference_data` — **seed** (create_invoice) | C2a | No | No |
| `test_group_b_reference_approval_billed.py::test_receipt_against_existing_invoice_shows_reference_data` — **main** (create_receipt by-ref) | C3b | No | No |
| `test_group_b_reference_approval_billed.py::test_credit_note_against_existing_invoice_shows_reference_data` — **seed** (create_invoice) | C2a | No | No |
| `test_group_b_reference_approval_billed.py::test_credit_note_against_existing_invoice_shows_reference_data` — **main** (create_credit_note) | C3b | No | No |
| `test_group_b_reference_approval_billed.py::test_combo_document_against_existing_transaction_account_shows_reference_data` — **seed** (create_transaction_account) | C2a | No | No |
| `test_group_b_reference_approval_billed.py::test_combo_document_against_existing_transaction_account_shows_reference_data` — **main** (create_combo_document_as_reference) | C3a | No | No |
| `test_group_b_reference_approval_billed.py::test_multi_turn_clarification_uses_the_real_internal_id_not_the_display_number` | C3b | Yes (test tolerates one being asked) | **Yes** |
| `test_ledger_event_capture_text_billed.py::test_given_real_gilyan_davidian_agreement_text_when_processed_then_captured_per_component` | C2c | No | No |
| `test_ledger_event_capture_text_billed.py::test_given_new_agreement_flat_fee_then_all_fields_correctly_persisted` | C2c | No | No |
| `test_ledger_event_capture_text_billed.py::test_given_agreement_percent_based_fee_then_percent_fields_correct` | C2c | No | No |
| `test_ledger_event_capture_text_billed.py::test_given_real_single_day_hours_message_then_hours_and_date_correctly_persisted` | C2c | No | No |
| `test_ledger_event_capture_text_billed.py::test_given_real_two_day_hours_message_then_split_per_day_with_correct_dates` | C2c | No | No |
| `test_ledger_event_capture_text_billed.py::test_given_real_hours_message_with_payer_reference_then_payer_name_captured` | C2c | No | No |
| `test_ledger_event_capture_text_billed.py::test_given_real_conditional_fee_text_then_trigger_condition_captured` | C2c | No | No |
| `test_ledger_event_capture_text_billed.py::test_given_real_addition_language_then_reference_hint_captured` | C2c | No | No |
| `test_ledger_event_capture_text_billed.py::test_given_ambiguous_hyphenated_name_then_model_asks_clarifying_question` | C2c | No (clarification is about the name, not VAT) | No |
| `test_ledger_event_capture_text_billed.py::test_given_real_minimal_hourly_message_then_captured_not_missed` | C2c | No | No |
| `test_ledger_event_capture_e2e.py::test_given_real_multi_component_agreement_image_then_components_correctly_persisted` | C2c | No | No |
| `test_ledger_event_capture_e2e.py::test_given_real_bank_deposit_image_then_full_fields_correctly_persisted` | C1b | No | No |
| `test_ledger_event_capture_e2e.py::test_given_real_six_component_agreement_image_mor_ben_shaya_then_all_components_correctly_persisted` | C2c | No | No |
| `test_ledger_event_capture_e2e.py::test_given_non_agreement_image_when_processed_then_no_ledger_event_captured` | N/A (false-positive guard, no VAT of any kind) | No | No |
| `test_group_b_reference_approval_e2e.py::test_given_a_deposit_matching_an_existing_tax_invoice_then_a_receipt_closes_it` — **seed** (create_invoice) | C2a | No | No |
| `test_group_b_reference_approval_e2e.py::test_given_a_deposit_matching_an_existing_tax_invoice_then_a_receipt_closes_it` — **main** (create_receipt by-ref, image-triggered) | C3b | No | No |
| `test_image_classification_e2e.py::test_bank_test_image_is_classified_as_a_bank_deposit` | N/A (pure classification, no VAT assertion) | No | No |
| `test_image_classification_e2e.py::test_kehunai_deposit_is_classified_as_a_bank_deposit` | N/A | No | No |
| `test_image_classification_e2e.py::test_idan_shabtai_agreement_is_classified_as_an_agreement` | N/A | No | No |
| `test_image_classification_e2e.py::test_multi_component_agreement_is_classified_as_an_agreement` | N/A | No | No |
| `test_image_classification_e2e.py::test_six_component_agreement_is_classified_as_an_agreement` | N/A | No | No |
| `test_image_classification_e2e.py::test_personal_note_is_neither_bank_nor_agreement` | N/A | No | No |
| `test_image_classification_e2e.py::test_whatsapp_marciano_bibi_fee_proposal_is_an_agreement` | N/A | No | No |
| `test_image_classification_e2e.py::test_whatsapp_mendel_shmulik_fee_proposal_is_an_agreement` | N/A | No | No |
| `test_image_classification_e2e.py::test_whatsapp_email_screenshot_is_never_a_bank_deposit` | N/A | No | No |

## bug61-relevant tests (summary)

Only **2** of the tests above actually bear on the bugfix-061 defect as scoped:

1. `test_denidin_morning_invoice_creation_e2e.py::test_godfather_creates_invoice_via_whatsapp_button_tap`
   — C2b, VAT left unstated, but the test never verifies a follow-up VAT question happened
   (or didn't) before letting the button tap approve — a gap, not a passing/failing assertion of
   the fixed behavior either way.
2. `test_group_b_reference_approval_billed.py::test_multi_turn_clarification_uses_the_real_internal_id_not_the_display_number`
   — C3b, and the test's own driver *tolerates* a VAT clarifying question appearing mid-flow,
   which contradicts the rule that no C3 action should ever prompt one.

Neither of these has a fixed test asserting the *correct* post-bugfix-061 behavior for its own
scenario — both are flagged as gaps, not as currently-red regression tests.
