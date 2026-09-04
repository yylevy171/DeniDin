# Feature 059 — billed/expensive test failures to revisit

Running log of failures seen while stabilizing + running the sanity suite. Each
entry: node id, what actually happened, and a first-pass classification —
**real bug** / **flaky model** (nondeterministic, correct-ish behavior) /
**over-strict assertion** (model got a correct result a different way) /
**sandbox clutter** (accumulated test-run data breaks name resolution).

`scripts/run_sanity.sh` appends a raw section here automatically on every
stop-on-failure. The curated analysis below is maintained by hand.

> 🚨 **NOTHING IN THIS FILE IS CONSIDERED FIXED UNTIL THE USER EXPLICITLY APPROVES
> A FIX FOR IT.** A test that later went green on a retry is still **OPEN** here
> (flaky ≠ fixed). Each item stays OPEN until (a) a root cause is agreed, (b) the
> user approves an action (assertion change / code fix / accept-as-flaky / sandbox
> cleanup), and (c) that action lands. Only then does its status change.

---

## STATUS LEDGER — every failure seen, all OPEN

Two sources: the 2026-09-02 unintended full `-m billed` sweep (9 failures — 3 are
sanity members, 6 are not), and the 2026-09-03 expensive sanity one-shot run
(2 real failures + 1 infra-only).

### Sanity-suite members

| ID | Test | First-pass class | Status |
|----|------|------------------|--------|
| S1 | `test_denidin_morning_client_management_e2e.py::test_godfather_finds_client_via_hebrew_vowel_variant` | test defect (missing geresh-normalization) | ✅ **FIXED 2026-09-03 (user-approved)** — line 389 now wraps both sides in `_normalize_hebrew_geresh` (matches siblings). Verified: 2 clean passes (56s, 37s) |
| S2 | `test_denidin_morning_list_invoices_e2e.py::test_client_all_payments_gets_the_complete_picture` | **real bug** — `ai_handler.py` only harvests `mcp_call` items from the final response, not from the intermediate responses in the `query_ledger_events` follow-up loop, so `list_invoices` (which the Morning server log proves ran at 19:01:29) is missing from `ai_response.mcp_calls` and the turn's audit line | **OPEN — deferred to Feature 69** (user decision 2026-09-03; that feature reworks this code path). Not fixed in Feature 059. Model behaviour was correct; only the app-side call accounting is incomplete. |
| S3 | `test_standalone_receipt_billed.py::test_godfather_records_a_deposit_as_a_standalone_receipt` | over-strict assertions ×2 | ✅ **FIXED 2026-09-03 (user-approved)** — (A) `original_internal_morning_id` check now parses JSON + asserts value `is None` (model legitimately passes explicit `null`); (B) "no tax invoice" now checked on the `create_receipt` result text, not a scan of the client's whole document history (random existing client routinely owns unrelated prior tax invoices). Verified: 2 clean passes (40s, 36s). Model behaviour was correct both times. |
| S4 | `test_image_classification_e2e.py::test_personal_note_is_neither_bank_nor_agreement` | real — no client-resolution / classification gate on the ledger-capture path | **OPEN — blocked on Feature 069** (user decision 2026-09-04). The 2026-09-03 fix (a) `prompts/image_analysis.txt` mandatory-classification bullets and (b) a looser assertion held on the *classification* half — but **regressed on the capture half**: parallel sanity run 2026-09-04 (`_sanity_parallel_20260904_011710.txt`) had the extractor correctly return `doc_type='unknown'` yet `capture_ledger_events_from_text` still fired a full 5-component `הסכם` event off the extracted note text (`שכר / בני / 4000 / 2000 / …`). Same root cause as S5 / N5: nothing gates the ledger-capture path. Feature 069 (`specs/backlog/069-mandatory-client-resolution-before-ledger-event`) is where this gets fixed — the classification-vs-capture split is 069's job, not Feature 059's. Prompt bullets + assertion change from 2026-09-03 stay in place; the test stays red until 069. |
| S5 | `test_ledger_event_capture_e2e.py::...test_given_real_six_component_agreement_image_mor_ben_shaya...` | real — no client-resolution gate in the ledger-capture path | **OPEN — blocked on Feature 069** (user decision 2026-09-03). Vision reads all 6 components but the fixture's glare band hides the client surname (`מר מור בן [לא קריא]`); with no readable `client_name`, `capture_ledger_events_from_text` persists nothing (0 events, test wants 6). Feature 069 (`specs/backlog/069-mandatory-client-resolution-before-ledger-event`) is the gate that makes a ledger event resolve the client (or ask) instead of silently dropping. The `_seed_client`/`resolve_client_name` billed-test machinery cannot be used here until 069 builds that path — the ledger-capture call is text-only, `LEDGER_EVENT_TOOL` only, and never touches Morning. Comment added in the test. Not fixed in Feature 059. |
| S6 | `test_image_classification_e2e.py::test_six_component_agreement_is_classified_as_an_agreement` | infra (network/DNS) only | ✅ **CLOSED 2026-09-03 (user-approved)** — passed clean on retry; transient network only, no code/test defect |

### Non-sanity billed failures (2026-09-02 sweep)

| ID | Test | First-pass class | Status |
|----|------|------------------|--------|
| N1 | `test_denidin_morning_invoice_lifecycle_e2e.py::test_godfather_cancels_invoice_via_whatsapp` | **Feature 059 regression** (commit `77868e6`) + rigid seed helper | ✅ **FIXED 2026-09-03 (user-approved)** — model behaviour was correct in both observed failures. (A) `77868e6` changed `_seed_fresh_invoice` from a fresh client to `pick_existing_client()`; the reused client often already owned another open invoice, making "cancel the invoice of X" genuinely ambiguous → model asked which → 2-turn `_send_turn_and_approve` can't answer. (B) seed text omitted VAT → constitution-mandated "כולל מע\"מ?" question desynced the ask→approve turns. Fix: N1-scoped `_seed_fresh_invoice_for_a_fresh_client()` — brand-new client (owns exactly 1 invoice) + VAT stated explicitly (`לא כולל מע"מ`) in the seed text. Verified: 1 clean pass (64.75s). Shared `_seed_fresh_invoice` left as-is (mark-paid family not in scope). |
| N2 | `test_denidin_morning_invoice_lifecycle_e2e.py::test_godfather_marks_transaction_account_invoice_paid_via_whatsapp` | rigid seed helper + missing `payment_date` in prompt (+ latent `77868e6` regression) | ✅ **FIXED 2026-09-03 (user-approved)** — model behaviour was correct: `create_combo_document_as_reference` requires `payment_date` and "כשולם" never stated when, so the model asked "האם התשלום התקבל היום?" and the 2-turn `_send_turn_and_approve` "כן" couldn't answer. Fix: N2-scoped `_seed_transaction_account_invoice_for_a_fresh_client()` (fresh client → unambiguous type-300) + mark-paid prompt now states `כשולם היום, כולל מע״מ` (both mandatory clarifications pre-answered, mirroring how VAT was already handled). Verified: 1 clean pass (97.33s). |
| N3 | `test_denidin_morning_list_invoices_e2e.py::test_zehavit_client_name_transcribed_exactly` | sandbox pollution (`resolve_client_name("זהבית")` → MULTI_CANDIDATE from junk `זהביתDENIDIN_039_T1_* צור` clients) blocked the test before any `list_invoices` call | ✅ **FIXED 2026-09-03 (user-approved)** — model behaviour was correct (it asked which "זהבית"). Shared `_drive_zehavit_to_list_invoices()` helper now drives `resolve_client_name`'s MULTI_CANDIDATE to EXACT via the built `_resolve_client_name` helper (disambiguator `זהבית צור`), then asserts. bugfix-013 garble check kept, relocated to the model's FIRST client reference on turn 1 (`== "זהבית"` verbatim); added a downstream check that the resolved name reaches `list_invoices` un-garbled. Verified: 1 clean pass (45s), trace confirms it drove the disambiguation. |
| N4 | `test_denidin_morning_list_invoices_e2e.py::test_no_date_mentioned_omits_date_range` | same sandbox pollution as N3 | ✅ **FIXED 2026-09-03 (user-approved)** — same `_drive_zehavit_to_list_invoices()` helper to reach a `list_invoices` call; the date-narrowing assertion (`from_date`/`to_date is None` on every call) is **unchanged**. Verified: 1 clean pass (39s). |
| N5 | `test_denidin_vcf_contact_e2e.py::test_godfather_shares_contact_card_missing_email_is_asked_for` | known Feature-69 blocker | **OPEN — blocked on Feature 069** (user decision 2026-09-03). On the bare contact card the model resolves "גיל ברטל" → EXACT and declines as a duplicate instead of first asking for the missing email (REQ-CLIENT-012 ordering); `capture_ledger_event` fires in the same turn. Feature 069 is the gate that fixes the ordering. `KNOWN FAILURE — BLOCKED ON FEATURE 069` block added to the test docstring (previously only in `spec.md`). Left red on purpose. Not fixed in Feature 059. |
| N6 | `test_group_b_reference_approval_billed.py::...test_multi_turn_clarification_uses_the_real_internal_id_not_the_display_number` | over-strict assertion (whole-blob substring scan) | ✅ **FIXED 2026-09-03 (user-approved)** — model behaviour was correct: `original_internal_morning_id` was the right GUID and the call succeeded; the display number `40445` appeared only in the free-text `description` ("...חשבון עסקה מספר 40445..."), which is natural. Assertion changed from `doc_number not in <entire args JSON>` to a field-specific check: any `internal_morning_id`/`original_internal_morning_id` present must `== real_id` (the real resolved GUID the seed helper returns). Stricter on the real bug, immune to free-text. Verified: 1 clean pass (56s), id check non-vacuous. |

Detail for every ID is in the sections below.

---

## Seed batch — 2026-09-02, unintended full `-m billed` sweep

Context: `run_sanity.sh` (old version) was driven with a shell-array bug that
collapsed the node list to one empty arg, so `run_single_test.sh` ran
`pytest "" -m billed` — the **entire** billed suite (1442 collected, 138
passed, 9 failed, 1 skipped, 56 min) instead of the intended 29. The 9
failures below are real results worth triaging; the over-broad run itself is
fixed (new `run_sanity.sh` only ever calls `run_single_test.sh` with one
explicit node id, tracks state, resumes).

Full log: `apps/denidin-app/logs/test_logs/pytest_results/_20260902_181930.txt`

### Sanity-suite members (3)

1. **`test_denidin_morning_client_management_e2e.py::test_godfather_finds_client_via_hebrew_vowel_variant`**
   — *flaky model.* **Passed earlier the same session, failed here.** Asked about
   `דוד וורובוביץ'`, the model replied with a disambiguation list
   (`דויד וורובוביץ׳` / `חולדה וורובוביץ׳` — "which did you mean?") instead of
   bridging the male/chaser vowel-letter difference and resolving to `דויד`.
   Morning's search has zero fuzzy tolerance; the model is supposed to
   compensate and here didn't. Revisit: is the constitution guidance strong
   enough, or is this inherent model variance to accept / assert more loosely?

2. **`test_denidin_morning_list_invoices_e2e.py::test_client_all_payments_gets_the_complete_picture`**
   — *over-strict assertion (probably).* Asked for "all payments" for
   `דורית אשכנזי`; the model called `get_invoice_details` ×2 (on two receipts it
   already had context for) and produced a **correct** full picture — 2 paid
   (₪90 total) + 4 unpaid (₪215 total). The test asserts `list_invoices` was
   called on the initial ask. Revisit: assert on the *answer content* (paid +
   unpaid both present, right totals), not the specific tool.

   **UPDATE 2026-09-03 (user decision): BLOCKED ON FEATURE 069.** Deeper look
   (Morning MCP server logs): `list_invoices` **did** run — inside an
   intermediate chained response in the `query_ledger_events` follow-up loop —
   but `ai_handler.py` only harvests `mcp_call` items from the final settled
   response, so it never reaches `ai_response.mcp_calls`. Feature 069 reworks
   this ledger/resolution code path and is expected to close the gap. A
   `KNOWN FAILURE — BLOCKED ON FEATURE 069` comment was added to the test.
   Left red on purpose. Not fixed in Feature 059.

3. **`test_standalone_receipt_billed.py::test_godfather_records_a_deposit_as_a_standalone_receipt`**
   — *over-strict assertion.* Deposit for existing client `לוסי צ׳ורנוב`; the
   model called `create_receipt` with `original_internal_morning_id: null`
   explicitly (correct standalone behavior — Feature 056 accepts exactly that).
   The test asserts the key is *absent* from the args string. Revisit: accept
   `null` as well as absent.

### Non-sanity billed failures from the same sweep (6)

4. **`test_denidin_morning_invoice_lifecycle_e2e.py::test_godfather_cancels_invoice_via_whatsapp`**
   — *flaky model / sandbox clutter.* "Cancel it" (by client name) → model asked
   "which invoice?" listing 2 candidates instead of calling `create_credit_note`.

5. **`test_denidin_morning_invoice_lifecycle_e2e.py::test_godfather_marks_transaction_account_invoice_paid_via_whatsapp`**
   — *flaky model.* "Mark the חשבון עסקה paid" → model asked "was payment
   received today, 2 Sep 2026?" instead of calling
   `create_combo_document_as_reference`. (A clarifying question that's arguably
   reasonable — but the test wants the tool call.)

6. **`test_denidin_morning_list_invoices_e2e.py::test_zehavit_client_name_transcribed_exactly`**
   — *sandbox clutter.* The sandbox now holds 4 `זהבית…צור` clients
   (`זהבית צור`, `זהביתDENIDIN_039_T1_1786629362 צור`, …two more) from prior
   test runs → `resolve_client_name` returns "found several similar" → model
   asks to disambiguate → never calls `list_invoices`. Needs a sandbox cleanup
   or a dedicated fixture client.

7. **`test_denidin_morning_list_invoices_e2e.py::test_no_date_mentioned_omits_date_range`**
   — *sandbox clutter.* Same `זהבית` collision as #6, same mechanism.

8. **`test_denidin_vcf_contact_e2e.py::test_godfather_shares_contact_card_missing_email_is_asked_for`**
   — *known blocker.* This is the Feature-69 red test (a `capture_ledger_event`
   misfire on the seed email routes the model past `resolve_client_name` via the
   ledger follow-up → `add_client` on an existing client → "לקוח כבר קיים").
   Left red on purpose; not a Feature 059 regression. Tracked in `spec.md`.

9. **`test_group_b_reference_approval_billed.py::TestGroupBReferenceApprovalBilled::test_multi_turn_clarification_uses_the_real_internal_id_not_the_display_number`**
   — *over-strict assertion.* The `original_internal_morning_id` arg **was**
   correct (`b85d9ab2-…`). The model additionally wrote the display number
   `40445` into the free-text `description` ("תשלום עבור חשבון עסקה מספר 40445…").
   The assertion is `'40445' not in <entire args JSON>`, so a legitimate mention
   in the description trips it. Revisit: assert specifically on the
   `original_internal_morning_id` field, not the whole blob.

## FAILED 2026-09-03T11:32:00 — `tests/billed/test_standalone_receipt_billed.py::test_godfather_records_a_deposit_as_a_standalone_receipt`
- app `den` | via `run_sanity.sh` -> `run_single_test.sh`
- results: `apps/denidin-app/logs/test_logs/pytest_results/tests_billed_test_standalone_receipt_billed.py__test_godfather_records_a_deposit_as_a_standalone_receipt_20260903_113138.txt`
```
___________ test_godfather_records_a_deposit_as_a_standalone_receipt ___________
        assert not _calls_for(ask_ai_response, "create_receipt"), (
        assert approve_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
        assert receipt_calls and receipt_calls[0]["error"] is None, (
E       AssertionError: Expected the STANDALONE branch (no original_internal_morning_id) to fire, got arguments: '{"original_internal_morning_id":null,"payment_date":"2026-09-03","amount":39,"client_name":"עובדיה פרלמן","description":"פיקדון שאינו הכנסה","name_resolved":true}'
E       assert 'original_in...l_morning_id' not in '{"original_...olved":true}'
E         
E         'original_internal_morning_id' is contained here:
E           {"original_internal_morning_id":null,"payment_date":"2026-09-03","amount":39,"client_name":"עובדיה פרלמן","description":"פיקדון שאינו הכנסה","name_resolved":true}
E         ?   ++++++++++++++++++++++++++++
FAILED tests/billed/test_standalone_receipt_billed.py::test_godfather_records_a_deposit_as_a_standalone_receipt
```
**Revisit:** classify (real bug / flaky-model / over-strict assertion / sandbox-clutter) and act.

## FAILED 2026-09-03T11:40 — `tests/expensive/test_image_classification_e2e.py::test_six_component_agreement_is_classified_as_an_agreement`
- app `den` | expensive sanity run, one-shot (user: "run all 7 exactly ONCE")
- **INFRA, not a real failure:** `httpx.ConnectError: [Errno 8] nodename nor servname provided, or not known`
  reaching the OpenAI vision endpoint — DNS/network dropped mid-test, `doc_type='unknown' fields={}`.
- results: `apps/denidin-app/logs/test_logs/pytest_results/tests_expensive_test_image_classification_e2e.py__test_six_component_agreement_is_classified_as_an_agreement_20260903_113807.txt`
- **RETRY 2026-09-03 12:28 (user-approved): PASSED (31.58s).** Confirmed transient network only.
  `pytest_results/..._20260903_122859.txt`. Ledger status stays **OPEN (low)** per the no-fix-without-approval rule.
**Revisit:** nothing to fix — user to confirm this can be closed as infra-only.

## FAILED 2026-09-03T12:21 — `tests/expensive/test_image_classification_e2e.py::test_personal_note_is_neither_bank_nor_agreement`
- app `den` | expensive sanity run, one-shot. **REAL failure — reached OpenAI (200 OK).**
- *flaky model / classifier over-eagerness.* `not_an_agreement_personal_note.jpg` (handwritten salary
  jotting for דני/שי, partly illegible) was classified `doc_type='agreement'` with 3 components
  (`client_name='[לא קריא]'`, amounts 4000/2000/3000) instead of "neither". `ledger_events_captured=0`
  (nothing was persisted), and the model's own reply hedged heavily and asked a clarifying question —
  but the extractor still stamped `agreement`.
- results: `apps/denidin-app/logs/test_logs/pytest_results/tests_expensive_test_image_classification_e2e.py__test_personal_note_is_neither_bank_nor_agreement_20260903_122039.txt`
**Revisit:** classify (flaky-model vs classifier prompt gap). No ledger event was actually captured,
so blast radius is limited to the classification label.

**UPDATE 2026-09-03:** fixed — `prompts/image_analysis.txt` mandatory-classification bullets + a
looser assertion (accept an incomplete flag / clarifying question; fail only on a confident complete
real-bucket classification *or* an actual ledger event off the note). Passed once.

**REGRESSED 2026-09-04 → BLOCKED ON FEATURE 069 (user decision).** Parallel sanity run
`_sanity_parallel_20260904_011710.txt`: extractor correctly returned `doc_type='unknown'` (the
classification fix held) but `capture_ledger_events_from_text` *still* fired a full 5-component
`הסכם` event off the extracted note text — exactly the second failure condition the assertion
guards. Root cause is identical to S5 / N5: the ledger-capture path has no gate. Folded into
Feature 069's scope; prompt + assertion changes stay in place, test stays red until 069.

## FAILED 2026-09-03T12:23 — `test_ledger_event_capture_e2e.py::TestLedgerEventCaptureE2E::test_given_real_six_component_agreement_image_mor_ben_shaya_then_all_components_correctly_persisted`
- app `den` | expensive sanity run, one-shot. **REAL failure — reached OpenAI.**
- *flaky model / OCR-gated capture.* Vision read the agreement body fine (all 6 fee components present
  in the extracted text) but could NOT read the client surname — `מר מור בן [לא קריא]` — so the model
  asked "חסרים לי הפרטים הבאים... שם הלקוח" instead of persisting. `0` ledger events, test expects `6`.
  `assert 0 == 6`.
- results: `apps/denidin-app/logs/test_logs/pytest_results/tests_expensive_test_ledger_event_capture_e2e.py__TestLedgerEventCaptureE2E__test_given_real_six_component_agreement_image_mor_ben_shaya_then_all_components_correctly_persisted_20260903_122314.txt`
**Revisit:** is a missing/illegible client name meant to block capture entirely, or should components
persist with `client_name` unknown/partial (`מור בן ...`)? Constitution + test intent question.

**RESOLVED 2026-09-03 (user decision): BLOCKED ON FEATURE 069.** The ledger-capture path has no
client-resolution step at all (`capture_ledger_events_from_text` is a text-only call with only
`LEDGER_EVENT_TOOL` attached — it never calls Morning). Making the client resolve here = building
Feature 069's gate (`specs/backlog/069-mandatory-client-resolution-before-ledger-event`), which is
out of Feature 059's "stabilize tests only" scope. A `KNOWN FAILURE — BLOCKED ON FEATURE 069`
comment was added to the test docstring. Same disposition as S2. Left red on purpose.

**RESOLVED 2026-09-03 (user-approved): FIXED.** Prompt gap, not pure model flakiness.
`prompts/image_analysis.txt` gained a mandatory-classification bullet for handwritten
name+amount notes (→ `unknown`) plus a general "in doubt → `unknown`, let the system ask"
rule. Test loosened to accept an incomplete flag / clarifying question and only fail on a
confident complete real-bucket classification or an actual captured ledger event. Passed
post-change; 6-test expensive regression pass all green.
