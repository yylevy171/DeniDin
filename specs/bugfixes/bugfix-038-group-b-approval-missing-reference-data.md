# Bugfix Spec: Group B document approvals show a blank preview, never fetch what's missing, AND duplicate a whole document type's creation logic

## Bug ID
bugfix-038-group-b-approval-missing-reference-data

## Title
The three "Group B" document tools — `create_receipt` (400), `create_credit_note` (330),
`close_transaction_account` (320-closing-300) — reference an existing document by an internal
Morning ID the user must never see, and today have **no mechanism at all** for surfacing that
document's real data (its display number, amount, actual VAT treatment) in the approval the
user is asked to sign off on. Two of the three also still hardcode payment method/date exactly
as `create_combo_document` did before bugfix-028's A3/A3b fix — never carried over to this
family of tools.

**Scope expanded 2026-08-13** (see "Additional scope" section below): investigating this bug's
`close_transaction_account` case surfaced a second, structurally deeper problem in the same
tool — it independently reimplements `create_combo_document`'s entire type-320 payload-building
logic (`_build_combo_closing_payload` vs. `_build_combo_document_payload`, two separate
functions building the same document shape), and that duplication is *why* the payment-date/
method/bank-detail gap above exists on `close_transaction_account` specifically: bugfix-028's
A3/A3b fix was applied to `create_combo_document`'s payload builder and never propagated to its
undiscovered twin. Both problems are fixed together in this bugfix now.

## Priority
P1 — surfaced while verifying bugfix-028's A1-T2 (deposit matching an existing invoice); real
documents (receipts, credit notes, transaction-account closings) are created today with a
2-line confirmation that names neither the money nor the reference clearly. Not P0: no evidence
yet of a live production incident from this specific gap, unlike bugfix-028's cluster.

## Status
**Open — root cause investigated and fix direction agreed with the user twice: originally
2026-08-10 (during bugfix-028's A1-T2 verification), and again 2026-08-13 with the scope
expansion above, when the same test failed again during an expensive-test sweep and the
investigation traced `close_transaction_account`'s gap to its duplicate-payload-builder root
cause.** Per Bug-Driven Development (METHODOLOGY.md §VII), the root-cause approval gate is
satisfied for both the original scope and the 2026-08-13 addition (this document's own edit
history is that approval). Test-gap analysis for the expanded scope is below, not yet started
for implementation.

## Date Opened
2026-08-10

## Reported By
yaronlev171, while approving bugfix-028's A1-T2 test run.

---

## Origin

A1-T2 (bugfix-028, "deposit matching an existing 305 → close it with a receipt, not a fresh
320") failed — correctly — on this assertion:

```
AssertionError: B3: the approval never says which invoice this receipt closes (expected 51560).
Approval was: '📋 לאישור:\nסוג מסמך: קבלה\n...\nלקוח: (מהמסמך המקושר)\n...
              מע״מ: (לא צוין — יש להבהיר לפני ההפקה)\nעבור: (לא צוין)\n...'
```

Investigating showed this isn't a display-format slip (like the DD/MM-vs-ISO date bug
bugfix-028 also caught and fixed in the same run) — it's a structural gap: `create_receipt`'s
only argument identifying what it closes is `original_invoice_id`, an internal Morning GUID
the constitution explicitly forbids showing the user. Client, purpose, and (for
`close_transaction_account`) VAT are not arguments at all on any of the three Group B tools —
they live only on the linked original document, which none of these tools' callers see before
approval.

`_build_pending_approval_details` (bugfix-028's B3 fix) is a pure function over the tool-call
arguments, with no network access — built against "Group A" (`create_invoice`/
`create_transaction_account`/`create_combo_document`), where client/description/VAT genuinely
are arguments. It was never extended for Group B's different shape, and doing so isn't a
one-line fix: there's currently nowhere in the pipeline that has the original's real data
before the approval is presented.

## Design directed by the user (2026-08-10) — the shape agreed, pending formal approval

**The user's own framing of the correct flow** (verbatim intent, condensed):
1. A deposit carries a client name + amount + other details (already true, per bugfix-028 A1).
2. Search for a matching type-305. **If more than one plausible candidate exists, ASK which
   one** — never guess among them.
3. **If none exists, fall through to the 320 flow** — already bugfix-028's A1 behavior,
   unaffected by this bugfix.
4. If one is chosen, its full real details must be loaded — number, amount, actual VAT
   treatment.
5. The approval message is **two parts**:
   - **Part 1** — the new document being created (the receipt itself), with everything a
     `create_combo_document` approval already shows: client, amount, date, VAT, payment method,
     bank details — **plus** the reference, shown by the original's **display number**, never
     its internal ID.
   - **Part 2** — the **original** document's own real details: its display number, its own
     amount (which may legitimately differ — a **partial payment is real and legal**), and
     especially its **actual VAT treatment**, which — unlike a fresh deposit (always VAT
     included, per bugfix-028 A2 requirement 2) — is **not definitive** for an existing 305 and
     is a real-world source of confusion worth surfacing explicitly.
6. User approves with "כן" → the 400 is created with the real `original_invoice_id` reference
   (never shown), against the 305 identified by its display number (which was shown).

**The architectural decision — the one point that changed mid-discussion, explicitly rejected
once:**
- **Rejected**: a new direct HTTP fetch from `ai_handler.py` to the Morning MCP tunnel,
  bypassing the model, to pull the original's data specifically for the approval preview. This
  would have been the first such direct-call pattern in the codebase (verified: no prior art —
  every existing Morning access goes through the model's own remote-MCP tool-calling loop).
  User's reason: *"the AI needs to do it all."*
- **Directed instead**: the model must do the resolving itself, via its own real tool calls
  (`get_invoice_details`/`list_invoices`), **before** it is in a position to propose the
  Group B call — and the tool signatures should require the resolved display data as explicit
  arguments (not just `original_invoice_id`), so (a) the model is structurally forced to have
  already fetched them, and (b) `_build_pending_approval_details` can render them exactly as it
  already does for Group A, with **no new architecture**, no network access added to
  `ai_handler.py`, and no change to the existing "the model does the querying" pattern.
- **`runtime_constitution.md` must state, per document type, exactly which data elements are
  required for approval, and explicitly instruct: if any is missing, go fetch it before
  proposing anything.** User: *"runtime_const should define CLEARLY which data elements are
  REQUIRED for approval of which doc types, and if they are missing - GO GET THEM!"*

**Execution-time integrity, not yet explicitly directed but a natural consequence worth
recording:** the tools already independently re-fetch the real original via
`client.get_invoice(original_invoice_id)` at execution time (confirmed reading
`create_receipt`/`create_credit_note`/`close_transaction_account`, all three) to build the real
payload — this is unaffected by adding display-only arguments. Whether the execution code
should also cross-check the model-supplied display values (number/amount) against what it
independently fetches, and refuse on mismatch, is an open question for the formal design phase,
not yet directed by the user.

## Scope — confirmed to span all three Group B tools, not just receipts

Read in full during this investigation (2026-08-10; re-verified against current code 2026-08-13):

| Tool | Doc type | Current gap |
|---|---|---|
| `create_receipt` | 400 | **`payment_date`/payment-recording gap CLOSED** — bugfix-028 A3 (2026-08-12) made `payment_date` a required, wired-up parameter; `_build_payment_receipt_payload` now correctly uses it (`payment: [{..., "date": validated_payment_date}]`), not a hardcoded today. **Still open**: no `description` parameter at all (its two siblings both have one), and no display-only reference number parameter, so `_build_pending_approval_details` has nothing to render for purpose or "which invoice does this close" — confirmed live 2026-08-13, approval showed `לקוח: (מהמסמך המקושר)` / `עבור: (לא צוין)` and failed the existing test on the missing invoice number. |
| `create_credit_note` | 330 | Mirrors the original's `vatType`/client/income automatically (no VAT decision needed — inherits it). Still hardcodes `payment`: `{"type": 1, ..., "date": today}` — same class of gap `create_receipt` had before A3, never fixed here. No display-only reference number parameter either. |
| `close_transaction_account` (→ renamed `create_combo_document_as_reference`, see below) | 320 (closing a 300) | Already has `vat_included` as an explicit, well-documented parameter (unlike the other two). **Also hardcodes `payment`'s date to today** (`_build_combo_closing_payload`) — no `payment_date`/`payment_method`/bank-detail parameters exist at all, unlike its own undiscovered twin `create_combo_document`, which bugfix-028 A3/A3b already required these on. No display-only reference number parameter either. |

User: *"It's not just 400, it's also the cancellations that work the same way! ... this needs to
be nailed."*

## Additional scope added 2026-08-13 — `close_transaction_account` is a duplicate of `create_combo_document`, not just missing fields

Found while re-investigating this bugfix's still-red test after an expensive-test sweep: `close_transaction_account` doesn't just have a *smaller* version of `create_combo_document`'s payment-detail gap — it is a **structurally independent reimplementation of the entire type-320 payload**, via its own `_build_combo_closing_payload`, parallel to and never sharing code with `_build_combo_document_payload`. That duplication is the actual root cause of the payment-date gap above: bugfix-028's A3/A3b fix touched `_build_combo_document_payload` only, and had no way to also fix a twin function nobody knew existed.

User's reaction on discovering this live: *"This is a real MESS!!! HOW DID YOU CREATE 2 TOOLS FOR THE SAME GODDAMN THING?!"* — traced to history: `create_combo_document` shipped in Feature 021; `close_transaction_account` was added later (Feature 023/bugfix-014) explicitly modeled after `create_receipt`/`create_credit_note`'s reference pattern instead of extending `create_combo_document`, because 320 is the one document type reachable both as a fresh standalone document and as the closing document for an existing 300.

**Decision (user, 2026-08-13, "Option B"): do not merge the two MCP tools into one.** The model-facing contracts genuinely differ (`create_combo_document` needs `client_name`+`name_resolved`; the closing tool needs `original_invoice_id`, client always inherited, never re-supplied) — collapsing them into one tool with optional-either-or parameters was considered and rejected as messier than two focused tools. Instead:

1. **Rename** `close_transaction_account` → **`create_combo_document_as_reference`** (user's chosen name) — a naming-only refactor, but touches every file that references the tool by name (confirmed 2026-08-13: 19 files across both apps — `runtime_constitution.md`, `ai_handler.py`'s approval-gated tool list, `formatters.py`, `server.py`/`tools.py`, unit/integration tests in `morning-mcp-app`, billed/expensive tests and `denidin_mcp_e2e_helpers.py` in `denidin-app`, plus `ARCHITECTURE.md`/`README.md`). Mechanical (grep/rename), not a logic change.
2. **Extract one shared internal payload-builder** used by both `create_combo_document` and the renamed tool, so a fix to one can never again silently fail to reach its twin.
3. **Fix the renamed tool's payment gap**: real `payment_date`/`payment_method`/bank-detail parameters, required, matching `create_combo_document`'s A3/A3b treatment exactly — no more hardcoded `today`.
4. **Add the missing display-only parameters to all three Group B tools** (this bugfix's original scope): `description` on `create_receipt` (parity with its siblings), and a display-only original-document reference number on all three, so `_build_pending_approval_details`'s existing (currently dead-code) `invoice_number`/`original_invoice_number` fallback line finally has data to render.

**Additional requirement (user, 2026-08-13): the reproduction test for this bug must move to (or be duplicated into) the `billed` tier, not stay `expensive`-only.** The existing test (`test_given_a_deposit_matching_an_existing_tax_invoice_then_a_receipt_closes_it`) only fails inside an `expensive` (vision/image) test because its scenario *starts* with a bank-deposit screenshot — but the actual bug (approval text missing the referenced document's display data) is purely a text/tool-argument/rendering problem, unrelated to image classification. User: *"make sure this is tested as billed tests and not 'wait' for expensives. There's no reason we need an image for this simple test - the bug should have been caught earlier."* A billed-tier version should drive the same scenario via a plain text request (e.g. "seed a 305, then ask in plain Hebrew text to create a receipt against it") so this class of bug is caught on every free, no-approval-needed `billed` run instead of only during an infrequent, gated `expensive` sweep.

## What is explicitly NOT part of this bugfix
- bugfix-028's A1 flow (no matching 305 → 320) — already correct, already tested, unaffected.
- Merging `create_combo_document` and the renamed reference tool into a single MCP tool —
  explicitly considered and rejected 2026-08-13 (see above); they stay two tools sharing
  internal implementation only.
- The rejected direct-HTTP-fetch design — recorded above for posterity, not to be revisited
  without a new decision.

## Test carried over from bugfix-028

**`test_given_a_deposit_matching_an_existing_tax_invoice_then_a_receipt_closes_it` (A1-T2)** —
originally written and approved as part of bugfix-028's test set, moved here 2026-08-10 (user:
*"put in it all we already said... moving this specific offending test there so it doesn't
pollute the tests here"*) once investigation showed it depends on this bugfix's fix, not
bugfix-028's approved scope. Relocated from
`apps/denidin-app/tests/expensive/test_ledger_event_capture_e2e.py` to
`apps/denidin-app/tests/expensive/test_group_b_reference_approval_e2e.py`. Still red as of
2026-08-13 (re-confirmed live during an expensive-test sweep) — expected, since the fix isn't
implemented.

## Test-gap analysis (2026-08-13)

1. **The existing `expensive` test stays** — it's still the right end-to-end check that a real
   bank-deposit *image* correctly resolves to an existing invoice and closes it, which is
   genuinely a vision-classification concern, not just an approval-rendering one.
2. **New: a `billed` (text-only) test covering the same approval-content assertion**, per the
   user's requirement above — seeds a 305 via a normal conversational `create_invoice` flow
   (no image), then asks in plain text to create a receipt against it, and asserts the pending
   approval names the real invoice number (mirroring the existing test's core assertion,
   `invoice_number in approval_text`). Lives in `tests/billed/`, likely alongside the other
   invoice-lifecycle billed tests.
3. **`create_credit_note` and the renamed `create_combo_document_as_reference` currently have
   no test asserting their approval CONTENT at all** (only the receipt case does, via the test
   above) — the fix must not ship for all three tools while only one has a regression test.
   Needs at least one billed test per tool (or one parametrized test covering all three) proving
   the approval names the real referenced document, not a placeholder.
4. **The rename itself needs no new test** — it's a pure identifier change; existing tests that
   already call the tool by name are the regression coverage, once updated to the new name.
5. **The shared-payload-builder extraction needs no new test either** — it's an internal
   refactor; `create_combo_document`'s own existing tests (already green) are sufficient to catch
   a behavior regression on that side, and the renamed tool's own (new/updated) tests cover the
   other side.

## Related Work
- `specs/in-progress/bugfixes/bugfix-028-invoicing-and-approval-gate-p0-cluster.md` — B3 (the
  approval content requirement) and A3/A3b (payment date/method/bank details) are the direct
  ancestors of this bugfix; this is explicitly the "next layer" for Group B that 028 didn't cover.
- `specs/done/023-reference-linked-document-creation/` — introduced all three Group B tools'
  current reference-by-ID pattern.
- `specs/done/027-mandatory-client-reference-invoicing/` — `_extract_linked_client_id`,
  `format_original_not_linked_to_client`, the pattern these tools already use for the client
  side of "resolve the original first."
- `specs/in-progress/bugfixes/bugfix-028-invoicing-and-approval-gate-p0-cluster/bugfix-028-HANDOFF.md`
  (2026-08-13 session) — the billed-suite sweep session that re-ran this test, found it still
  red, and traced `close_transaction_account`'s gap to the duplicate-payload-builder root cause
  documented in "Additional scope added 2026-08-13" above. That session's own scope stayed
  test-only (bugfix-028); this bugfix absorbs the actual fix.
