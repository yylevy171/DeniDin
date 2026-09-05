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
| `tests/expensive/test_ledger_event_capture_e2e.py` | 6 → 4 | **DONE 2026-09-06 (static rework — model-behaviour asserts UNTUNED, need real runs).** `..._via_image_path` and `..._bank_deposit_screenshot_...` **DELETED** — fully superseded by Batch 1 `test_e2e_media_client_resolution.py::test_us9_...` / `::test_us7a_...` (same images, same amounts, fuller two-hop fidelity); those 2 sanity slots moved to US9/US7a. F3 (`..._multi_component_agreement_image`), F4 (`..._bank_deposit_image_then_full_fields_...`, bugfix-028), F5 (`..._six_component_..._mor_ben_shaya`) reworked: `denidin_app` fixture gained the live-tunnel check; every test runs as `_godfather_chat_id(config)` + seeds an exact-match Morning client (שחר פישר / אסתר אסולין / מור בן שעיה) + drives the resolution-detour loop (`_drive_detour_until_captured`); `_assert_ledger_events_persisted` no longer asserts `event_datetime`; F4's approval uses a 3-round loop and `_assert_no_open_invoice_for` parses `list_invoices` JSON (`status_code`/`status`); F5's "KNOWN FAILURE / blocked-on-069" block removed. F5 keeps `expected_count=6` + the fixed-amount multiset (a wrong split SHOULD fail). `test_given_non_agreement_image...` stays a Tier 3 false-positive guard (unchanged). `deposit_zero_matches.manifest.json` gained `vat_status: "כולל"` to preserve the deleted F2's one forced-field assertion. |

**Subtotal: 18 → 16 tests** (2026-09-06: the 2 deleted `test_ledger_event_capture_e2e.py`
cases drop out — superseded by Batch 1, not reworked).

**B4 — Hop-1 two-hop coverage gap (`test_e2e_media_client_resolution.py`).**
`_ledger_069_acceptance.assert_event_matches_manifest_two_hop`'s Hop-1 structured check
(`comp0`/`ev0`) is inert: `MediaHandler` never persists the raw structured `ledger_events`
list, so `_extractor_output_for_chat` reconstructs only the stash TEXT and `ledger_events`
is always `[]`. Hop-1 therefore only substring-checks the stash text blob. That IS
meaningful now that `build_ledger_stash_text` renders `סכום`/`תאריך הפקדה`/`מספר בנק`
onto the stash (the 2026-09-06 `components[0]` fix), but it cannot catch a
structured-vs-verbatim divergence. **Follow-up:** have `MediaHandler` persist the
`image_event` dict onto the `Message` (new field) so Hop-1 can compare against it.

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
| `tests/billed/test_denidin_morning_document_flows_e2e.py` | 8 | **NEW via Feature 075 merge (2026-09-04)** — `create_*` document flows incl. new-client-then-decline-document; every turn now runs post-turn recognition |
| `tests/billed/test_denidin_morning_document_creation_e2e.py` | 7 | the 4 Feature-021 `create_*` doc types |
| `tests/billed/test_denidin_morning_invoice_lifecycle_e2e.py` | 7 | create → receipt; recognition on each turn |
| `tests/billed/test_standalone_receipt_billed.py` | 1 | standalone type-400 — does it produce a `חשבונית` event? decision |
| `tests/billed/test_cancel_transaction_account_billed.py` | 1 | cancel creates no document → recognition must return `none` |
| `tests/billed/test_group_b_reference_approval_billed.py` | 4 | Group-B reference tools + approval prompt + recognition |
| `tests/expensive/test_group_b_reference_approval_e2e.py` | 1 | **bank image → invoice**: the image now routes as a synthetic turn — highest break risk in this tier; `BANK_IMAGE_PAYER = עטיה רועי מאיר` is seeded |
| `tests/billed/test_denidin_approval_content_and_vat_e2e.py` | 4 | approval-content pipeline via `_send_ai_response_and_attach` |
| `tests/billed/test_accounting_reconciliation_billed.py` | 9 | shares `LedgerEventManager` dedup tri-state index + is the sibling of `persist_recognized_event`; the `_content_fingerprint` `str()`-coercion fix changed this code; 069's synchronous `חשבונית` must dedup vs. the reconciliation tick (spec line 74) |

**Subtotal: 60 tests** (59 billed + 1 expensive).

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
| Tier 2 (run + small assert) | 59 | 1 | **60** |
| Tier 3 (run, no change) | 77 | 14 | **91** |
| Tier 4 (untouched) | 8 | 0 | **8** |
| **Pre-existing subtotal** | **156** | **21** | **177** |
| New 069 acceptance (Phase 11) | 10 (3 files) | 5 (1 file) | **15** |
| **Grand total acceptance surface** | **166** | **26** | **192** |

*Tier 2 gained `test_denidin_morning_document_flows_e2e.py` (+8) from the Feature 075 merge (2026-09-04). Counts are approximate — collect-time, pre-rework.*

## Parallel execution (Feature 075 engine, non-sanity)

`scripts/run_parallel_tests.sh` (added 2026-09-04) — the non-sanity sibling of
`run_sanity_parallel.sh`: pytest-xdist, `--dist loadfile`, per-worker
`test_data/<worker>/` isolation (already wired in `tests/billed/conftest.py` via
`sanity_worker_data_root()`, which keys off `PYTEST_XDIST_WORKER`, not any sanity
flag), one infra-signature retry round. No `-m sanity` filter, no gate by default.

`--dist loadfile` pins each FILE to one worker (preserves within-file shared-chat
ordering) — so parallelism = number of distinct files. The Feature 069 billed
acceptance suite was therefore split into per-class files:

| File | tests | US |
|---|---|---|
| `tests/billed/test_e2e_ledger_069_text_billed.py` | 8 | US1, US3a/b, US4, US5, US6, US8a/b |
| `tests/billed/test_e2e_ledger_069_morning_create_billed.py` | 1 | US2 |
| `tests/billed/test_e2e_ledger_069_docx_billed.py` | 1 | US10 |

```
scripts/run_parallel_tests.sh tests/billed/test_e2e_ledger_069_*_billed.py
```

Shared driver: `tests/billed/_ledger_069_post_turn_base.py`. C9 helper:
`tests/billed/_ledger_069_acceptance.py`. The expensive suite stays one file
(`tests/expensive/test_e2e_media_client_resolution.py`) — expensive runs
one-at-a-time with per-test approval regardless, so file-splitting buys nothing.

Requires `pytest-xdist` in the clone venv (Feature 075 added it to
`requirements.txt`; `pip install -r requirements.txt` if missing — an absent
xdist also makes plain `pytest` INTERNALERROR on the merged `conftest.py` hook).

## Run order for the acceptance pass

1. **Tier 1** rework (T052) — needs real runs to tune model-behaviour asserts; interleave code+run.
2. **Tier 2** — `scripts/run_multiple_billed_tests.sh` the billed ones (stop-on-fail, sound off live); the 1 expensive (`test_group_b_reference_approval_e2e`) with its own approval.
3. **Tier 3** — same, billed sweep + per-approval expensive.
4. **Tier 4** — falls out of any full billed/expensive run.
5. **New Phase 11 suite** — `test_e2e_ledger_069_*_billed.py` (3 billed files), then `test_e2e_media_client_resolution.py` (expensive, per-test approval). All 5 expensive scenarios have real images (`bank_transfer_grinfeld.jpg` added 2026-09-04 for US7b/US7c).

Every `expensive` test = its own fresh explicit approval, one at a time, STOP at every failure
(CLAUDE.md). `billed` sweeps need no per-run approval but MUST sound off each result live.
