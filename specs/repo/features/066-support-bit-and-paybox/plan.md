# Implementation Plan: Bit, PayBox, Cheques, Cash (Feature 066)

**Spec**: `spec.md` · **Scenarios**: `acceptance-scenarios.md` (approved) · **Design approved 2026-10-09**: new `הפקדה` events reuse event-ID letter `B`; bank subtype label stays `בנק`.

## Technical context
Python 3.x, shared ledger code (`apps/denidin-app/src/managers/ledger_event_manager.py`, `ledger_event_recognizer.py`), shared image extractor, Backbone prompts, `morning-mcp-app` payment-line builder, webapp, player, reconciliation. Spec scope is Backbone-only, but ledger/extractor code is shared with the legacy pipeline; the data model flips for both (one ledger can't hold two shapes) - the legacy pipeline gets only the consistency edits needed to keep working.

## Constitution check
No env vars; `now_local()`; no mocks; no feature flag (human decision); **`CURRENT_SCHEMA_VERSION` change = human-only** - number and history text supplied by the human, bumped with its `SCHEMA_VERSION_HISTORY` entry in the same commit, no test asserts its value; existing tests asserting `בנק` are immutable without human sign-off (listed as 66-9); every prompt-bearing change keeps the "explicit boundary" rule (cash/deposit scoped in `flow_deposit_provided_by_user`).

## Design
1. **Classification** (`handlers/extractors/image_extractor.py`, `prompts/image_analysis.txt`): `doc_type` values `bank`, `bit`, `paybox`, `check`, `agreement`, `unknown`. Required fields: bank unchanged; bit/paybox = `payer_name, amount, txn_date`; check = `payer_name, amount, check_number, bank_number, bank_branch, bank_account` (no date required). (Cheque due date not extracted; Bit/PayBox only the basics.)
2. **Stash + recognition** (`ledger_event_recognizer.py`, `config/ledger_recognition_prompt.md`): `build_ledger_stash_text` renders a deposit of any method; tool schema `source_type` enum `הסכם | הפקדה | חשבונית`; for `הפקדה`, `event_subtype` enum `בנק | ביט | פייבוקס | צ׳ק | מזומן`; new optional `check_number`. `txn_date` guidance for deposits relaxed from "optional, only if distinct" to "the date shown on the evidence; null only when none (cash)".
3. **Manager** (`ledger_event_manager.py`): every `"בנק"` source-type branch becomes `"הפקדה"` (validation, VAT forced `כולל`, client/payer rule, bank-field handling, letter map -> `"הפקדה": "B"`, dedup fingerprint now also keyed by subtype, `_TYPE_TOKEN_BY_SOURCE` -> `"הפקדה": "deposit"`, completing-message dating); `check_number` added to the persisted field list; `capture` keeps accepting nothing but the new shape. `media_handler.py` legacy filter `("בנק","הסכם")` -> `("הפקדה","הסכם")`.
4. **Schema version**: bump + history entry (human-supplied). Existing history entries untouched.
5. **Morning MCP** (`morning-mcp-app/.../tools.py`): `_build_payment_line` persists `chequeNum` (+ bank fields) for `cheque` (type 2) - live-verified 2026-10-09; Bit/PayBox already supported (type 10, appType 1/3). `create_receipt`/`create_combo_document` signatures gain `cheque_number`. Flow/capability prompts map the deposit's subtype to `payment_method` (`ביט->bit`, `פייבוקס->paybox`, `צ׳ק->cheque`, `מזומן->cash`, `בנק->bank_transfer`).
6. **Cash**: text only, recorded by post-turn recognition via the existing text-deposit path (`flow_deposit_provided_by_user`), subtype `מזומן`, no bank fields, `txn_date` may be null.
7. **Migration** `apps/denidin-app/scripts/migrate_066_deposit_flip.py`: dry-run default; `--apply`; takes a timestamped backup copy of the events folder first; rewrites only events with `source_type == "בנק"` to `source_type "הפקדה"`, `event_subtype "בנק"`; idempotent (re-run = no-op); verifies event count and every non-flipped field byte-equal before/after, aborts on any mismatch; never renames files or changes `event_id`; prints a report. Run by the human while the app is stopped.
8. **Consumers**: webapp backend (`ledger_reader`/filters) and frontend (type filter + label showing subtype), player (rendering of source type), accounting reconciliation (type handling) - audited; changes only where `בנק` is assumed. Prompts mentioning `בנק` (`cap_ledger_query.md`, ledger recognition prompt) updated.

## Out of scope
Cheque due date, Bit/PayBox extras (phone, reference, note), cash confirmation step, per-method 320/400 tests (66-5/66-6 removed), a rollback script (backup only).

## Tests
Acceptance (approved): 66-1..66-3 `expensive`, 66-4 `billed`, 66-7 = existing regression (adjusted with sign-off), 66-9 tracking. Unit: classification fields, stash, recognizer schema, manager (flip, fingerprint by subtype, `check_number`), migration script on a copy (dry-run, apply, idempotent, abort-on-mismatch), `_build_payment_line` cheque. Integration: webapp reader/endpoints with new events; morning sandbox cheque line.

## Project structure (touched)
`denidin-app`: extractors, recognizer, event manager, media_handler, `media_analysis/handler.py`, `config/ledger_recognition_prompt.md`, `config/prompts/**`, `scripts/migrate_066_deposit_flip.py`. `morning-mcp-app`: `tools.py`, `server.py` (tool signatures). `webapp`: backend + frontend. `player`, reconciliation as audited.
