# Feature 069 — Acceptance / regression map (billed + expensive)

**Purpose.** Feature 069 moves ledger capture to a **post-turn recognition call**, makes
client resolution **mandatory** for `הסכם`/`בנק`/`חשבונית`, routes recognised bank/agreement
media through the conversational pipeline, and refactors `denidin.py`'s conversational send
path (`_send_ai_response_and_attach`) + adds `Message.mcp_calls`. This document maps **every
pre-existing billed/expensive test** whose exercised path this feature touches, so the
acceptance pass proves *we did not break anything*.

Generated 2026-09-04. Counts are `pytest --collect-only -m "billed or expensive"`.

`tests/billed/conftest.py` already has a **directory-wide autouse**
`_clean_ledger_events_around_every_test` — so a newly-captured `חשבונית` event from a
Morning-create turn cannot *pollute* a neighbouring billed test even where that test does not
assert on it. `tests/expensive/` has **no** such autouse (each expensive ledger file rolls its
own) — noted per-file below.

---

## Tier 1 — MUST REWORK (assertions encode pre-069 behaviour that legitimately changed)

The model is no longer handed an inline `capture_ledger_event` tool; capture is a post-turn
call; `client_name` must be an **exact Morning name** (resolution detour) or carry the
store-anyway marker. These files assert the old inline call and/or an un-resolved OCR/operator
`client_name` and/or a direct-persist `expected_count`.

| File | # | Rework |
|---|---|---|
| `tests/billed/test_ledger_event_capture_text_billed.py` | 10 | drop `capture_ledger_event`-call asserts; add `live_morning_tunnel` dep; seed an exact-match client OR script the resolution detour (`ClarificationAnswerBank`); assert `client_name` == exact Morning name; move count checks to "events land post-turn". |
| `tests/billed/test_ledger_event_capture_billed.py` | 2 | same |
| `tests/expensive/test_ledger_event_capture_e2e.py` | 6 | image cases now route as a synthetic turn → resolution detour before capture; `עידן שבתאי` / `קהילת צעיר` are not sandbox clients, so each needs the detour or a seeded client; `expected_count` direct-persist asserts become post-turn. Overlaps heavily with the new `tests/expensive/test_e2e_media_client_resolution.py` — decide which scenarios stay here vs. move. |

**Subtotal: 18 tests** (this is the "~16" from the earlier note, exact count 18).

---

## Tier 2 — REGRESSION RUN + likely a small positive assertion (real behaviour change lands here, but the *reply* is unchanged)

Every in-conversation Morning `create_*` turn now also runs the post-turn recognition call.
Per spec US2/US3 a **type-320 `create_combo_document`** yields exactly **1 `חשבונית`** ledger
event that turn; other `create_*` types (305 plain invoice, 400 receipt, credit note, txn
account, cancel) — **confirm** against `config/ledger_recognition_prompt.md` whether they do
too (the regression run is what surfaces this). These tests don't assert event counts today,
so they should stay green; where cheap, add "exactly N `חשבונית` events / none".

| File | # | Watch for |
|---|---|---|
| `tests/billed/test_denidin_morning_invoice_creation_e2e.py` | 18 | type-305 & type-320 creates; also the only file touching `offer_approval_buttons`/`attach_sent_message_id` → validates the `_send_ai_response_and_attach` extraction end-to-end |
| `tests/billed/test_denidin_morning_document_creation_e2e.py` | 7 | the 4 Feature-021 `create_*` doc types |
| `tests/billed/test_denidin_morning_invoice_lifecycle_e2e.py` | 7 | create → receipt; recognition on each turn |
| `tests/billed/test_standalone_receipt_billed.py` | 1 | standalone type-400 — does it produce a `חשבונית` event? decision |
| `tests/billed/test_cancel_transaction_account_billed.py` | 1 | cancel creates no document → recognition must return `none` |
| `tests/billed/test_group_b_reference_approval_billed.py` | 4 | Group-B reference tools + approval prompt + recognition |
| `tests/expensive/test_group_b_reference_approval_e2e.py` | 1 | **bank image → invoice**: the image now routes as a synthetic turn — highest break risk in this tier; `BANK_IMAGE_PAYER = עטיה רועי מאיר` is seeded |
| `tests/billed/test_denidin_approval_content_and_vat_e2e.py` | 4 | approval-content pipeline via `_send_ai_response_and_attach` |
| `tests/billed/test_accounting_reconciliation_billed.py` | 9 | shares `LedgerEventManager` dedup tri-state index + is the sibling of `persist_recognized_event`; the `_content_fingerprint` `str()`-coercion fix changed this code; 069's synchronous `חשבונית` must dedup vs. the reconciliation tick (spec line 74) |

**Subtotal: 51 tests.**

---

## Tier 3 — REGRESSION RUN, NO EXPECTED CHANGE (touch the refactored conversational path / `Message.mcp_calls` / extractor base, but behaviour is byte-identical when the flag-free code path is unchanged)

| File | # | Touch point |
|---|---|---|
| `tests/billed/test_ledger_query_billed.py` | 23 | `query_ledger_events` — recognition attaches the same tool + a bounded chained-query loop; confirm query path untouched |
| `tests/billed/test_reminder_lifecycle_billed.py` | 14 | `_send_ai_response_and_attach` now calls `pending_local_tool_approval_manager.attach_sent_message_id` from the extracted helper |
| `tests/billed/test_denidin_morning_client_management_e2e.py` | 10 | `resolve_client_name`/`add_client` conversational path (the resolution machinery 069 leans on) |
| `tests/billed/test_denidin_morning_list_invoices_e2e.py` | 11 | read-tool turns + `query_ledger_events` chained-loop call-accounting (already has a 069 forward-ref note at line ~452) |
| `tests/billed/test_group_etiquette_billed.py` | 8 | group RBAC + `_process_conversational_message` no-reply path |
| `tests/billed/test_denidin_vcf_contact_e2e.py` | 2 | contact-card → conversational pipeline; already asserts the ledger false-positive guard holds (lines 189-292) — 069 should keep these green |
| `tests/billed/test_ai_handler_real_api.py` | 3 | raw `AIHandler` Responses-API path + system-prompt assembly |
| `tests/billed/test_simple_text_e2e.py` | 1 | plainest conversational turn |
| `tests/billed/test_memory_integration_billed.py` | 4 | session→longterm; `Message` persistence with the new `mcp_calls` field |
| `tests/billed/test_session_transfer.py` | 1 | same |
| `tests/expensive/test_media_e2e.py` | 5 | media extraction + `DOCXExtractor.analyze_media` return shape change (`document_analysis` now always present) |
| `tests/expensive/test_image_classification_e2e.py` | 9 | extractor-only; line 247 asserts *no* ledger event off an ambiguous note — 069's routing signal must not fire on it |

**Subtotal: 91 tests.**

---

## Tier 4 — UNTOUCHED (run only as whole-suite sanity; no 069 code in path)

| File | # |
|---|---|
| `tests/billed/test_real_api_connectivity.py` | 6 |
| `tests/billed/test_denidin_version_query_e2e.py` | 2 |

**Subtotal: 8 tests.**

---

## Totals

| | billed | expensive | total |
|---|---|---|---|
| Tier 1 (rework) | 12 | 6 | **18** |
| Tier 2 (run + small assert) | 50 | 1 | **51** |
| Tier 3 (run, no change) | 77 | 14 | **91** |
| Tier 4 (untouched) | 8 | 0 | **8** |
| **Pre-existing subtotal** | **147** | **21** | **168** |
| New 069 acceptance (Phase 11) | 10 | 5 | **15** |
| **Grand total acceptance surface** | **157** | **26** | **183** |

## Run order for the acceptance pass

1. **Tier 1** rework (T052) — needs real runs to tune model-behaviour asserts; interleave code+run.
2. **Tier 2** — `scripts/run_multiple_billed_tests.sh` the billed ones (stop-on-fail, sound off live); the 1 expensive (`test_group_b_reference_approval_e2e`) with its own approval.
3. **Tier 3** — same, billed sweep + per-approval expensive.
4. **Tier 4** — falls out of any full billed/expensive run.
5. **New Phase 11 suite** — `test_e2e_ledger_post_turn_capture.py` (billed), then `test_e2e_media_client_resolution.py` (expensive, per-test approval). All 5 expensive scenarios have real images (`bank_transfer_grinfeld.jpg` added 2026-09-04 for US7b/US7c).

Every `expensive` test = its own fresh explicit approval, one at a time, STOP at every failure
(CLAUDE.md). `billed` sweeps need no per-run approval but MUST sound off each result live.
