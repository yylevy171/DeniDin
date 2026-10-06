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

## T2 - adjusted variants of existing tests (written 2026-10-06)

Each is a new test next to its original; the original is unchanged (two are sanity tests,
pinned by node id in `run_sanity.sh`).

| New test | Original | Coverage it adds |
|---|---|---|
| `tests/billed/test_group_b_reference_approval_billed.py::TestGroupBReferenceApprovalBilled::test_closing_a_transaction_account_above_the_threshold_for_a_client_with_an_id` | `test_combo_document_against_existing_transaction_account_shows_reference_data` | Closing an 11,800 ₪ transaction account for a client whose ID is on file: no ID question, Morning-MCP reads the client's current record and lets it through, the approval still shows the reference data. |
| `tests/billed/test_e2e_ledger_069_morning_create_billed.py::TestLedgerPostTurnCaptureMorningCreate::test_us2_above_threshold_with_client_id_is_captured_synchronously` (manifest `morning_create_us2_above_threshold`) | `test_us2_morning_create_is_captured_synchronously` | An 11,800 ₪ 320 for a client with an ID is created without an ID question and still captured in the ledger that turn. |
| `tests/billed/test_denidin_morning_client_management_e2e.py::test_godfather_saves_a_client_id_via_whatsapp` | `test_godfather_updates_client_via_whatsapp` | Saving an ID on its own, outside the chain, and reading it back with `get_client_details`. |

Shared helper: `seed_client_with_tax_id` (`denidin_mcp_e2e_helpers.py`), also used by the
T1 tests; a ledger-069 manifest seed entry may carry `tax_id`.

## T3 - existing tests run as is (regression), highly impacted only

Chosen by what 098 changed on the backbone: the ID step inserted into the three issuing
flows (every 305/320/closing turn may now look the client up first), the hand-back at the end
of `flow_modify_client`, and the new section in `cap_invoicing_write`. Each test below drives
one of those flows end to end and asserts on the turn shape or the approval, so an extra
lookup, a wrong ID question below the threshold, or a changed approval can fail it. All are
below 5,000 ₪. Morning-MCP: none - its code is covered by its unit and sandbox integration
tests (all passing).

**DeniDin, billed**

| Test | Flow it drives |
|---|---|
| `tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_creates_invoice_via_whatsapp` | 305, typed yes |
| `tests/billed/test_denidin_morning_invoice_creation_e2e.py::test_godfather_creates_invoice_via_whatsapp_button_tap` | 305, button tap |
| `tests/billed/test_denidin_morning_document_creation_e2e.py::test_godfather_creates_combo_document_via_whatsapp` | 320 |
| `tests/billed/test_denidin_morning_document_flows_e2e.py::test_create_document_for_new_client_full_flow_happy_path` | new client (no ID), then the document |
| `tests/billed/test_small_bugfixes_027_032_054_058_061_billed.py::test_bugfix_027_client_stored_with_ascii_apostrophe_can_get_a_document` | 320 for a name with an apostrophe - the new client lookup must resolve it |
| `tests/billed/test_denidin_morning_invoice_lifecycle_e2e.py::test_godfather_marks_transaction_account_invoice_paid_via_whatsapp` | closing a 300 |
| `tests/billed/test_group_b_reference_approval_billed.py::TestGroupBReferenceApprovalBilled::test_combo_document_against_existing_transaction_account_shows_reference_data` | closing a 300, approval content |
| `tests/billed/test_group_b_reference_approval_billed.py::TestGroupBReferenceApprovalBilled::test_receipt_against_existing_invoice_shows_reference_data` | receipt on a 305 (same flow; must never ask for the ID) |
| `tests/billed/test_denidin_morning_client_management_e2e.py::test_godfather_updates_client_via_whatsapp` | `flow_modify_client` on its own |
| `tests/billed/test_e2e_ledger_069_morning_create_billed.py::TestLedgerPostTurnCaptureMorningCreate::test_us2_morning_create_is_captured_synchronously` | 320 + same-turn ledger capture |

**Sanity spot checks (not affected by 098)**
- `tests/billed/test_reminder_lifecycle_billed.py::TestReminderLifecycleBilled::test_godfather_creates_one_time_reminder_button_approval`
- `tests/billed/test_ledger_query_billed.py::TestLedgerQueryBilled::test_explicit_date_lookup`

**DeniDin, expensive** (needs its own approval)
- `tests/expensive/test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_bank_deposit_image_then_full_fields_correctly_persisted` - a bank-slip image becomes a 554 ₪ 320: the only test that goes through the media step into the edited 320 flow.

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
