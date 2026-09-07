# Handoff — Feature 069 Batch 1 acceptance: US2 + the Morning `create_*` full-document fix

**Date**: 2026-09-07 · **Branch**: `feature/069-mandatory-client-resolution-before-ledger-event`
**Clone**: root (`/Users/yaron/Projects/DeniDin`, personality = Ruth)
**Status**: US2 blocked on a two-app fix. morning-mcp-app half **done + verified**; denidin-app
recognition-schema half **partly done, not verified**. **Nothing deployed. Nothing committed.**

---

## 1. TL;DR

- Feature 069 "Batch 1" = **11 billed + 5 expensive** acceptance tests. **10 / 11 billed green**,
  `test_us2_morning_create_is_captured_synchronously` **red**.
- Root cause of US2: the recognition tool schema had **no field** for the Morning document
  number on the *synchronous* `חשבונית` path, and — one level deeper — the morning-mcp-app
  `create_*` tools return a **sparse stub**, not the full document, so even the fields that
  *do* have a home come back `null`.
- **User-approved plan**: fix the 3 document `create_*` tools to re-fetch the full document
  (morning side), then make the recognition schema treat a synchronous `חשבונית` as **flat**
  (no `components[]`), mapping **only** what Morning actually returns.
- This session: morning-mcp-app fix **written + unit/integration-verified**; new billed+sanity
  test written; denidin recognition-schema work **partly applied, unverified**.
- Work paused mid-verification because **the shared `dev` environment was taken by another
  user** ("WE WAIT"). A separate ~1h Morning-sandbox 403 outage earlier the same evening also
  blocked verification for a while (now recovered).

---

## 2. Current test status — individual verdicts

### 2a. Feature 069 Batch 1 — BILLED (`apps/denidin-app`, 11 tests)

Last known verdict per test. "run6b" = parallel retry batch 2026-09-06 21:11; targeted US2
re-runs = 2026-09-06 21:25–21:37 (`run_us2{,b,c,d}.log` in the scratchpad).

| # | Test (node id under `tests/billed/`) | Verdict | Last seen |
|---|---|---|---|
| US1 | `test_e2e_ledger_069_text_billed.py::TestLedgerPostTurnCaptureText::test_us1_mechanism_move_agreement_text_exact_client` | ✅ PASS | run5 21:00, batch1_billed2 14:31 |
| US2 | `test_e2e_ledger_069_morning_create_billed.py::TestLedgerPostTurnCaptureMorningCreate::test_us2_morning_create_is_captured_synchronously` | ❌ **FAIL** | run_us2d 21:37 (4 consecutive fails 17:28→21:37; passed intermittently earlier at 14:31/14:58 before manifest tightening) |
| US3-guard | `test_e2e_ledger_069_text_billed.py::TestLedgerPostTurnCaptureText::test_us3_regression_guard_ordinary_turn_no_capture` | ✅ PASS | batch1_r4 17:28, batch1_billed2 |
| US3-email | `test_e2e_ledger_069_text_billed.py::TestLedgerPostTurnCaptureText::test_us3_bare_email_is_not_a_ledger_event` | ✅ PASS | batch1_r4 17:28, batch1_billed2 |
| US4 | `test_e2e_ledger_069_text_billed.py::TestLedgerPostTurnCaptureText::test_us4_new_client_agreement_full_detour` | ✅ PASS | run6b 21:11 |
| US5 | `test_e2e_ledger_069_text_billed.py::TestLedgerPostTurnCaptureText::test_us5_ambiguous_agreement_operator_picks` | ✅ PASS | run6b 21:11 |
| US5b | `test_e2e_ledger_069_text_billed.py::TestLedgerPostTurnCaptureText::test_us5b_one_partial_agreement_operator_picks` | ✅ PASS | run5 20:58 (**not re-run in run6b** — see note) |
| US6 | `test_e2e_ledger_069_text_billed.py::TestLedgerPostTurnCaptureText::test_us6_exact_match_captures_without_a_question` | ✅ PASS | run6b 21:11 |
| US8 | `test_e2e_ledger_069_text_billed.py::TestLedgerPostTurnCaptureText::test_us8_store_anyway_marks_the_record` | ✅ PASS | run6b 21:11 |
| US8-no | `test_e2e_ledger_069_text_billed.py::TestLedgerPostTurnCaptureText::test_us8_dont_store_persists_nothing` | ✅ PASS | batch1_r4 17:28, batch1_billed3 14:58 |
| US10 | `test_e2e_ledger_069_docx_billed.py::TestLedgerPostTurnCaptureDocx::test_us10_docx_multi_component_agreement_two_hop` | ✅ PASS | run6b 21:11 |

**Confidence caveats**
- **US5b**: last green in `run5` (20:58); it was NOT in the run6b retry set (run6b only re-ran
  the 6 that were red at 20:58: us4, us8-store, us10, us2, us6, us5). Its helper (`_ledger_069_acceptance.py`)
  and `_ledger_069_post_turn_base.py` have since been edited (same edits that fixed us5/us6),
  so a fresh full-11 run is warranted before declaring 10/11 final.
- **A clean, single, full-batch 11-test run has never completed** — the 10 greens are stitched
  from `run6b` (6 tests) + earlier batches. First order of business when resuming: one
  `scripts/run_parallel_tests.sh` pass over all 11.

### 2b. Feature 069 Batch 1 — EXPENSIVE (`apps/denidin-app/tests/expensive/`, 5 tests)

**None have been run this feature.** All 5 need explicit per-test user approval, one at a time,
never `-n`/batched (CLAUDE.md expensive rules).

| Test (`test_e2e_media_client_resolution.py::TestMediaClientResolutionE2E::`) | Status |
|---|---|
| `test_us7a_deposit_image_zero_matches_new_client` | ⏸ never run — manifest `deposit_zero_matches.manifest.json` flagged `_incomplete` (bank triplet never transcribed; first run is the signal to fill it) |
| `test_us7b_deposit_image_one_partial_match` | ⏸ never run |
| `test_us7c_deposit_image_two_plus_matches` | ⏸ never run |
| `test_us7d_deposit_image_exact_match_no_question` | ⏸ never run — manifest `deposit_exact_match.manifest.json` flagged `_incomplete` |
| `test_us9_photographed_multi_component_agreement` | ⏸ never run — manifest `agreement_photo_multi.manifest.json` flagged `_incomplete` (JPEG values never transcribed) |

### 2c. morning-mcp-app — this session's changes

| Suite | Verdict | When |
|---|---|---|
| `tests/unit/` (full) | ✅ **340 passed**, 1 deselected | 2026-09-07, after `add_client` reverted |
| — `test_logger_retention.py::TestLosslessRotation::test_concurrent_emit_across_rotations_loses_nothing` | ⚠️ flake — **pre-existing, unrelated**. Passes in isolation with *and* without my changes (verified by `git stash`); only fails under full-suite timing. Deselected in the 340 run. | — |
| — `test_tools_client_management.py::test_add_client_normalizes_name_before_sending_and_in_confirmation` | was ❌ **broken by my first `add_client` change** → change **reverted** → now ✅ | — |
| `tests/integration/` document-creation subset (45 tests: `test_morning_sandbox_document_creation_tools.py`, `test_morning_sandbox_invoices_crud.py`, `test_morning_sandbox_invoice_status_tools.py`, `test_morning_sandbox_payment_details.py`, `test_morning_sandbox_linked_documents.py`, `test_morning_sandbox_standalone_receipt.py`) | ✅ **45 passed** | 2026-09-06 23:07 (`mm_integ.log`), after sandbox recovered |
| `tests/billed/test_create_returns_full_document_e2e.py::test_create_combo_document_result_carries_the_full_document` (**new this session**) | ⏸ **never run** — needs `dev` free (real OpenAI + real MCP tunnel + real sandbox) | — |
| `tests/billed/test_openai_invokes_mcp_e2e.py` (3 tests, pre-existing) | not run this session | — |
| Full `tests/` suite | ⚠️ **aborted** 2026-09-06 22:50 — Morning sandbox was returning **403 Forbidden on every `/api/v1/*` call** (OAuth 200, everything after denied). ~1h outage, entirely sandbox-side, unrelated to any change. **Recovered** — confirmed 2026-09-07 via `search_clients` probe. | — |

### 2d. denidin-app unit tests for the recognition-schema changes

**Not re-run this session.** Prior session reported 239 ledger/recognition unit tests green
*before* the `accounting_document_display_number` property + `required`-list addition. That
addition (this session) has **not** been unit-tested — **run `tests/unit/test_recognition_call.py`
+ `tests/unit/test_ledger_event_manager.py` before anything else on the denidin side.**

---

## 3. US2 — the failure, in detail

`test_us2_morning_create_is_captured_synchronously` (`tests/billed/test_e2e_ledger_069_morning_create_billed.py`).
Last run `run_us2d.log` / `logs/test_logs/pytest_results/…_20260906_213622.txt`.

**What happens**: operator asks DeniDin to issue a `חשבונית מס/קבלה` (type-320 combo doc);
`create_combo_document` **succeeds** (real sandbox invoice, e.g. `60536`); the post-turn
recognition call fires with that `create_*` call + result in its window.

**Winning recognition verdict** (`report_ledger_recognition`, `run_us2d`):
```json
{"verdict":"complete","event":{
  "source_type":"חשבונית","event_subtype":"הפקה","client_name":"בנימין אוסיפין",
  "payer_name":null,"agreement_id":null,"reference_hint":null,
  "bank_number":null,"bank_branch":null,"bank_account":null,
  "accounting_document_json":null,          // ← my prompt fix worked: model left the blob null
  "component_count":1,
  "components":[{"component_label":null,"description":"ייעוץ משפטי","amount":"1200",
    "percent":null,"percent_base":null,"hours":null,"hourly_rate":null,
    "txn_date":"2026-09-06","vat_status":"כולל","trigger_condition":null}]
}}
```

**Persisted event**: `description`, `vat_status`, `txn_date`, `amount`, `client_name` — **all
correct** (the flat path preserved the model's mapping). **But
`accounting_document_display_number: null`** — the model had nowhere to put `60536`.

**Two bugs, both now understood:**

1. **No schema home for the document number on the synchronous path.** `LEDGER_EVENT_TOOL` /
   `RECOGNITION_TOOL` had *no* `accounting_document_display_number` property, and *no*
   top-level `amount`/`txn_date`/`vat_status`/`description` — those live only inside
   `components[].items`. The `accounting_document_*` fields existed **only** as code-derived
   outputs of `_expand_accounting_document_json` (the Feature-025 reconciliation blob path).
   So on a synchronous create the model structured everything under `components[]` and simply
   **omitted the display number** — no field for it.

2. **`_mandatory_field_gaps` checks the wrong shape for `חשבונית`.** It reads top-level
   `event.get("txn_date")` / `event.get("amount")` / `event.get("accounting_document_display_number")`
   on the *raw pre-flatten* verdict — all `null` for a synchronous `חשבונית` (data is under
   `components[0]`). So it logs `[רישום חלקי — חסר: תאריך, סכום, מספר מסמך]` on every
   synchronous create; that marker then gets **silently clobbered** when
   `add_ledger_events_from_call` flattens `components[0].description` up over it.

**Deepest root cause** (why even `accounting_document_json` wouldn't have saved it): the
morning-mcp-app `create_combo_document` response is a **sparse stub**:
```json
{"display_number":"60536","type":320,"type_name":"חשבונית מס / קבלה","status":null,
 "client_name":"בנימין אוסיפין","description":null,"amount":1200.0,"vat_amount":null,
 "document_date":null,"creation_date":null,"payment":null,"line_items":[],"linked_document":null}
```
`description`, `document_date`, `vat_amount`, `payment`, `line_items`, `creation_date` all
`null`/empty — even though Morning has them. Feeding this to `_expand_accounting_document_json`
overwrites the model's correct flat mapping with nulls. That's what the morning-mcp-app fix
below addresses.

---

## 4. What was changed this session (all uncommitted, on disk)

`git diff --stat`:
```
apps/denidin-app/config/ledger_recognition_prompt.md      | 25 +++--    (partly prior session)
apps/denidin-app/src/handlers/ai_handler.py               | 47 +++++--  (partly prior session)
apps/denidin-app/src/managers/ledger_event_manager.py     | 77 ++++++-- (mostly prior session)
apps/morning-mcp-app/src/denidin_mcp_morning/tools.py     | 122 ++++--  (THIS session)
scripts/run_sanity.sh                                     | 1 +        (THIS session)
apps/morning-mcp-app/tests/billed/test_create_returns_full_document_e2e.py  (NEW, untracked)
```
Plus a large number of `apps/denidin-app/tests/**` + `tests/fixtures/ledger_069/**` changes
from the **prior** session's Batch-1 redesign (helpers, manifests, fixtures) — those are the
context, not this session's work. See the prior session summary for that inventory.

### 4a. morning-mcp-app — `src/denidin_mcp_morning/tools.py` ✅ DONE + VERIFIED

Two new helpers after `_with_amount_mismatch`:
- **`_read_back_full_document(client, doc_id) -> Optional[dict]`** — `GET /documents/{id}`,
  never raises (returns `None` on failure).
- **`_finalize_created_document(client, doc_id, requested_amount, fallback_invoice) -> str`** —
  re-fetch → `Invoice.model_validate(full)` → `format_invoice_json`; on any failure falls back
  to `fallback_invoice` (the minimal echo). Preserves the bugfix-028 A4 amount-mismatch guard.

Rewired to use it (were building a sparse `Invoice(id, number, client_name, amount,
total_amount, currency, status, type)` and formatting *that*):
- `create_invoice`
- `create_transaction_account`
- `create_combo_document`

Already did the equivalent re-fetch and were **left untouched**: `create_credit_note`,
`create_receipt`, `create_combo_document_as_reference` (their inline
`format_invoice_json(Invoice.model_validate(client.get_invoice(new_id)))` is the pattern the
helper generalises).

**`add_client` — reverted to original.** First attempt (validate `POST /clients` response
through `Client`, surface stored values) broke
`test_add_client_normalizes_name_before_sending_and_in_confirmation` (the fake returns a
fictitious name; the test asserts the normalized *input* name in the confirmation). **User
decision: "leave add-clients alone for now."** Unlike documents, a client record has no
sparse-vs-full gap, and the real `POST /clients` response shape can't be seen with the
sandbox in its earlier outage state.

**Known minor**: `_read_back_stored_total` is now referenced only in comments (its 3 callers
were the 3 rewired tools). Left in place — 4 doc-comments point at it as the canonical
bugfix-028-A4 lesson; deleting it is churn, not cleanup. The fallback path no longer runs a
mismatch check (was: separate lightweight total fetch), but `_read_back_full_document` and the
old `_read_back_stored_total` both hit the same `client.get_invoice(doc_id)` — if one fails so
would the other, so no real regression.

Verified: **unit 340 pass**, **integration create-subset 45 pass** (see §2c).

### 4b. morning-mcp-app — `tests/billed/test_create_returns_full_document_e2e.py` ✅ WRITTEN, ⏸ NOT RUN

New file. `@pytest.mark.billed` + `@pytest.mark.sanity`. Drives real OpenAI → `create_combo_document`
over the real MCP tunnel, then asserts on the `mcp_call` output JSON:
1. existing always-present fields still correct (`display_number`, `type == 320`, `type_name`,
   `client_name`, `currency`, `amount ≈ 120`);
2. the previously-`null` fields are now populated (`document_date`, `creation_date`,
   `amount_excl_vat`, `status_code`, `status_label`, `line_items` non-empty with a description,
   `payment` with `method` + `date`);
3. the create result **equals** an independent `get_invoice_details` fetch of the same doc.

Fixtures (`config`, `morning_client`, `mcp_endpoint`) are copied from
`test_openai_invokes_mcp_e2e.py` (module-scoped, not shared via conftest). `TEST_PORT = 8793`
to avoid colliding with that file's `8792`.

### 4c. `scripts/run_sanity.sh` ✅ DONE

Added the new test to the `GATE=(…)` array (2nd `mm|` entry):
```
"mm|tests/billed/test_create_returns_full_document_e2e.py::test_create_combo_document_result_carries_the_full_document"
```
**Must run `./scripts/verify_sanity_lists.sh`** to confirm the `@pytest.mark.sanity`
decorators and the array don't drift (not yet run — needs the morning venv, no sandbox).

### 4d. denidin-app — recognition schema / prompt / manager ⚠️ PARTLY DONE, UNVERIFIED

**Applied this session:**
- `ai_handler.py` — `accounting_document_json` description rewritten: *"ONLY for a reconciliation
  sweep… For a SYNCHRONOUS capture leave this null and map the real response into the flat
  fields instead."*
- `ai_handler.py` — **new `accounting_document_display_number` property** on
  `LEDGER_EVENT_TOOL["parameters"]["properties"]` (`["string","null"]`, "synchronous `חשבונית`
  only, verbatim from the create response") + added to the `required` list. One edit covers
  `RECOGNITION_TOOL` too (it deep-copies `properties`).
- `config/ledger_recognition_prompt.md` — synchronous-`חשבונית` section rewritten to name the
  flat fields explicitly and say "leave `accounting_document_json` null here".

**Applied in the PRIOR session (context, already unit-tested then):**
- `ai_handler.py` — `txn_date` description: signing date (`נחתם ביום…`) is NEVER `txn_date`.
- `ai_handler.py` — `trigger_condition` description: % success-fee / per-occurrence fee ARE
  conditional; due-date / payment-timing wording is NOT.
- `ledger_recognition_prompt.md` — removed "the agreement's own date (you)" from the `הסכם`
  mandatory column; added `trigger_condition` + signing-date bullets.
- `ledger_event_manager.py` — `LEDGER_EVENT_FIELDS` roster tuple + `assert set(record) ==
  set(LEDGER_EVENT_FIELDS)` in `add_ledger_event`.
- `ledger_event_manager.py` — `_derive_vat_status`: types **320/400 forced `"כולל"`**
  unconditionally (`_VAT_INCLUSIVE_DOC_TYPES`).
- `tests/unit/test_recognition_call.py`, `tests/unit/test_ledger_event_manager.py` — matching
  unit tests (prior session).

**NOT yet done on the denidin side** (the rest of the user-approved US2 plan):
1. **Drop `components[]` for a synchronous `חשבונית`** — the verdict should be flat
   (`component_count: 0`, `components: []`), matching the blob path which never uses components.
   Right now the model still nests `amount`/`txn_date`/`vat_status`/`description` in
   `components[0]` and code flattens it.
2. **`event_subtype` ← Morning's `type_name` verbatim** for `חשבונית` (e.g. "חשבונית מס / קבלה").
   User was explicit: *"Use event_subtype - that's exactly the mapping!"* — **no new
   `accounting_document_type` field.** The `event_subtype` enum (`["יצירה","הפקדה","הפקה"]`,
   `strict`) needs relaxing for `חשבונית`, OR code overwrites it post-validation the way the
   blob path already does (`_expand_accounting_document_json` sets `event_subtype =
   doc["type_name"]`).
3. **Add the rest of the flat `חשבונית` field group** to the schema, mirroring
   `_expand_accounting_document_json` 1:1: `accounting_document_status` / `_status_code` /
   `_status_label` / `_payment_method`, and shared fields used flat (`amount`, `txn_date`,
   `description`, `vat_status`, `bank_number`/`_branch`/`_account`, `reference`).
4. **Fix `_mandatory_field_gaps`** for `חשבונית` — read component-level `amount`/`txn_date`
   (or run the gap check *after* flatten), so the spurious `[רישום חלקי]` flag stops.
5. **`_us2_manifest()`** in `test_e2e_ledger_069_morning_create_billed.py` — update to the flat
   shape once the schema is flat: `accounting_document_display_number` tested-present,
   `event_subtype` = the real type name (present, not value-pinned), status fields from the
   real response, no `components`.

**User's binding constraints on this half (verbatim intent):**
- *"the model is NOT ALLOWED to invent data that Morning did not send"* — the model maps
  **only** fields present in the `create_*` **result**; never from the create-call arguments,
  never a default. A field Morning omits stays `null` (and `_mandatory_field_gaps` then
  legitimately flags it — which is now the correct signal that Morning/MCP under-returned;
  §4a's fix is what makes Morning return it).
- *"Morning is NOT allowed to send less data than it is expected"* — hence the §4a morning fix
  is a prerequisite; the denidin schema change alone is not enough.
- *"for 320 and 400 it was said many MANY times that these are ALWAYS vat included"* — the
  `_derive_vat_status` 320/400 force (prior session) stays; `vat_status` is code-derived, not
  model-asked, for `חשבונית`.

---

## 5. Resume checklist (in order)

Pre-req for everything sandbox/MCP: **`dev` must be free** (was taken by another user) AND you
must get **explicit approval to start/rebuild the morning-mcp `dev` container** (every time —
CLAUDE.md).

1. **denidin unit tests** (no sandbox needed) — `tests/unit/test_recognition_call.py` +
   `tests/unit/test_ledger_event_manager.py`. Confirm the prior-session + this-session schema
   edits are green. Fix any fallout from the new `accounting_document_display_number`
   `required` entry.
2. **One clean full Batch-1 billed run** — all 11 via `scripts/run_parallel_tests.sh` (node
   ids relative to `apps/denidin-app/`, NO `apps/denidin-app/` prefix; run from repo root).
   Confirms the 10 greens survive the helper edits (esp. **US5b**, never re-run since 20:58).
3. **`./scripts/verify_sanity_lists.sh`** — confirm the `run_sanity.sh` GATE edit matches the
   new `@pytest.mark.sanity`.
4. **morning-mcp-app** — with approval, `./stop_morning_mcp.sh dev` + `./run_morning_mcp.sh dev`
   (rebuilds the image with the `tools.py` change; verify the new tunnel URL lands in
   `shared/mcp-status-dev/morning_mcp_status.dev.json` with `"status": "running"`).
5. **Run the new billed sanity test** —
   `scripts/run_single_test.sh "tests/billed/test_create_returns_full_document_e2e.py::test_create_combo_document_result_carries_the_full_document"`
   (billed, no approval needed; from `apps/morning-mcp-app/`). This is the proof the §4a fix
   works end-to-end.
6. **Finish the denidin recognition-schema half** — items 1–5 of §4d. Propose the exact schema
   diff to the user first (schema = recognition behavior = a watched surface); wait for
   sign-off before applying.
7. **Re-run US2** —
   `scripts/run_single_test.sh "tests/billed/test_e2e_ledger_069_morning_create_billed.py::TestLedgerPostTurnCaptureMorningCreate::test_us2_morning_create_is_captured_synchronously"`.
8. **Full Batch-1 billed re-run** (11/11) once US2 is green.
9. **Batch-1 expensive** — 5 tests, one at a time, **explicit approval each**, never `-n`.
   Read `logs/test_logs/` for any prior output first. Expect the 3 `_incomplete` manifests
   (`deposit_zero_matches`, `deposit_exact_match`, `agreement_photo_multi`) to need values
   filled from the first real run's transcript.
10. Do **not** `haleluya` / commit / push / deploy without fresh explicit approval.

---

## 6. Standing constraints (do not drop these on resume)

- **Confined to the root clone** (`/Users/yaron/Projects/DeniDin`). Never read/list/grep/cd
  into `coder1`/`coder2`/parent. Always use each app's own `venv/bin/python3` explicitly;
  `which python3` before trusting a bare command.
- **Billed tests need NO approval.** **Expensive tests need explicit approval EVERY time, one
  at a time, NEVER `-n`/batched, read prior logs first.** Never re-run an expensive test once
  it has reached OpenAI without fresh approval.
- **Every billed/expensive test via `scripts/run_single_test.sh`** (or the parallel/sanity
  scripts) — never a bare `pytest | tail/grep/head`. Individual per-test sound-off always.
  **Stop on failure = stop** (every failure its own gate).
- **Never start/rebuild an environment** (`run_*.sh`, `docker compose up`, deploy scripts)
  without explicit per-action approval, every time.
- **Config is code** — never edit `config.*.json` mid-run.
- **Never adjust/relax a test to make it pass on your own** — propose the exact diff + wait.
  (Standing exception for this feature: authority to fix Batch-1 tests "as if writing them
  from scratch" — but the user watches closely; ASK if unsure.)
- **No test may assert on `schema_version`'s value.**
- **Translate ALL Hebrew** in terminal output (user's terminal renders it reversed).
- Never `git add` `shared_state.local.json` (stray untracked file at repo root).
- Remote-control session — `PushNotification` at end of actionable turns.

---

## 7. Key file/line references

| What | Where |
|---|---|
| US2 test + `_us2_manifest()` | `apps/denidin-app/tests/billed/test_e2e_ledger_069_morning_create_billed.py` |
| Recognition tool schema | `apps/denidin-app/src/handlers/ai_handler.py` — `LEDGER_EVENT_TOOL` ~L650, `RECOGNITION_TOOL` ~L936 (deep-copies `properties` at L977) |
| Recognition prompt | `apps/denidin-app/config/ledger_recognition_prompt.md` — mandatory table ~L128, synchronous-`חשבונית` section ~L143 |
| Blob→event mapping (the 1:1 target) | `apps/denidin-app/src/managers/ledger_event_manager.py` — `_expand_accounting_document_json` L545, `_derive_vat_status` L645, `_mandatory_field_gaps` L1382, flat-path `add_ledger_events_from_call` L905 (`accounting_document_json` branch L935) |
| `LEDGER_EVENT_FIELDS` roster | `apps/denidin-app/src/managers/ledger_event_manager.py` ~L335 + assertion in `add_ledger_event` ~L1225 |
| Morning create fix | `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py` — `_read_back_full_document` / `_finalize_created_document` after `_with_amount_mismatch` (~L323); rewired `create_transaction_account` L503, `create_combo_document` L748, `create_invoice` L833 |
| Full-doc formatter (unchanged, already correct) | `apps/morning-mcp-app/src/denidin_mcp_morning/formatters.py` — `format_invoice_json` L248; `Invoice._map_morning_document_shape` in `models.py` |
| New billed sanity test | `apps/morning-mcp-app/tests/billed/test_create_returns_full_document_e2e.py` |
| Design proposal (reconciliation path, resolved 2026-08-23) | `specs/done/v0.5.2/025-morning-sourced-ledger-events/proposal-full-document-capture.md` |
| Run logs from the US2 iteration | `<scratchpad>/run_us2{,b,c,d}.log`, `<scratchpad>/run6b.log`, `<scratchpad>/mm_integ.log`, `<scratchpad>/morning_suite.log` |
| Latest US2 pytest result | `apps/denidin-app/logs/test_logs/pytest_results/tests_billed_test_e2e_ledger_069_morning_create_billed.py__…__test_us2_morning_create_is_captured_synchronously_20260906_213622.txt` |

(`<scratchpad>` = `/private/tmp/claude-502/-Users-yaron-Projects-DeniDin/c54da162-da90-46ec-b7da-be52753e59c2/scratchpad` — session-local, may be cleaned up.)
