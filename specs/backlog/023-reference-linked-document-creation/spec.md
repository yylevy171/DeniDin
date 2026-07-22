# Feature Spec: Create Documents as References to Existing Ones

**Feature ID**: 023-reference-linked-document-creation
**Priority**: P2
**Status**: Draft - Needs Clarification
**Created**: July 22, 2026

---

## Problem Statement

Every document-creating capability this app has today (`create_invoice`, and the receipt/credit-invoice creation inside `update_invoice_status`) builds a brand-new, freestanding document. Real Morning usage, per bugfix-014's investigation, frequently creates documents that are explicitly **linked to an existing one** — a receipt referencing the invoice it pays, a credit invoice referencing the invoice it cancels, and (per bugfix-014's Flow 4) a combo document referencing the "חשבון עסקה" it closes.

This is likely largely a mechanism that already exists implicitly inside 020 (flexible payment-marking) — `_build_payment_receipt_payload` already sets `linkedDocumentIds` when building a receipt — but this feature proposes making "create a new document AS A REFERENCE to an existing one" an explicit, general capability/pattern, not just an internal implementation detail of the paid-marking flow.

**Not yet clarified — needs its own spec session**:
- Is this actually a distinct feature, or should it be folded entirely into 020 (flexible payment-marking methods) once that's scoped, since every real example so far is a payment-related linkage?
- Are there non-payment cases where a user would want to create a document explicitly referencing another (e.g. "an updated quote based on the old one")?
- What does the user-facing request look like ("issue a receipt for invoice X", "link this to that")?

## Relationship to bugfix-014

Emerged directly from bugfix-014's Flow 2/3/4 investigation into Morning's `linkedDocuments` mechanism (the same structured, bidirectional field bugfix-014 is adding read-side support for via `get_invoice_details`).

## References

- `specs/bugfixes/bugfix-014-list-invoices-only-returns-one-of-many.md` (linkedDocuments investigation, Flows 2-4)
- `specs/backlog/020-flexible-invoice-payment-methods/spec.md` — likely significant overlap, resolve during clarification
- `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py` (`_build_payment_receipt_payload`'s existing `linkedDocumentIds` usage)
