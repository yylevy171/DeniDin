# Feature 089 - billed / expensive tests to run

Status: NOTHING below has been run with permission yet. One new test was run once by mistake
(2026-10-11) and failed; it must be re-run in the normal order. All run through
`scripts/run_single_test.sh <node_id>` from `apps/denidin-app` (one at a time, sound off each
result). Backbone flag stays ON (config.test.json). `expensive` tests need separate per-run approval.

## A. New for 089 (authored, never validly run) - `billed`, 7 tests

File: `apps/denidin-app/tests/billed/test_agreements_whatsapp.py`, class `TestAgreementsWhatsAppBilled`

1. `tests/billed/test_agreements_whatsapp.py::TestAgreementsWhatsAppBilled::test_uat_5_1_query_with_agreement_ambiguity`
2. `tests/billed/test_agreements_whatsapp.py::TestAgreementsWhatsAppBilled::test_uat_5_2_edit_component_amount`
3. `tests/billed/test_agreements_whatsapp.py::TestAgreementsWhatsAppBilled::test_uat_5_3_edit_payer_and_partner`
4. `tests/billed/test_agreements_whatsapp.py::TestAgreementsWhatsAppBilled::test_uat_5_4_add_component_starts_pending`
5. `tests/billed/test_agreements_whatsapp.py::TestAgreementsWhatsAppBilled::test_uat_5_5a_complete_single_component`
6. `tests/billed/test_agreements_whatsapp.py::TestAgreementsWhatsAppBilled::test_uat_5_5b_complete_whole_agreement_cascades`
7. `tests/billed/test_agreements_whatsapp.py::TestAgreementsWhatsAppBilled::test_uat_5_6_ambiguous_short_reply_changes_nothing`

Known coverage limit: UAT 5.1's "two Morning clients named Israel" detour needs two such clients in
the Morning sandbox; not covered.

## B. New `expensive` tests

None authored. 089 has no image/PDF/DOCX behaviour.

## C. Regression - existing tests whose behaviour 089 touched (recommend, your call)

089 changed: `הסכם` ledger events are now written via the Agreements DB (`create_from_capture`),
ledger schema v4, new capabilities/flow in the backbone catalog, constitution + `cap_ledger_query.md`
edits. Existing tests that exercise those paths:

| File | Tier | Tests | Why |
|---|---|---|---|
| `tests/billed/test_ledger_event_capture_billed.py` | billed | 2 | `הסכם` capture now routes through the DB |
| `tests/billed/test_ledger_event_capture_text_billed.py` | billed | 10 | same, text variants incl. multi-component |
| `tests/billed/test_ledger_query_billed.py` | billed | 23 | queries over `הסכם` events (schema v4 fields) |
| `tests/billed/test_fee_agreement_generation_flow.py` | billed | 5 | fee-agreement flow vs. the new agreement flow in the catalog |
| `tests/expensive/test_ledger_event_capture_e2e.py` | expensive | 4 | image-sourced `הסכם` capture; each needs its own approval |

Minimum sensible regression subset: the 2 + 10 capture tests and the 5 fee-agreement-flow tests.
