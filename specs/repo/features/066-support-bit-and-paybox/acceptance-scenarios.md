# Feature 066 - Acceptance scenarios (DRAFT, approved 2026-10-09 by the human operator)

Tier: `expensive` = sends an image to the vision model (own fresh approval per run).
Scope: Backbone pipeline. Data model: `type="deposit"`, subtype bank/bit/paybox/check/cash.

In 66-1..66-4 the correctness check is done in **Morning**: after the deposit is recorded, the admin has the 320 created from it (for image cases via the 064 offer), then the test fetches the document's details from Morning (`get_invoice_details`) and checks the fields there. (The ledger event is also checked.)

| # | Tier | Scenario |
|---|---|---|
| 66-1 | expensive | The admin sends a **Bit** screenshot, then has the 320 created. In Morning the document shows payment method Bit, the amount, the date, and the client. |
| 66-2 | expensive | Same with a **PayBox** screenshot (payment method PayBox). |
| 66-3 | expensive | The admin sends a **cheque** image, then has the 320 created. In Morning the document shows payment method cheque, the amount, the payer, the cheque number, and bank / branch / account (to the extent Morning stores them - confirm at planning). |
| 66-4 | billed | The admin writes "קיבלתי 500 במזומן מיוסי", then has the 320 created. The ledger records a cash deposit of 500 from Yossi with no confirmation question; in Morning the document shows payment method cash and the amount. |
| 66-7 | (existing) | **Regression:** a normal bank slip is still recorded. Existing test to be adjusted, not duplicated: `tests/expensive/test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_bank_deposit_image_then_full_fields_correctly_persisted` (sanity; asserts `source_type == "בנק"` at line ~621 - needs human sign-off to change to the new model). Related: `tests/expensive/test_image_classification_e2e.py` (bank-classification tests), `tests/expensive/test_e2e_media_client_resolution.py` (US7a-d). |
| 66-9 | tracking only | **List of existing tests whose expectations may need adjusting** because of the type flip and the new methods. Not a test; each change needs human sign-off. Areas: ledger (event manager, recognizer, audit log, query), webapp (backend ledger reader / events endpoints / clients tab, Playwright seeds), regular 320 and 400 document creation (`morning-mcp-app` tools/formatters/payment-details tests; denidin-app `billed` document tests), accounting reconciliation (unit + billed), the player (`apps/denidin-app/player`). First-pass candidate files (broad grep on `בנק` / `source_type` / `deposit`) are in the planning notes; to be narrowed at planning. |

Removed at approval: 66-5, 66-6 (per-method 320/400 creation), 66-8 (migration - replaced by 66-9 tracking).
