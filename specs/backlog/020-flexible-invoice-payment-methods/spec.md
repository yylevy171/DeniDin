# Feature Spec: Flexible Invoice Payment-Marking Methods

**Feature ID**: 020-flexible-invoice-payment-methods
**Priority**: P1
**Status**: Clarified
**Created**: July 22, 2026

---

## Problem Statement

`update_invoice_status(status="paid")` (`apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`, `_mark_invoice_paid`/`_build_payment_receipt_payload`) currently has exactly one way to mark an invoice paid: it unconditionally builds a full-amount type-400 receipt payload, regardless of the original document's own type.

This was found to be incomplete/incorrect while investigating `bugfix-014-list-invoices-only-returns-one-of-many.md`'s "Flow 4" (type-300 "חשבון עסקה" documents, observed by the human on the customer's real Morning site): a type-300 document should be closed by a type-320 combo document when paid, not a type-400 receipt — the current code would create the wrong document type if ever used on one.

## Clarifications

### Session 2026-07-23

- Q: Should this feature include partial/installment payment support, or scope to just fixing the closing-document-type bug (300→320 vs 305→400)? → A: Doc-type fix only. Partial/installment payments are deferred to a separate future spec.
- Q: Which original document types should update_invoice_status("paid") support auto-detecting a closing-doc type for? → A: Only 300 and 305 — the only two types this app can currently create and the only two confirmed live in bugfix-014. Any other original type raises a clear `ValueError` rather than guessing an unverified mapping.
- Q: For an already-closed/paid type-300 document, should the idempotent no-op check use the same status codes (1, 2) as type-305 today? → A: Yes, unchanged — reuse the existing `_CLOSED_STATUS_CODES = {1, 2}` check as-is; bugfix-014 confirmed Morning's status semantics are document-type-agnostic.

## Functional Requirements

- `_mark_invoice_paid` must branch on the original document's `type` field:
  - `type == 300` ("חשבון עסקה"): issue a linked type-320 combo document (תשלום/קבלה) instead of today's unconditional type-400 receipt.
  - `type == 305` ("חשבונית מס"): keep today's existing type-400 receipt behavior, unchanged.
  - Any other `type`: raise `ValueError` with a message naming the unsupported type — do not guess a mapping.
- The idempotent no-op check (`original.get("status") in _CLOSED_STATUS_CODES`) applies unchanged to both branches, before building any payload.
- Partial/installment payments are explicitly out of scope for this feature (see Problem Statement); nothing in this change should require or preclude adding that later.

## Relationship to bugfix-014

`bugfix-014` documents the read/display-side Morning document model (types, `linkedDocuments`, the four flows) that this feature depends on understanding correctly. This feature is scoped separately because it is a write-path (mutating) concern — it changes what documents get created in Morning — versus bugfix-014's read/display-only fix.

## References

- `specs/bugfixes/bugfix-014-list-invoices-only-returns-one-of-many.md` (Flow 4, and the related-latent-bug note under Investigation Findings)
- `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py` (`_mark_invoice_paid`, `_build_payment_receipt_payload`, `update_invoice_status`)
