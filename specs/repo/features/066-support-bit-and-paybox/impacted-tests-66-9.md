# 66-9 - existing tests adjusted for the type flip and the new methods (2026-10-09)

Unit/integration tests were adapted by the agent (human instruction 2026-10-09: "unit and integration tests ARE YOURS").
`billed`/`expensive`/fixture/Playwright items are listed separately and need the human's sign-off.

## Ledger (denidin-app) - unit / integration (adapted; same intent, new shape `source_type=הפקדה`, `event_subtype=<method>`)
test_ledger_event_manager, test_ledgerer, test_recognition_call, test_ledger_audit_log, test_ledger_capture_breadcrumbs,
test_ai_handler_ledger_events, test_ai_handler_ledger_query, test_ai_handler_media_ledger_routing, test_backbone_media_turn,
test_denidin_media_ledger_routing, test_media_handler, test_extractor_constitution_caption, test_today_timestamp_threading,
integration/_ledger_069_harness, integration/test_ledger_client_resolution_routing, integration/test_ledger_query_conversation_routing.
`tests/unit/test_pdf_extractor.py` deleted (071: it only tested per-page aggregation, which no longer exists; replaced by test_pdf_single_call_071).

## Needs human sign-off (billed / expensive / fixtures)
- billed: `tests/billed/test_ledger_query_billed.py` (seed events moved to the new shape).
- expensive: `tests/expensive/test_ledger_event_capture_e2e.py` (66-7: the bank-slip regression now asserts `source_type == "הפקדה"`, subtype `בנק`).
- fixtures: all 13 `tests/fixtures/ledger_069/*.manifest.json` gained a `check_number` rule (null); the 4 `deposit_*` manifests flipped to `הפקדה`/`בנק`.

## Webapp
- backend: no existing test needed changes (reader accepts both the old and the new shape); new `test_ledger_reader_deposit_066.py`. `test_preview_092_migration.py` fails with or without this work (pre-existing).
- Playwright (`apps/webapp/e2e`): seeds `seed_fixture.py`, `seed_clients_fixture.py` and specs `03-filters`, `04-expand-single` moved to the new shape; frontend type list no longer offers `בנק` as a type. All three Playwright suites pass.

## Not affected (checked)
Regular 320/400 creation (morning-mcp-app unit + sandbox integration pass), accounting reconciliation and the player: their unit/integration tests pass unchanged. Their `billed` tests have not been run.
`morning-mcp-app/tests/unit/test_tools_document_creation.py` has 3 failures that also fail without this work (pre-existing).
