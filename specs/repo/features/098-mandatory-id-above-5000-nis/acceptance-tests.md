# Acceptance Tests: Feature 098

Every new `billed` / `expensive` test written for this feature. **None has been run yet.**
There are no `expensive` tests: every scenario is text-only.

Run each one through `scripts/run_single_test.sh <node id>` (in that app), or a sequence
through `scripts/run_multiple_billed_tests.sh`.

## Before running

- **Morning-MCP (UAT 4.1):** the dev Morning-MCP container must be rebuilt with Feature 098
  (`stop_all.sh dev` then `run_all.sh dev`, after a build). This needs explicit approval,
  like every environment start. Runnable as soon as that's done.
- **DeniDin (UATs 1.1–3.5 and the edge cases):** run on the backbone (063 merged; plan.md
  Phase 5 applied). `config.test.json` has `enable_capability_backbone: true`, so no
  override is needed. Needs the same rebuilt dev environment.

## T1 - new tests (written for this feature)

Every approved UAT (1.1-4.1) and both edge cases have a test. Feature 086's edge case
(one 320 closing several transaction accounts) needs none until 086 lands.

### Morning-MCP (`apps/morning-mcp-app`)

| Node id | UAT | Tier | Status |
|---|---|---|---|
| `tests/billed/test_allocation_tax_id_billed.py::test_openai_create_combo_refused_without_client_id` | 4.1 | billed | runnable after rebuild |

### DeniDin (`apps/denidin-app`)

All in `tests/billed/test_allocation_tax_id_billed.py`, all `billed`, run on the backbone
(063 merged; Phase 5 applied). Adapted to 063's helpers: approvals are checked as "buttons
on screen" (`approval_buttons_on_screen`), and which write an approval was for is proven on
the tap turn, by the tool that actually runs.

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

## T2 - existing tests that become relevant with a small adjustment

Not adjusted: changing an approved test needs PM sign-off. Each adds coverage T1 doesn't have.

| Test | Adjustment | Coverage it would add |
|---|---|---|
| `tests/billed/test_group_b_reference_approval_billed.py::TestGroupBReferenceApprovalBilled::test_combo_document_against_existing_transaction_account_shows_reference_data` | Seed the 300 above 5,000 ₪ for a client whose ID is on file. | Closing a 300 above the threshold through DeniDin when the ID exists: Morning-MCP reads the client's current record, the document is created, and the approval still shows the reference data. UAT 3.3 covers only a fresh 320. |
| `tests/billed/test_e2e_ledger_069_morning_create_billed.py::TestLedgerPostTurnCaptureMorningCreate::test_us2_morning_create_is_captured_synchronously` | Raise the 320 from 1,200 ₪ to above 5,000 ₪ and seed the client with an ID. | The ledger still captures an above-threshold document in the same turn. |
| `tests/billed/test_denidin_morning_client_management_e2e.py::test_godfather_updates_client_via_whatsapp` | Update the ID (ת.ז / ח.פ) instead of the phone. | Saving an ID on its own, outside the chain, and reading it back with `get_client_details`. |

## T3 - existing tests to run as is (regression)

They exercise code or prompts this feature changed. On the backbone that is
`cap_invoicing_write`, `cap_client_write`, the three 305/320 issuing flows and
`flow_modify_client`; in Morning-MCP, the three create tools. All their amounts are below
5,000 ₪, or the document type is out of scope, so all are expected to pass unchanged. Same
prerequisites as T1 (rebuilt dev environment).

**Morning-MCP, billed**
- `tests/billed/test_openai_invokes_mcp_e2e.py` (whole file; the sanity gate)
- `tests/billed/test_create_returns_full_document_e2e.py::test_create_combo_document_result_carries_the_full_document` - a 120 ₪ 320 (new on master, 2026-10-06)

**DeniDin, billed** (whole files unless named)
- `tests/billed/test_denidin_morning_invoice_creation_e2e.py` (10) - 305/320 creation
- `tests/billed/test_denidin_morning_document_creation_e2e.py` (7) - 305/320/300/400
- `tests/billed/test_denidin_morning_document_flows_e2e.py` (8) - 305/320 flows
- `tests/billed/test_denidin_morning_invoice_lifecycle_e2e.py` (7) - 305, 300, closing
- `tests/billed/test_group_b_reference_approval_billed.py` (4) - closing a 300 (the as-reference path changed)
- `tests/billed/test_denidin_approval_content_and_vat_e2e.py` (4) - approval content, VAT, a client with a ח.פ
- `tests/billed/test_e2e_ledger_069_morning_create_billed.py` (1) - ledger capture of a 320
- `tests/billed/test_denidin_morning_client_management_e2e.py` (10) - `update_client` / `add_client` (constitution `tax_id` text changed)
- `tests/billed/test_small_bugfixes_027_032_054_058_061_billed.py::test_bugfix_027_client_stored_with_ascii_apostrophe_can_get_a_document` - a 320
- `tests/billed/test_denidin_morning_list_invoices_e2e.py::test_godfather_searches_invoice_by_number_finds_it` - seeds a 305
- `tests/billed/test_reminder_lifecycle_billed.py`, `tests/billed/test_ledger_query_billed.py` - listed because of a cross-reference added to their *legacy* constitution sections. 098 changed none of their backbone prompts, so on the backbone they are no longer affected (open question: keep or drop).

**DeniDin, expensive** (one at a time, each needs its own approval)
- `tests/expensive/test_group_b_reference_approval_e2e.py::TestGroupBReferenceApprovalE2E::test_given_a_deposit_matching_an_existing_tax_invoice_then_a_receipt_closes_it` - seeds a 305 (1,500 ₪)
- `tests/expensive/test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_bank_deposit_image_then_full_fields_correctly_persisted` - creates a 320 (554 ₪)

## Integration coverage added alongside (not billed)

- **Backbone:** `apps/denidin-app/tests/integration/test_backbone_allocation_tax_id_chain.py`
  (3 tests, passing): the "yes" that saves the ID runs `update_client` and offers the
  document's approval in the same turn, with buttons and no write-guard note; the next "yes"
  is again an approved write. A typed "כן", a button tap, and declining the document.
- **Legacy (flag off):** `apps/denidin-app/tests/integration/test_allocation_tax_id_approval_routing.py`
  (3 tests, passing): the same chain through the pending-approval manager.

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

## Residual risk (analyze finding A2) - closed

Audited 2026-10-06: no existing billed or expensive test issues a 305/320 above 5,000 ₪
before VAT. The largest amounts in that set are 1,888 ₪ (a deposit image) and 40,000 ₪ (a
transaction account, out of scope).
