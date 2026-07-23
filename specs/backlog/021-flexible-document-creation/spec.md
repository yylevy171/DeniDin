# Feature Spec: Flexible Morning Document Creation

**Feature ID**: 021-flexible-document-creation
**Priority**: P1
**Status**: Ready for Implementation
**Created**: July 22, 2026

---

## Problem Statement

`create_invoice` (`apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`, `_build_create_invoice_payload`) always hardcodes `type=305` ("חשבונית מס", a tax invoice). There is no way for a godfather/admin to ask DeniDin to create any other Morning document type in scope — a non-tax transaction account ("חשבון עסקה", type 300 — see bugfix-014's Flow 4), a combo invoice+receipt for immediate payment (type 320, bugfix-014's Flow 1), or a standalone credit note (type 330) / receipt (type 400) not tied to an `update_invoice_status` call.

**Resolved direction**: add new type-specific MCP tools (`create_transaction_account`, `create_combo_document`, `create_credit_note`, `create_receipt`) alongside the existing `create_invoice`, so the user can ask for the right document type in natural language ("תפיק לי חשבון עסקה ל...", "תעשה חשבונית זיכוי לחשבונית מספר..."), with DeniDin's model choosing the matching tool. Morning's real model treats the document itself as the unit of state (no separate "mark paid" flag) — a document is created and that creation is itself what changes visible status — so the user can request any in-scope document type directly, not only indirectly via `update_invoice_status`.

## Clarifications

### Session 2026-07-23

- Q: Which Morning document types should be in scope for direct creation? → A: 300 (חשבון עסקה, transaction account), 305 (חשבונית מס, already works), 320 (חשבונית מס/קבלה, combo), 330 (חשבונית זיכוי, credit note), 400 (קבלה, receipt). Quote (10), order (100), delivery note (200), return document (210), donation receipt (405), purchase order (500), deposit receipt/withdrawal (600/610) are out of scope — no evidence of business need. (Full 13-code reference table sourced from an unofficial community API-notes repo, not Morning's own live docs — verify against `GET /documents/types` before relying on it further.)
- Q: Should this replace `create_invoice` with a general `create_document(type, ...)` tool, or add new type-specific tools? → A: New type-specific tools (`create_transaction_account`, `create_combo_document`, `create_credit_note`, `create_receipt`). `create_invoice` (type 305) stays untouched.
- Q: How should per-type field/validation differences be handled? → A: Type-aware payload builders — type 300 has no VAT line at all; types 330/400 require a reference document id (`linkedDocumentIds`) and support optional amount/description overrides (partial credit notes/receipts).
- Q: Does this need a `config.feature_flags` gate? → A: No — purely additive new tools; `create_invoice`'s existing behavior is unchanged, so there's no "old behavior" requiring a flag.
- Q: Should types 330 (credit note) and 400 (receipt) — which already exist internally as side effects of `update_invoice_status` — also get standalone, directly user-invocable creation tools? → A: Yes. Morning's documents ARE the state (no separate status flag); the user may ask indirectly ("mark this paid") or directly ("give me a receipt for X"), and both should be supported. `_build_cancellation_payload`/`_build_payment_receipt_payload` are refactored to accept optional amount/description overrides and are shared between the existing internal call sites (`_cancel_invoice`, `_mark_invoice_paid`) and the new standalone tools.
- Q: Should this feature also implement approval/confirmation before executing? → A: No — that's spec 022 (`specs/backlog/022-explicit-approval-for-document-creation`, still Draft), which will apply a confirmation gate across all document-creating tools, including the new ones from this feature, once clarified separately.

## Relationship to bugfix-014

Emerged directly from bugfix-014's Flow 4 investigation (type-300 documents observed in real customer data that this app cannot itself create). Scoped as a separate feature because it's new capability, not a fix to existing (wrong) behavior.

## References

- `specs/bugfixes/bugfix-014-list-invoices-only-returns-one-of-many.md` (Flow 4)
- `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py` (`create_invoice`, `_build_create_invoice_payload`)
- Live `GET /documents/types` (see bugfix-014 spec for the full confirmed enum)
