# Bugfix Spec: Credit notes are silently dropped from invoice listings and financial answers

## Bug ID
bugfix-033-credit-notes-silently-dropped-from-financial-answers

## Title
`Invoice.amount` is constrained to `>= 0`, so any Morning document with a negative amount — a
credit note (`חשבונית זיכוי`, type 330) — fails validation, is skipped with only a `WARNING`,
and is excluded from both the returned list and the reported match count.

## Priority
**P2** — produces a wrong number in answer to a direct financial question, but only when
credit notes fall in the queried range.

## Status
**Open — backlogged.** No fix designed. Per Bug-Driven Development (METHODOLOGY.md §VII), next
step is human approval of the root cause before test-gap analysis.

## Date Opened
2026-08-09

## Reported By
yaronlev171, from the 7–9 Aug 2026 production review
([`docs/production-analysis/2026-08-09-aug7-9-review.md`](../../docs/production-analysis/2026-08-09-aug7-9-review.md), P2-5 — originally ranked P1, moved to P2 by user decision 2026-08-09).

> **Shared session context** — how this review was run, the read-only access paths, the full
> map of bugfix-028…037, the triage decisions (including what was closed as *not* a bug), and
> the open verification items:
> [`bugfix-028` § Session Context](../in-progress/bugfixes/bugfix-028-invoicing-and-approval-gate-p0-cluster.md#session-context-2026-08-09-production-review) (moved to `specs/in-progress/bugfixes/` 2026-08-10).
> All ten bugs in that set are **fix-forward only** — existing production documents are being
> left as they are by explicit user decision.

## Affected Area
- `apps/morning-mcp-app/src/denidin_mcp_morning/models.py:147` — `Invoice.amount: float = Field(ge=0)`
  (also lines 95, 119 — same constraint on sibling models, check each)
- `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py:613-616` — the skip-and-continue in
  `list_invoices`
- Possibly `get_financial_summary` — **needs verification**: it may compute server-side at
  Morning rather than from these models, in which case only `list_invoices` is affected.

## Description
A credit note legitimately carries a negative amount. The model forbids it:

```python
amount: float = Field(ge=0)      # models.py:147
```

`list_invoices` catches the resulting `ValidationError` and continues:

```python
try:
    invoices.append(Invoice.model_validate(item))
except ValidationError as exc:
    logger.warning("Skipping unparseable invoice in list_invoices result: %s", exc)
```

It then reports `total_matched=len(invoices)` — **a count that excludes everything it just
dropped**. The user is given a confident total that is silently short.

Real drops in prod (`morning-mcp.log`, 2026-08-04, 8 occurrences):
```
Skipping unparseable invoice in list_invoices result: 1 validation error for Invoice
amount
  Input should be greater than or equal to 0 [input_value=-532]
  Input should be greater than or equal to 0 [input_value=-1500]
  Input should be greater than or equal to 0 [input_value=-7000]
```

Note the log message itself is misleading — these documents are not "unparseable"; they are
valid documents the model refuses.

`_CREDIT_INVOICE_DOCUMENT_TYPE = 330` is already a known, supported type
(`tools.py:46`), and `create_credit_note` exists as a tool — so the system creates documents
it then cannot read back.

## Expected
Negative amounts must be valid on credit-note-type documents. Listings and any count/total
derived from them must include credit notes (as negatives). If a document genuinely cannot be
parsed, that should surface to the user, not be swallowed into a silently smaller number.

## Verification note
Confirm whether `get_financial_summary`'s figures come through these same models. The Aug 9
answer to *"כמה כסף הכנס לחודש אוגוסט"* (`סה"כ הופק: ₪126,658.80 · 23 חשבוניות`) may or may not
be affected — do not assume either way.

## Related Work
- Feature 021 — introduced `create_credit_note` / type 330.
