# Feature Spec: Flexible Invoice Payment-Marking Methods

**Feature ID**: 020-flexible-invoice-payment-methods
**Priority**: P2
**Status**: Draft - Needs Clarification
**Created**: July 22, 2026

---

## Problem Statement

`update_invoice_status(status="paid")` (`apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`, `_mark_invoice_paid`/`_build_payment_receipt_payload`) currently has exactly one way to mark an invoice paid: it unconditionally builds a full-amount type-400 receipt payload, regardless of the original document's own type.

This was found to be incomplete/incorrect while investigating `bugfix-014-list-invoices-only-returns-one-of-many.md`'s "Flow 4" (type-300 "חשבון עסקה" documents, observed by the human on the customer's real Morning site): a type-300 document should be closed by a type-320 combo document when paid, not a type-400 receipt — the current code would create the wrong document type if ever used on one. Separately, the tool has no partial-payment (installment) path at all — Morning's own data model supports multiple receipts against one invoice summing to less than the full amount, but nothing in this app can produce that today.

**Not yet clarified — needs its own spec session**:
- Should the tool support marking a *partial* amount paid (installment), and if so, how does the user express that in natural language?
- Should the tool auto-detect the correct closing-document type from the original's type (300→320, 305→400), or should this only be reachable for types the app itself can create?
- How should idempotency/re-marking-paid behave once a partial payment already exists?

## Relationship to bugfix-014

`bugfix-014` documents the read/display-side Morning document model (types, `linkedDocuments`, the four flows) that this feature depends on understanding correctly. This feature is scoped separately because it is a write-path (mutating) concern — it changes what documents get created in Morning — versus bugfix-014's read/display-only fix.

## References

- `specs/bugfixes/bugfix-014-list-invoices-only-returns-one-of-many.md` (Flow 4, and the related-latent-bug note under Investigation Findings)
- `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py` (`_mark_invoice_paid`, `_build_payment_receipt_payload`, `update_invoice_status`)
