# diff1 (constitution — near-identical-name bullet) — impacted tests

**Change:** one bullet added to `config/runtime_constitution.md`, in the
"Ambiguous names, OR, NOT, and threshold questions" subsection of
"Ledger Event Querying" — a one/two-character name difference (typo,
vowel-letter swap) still counts as "more than one distinct name came back",
so the model must sum-if-resolved-as-same-person or name both spellings and
ask, never silently answer from one.

**Scope:** in-context only when `query_ledger_events` is attached
(godfather/admin RBAC turns). Read-only tool — no write-path exposure.
Direction: more asking / less silent guessing.

## Run these (all 23 `test_ledger_query_billed.py` billed tests)

Every test in this file exercises `query_ledger_events` through a real
OpenAI call, so all are in the blast radius. The two that assert directly
on multi-name behaviour are marked **[direct]**.

```
tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_typo_variant_name_resolved_or_clarified_never_silently_dropped   [direct — the F1 test]
tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_ambiguous_name_asks_then_both_confirmed_merges                   [direct]
tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_payment_under_a_different_payer_name_still_resolves              [direct]
tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_owed_via_transaction_account_no_agreement_at_all
tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_agreement_modification_reports_the_latest_state
tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_hours_by_payer_this_month
tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_payer_name_search
tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_four_way_multi_criterion_with_date_range
tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_credit_note_reverses_a_receipt_so_invoice_stays_owed
tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_hours_by_client_last_month
tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_combined_owed_across_two_clients_requires_multiple_search_rounds
tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_no_match_never_fabricates
tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_total_paid_dedups_matching_deposit_and_receipt
tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_natural_language_exclusion
tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_monthly_income_aggregation
tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_exclusion_with_percent_threshold
tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_conditional_component_status_stays_uncertain_not_guessed
tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_explicit_amount_lookup
tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_broad_threshold_who_owes_above_amount
tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_cross_category_two_figures_for_one_identity
tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_or_across_two_identities_single_turn
tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_explicit_date_lookup
tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_tax_invoice_closed_by_receipt_excluded_from_owed_sum
```

## Parallel run command

```
scripts/run_parallel_tests.sh -n 6 tests/billed/test_ledger_query_billed.py
```
(single file → runs effectively serially under `--dist loadfile`; use
`scripts/run_multiple_billed_tests.sh` with the node ids above for
stop-on-fail, or just the whole file.)
