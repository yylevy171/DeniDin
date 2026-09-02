#!/usr/bin/env bash
set -uo pipefail

# ============================================================================
# Feature 059 - the SANITY suite runner.
#
# A curated, high-signal subset of the billed/expensive tiers across BOTH apps,
# each test tagged @pytest.mark.sanity (in addition to its billed/expensive
# marker). The point is a single "is anything obviously broken end-to-end"
# pass - NOT a replacement for the full billed/expensive tiers, and NOT CI.
#
# The subset definition lives in TWO places, on purpose:
#   - the @pytest.mark.sanity decorators on the tests themselves (authoritative
#     for pytest; `-m sanity` selects exactly these);
#   - the node-id lists below (authoritative for THIS script's run order and
#     for the stop-on-first-failure sound-off).
# `scripts/verify_sanity_lists.sh` (run by nothing automatically - there
# is no CI) checks the two never drift: every id below is @pytest.mark.sanity
# and every @pytest.mark.sanity test is listed below.
#
# HOW IT RUNS (per the user's explicit instruction, 2026-09-02):
#   * Billed sanity tests run THROUGH run_multiple_billed_tests.sh - one test
#     per pytest process, stop on the FIRST failure, and SOUND OFF each test's
#     PASSED/FAILED the instant it's known (that script already prints
#     `[N/TOTAL] PASSED/FAILED:` live; this script does NOT pipe it through
#     anything that buffers, so the sound-off reaches the terminal in real
#     time). morning-mcp-app's copies of run_single_test.sh /
#     run_multiple_billed_tests.sh are symlinks to apps/denidin-app/scripts/'s
#     - ONE implementation, resolved to each app's own venv via BASH_SOURCE.
#   * The morning-mcp-app GATE test runs first. If it fails, STOP - a broken
#     tunnel / remote-MCP / Morning-sandbox path makes every denidin-app
#     Morning test below meaningless.
#   * EXPENSIVE sanity tests are NOT run here. CLAUDE.md requires a fresh,
#     explicit human approval for EVERY expensive test, one at a time, no
#     batching - structurally incompatible with an unattended runner. This
#     script just PRINTS them as a copy-paste checklist at the end.
#
# This script starts NO containers. apps/morning-mcp-app must already be
# running for its env (./run_morning_mcp.sh dev) so the tunnel/status file is
# live - same precondition as running any of these tests by hand.
# ============================================================================

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

MM_RUNNER="${ROOT}/apps/morning-mcp-app/scripts/run_multiple_billed_tests.sh"
DEN_RUNNER="${ROOT}/apps/denidin-app/scripts/run_multiple_billed_tests.sh"
DEN_SINGLE="${ROOT}/apps/denidin-app/scripts/run_single_test.sh"

# --- morning-mcp-app: the GATE (billed) -------------------------------------
MM_GATE=(
  "tests/billed/test_openai_invokes_mcp_e2e.py::test_openai_invokes_create_invoice_via_remote_mcp"
)

# --- denidin-app: billed sanity subset -------------------------------------
DEN_BILLED=(
  "tests/billed/test_real_api_connectivity.py::TestRealGreenAPIConnectivity::test_greenapi_real_connection"
  "tests/billed/test_real_api_connectivity.py::TestRealEndToEndFlow::test_complete_real_api_flow"
  "tests/billed/test_simple_text_e2e.py::TestSimpleTextE2E::test_e2e_simple_text_message_hebrew"
  "tests/billed/test_ai_handler_real_api.py::TestBotExceptionHandlingWithRealAPI::test_openai_error_handling_real_api"
  "tests/billed/test_denidin_version_query_e2e.py::test_godfather_role_gets_accurate_version_answer"
  "tests/billed/test_denidin_morning_client_management_e2e.py::test_godfather_gets_client_details_via_whatsapp"
  "tests/billed/test_denidin_morning_client_management_e2e.py::test_godfather_finds_client_via_hebrew_vowel_variant"
  "tests/billed/test_denidin_morning_client_management_e2e.py::test_godfather_get_client_details_resolves_ambiguous_first_name_prefix_after_confirmation"
  "tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_creates_invoice_via_whatsapp_button_tap"
  "tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_add_client_requires_approval"
  "tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_add_client_missing_field_is_asked_for"
  "tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_add_client_near_duplicate_name_is_asked_before_creating"
  "tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_create_document_for_existing_client_happy_path"
  "tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_create_document_for_new_client_full_flow_happy_path"
  "tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_create_document_for_new_client_asked_for_missing_info_then_provided"
  "tests/billed/test_denidin_morning_document_creation_e2e.py::test_godfather_creates_transaction_account_via_whatsapp"
  "tests/billed/test_denidin_morning_document_creation_e2e.py::test_godfather_creates_combo_document_via_whatsapp"
  "tests/billed/test_denidin_morning_document_creation_e2e.py::test_godfather_creates_credit_note_against_real_invoice"
  "tests/billed/test_denidin_morning_document_creation_e2e.py::test_godfather_creates_receipt_against_unpaid_invoice"
  "tests/billed/test_standalone_receipt_billed.py::test_godfather_records_a_deposit_as_a_standalone_receipt"
  "tests/billed/test_denidin_morning_invoice_lifecycle_e2e.py::test_godfather_gets_invoice_details_via_whatsapp"
  "tests/billed/test_denidin_morning_list_invoices_e2e.py::test_godfather_lists_invoices_via_whatsapp"
  "tests/billed/test_denidin_morning_list_invoices_e2e.py::test_client_all_payments_gets_the_complete_picture"
  "tests/billed/test_group_b_reference_approval_billed.py::TestGroupBReferenceApprovalBilled::test_receipt_against_existing_invoice_shows_reference_data"
  "tests/billed/test_group_b_reference_approval_billed.py::TestGroupBReferenceApprovalBilled::test_combo_document_against_existing_transaction_account_shows_reference_data"
  "tests/billed/test_group_etiquette_billed.py::TestGroupEtiquetteBilled::test_case1_default_address_gets_substantive_reply"
  "tests/billed/test_group_etiquette_billed.py::TestGroupEtiquetteBilled::test_case2_clearly_for_someone_else_gets_no_reply"
  "tests/billed/test_ledger_event_capture_billed.py::TestLedgerEventCaptureBilled::test_given_clear_fee_agreement_text_when_processed_then_ledger_event_captured"
  "tests/billed/test_ledger_event_capture_billed.py::TestLedgerEventCaptureBilled::test_given_ordinary_chatter_when_processed_then_no_ledger_event_captured"
  "tests/billed/test_ledger_event_capture_text_billed.py::TestLedgerEventCaptureTextBilled::test_given_real_gilyan_davidian_agreement_text_when_processed_then_captured_per_component"
  "tests/billed/test_ledger_event_capture_text_billed.py::TestLedgerEventCaptureTextBilled::test_given_real_single_day_hours_message_then_hours_and_date_correctly_persisted"
  "tests/billed/test_ledger_event_capture_text_billed.py::TestLedgerEventCaptureTextBilled::test_given_real_conditional_fee_text_then_trigger_condition_captured"
  "tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_explicit_date_lookup"
  "tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_hours_by_client_this_month"
  "tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_four_way_multi_criterion_with_date_range"
  "tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_or_across_two_identities_single_turn"
  "tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_broad_threshold_who_owes_above_amount"
  "tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_typo_variant_name_resolved_or_clarified_never_silently_dropped"
  "tests/billed/test_reminder_lifecycle_billed.py::TestReminderLifecycleBilled::test_godfather_creates_one_time_reminder_button_approval"
  "tests/billed/test_reminder_lifecycle_billed.py::TestReminderLifecycleBilled::test_godfather_creates_recurring_reminder"
  "tests/billed/test_reminder_lifecycle_billed.py::TestReminderLifecycleBilled::test_modify_single_occurrence_of_recurring_reminder"
)

# --- denidin-app: expensive sanity subset (checklist only, NEVER auto-run) --
DEN_EXPENSIVE=(
  "tests/expensive/test_image_classification_e2e.py::test_bank_test_image_is_classified_as_a_bank_deposit"
  "tests/expensive/test_image_classification_e2e.py::test_six_component_agreement_is_classified_as_an_agreement"
  "tests/expensive/test_image_classification_e2e.py::test_personal_note_is_neither_bank_nor_agreement"
  "tests/expensive/test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_agreement_image_when_processed_then_ledger_event_captured_via_image_path"
  "tests/expensive/test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_bank_deposit_screenshot_when_processed_then_captured_as_bank_deposit"
  "tests/expensive/test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_multi_component_agreement_image_then_components_correctly_persisted"
  "tests/expensive/test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_bank_deposit_image_then_full_fields_correctly_persisted"
  "tests/expensive/test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_six_component_agreement_image_mor_ben_shaya_then_all_components_correctly_persisted"
)

for r in "$MM_RUNNER" "$DEN_RUNNER" "$DEN_SINGLE"; do
  if [ ! -x "$r" ]; then
    echo "ERROR: expected executable runner at $r" >&2
    exit 2
  fi
done

echo "############################################################"
echo "# SANITY SUITE  -  ${#MM_GATE[@]} gate + ${#DEN_BILLED[@]} billed (auto)  |  ${#DEN_EXPENSIVE[@]} expensive (manual)"
echo "############################################################"
echo

echo "===== STEP 1/2 : morning-mcp-app GATE (billed) ====="
"$MM_RUNNER" "${MM_GATE[@]}"
GATE_RC=$?
if [ "$GATE_RC" -ne 0 ]; then
  echo
  echo "!!!!! GATE FAILED (rc=$GATE_RC) - STOPPING. The tunnel / remote-MCP /"
  echo "!!!!! Morning-sandbox path is broken; every denidin-app Morning test is"
  echo "!!!!! meaningless until this passes. Nothing else was run."
  exit 1
fi
echo "===== GATE PASSED ====="
echo

echo "===== STEP 2/2 : denidin-app billed sanity (${#DEN_BILLED[@]} tests, stop-on-first-failure) ====="
"$DEN_RUNNER" "${DEN_BILLED[@]}"
DEN_RC=$?
echo

echo "############################################################"
echo "# EXPENSIVE sanity tests  -  NOT run by this script."
echo "# CLAUDE.md: fresh explicit approval for EVERY expensive test, one at a"
echo "# time, no batching. Run each of these by hand:"
echo "############################################################"
for t in "${DEN_EXPENSIVE[@]}"; do
  echo "  apps/denidin-app/scripts/run_single_test.sh \"$t\""
done
echo

if [ "$DEN_RC" -ne 0 ]; then
  echo "SANITY: FAILED (denidin-app billed subset stopped on a failure, rc=$DEN_RC)."
  exit 1
fi
echo "SANITY: gate + all ${#DEN_BILLED[@]} denidin-app billed sanity tests PASSED."
echo "        (expensive checklist above still owed, by hand.)"
exit 0
