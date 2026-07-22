# Feature Spec: Flexible Morning Document Creation

**Feature ID**: 021-flexible-document-creation
**Priority**: P2
**Status**: Draft - Needs Clarification
**Created**: July 22, 2026

---

## Problem Statement

`create_invoice` (`apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`, `_build_create_invoice_payload`) always hardcodes `type=305` ("חשבונית מס", a tax invoice). There is no way for a godfather/admin to ask DeniDin to create any other Morning document type — a quote ("הצעת מחיר", type 10), an order (type 100), a delivery note (type 200), a non-tax transaction account ("חשבון עסקה", type 300 — see bugfix-014's Flow 4), a combo invoice+receipt for immediate payment (type 320, bugfix-014's Flow 1), etc.

**Desired direction (not yet clarified)**: let the user ask for the right document type in natural language ("תפיק לי הצעת מחיר ל...", "תעשה חשבון עסקה במקום חשבונית מס"), with DeniDin resolving which of Morning's real document types that maps to, rather than the tool being permanently locked to one type.

**Not yet clarified — needs its own spec session**:
- Full scope: which of Morning's ~16 document types (per live `GET /documents/types`) are actually relevant to this app's real usage, vs. out of scope?
- Does this replace `create_invoice` with a more general `create_document(type, ...)` tool, or add new type-specific tools?
- What validation/required-fields differences exist per document type (e.g. a quote likely doesn't need a `due_date`; a non-tax `חשבון עסקה` needs no VAT handling)?

## Relationship to bugfix-014

Emerged directly from bugfix-014's Flow 4 investigation (type-300 documents observed in real customer data that this app cannot itself create). Scoped as a separate feature because it's new capability, not a fix to existing (wrong) behavior.

## References

- `specs/bugfixes/bugfix-014-list-invoices-only-returns-one-of-many.md` (Flow 4)
- `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py` (`create_invoice`, `_build_create_invoice_payload`)
- Live `GET /documents/types` (see bugfix-014 spec for the full confirmed enum)
