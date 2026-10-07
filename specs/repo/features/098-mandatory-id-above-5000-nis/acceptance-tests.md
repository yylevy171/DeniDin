# Acceptance Tests: Feature 098

Every new `billed` / `expensive` test written for this feature. **None has been run yet.**
There are no `expensive` tests: every scenario is text-only.

Run each one through `scripts/run_single_test.sh <node id>` (in that app), or a sequence
through `scripts/run_multiple_billed_tests.sh`.

## Before running

- **DeniDin (UATs 1.1–3.5 and the edge cases):** run on the backbone (063 merged; plan.md
  Phase 5 applied). `config.test.json` has `enable_capability_backbone: true`, so no
  override is needed. Needs the same rebuilt dev environment.

## T1 - new tests (written for this feature)

Every approved UAT (1.1-3.5) and both edge cases have a test. UAT 4.1 (the Hebrew refusal reaches the caller) is covered by the Morning-MCP sandbox integration test `test_mcp_refusal_is_an_error_carrying_the_hebrew_message`; no billed test is needed for it. Feature 086's edge case
(one 320 closing several transaction accounts) needs none until 086 lands.

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

## T2 - existing tests adjusted in place (3, billed)

| # | Node id | Change | Status |
|---|---|---|---|
| T2.1 | `tests/billed/test_group_b_reference_approval_billed.py::TestGroupBReferenceApprovalBilled::test_combo_document_against_existing_transaction_account_shows_reference_data` (sanity) | Closes a 11,8xx ₪ 300 for a client seeded with an ID: no ID question, reference data still in the approval | - |
| T2.2 | `tests/billed/test_e2e_ledger_069_morning_create_billed.py::TestLedgerPostTurnCaptureMorningCreate::test_us2_morning_create_is_captured_synchronously` | 11,800 ₪ 320, client with no ID: ID asked → saved (own approval) → document (own approval) → ledger event captured after the create | - |
| T2.3 | `tests/billed/test_denidin_morning_client_management_e2e.py::test_godfather_updates_client_via_whatsapp` | Updates phone AND ID; reads both back; email untouched | - |

## T3 - existing tests run as is (regression)

Each drives an issuing flow 098 edited, below 5,000 ₪: a wrong ID question or a skipped
approval would fail it.

| # | Tier | Node id | Why | Status |
|---|---|---|---|---|
| T3.1 | billed | `tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_creates_invoice_via_whatsapp_button_tap` | 305 flow | - |
| T3.2 | billed | `tests/billed/test_denidin_morning_document_creation_e2e.py::test_godfather_creates_combo_document_via_whatsapp` | 320 flow | - |
| T3.3 | billed | `tests/billed/test_denidin_morning_document_flows_e2e.py::test_create_document_for_new_client_full_flow_happy_path` | New client (no ID) → document | - |
| T3.4 | billed | `tests/billed/test_group_b_reference_approval_billed.py::TestGroupBReferenceApprovalBilled::test_receipt_against_existing_invoice_shows_reference_data` | Reference-doc flow, receipt: never asks for an ID | - |
| T3.5 | billed | `tests/billed/test_reminder_lifecycle_billed.py::TestReminderLifecycleBilled::test_godfather_creates_one_time_reminder_button_approval` | Sanity spot check: reminders | - |
| T3.6 | billed | `tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_explicit_date_lookup` | Sanity spot check: ledger queries | - |
| T3.7 | expensive | **Blocked: no bank-slip fixture above 5,000 ₪ exists** (current slips: 554, 800, 1,500, 1,888 ₪) | Slip → 320 above 5,000 → ID chain | - |

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
