#!/usr/bin/env bash
set -uo pipefail

# ============================================================================
# Feature 059 - the SANITY suite runner.
#
# A curated, high-signal subset of the billed/expensive tiers across BOTH apps,
# each test also tagged @pytest.mark.sanity. A single "is anything obviously
# broken end-to-end" pass - NOT a replacement for the full tiers, and NOT CI.
#
# ---------------------------------------------------------------------------
# HARD RULES this script obeys (2026-09-03, after a botched run):
#
#  1. RUNS TESTS ONLY THROUGH scripts/run_single_test.sh - one test, one
#     process, per invocation. This script NEVER calls `pytest` itself and
#     never batches a bare `-m` marker. apps/morning-mcp-app/scripts/
#     run_single_test.sh is a symlink to apps/denidin-app's - one
#     implementation, resolved to each app's own venv via BASH_SOURCE.
#
#  2. SOUNDS OFF on every test the instant its result is known - a loud
#     `>>> SANITY [k/N] PASSED|FAILED|SKIP: <nodeid>` line plus a
#     grep-friendly `SANITY-PROGRESS k/N pass=P fail=F` line. Nothing is
#     buffered; run in the foreground (or `tee`) and you see each result live.
#
#  3. TRACKS PROGRESS and RESUMES. Each test's state (pending/passed/failed)
#     is written to apps/denidin-app/logs/test_logs/sanity_state.tsv after
#     every result. Re-running SKIPS anything already `passed` and picks up
#     where it stopped. --fresh wipes state; --status prints the table;
#     --include-passed re-runs green ones too; --mark <status> <nodeid>
#     hand-sets one row (used to record an expensive test you ran yourself).
#
#  4. STOP-ON-FIRST-FAILURE (billed): record it, append to the failures file,
#     print the expensive checklist, exit 1. Progress is saved - fix, re-run.
#
#  5. EXPENSIVE sanity tests are NEVER run here (CLAUDE.md: fresh explicit
#     approval for EVERY expensive test, one at a time, no batching). Only
#     printed as a checklist; tracked in state so --status shows what's owed.
# ---------------------------------------------------------------------------
#
# The subset is defined twice on purpose: @pytest.mark.sanity decorators
# (authoritative for `-m sanity`) and the arrays below (run order / state).
# scripts/verify_sanity_lists.sh asserts they never drift.
#
# Precondition: apps/morning-mcp-app must already be running for its env
# (./run_morning_mcp.sh dev). This script starts NO containers.
#
# Usage:
#   ./scripts/run_sanity.sh                    # gate + billed, resuming
#   ./scripts/run_sanity.sh --fresh            # wipe state, run all
#   ./scripts/run_sanity.sh --status           # print state table, exit
#   ./scripts/run_sanity.sh --include-passed   # re-run green ones too
#   ./scripts/run_sanity.sh --mark passed "tests/expensive/....::test_x"
# ============================================================================

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEN_SINGLE="${ROOT}/apps/denidin-app/scripts/run_single_test.sh"
MM_SINGLE="${ROOT}/apps/morning-mcp-app/scripts/run_single_test.sh"
STATE_DIR="${ROOT}/apps/denidin-app/logs/test_logs"
STATE_FILE="${STATE_DIR}/sanity_state.tsv"
FAIL_FILE="${ROOT}/specs/done/v0.5.4/059-stabilize-tests-sanity-suite/sanity-failures.md"

# ---- ordered test lists.  entry = "<app>|<nodeid>"  (app = mm | den) -------
GATE=(
  "mm|tests/billed/test_openai_invokes_mcp_e2e.py::test_openai_invokes_create_invoice_via_remote_mcp"
)

BILLED=(
  "den|tests/billed/test_real_api_connectivity.py::TestRealGreenAPIConnectivity::test_greenapi_real_connection"
  "den|tests/billed/test_real_api_connectivity.py::TestRealEndToEndFlow::test_complete_real_api_flow"
  "den|tests/billed/test_simple_text_e2e.py::TestSimpleTextE2E::test_e2e_simple_text_message_hebrew"
  "den|tests/billed/test_ai_handler_real_api.py::TestBotExceptionHandlingWithRealAPI::test_openai_error_handling_real_api"
  "den|tests/billed/test_denidin_version_query_e2e.py::test_godfather_role_gets_accurate_version_answer"
  "den|tests/billed/test_denidin_morning_client_management_e2e.py::test_godfather_gets_client_details_via_whatsapp"
  "den|tests/billed/test_denidin_morning_client_management_e2e.py::test_godfather_finds_client_via_hebrew_vowel_variant"
  "den|tests/billed/test_denidin_morning_client_management_e2e.py::test_godfather_get_client_details_resolves_ambiguous_first_name_prefix_after_confirmation"
  "den|tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_creates_invoice_via_whatsapp_button_tap"
  "den|tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_add_client_requires_approval"
  "den|tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_add_client_missing_field_is_asked_for"
  "den|tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_add_client_near_duplicate_name_is_asked_before_creating"
  "den|tests/billed/test_denidin_morning_document_flows_e2e.py::test_create_document_for_existing_client_happy_path"
  "den|tests/billed/test_denidin_morning_document_flows_e2e.py::test_create_document_for_new_client_full_flow_happy_path"
  "den|tests/billed/test_denidin_morning_document_flows_e2e.py::test_create_document_for_new_client_asked_for_missing_info_then_provided"
  "den|tests/billed/test_denidin_morning_document_creation_e2e.py::test_godfather_creates_transaction_account_via_whatsapp"
  "den|tests/billed/test_denidin_morning_document_creation_e2e.py::test_godfather_creates_combo_document_via_whatsapp"
  "den|tests/billed/test_denidin_morning_document_creation_e2e.py::test_godfather_creates_credit_note_against_real_invoice"
  "den|tests/billed/test_denidin_morning_document_creation_e2e.py::test_godfather_creates_receipt_against_unpaid_invoice"
  "den|tests/billed/test_standalone_receipt_billed.py::test_godfather_records_a_deposit_as_a_standalone_receipt"
  "den|tests/billed/test_denidin_morning_invoice_lifecycle_e2e.py::test_godfather_gets_invoice_details_via_whatsapp"
  "den|tests/billed/test_denidin_morning_list_invoices_e2e.py::test_godfather_lists_invoices_via_whatsapp"
  "den|tests/billed/test_denidin_morning_list_invoices_e2e.py::test_client_all_payments_gets_the_complete_picture"
  "den|tests/billed/test_group_b_reference_approval_billed.py::TestGroupBReferenceApprovalBilled::test_receipt_against_existing_invoice_shows_reference_data"
  "den|tests/billed/test_group_b_reference_approval_billed.py::TestGroupBReferenceApprovalBilled::test_combo_document_against_existing_transaction_account_shows_reference_data"
  "den|tests/billed/test_group_etiquette_billed.py::TestGroupEtiquetteBilled::test_case1_default_address_gets_substantive_reply"
  "den|tests/billed/test_group_etiquette_billed.py::TestGroupEtiquetteBilled::test_case2_clearly_for_someone_else_gets_no_reply"
  "den|tests/billed/test_ledger_event_capture_billed.py::TestLedgerEventCaptureBilled::test_given_clear_fee_agreement_text_when_processed_then_ledger_event_captured"
  "den|tests/billed/test_ledger_event_capture_billed.py::TestLedgerEventCaptureBilled::test_given_ordinary_chatter_when_processed_then_no_ledger_event_captured"
  "den|tests/billed/test_ledger_event_capture_text_billed.py::TestLedgerEventCaptureTextBilled::test_given_real_gilyan_davidian_agreement_text_when_processed_then_captured_per_component"
  "den|tests/billed/test_ledger_event_capture_text_billed.py::TestLedgerEventCaptureTextBilled::test_given_real_single_day_hours_message_then_hours_and_date_correctly_persisted"
  "den|tests/billed/test_ledger_event_capture_text_billed.py::TestLedgerEventCaptureTextBilled::test_given_real_conditional_fee_text_then_trigger_condition_captured"
  "den|tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_explicit_date_lookup"
  "den|tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_hours_by_client_last_month"
  "den|tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_four_way_multi_criterion_with_date_range"
  "den|tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_or_across_two_identities_single_turn"
  "den|tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_broad_threshold_who_owes_above_amount"
  "den|tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_typo_variant_name_resolved_or_clarified_never_silently_dropped"
  "den|tests/billed/test_reminder_lifecycle_billed.py::TestReminderLifecycleBilled::test_godfather_creates_one_time_reminder_button_approval"
  "den|tests/billed/test_reminder_lifecycle_billed.py::TestReminderLifecycleBilled::test_godfather_creates_recurring_reminder"
  "den|tests/billed/test_reminder_lifecycle_billed.py::TestReminderLifecycleBilled::test_modify_single_occurrence_of_recurring_reminder"
)

EXPENSIVE=(
  "den|tests/expensive/test_image_classification_e2e.py::test_bank_test_image_is_classified_as_a_bank_deposit"
  "den|tests/expensive/test_image_classification_e2e.py::test_six_component_agreement_is_classified_as_an_agreement"
  "den|tests/expensive/test_image_classification_e2e.py::test_personal_note_is_neither_bank_nor_agreement"
  "den|tests/expensive/test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_agreement_image_when_processed_then_ledger_event_captured_via_image_path"
  "den|tests/expensive/test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_bank_deposit_screenshot_when_processed_then_captured_as_bank_deposit"
  "den|tests/expensive/test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_multi_component_agreement_image_then_components_correctly_persisted"
  "den|tests/expensive/test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_bank_deposit_image_then_full_fields_correctly_persisted"
  "den|tests/expensive/test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_six_component_agreement_image_mor_ben_shaya_then_all_components_correctly_persisted"
)

ALL_ENTRIES=( "${GATE[@]}" "${BILLED[@]}" "${EXPENSIVE[@]}" )

# --- args ----------------------------------------------------------------
MODE="run"; FRESH=0; INCLUDE_PASSED=0; MARK_STATUS=""; MARK_NODE=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --status)         MODE="status" ;;
    --fresh)          FRESH=1 ;;
    --include-passed) INCLUDE_PASSED=1 ;;
    --mark)           MODE="mark"; MARK_STATUS="${2:-}"; MARK_NODE="${3:-}"; shift 2 ;;
    -h|--help)        sed -n '1,60p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1 (see --help)" >&2; exit 2 ;;
  esac
  shift
done

# --- runners must exist (dereferences symlinks) -------------------------
for r in "$DEN_SINGLE" "$MM_SINGLE"; do
  if [ ! -x "$r" ]; then
    echo "ERROR: missing/broken/non-executable runner: $r" >&2
    exit 2
  fi
done

mkdir -p "$STATE_DIR"; touch "$STATE_FILE"
if [ "$FRESH" -eq 1 ]; then : > "$STATE_FILE"; echo "(state wiped: ${STATE_FILE#$ROOT/})"; fi

# --- state helpers  (TSV: <app>\t<nodeid>\t<status>\t<iso-ts>) ----------
get_state() { awk -F'\t' -v a="$1" -v n="$2" '$1==a && $2==n {print $3; exit}' "$STATE_FILE" 2>/dev/null || true; }
set_state() {
  local a="$1" n="$2" s="$3" tmp; tmp="$(mktemp)"
  awk -F'\t' -v a="$a" -v n="$n" -v s="$s" -v ts="$(date +%Y-%m-%dT%H:%M:%S)" '
    BEGIN{OFS="\t"} !($1==a && $2==n){print} END{print a,n,s,ts}
  ' "$STATE_FILE" 2>/dev/null > "$tmp"
  mv "$tmp" "$STATE_FILE"
}

entry_known() { local x; for x in "${ALL_ENTRIES[@]}"; do [ "$x" = "$1" ] && return 0; done; return 1; }

# seed unknown ids as pending
for entry in "${ALL_ENTRIES[@]}"; do
  a="${entry%%|*}"; n="${entry#*|}"
  [ -z "$(get_state "$a" "$n")" ] && set_state "$a" "$n" pending
done

print_table() {
  local entry a n s
  printf '%-4s %-9s %s\n' app status nodeid
  printf '%-4s %-9s %s\n' ---- --------- ----------------------------------------------
  for entry in "${ALL_ENTRIES[@]}"; do
    a="${entry%%|*}"; n="${entry#*|}"
    s="$(get_state "$a" "$n")"; [ -z "$s" ] && s="pending"
    printf '%-4s %-9s %s\n' "$a" "$s" "$n"
  done
  echo
  printf 'counts: '; awk -F'\t' '{c[$3]++} END{for(k in c) printf "%s=%d  ", k, c[k]; print ""}' "$STATE_FILE"
}

print_expensive_checklist() {
  local entry a n s
  echo
  echo "############################################################"
  echo "# EXPENSIVE sanity tests - NOT run by this script."
  echo "# CLAUDE.md: fresh explicit approval for EVERY expensive test, one"
  echo "# at a time, no batching. Run each by hand, then record it with:"
  echo "#   ./scripts/run_sanity.sh --mark passed \"<nodeid>\""
  echo "############################################################"
  for entry in "${EXPENSIVE[@]}"; do
    a="${entry%%|*}"; n="${entry#*|}"
    s="$(get_state "$a" "$n")"; [ -z "$s" ] && s="pending"
    printf '  [%-7s] apps/denidin-app/scripts/run_single_test.sh "%s"\n' "$s" "$n"
  done
}

results_file_for() {
  local a="$1" n="$2" dir safe
  if [ "$a" = "mm" ]; then dir="${ROOT}/apps/morning-mcp-app/logs/test_logs/pytest_results"
  else dir="${ROOT}/apps/denidin-app/logs/test_logs/pytest_results"; fi
  safe="$(printf '%s' "$n" | tr -c 'A-Za-z0-9_.' '_')"
  ls -t "${dir}/${safe}_"*.txt 2>/dev/null | head -1
}
record_failure() {
  local a="$1" n="$2" rf; rf="$(results_file_for "$a" "$n")"
  mkdir -p "$(dirname "$FAIL_FILE")"
  {
    echo
    echo "## FAILED $(date +%Y-%m-%dT%H:%M:%S) — \`$n\`"
    echo "- app \`$a\` | via \`run_sanity.sh\` -> \`run_single_test.sh\`"
    if [ -n "$rf" ]; then
      echo "- results: \`${rf#$ROOT/}\`"
      echo '```'
      grep -E '^(FAILED |E +|_{6,}| +assert )' "$rf" | head -40
      echo '```'
    else
      echo "- results: (none found)"
    fi
    echo "**Revisit:** classify (real bug / flaky-model / over-strict assertion / sandbox-clutter) and act."
  } >> "$FAIL_FILE"
  echo "   -> appended to ${FAIL_FILE#$ROOT/}"
}

# --- modes -------------------------------------------------------------
if [ "$MODE" = "status" ]; then print_table; exit 0; fi

if [ "$MODE" = "mark" ]; then
  case "$MARK_STATUS" in passed|failed|pending|skipped) ;; *)
    echo "ERROR: --mark needs a status (passed|failed|pending|skipped) and a nodeid" >&2; exit 2 ;;
  esac
  # accept the bare nodeid; find which app it belongs to
  hit=""
  for entry in "${ALL_ENTRIES[@]}"; do
    [ "${entry#*|}" = "$MARK_NODE" ] && hit="$entry" && break
  done
  if [ -z "$hit" ]; then echo "ERROR: '$MARK_NODE' is not a sanity nodeid" >&2; exit 2; fi
  set_state "${hit%%|*}" "${hit#*|}" "$MARK_STATUS"
  echo "marked: ${hit#*|}  ->  $MARK_STATUS"
  exit 0
fi

# --- the run  (gate + billed only) ------------------------------------
RUNSET=( "${GATE[@]}" "${BILLED[@]}" )
N="${#RUNSET[@]}"; k=0; pass=0; fail=0; skip=0; ran=0

echo "############################################################"
echo "# SANITY  -  ${#GATE[@]} gate + ${#BILLED[@]} billed  (expensive: ${#EXPENSIVE[@]}, manual)"
echo "# state: ${STATE_FILE#$ROOT/}   (--status to view, --fresh to reset)"
echo "############################################################"

for entry in "${RUNSET[@]}"; do
  k=$((k + 1)); a="${entry%%|*}"; n="${entry#*|}"
  cur="$(get_state "$a" "$n")"

  if [ "$cur" = "passed" ] && [ "$INCLUDE_PASSED" -eq 0 ]; then
    skip=$((skip + 1)); pass=$((pass + 1))
    echo ">>> SANITY [$k/$N] SKIP (already passed): $n"
    echo "SANITY-PROGRESS $k/$N pass=$pass fail=$fail skip=$skip"
    continue
  fi

  echo
  echo "------------------------------------------------------------"
  echo ">>> SANITY [$k/$N] RUNNING ($a): $n"
  echo "------------------------------------------------------------"
  set_state "$a" "$n" running
  runner="$DEN_SINGLE"; [ "$a" = "mm" ] && runner="$MM_SINGLE"
  "$runner" "$n"
  rc=$?
  ran=$((ran + 1))

  if [ "$rc" -eq 0 ]; then
    set_state "$a" "$n" passed; pass=$((pass + 1))
    echo ">>> SANITY [$k/$N] PASSED: $n"
    echo "SANITY-PROGRESS $k/$N pass=$pass fail=$fail skip=$skip"
  elif [ "$rc" -eq 3 ]; then
    set_state "$a" "$n" pending
    echo ">>> SANITY [$k/$N] SETUP ERROR (venv, not a test result): $n"
    echo "SANITY-PROGRESS $k/$N pass=$pass fail=$fail skip=$skip  (aborted: setup)"
    exit 3
  else
    set_state "$a" "$n" failed; fail=$((fail + 1))
    echo ">>> SANITY [$k/$N] FAILED: $n"
    echo "SANITY-PROGRESS $k/$N pass=$pass fail=$fail skip=$skip"
    record_failure "$a" "$n"
    echo
    echo "############################################################"
    echo "# STOP-ON-FIRST-FAILURE. Progress saved."
    echo "#   passed so far : $pass   (of which already-green skips: $skip)"
    echo "#   FAILED        : $n"
    echo "#   resume        : ./scripts/run_sanity.sh"
    echo "############################################################"
    print_expensive_checklist
    exit 1
  fi
done

echo
echo "############################################################"
echo "# SANITY billed: ALL PASSED  (pass=$pass, newly-run=$ran, skipped-green=$skip, of $N)"
echo "############################################################"
print_expensive_checklist
exit 0
