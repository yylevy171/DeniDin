# Implementation Plan: Flexible Invoice Payment-Marking Methods

**Feature**: 020-flexible-invoice-payment-methods
**Spec**: `spec.md` (Status: Clarified)

## Summary

`_mark_invoice_paid` (`apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`)
branches on the original document's `type` to build the correct closing
document: type 305 keeps today's type-400 receipt; type 300 gets a new
type-320 combo-document builder; any other type raises `ValueError`. The
idempotency check (`status in _CLOSED_STATUS_CODES`) stays unchanged and
runs before the branch, for both types.

## Code changes

`apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`:
- New constant `_COMBO_DOCUMENT_TYPE = 320`, alongside the existing
  `_TAX_INVOICE_DOCUMENT_TYPE`/`_CREDIT_INVOICE_DOCUMENT_TYPE`.
- New `_build_combo_closing_payload(original: dict) -> dict`, modeled on
  `_build_cancellation_payload` (income line items, `vatType`, `client`,
  `payment` fields) rather than the bare `_build_payment_receipt_payload`,
  since a 320 document is self-contained invoice-shaped, not a bare
  receipt. `type=320`, description
  `f"תשלום עבור חשבון עסקה מספר {original_number or original_id}"`.
  Field list is a first draft, to be corrected against live sandbox
  behavior if the integration test reveals a mismatch.
- `_mark_invoice_paid`: after the existing idempotency check, branch on
  `original.get("type")`: `300` → `_build_combo_closing_payload`, `305` →
  existing `_build_payment_receipt_payload` (unchanged), else → raise
  `ValueError(f"Cannot mark invoice paid: unsupported document type {type_}")`.

No changes to `update_invoice_status`, `_mark_invoice_unpaid`, `models.py`,
or `formatters.py`.

## Test plan

- **Unit** — new `apps/morning-mcp-app/tests/unit/test_mark_invoice_paid.py`:
  fake `MorningClient` + fake `original` dicts for types 300/305/unsupported;
  assert correct payload type chosen, `ValueError` on unsupported type,
  idempotency no-op unaffected by the branch.
- **Integration** — extend
  `apps/morning-mcp-app/tests/integration/test_morning_sandbox_invoice_status_tools.py`:
  seed a real type-300 document directly via `client.create_invoice(...)`
  (the app's own `create_invoice` tool hardcodes type 305, so this bypasses
  it purely for test seeding), mark it paid, assert a linked type-320
  document was actually created (via `get_invoice_details`'s
  `linkedDocuments`). This is what confirms/corrects the first-draft 320
  payload shape.
- **Expensive E2E** — extend
  `apps/denidin-app/tests/expensive/test_denidin_morning_mcp_e2e.py`:
  multi-turn Hebrew WhatsApp conversations covering happy path (300→320,
  305→400, each direct-API-verified via `MorningClient`, not just the
  bot's reply text), negative (unsupported original type → friendly
  refusal, no document created), and edge cases (idempotent re-mark-paid,
  indirect natural-language invoice reference across turns). Each run
  needs its own fresh explicit approval, one at a time, per this project's
  expensive-test rules.

Tests are written and shown for approval before implementation lands
(BDD gate, METHODOLOGY §VII).

## Out of scope

Partial/installment payments (deferred to a future spec, per
clarification). Document types other than 300/305 as the *original*
document (raise instead of guessing a mapping).
