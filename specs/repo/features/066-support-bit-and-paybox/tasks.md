# Tasks: Feature 066
Order in bundle: 2nd.
- T066-A1 Unit tests: extractor classification/required fields for bank/bit/paybox/check; stash text per method; recognizer tool schema (`source_type` enum, subtype enum, `check_number`); event manager (flip, VAT forced, fingerprint with subtype, ID letter `B`, `check_number` persisted, bank-field handling for cheque); `_build_payment_line` cheque (morning-mcp-app).
- T066-A2 Unit tests: migration script on a temp copy (dry-run changes nothing; apply flips only `בנק`; idempotent; byte-equal other fields; aborts on mismatch; backup created).
- T066-A3 Integration tests: webapp backend reader/endpoints with deposit events of all subtypes; morning sandbox cheque payment line (real sandbox, `morning-mcp-app/tests/integration`).
- T066-B1 Extractor + `prompts/image_analysis.txt` (new doc types, required fields).
- T066-B2 Recognizer (schema, stash, prompt `ledger_recognition_prompt.md`) and manager flip; `media_handler.py` legacy filter; `media_analysis/handler.py` stash mapping.
- T066-B3 Migration script `scripts/migrate_066_deposit_flip.py`.
- T066-B4 Morning MCP: cheque number in `_build_payment_line`, `create_receipt`/`create_combo_document` signature + server registration; prompts (`cap_invoicing_write.md`, flows) subtype -> `payment_method`.
- T066-B5 Consumers: webapp backend + frontend, player, reconciliation; prompts mentioning `בנק`.
- T066-B6 **Schema version bump** - BLOCKED on the human's exact number and history text.
- T066-B7 66-9: run the full unit/integration suites, list every existing test that fails or asserts the old shape; adjust only with human sign-off.
- T066-C Acceptance: `expensive` 66-1..66-3, `billed` 66-4 (Morning document details fetched and asserted), 66-7 = existing sanity regression adjusted with sign-off - written last.
