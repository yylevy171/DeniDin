# Bugfix Spec: get_financial_summary silently drops invoices of non-allowlisted document types

## Bug ID
bugfix-012-financial-summary-drops-nonallowlisted-invoice-types

## Title
`get_financial_summary` omits real, genuinely-unpaid invoices from its totals whenever their Morning `type` isn't 305 or 320 — while `list_invoices` (no such filter) reports them correctly

## Status
Fixed - merged to master (PR #111). Re-approved and re-applied 2026-07-21. Root cause and fix strategy revisited: an explicit allowlist (`{300, 305, 320}`) was chosen over both "delete the check entirely" (would double-count receipts/quotes/orders) and a `300-399` range (would risk absorbing 330/credit-invoice semantics into the wrong bucket). See Root Cause and Fix sections below for the final reasoning.

## Date Opened
2026-07-20

## Reported By
yylevy171 (found via manual prod-environment testing, same live session as bugfix-013/014)

## Affected Area
- `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py` — `get_financial_summary()` (around line 589 at time of writing)

## Description
User asked a real, live WhatsApp question in prod (admin role, real Morning production account): "אני מעוניין לבדוק כמה כסף לקוחות עוד חייבים לי החודש" (how much do clients still owe me this month). The model correctly called `get_financial_summary` for the July 2026 range (after an earlier, separate RBAC issue — bugfix-010 — was fixed and the affected container rebuilt). The tool reported **0 unpaid invoices, 24/24 paid, ₪168,585 total** for July.

Independently, an earlier `list_invoices(status="unpaid", July range)` call in the same session had found a real unpaid invoice: #90192, client "מתנס שורק", ₪10,620, issued 10/07/2026, due 31/07/2026.

The user manually verified via the Morning dashboard that this invoice **is genuinely still unpaid** — ruling out "it got paid in between the two calls" as an explanation. Two separate, independent `get_financial_summary` calls (five minutes apart) both returned the identical "24 paid, 0 unpaid" result, ruling out a one-off fluke or model hallucination on that specific call (the model did call the tool for real both times — it just got a wrong answer from the tool itself).

## Root Cause (confirmed)

`get_financial_summary` (`tools.py`) fetches raw documents from Morning the same way `list_invoices` does (`client.list_invoices(params={"fromDate": start, "toDate": end})`), but then applies an extra filter that `list_invoices` does not have:

```python
_TAX_INVOICE_DOCUMENT_TYPE = 305
_INVOICE_RECEIPT_COMBO_DOCUMENT_TYPE = 320
_PRIMARY_INVOICE_DOCUMENT_TYPES = {_TAX_INVOICE_DOCUMENT_TYPE, _INVOICE_RECEIPT_COMBO_DOCUMENT_TYPE}
...
if document_type not in _PRIMARY_INVOICE_DOCUMENT_TYPES:
    continue  # skip receipts/orders/other non-sale document types
```

Only Morning document `type` 330 (credit invoice — confirmed meaning, handled separately for netting) has confirmed semantics in this codebase. The 305/320 allowlist is not similarly confirmed to be exhaustive of "real sale documents" — and evidently isn't: invoice #90192 has some other `type` value, so it's silently excluded from every total (`total_invoiced`, `total_unpaid`, `invoice_count`, `unpaid_invoice_count`) even though it's a completely real, genuinely unpaid invoice. `list_invoices` applies no such type filter and reports it correctly.

## Steps to Reproduce
1. Have at least one real invoice in the account whose Morning `type` is not 305 or 320 (and not 330/credit-invoice).
2. Call `get_financial_summary` for a date range including that invoice.
3. Observe: the invoice is entirely absent from every total, while `list_invoices` for the same range/filters shows it correctly.

## Expected Behavior
`get_financial_summary`'s totals should include every real sale document Morning returns for the range, excluding only credit invoices (330, which are already netted separately) — consistent with what `list_invoices` already shows for the identical underlying data.

## Impact
Any "how much is still owed / what's the total this period" question can silently under-report unpaid amounts and invoice counts whenever any invoice in the range has a type outside the narrow {305, 320} allowlist — a serious correctness issue for the tool's core purpose (this is real financial data, not a cosmetic bug).

## Fix (applied)

Widened `_PRIMARY_INVOICE_DOCUMENT_TYPES` to an explicit set of confirmed billable document types — `{300, 305, 320}` — instead of removing the check outright. 300 (`חשבון עסקה` — transaction account) was confirmed via the cached Green Invoice API document-type list as a genuine billable document, distinct from receipts (400/405), quotes (10), orders (100), delivery/return notes (200/210), and purchase orders (500), none of which represent money owed and would double-count or misclassify totals if included. 330 (credit invoice) continues to be special-cased for netting, checked before the allowlist membership test — its own `continue` runs first, so it's never affected by the allowlist's contents.

An explicit set was chosen over a `300-399` range (initially proposed, then withdrawn) once it was noted that 330 falls inside that range and needs its distinct credit-invoice/netting treatment kept separate rather than folded into "billable claim" semantics.

```python
_TAX_INVOICE_DOCUMENT_TYPE = 305
_TRANSACTION_ACCOUNT_DOCUMENT_TYPE = 300  # "חשבון עסקה" — confirmed live via GET /documents/types
_INVOICE_RECEIPT_COMBO_DOCUMENT_TYPE = 320
_PRIMARY_INVOICE_DOCUMENT_TYPES = {
    _TRANSACTION_ACCOUNT_DOCUMENT_TYPE,
    _TAX_INVOICE_DOCUMENT_TYPE,
    _INVOICE_RECEIPT_COMBO_DOCUMENT_TYPE,
}
_CREDIT_INVOICE_DOCUMENT_TYPE = 330  # "חשבונית זיכוי" — confirmed live via GET /documents/types
```

## Test (written, confirmed failing pre-fix, passing post-fix)

`apps/morning-mcp-app/tests/unit/test_get_financial_summary.py`:
- `test_unpaid_invoice_with_non_allowlisted_type_is_still_counted` — a fake `MorningClient` returns one type-305 paid invoice and one type-300 unpaid invoice; asserts both appear in the totals. Confirmed failing against the unfixed code (only 1 of 2 invoices counted, `לא שולם: ₪0.00`), passing after the fix.
- `test_credit_invoice_is_still_excluded_from_total_invoiced` — confirms the credit-note netting behavior is unaffected by the allowlist change. Passed against unfixed and fixed code alike (this part of the logic was never broken).
- `test_receipt_type_is_excluded_from_totals` (added during the second approval round) — a type-400 receipt alongside a type-305 invoice must not be counted or added to totals. Passes against both unfixed and fixed code today; its purpose is to catch a *future* regression if the allowlist is ever widened too far (e.g. back to "delete the check entirely," which was this bug's original, reverted draft fix).

Full run: `apps/morning-mcp-app/tests/unit/` — 71 passed, 0 failed.

## Acceptance Criteria
- [x] Bug reproduced live against real production data (see Evidence above)
- [x] Root cause confirmed (this document)
- [x] Failing test written and confirmed failing before any fix (BDD, per METHODOLOGY §VII)
- [x] Fix re-applied with explicit approval (explicit `{300, 305, 320}` set, after root cause + test proposal were separately re-approved)
- [x] Full regression check against the rest of the Morning tools unit test suite (71/71 passed)
- [ ] Deployed (rebuild + restart) to whichever environment(s) are running, per the `/haleluya` Deploy step
- [ ] Re-verified live in prod against real production data (deferred — user opted to move on without further live verification for this round)

## References
- `specs/bugfixes/bugfix-013-client-name-garbling-and-unrequested-date-narrowing.md` and `bugfix-014-list-invoices-only-returns-one-of-many.md` — same live testing session
- `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`
- `apps/morning-mcp-app/tests/unit/test_get_financial_summary.py`
- `.github/METHODOLOGY.md` §VII (Bug-Driven Development)
