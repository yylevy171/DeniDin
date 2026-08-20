# Implementation Plan: Reference-Linked Combo Document Creation

**Feature**: 023-reference-linked-document-creation
**Spec**: `spec.md` (Status: Clarified - Ready for Planning)

## Summary

Add a new standalone MCP tool, `close_transaction_account`, that creates a
type-320 combo document ("חשבונית מס/קבלה") explicitly linked to (via
`linkedDocumentIds`) an existing type-300 document ("חשבון עסקה"), with an
optional partial-amount/description override. This gives combo-document
creation the same standalone-with-reference capability 021 already gave
`create_credit_note`/`create_receipt`, without touching `update_invoice_status`'s
existing automatic type-300→320 branching (020), which remains the only path
for "mark as paid" phrasing and stays byte-for-byte unchanged.

No feature flag: per 021's own precedent, this is a purely additive new tool
— no existing tool's behavior changes when it isn't called (CONSTITUTION §I's
flag requirement is for *changed* code paths, not new independent ones).

## Code changes

`apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`:
- `_build_combo_closing_payload(original, amount=None, description=None)` —
  add the two optional parameters. When both are `None` (the existing
  `_mark_invoice_paid` call site's usage, unchanged), output is byte-for-byte
  identical to today: mirrors the original's own income items/total, same
  hardcoded description string. When `amount` is given (partial close), the
  payload uses a single overridden income line item (`price=amount`,
  `description=description or <default>`) instead of mirroring the
  original's items — same pattern `_build_cancellation_payload` already uses
  for partial credit notes.
- New `close_transaction_account(client, original_invoice_id, amount=None,
  description=None) -> str`: fetches the original via `client.get_invoice`,
  raises `ValueError` naming the type if `original.get("type") !=
  _TRANSACTION_ACCOUNT_DOCUMENT_TYPE` (mirrors `_mark_invoice_paid`'s
  unsupported-type message), else builds the payload via
  `_build_combo_closing_payload` and calls `client.create_invoice`. Returns a
  Hebrew confirmation naming both the new combo document's number and the
  original transaction account's number. Modeled directly on
  `create_credit_note`/`create_receipt`'s existing structure.

`apps/morning-mcp-app/src/denidin_mcp_morning/server.py`:
- New `@mcp.tool() def close_transaction_account(original_invoice_id, amount=None,
  description=None) -> str`, registered alongside the other document-creation
  tools, wrapped in `_call_with_error_boundary` like every other tool.

No changes to `_mark_invoice_paid`, `update_invoice_status`, `create_combo_document`,
`create_credit_note`, `create_receipt`, `models.py`, or `formatters.py`.

## Constitution updates

`apps/denidin-app/config/runtime_constitution.md` ("Invoice Management
Context" section):
- Add `close_transaction_account` to the tool list and to the "which
  document-creation tool to call" guidance (use when the user directly asks
  to close/settle an existing חשבון עסקה with a combo document — distinct
  from `update_invoice_status(status="paid")`, which does the same thing as
  a side effect of "mark as paid" phrasing on a type-300 original).
- Add it alongside `create_credit_note`/`create_receipt` in the
  `original_invoice_id`-resolution note (same resolution rules — never ask
  the user for it, resolve via `list_invoices`/session memory).
- Add it to the "every document-creating tool requires explicit approval
  first" list (Feature 022), with a pending-approval phrasing example
  matching the existing ones.

## Test plan

- **Unit** — extend `apps/morning-mcp-app/tests/unit/test_tools_document_creation.py`
  (same `_FakeMorningClient` fixture already used there):
  - `_build_combo_closing_payload` defaults mirror the original (unchanged
    behavior) vs. amount/description override produces a single overridden
    income line.
  - `close_transaction_account` happy path (type-300 original, full and
    partial amount).
  - `close_transaction_account` rejects a non-300 original with `ValueError`
    naming the type (US3).
  - `_mark_invoice_paid`/`update_invoice_status` still produce the exact
    same payload as before the signature change (regression guard for the
    "020 unchanged" requirement).
- **Integration** — extend
  `apps/morning-mcp-app/tests/integration/test_morning_sandbox_document_creation_tools.py`:
  seed a real type-300 document (`create_transaction_account`), call
  `close_transaction_account` against it, assert via `get_invoice_details`
  that a linked type-320 document was actually created; one more case for
  the partial-amount override; one more for the non-300-original rejection
  (e.g. against a seeded type-305 invoice).
- **Expensive E2E** — extend
  `apps/denidin-app/tests/expensive/test_denidin_morning_document_creation_e2e.py`:
  a Hebrew WhatsApp conversation asking to close an existing חשבון עסקה with
  a combo document (full amount), one for a partial amount, and one negative
  case (asking to "close" a regular tax invoice this way → friendly refusal,
  no document created). Each run needs its own fresh explicit approval, one
  at a time, per this project's expensive-test rules.

Tests are written and shown for approval before implementation lands (BDD-style
TDD gate, METHODOLOGY §VI/§VII, even though this is new-feature work rather than
a bug fix).

## Out of scope

Non-payment reference/linking use cases; changes to any of the other four
document-creation tools or to `update_invoice_status`'s existing branching; a
general N-to-N document-linking mechanism (see spec.md's "Explicitly out of
scope").
