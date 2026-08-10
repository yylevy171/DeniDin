# Bugfix Spec: Group B document approvals show a blank preview and never fetch what's missing

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

## Priority
P1 — surfaced while verifying bugfix-028's A1-T2 (deposit matching an existing invoice); real
documents (receipts, credit notes, transaction-account closings) are created today with a
2-line confirmation that names neither the money nor the reference clearly. Not P0: no evidence
yet of a live production incident from this specific gap, unlike bugfix-028's cluster.

## Status
**Open — root cause investigated and fix direction agreed with the user in the same session
that found it (2026-08-10, during bugfix-028's A1-T2 verification).** Per Bug-Driven Development
(METHODOLOGY.md §VII), this still needs the formal root-cause approval gate and test-gap
analysis before implementation — the direction below is what was discussed live, not yet a
signed-off spec in the METHODOLOGY sense.

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

Read in full during this investigation (2026-08-10):

| Tool | Doc type | Current gap |
|---|---|---|
| `create_receipt` | 400 | `payment_date` parameter **already exists and is documented as "Currently unused — payload uses today's date; reserved for backdating support"** — never wired up. No `payment_method`/bank-detail parameters at all; `_build_payment_receipt_payload` hardcodes `{"type": 1, "price": ..., "date": today}` — the exact cash/today-date defaults bugfix-028 A3/A3b fixed for `create_combo_document`, never carried to this tool. |
| `create_credit_note` | 330 | Mirrors the original's `vatType`/client/income automatically (no VAT decision needed — inherits it). Same hardcoded `payment`: `{"type": 1, ..., "date": today}`. |
| `close_transaction_account` | 320 (closing a 300) | Already has `vat_included` as an explicit, well-documented parameter (unlike the other two) — closest of the three to Group A's shape already. Still no way to surface the original 300's own data in the approval. |

User: *"It's not just 400, it's also the cancellations that work the same way! ... this needs to
be nailed."*

## What is explicitly NOT part of this bugfix
- bugfix-028's A1 flow (no matching 305 → 320) — already correct, already tested, unaffected.
- Any change to `create_combo_document` itself — it already has everything this bugfix gives
  the other three tools.
- The rejected direct-HTTP-fetch design — recorded above for posterity, not to be revisited
  without a new decision.

## Test carried over from bugfix-028

**`test_given_a_deposit_matching_an_existing_tax_invoice_then_a_receipt_closes_it` (A1-T2)** —
originally written and approved as part of bugfix-028's test set, moved here 2026-08-10 (user:
*"put in it all we already said... moving this specific offending test there so it doesn't
pollute the tests here"*) once investigation showed it depends on this bugfix's fix, not
bugfix-028's approved scope. Relocated from
`apps/denidin-app/tests/expensive/test_ledger_event_capture_e2e.py` to
`apps/denidin-app/tests/expensive/test_group_b_reference_approval_e2e.py`. Still red — expected,
since the fix isn't implemented — and will need re-review once this bugfix's own root cause and
test plan go through their own METHODOLOGY §VII gates rather than inheriting bugfix-028's.

## Test-gap analysis
Not started — this bugfix has not yet been through its own root-cause approval gate as a
standalone item (the discussion above happened live while investigating bugfix-028's A1-T2,
and captures the user's direction, but METHODOLOGY §VII's formal steps 1-2 for *this* bugfix
should still run before test design proceeds).

## Related Work
- `specs/in-progress/bugfixes/bugfix-028-invoicing-and-approval-gate-p0-cluster.md` — B3 (the
  approval content requirement) and A3/A3b (payment date/method/bank details) are the direct
  ancestors of this bugfix; this is explicitly the "next layer" for Group B that 028 didn't cover.
- `specs/done/023-reference-linked-document-creation/` — introduced all three Group B tools'
  current reference-by-ID pattern.
- `specs/done/027-mandatory-client-reference-invoicing/` — `_extract_linked_client_id`,
  `format_original_not_linked_to_client`, the pattern these tools already use for the client
  side of "resolve the original first."
