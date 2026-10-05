# Acceptance Tests: Feature 098

Every new `billed` / `expensive` test written for this feature. **None has been run yet.**
There are no `expensive` tests: every scenario is text-only.

Run each one through `scripts/run_single_test.sh <node id>` (in that app), or a sequence
through `scripts/run_multiple_billed_tests.sh`.

## Before running

- **Morning-MCP (UAT 4.1):** the dev Morning-MCP container must be rebuilt with Feature 098
  (`stop_all.sh dev` then `run_all.sh dev`, after a build). This needs explicit approval,
  like every environment start. Runnable as soon as that's done.
- **DeniDin (UATs 1.1–3.5 and the edge cases):** deferred, per PM D-3. Run after Feature 063
  merges, on the backbone, with the 063 adoption checklist in `plan.md` applied. Needs the
  same rebuilt dev environment.

## Morning-MCP (`apps/morning-mcp-app`)

| Node id | UAT | Tier | Status |
|---|---|---|---|
| `tests/billed/test_allocation_tax_id_billed.py::test_openai_create_combo_refused_without_client_id` | 4.1 | billed | runnable after rebuild |

## DeniDin (`apps/denidin-app`)

All in `tests/billed/test_allocation_tax_id_billed.py`, all `billed`, all **deferred
until 063 merges**.

| Test | UAT |
|---|---|
| `test_uat_1_1_combo_above_threshold_asks_for_id` | 1.1 |
| `test_uat_1_2_tax_invoice_above_threshold_asks_for_id` | 1.2 |
| `test_uat_1_3_closing_transaction_account_above_threshold_asks_for_id` | 1.3 |
| `test_uat_2_1_valid_id_saved_then_document_issued` | 2.1 |
| `test_uat_2_2_wrong_format_asks_again` | 2.2 |
| `test_uat_2_3_user_declines` | 2.3 |
| `test_uat_3_1_below_threshold` | 3.1 |
| `test_uat_3_2_exactly_the_threshold_before_vat` | 3.2 |
| `test_uat_3_3_client_already_has_an_id` | 3.3 |
| `test_uat_3_4_transaction_account_is_out_of_scope` | 3.4 |
| `test_uat_3_5_just_above_the_threshold_asks_for_id` | 3.5 |
| `test_edge_id_given_in_the_original_request` | Edge case: ID in the request |
| `test_edge_id_saved_but_document_declined` | Edge case: ID saved, document declined |

## Where the tests differ from the UAT wording

- **"Then, in Morning" checks** are made through further WhatsApp turns that ask DeniDin to
  read Morning directly (`get_client_details`, `list_invoices`). The DeniDin billed suite
  never calls Morning's API itself (its app-wall rule).
- **UAT 1.3's open transaction account** is created through DeniDin (an approved
  `create_transaction_account` turn), not "directly in the sandbox by the test". Same
  app-wall reason.
- **UAT 4.1's prompt** tells the model to call `create_combo_document` directly, without
  checking the client first. Without that, the model may read the tool description, check
  the client, and never make the call the scenario is about.

## Residual risk (analyze finding A2)

Existing billed/expensive tests that issue a 305/320 above 5,000 ₪ before VAT for a client
with no ID would now be refused. A text search found none. Image-driven `expensive` tests
can't be fully checked by text search, so this is confirmed only when those tiers next run.
