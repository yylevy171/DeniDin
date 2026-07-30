# Feature Spec: Create Documents as References to Existing Ones

**Feature ID**: 023-reference-linked-document-creation
**Priority**: P2
**Status**: Done - Merged
**Created**: July 22, 2026
**Updated**: July 29, 2026

---

## Problem Statement

Every document-creating capability this app has today (`create_invoice`, and the receipt/credit-invoice creation inside `update_invoice_status`) builds a brand-new, freestanding document. Real Morning usage, per bugfix-014's investigation, frequently creates documents that are explicitly **linked to an existing one** — a receipt referencing the invoice it pays, a credit invoice referencing the invoice it cancels, and (per bugfix-014's Flow 4) a combo document referencing the "חשבון עסקה" it closes.

**Original scope was stale — re-scoped 2026-07-29**: by the time this spec was picked up, `020-flexible-invoice-payment-methods` and `021-flexible-document-creation` had both already shipped (PR #131, PR #137), and between them they already delivered most of what this spec originally proposed:
- `_build_payment_receipt_payload`, `_build_cancellation_payload`, and `_build_combo_closing_payload` (`apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`) all already set `linkedDocumentIds` referencing an original document.
- 021 added standalone, directly user-invocable `create_credit_note` and `create_receipt` tools that *require* an explicit reference document id as input (`original_invoice_id`), plus optional `amount`/`description` overrides for partial credit notes/receipts — this is exactly "create a document as an explicit reference to an existing one," already shipped and user-facing.

**One confirmed remaining gap, and this feature's narrowed scope**: `create_combo_document` (021, type 320) has no way to link to an existing document — it only ever builds a brand-new, independent immediate-sale document (`client_name`, `amount`, `description`, `vat_included`). The *only* way today to get a linked type-320 combo document (closing an existing type-300 "חשבון עסקה") is indirectly, via `update_invoice_status(status="paid")`'s automatic type-branching (`_build_combo_closing_payload`) — and that path always closes the *original's full amount*, mirroring its own line items; it has no standalone, directly-requestable equivalent and no partial-amount override, unlike `create_credit_note`/`create_receipt`.

This feature adds that missing parity: a standalone way to create a type-320 combo document that explicitly references/closes an existing type-300 document, with an optional partial amount/description override — bringing combo-document creation to the same standalone-with-reference capability level 021 already gave credit notes and receipts.

**Scope expanded again 2026-07-29 (same day, second session)**: implementing the above surfaced a real, confirmed bug — `_build_combo_closing_payload` (used by both the new standalone tool and `update_invoice_status`'s existing type-300 branch) copies the original document's own `vatType`, but a real type-300 document (created via `create_transaction_account`, 021) carries no VAT concept and Morning reports it back as `vatType: 0`; propagating that onto a type-320 closing document breaks Morning's own income/payment reconciliation (`400: קיים חוסר התאמה בין סכום התקבולים לסכום התשלומים`, confirmed live). Discussing the fix surfaced a larger architectural decision, made explicitly by the human this session: **remove `update_invoice_status` entirely**, folding its responsibilities into the model's own judgment plus the existing direct create/close tools.

**Rationale for removing `update_invoice_status`**: Morning has no real "status" field — status is purely Morning's own computed reflection of linked documents. `update_invoice_status` was a natural-language dispatch layer that inferred, in code, which document to create from status-change phrasing ("mark as paid" → receipt or combo depending on original type; "cancel" → credit note). The human's decision: this inference belongs to the model, not hardcoded status-word matching, because the model already has full deterministic access to the same information the code was inferring from (`get_invoice_details`, `list_invoices`) and can ask the user when genuinely uncertain (document type, VAT-inclusion) rather than the code guessing. Two status-word branches thus disappear entirely:
- **"mark as paid"** → the model resolves the target document's real type itself (via `get_invoice_details`) and calls `create_receipt` (type 305) or `close_transaction_account` (type 300) directly — no `update_invoice_status` indirection.
- **"cancel"** → the model calls `create_credit_note` directly (full amount, no override) — functionally identical to the old `_cancel_invoice`, just reached directly.
- **"mark as unpaid"/reversal** → there is no document-creation action for this (Morning has no reversal mechanism for a receipt-based payment) — the model must explain this is not supported, not attempt any tool call.

**A second, related bug this surfaced**: removing the code-level idempotency guard (`_mark_invoice_paid`'s "already closed → no-op" check) without a replacement would allow real duplicate financial documents. Verified live: Morning does **not** itself reject a duplicate receipt against an already-paid invoice — two full ₪200 receipts were both successfully created against the same seeded invoice with no rejection. The replacement is a deterministic model-side check, not a code-side guard: **before calling any document-creating tool that could duplicate an existing linked document, the model must first call `get_invoice_details` on the target and check whether the relevant linked document already exists**, reporting the existing state instead of creating a duplicate if so.

**Explicitly out of scope**:
- Non-payment reference use cases (e.g. "an updated quote based on the old one") — quote documents (type 10) are themselves out of scope per 021's own clarification, and no real business need for non-payment linking has surfaced.
- Any change to `create_invoice`, `create_transaction_account`, `create_credit_note`, or `create_receipt`'s own payload-building logic (their signatures/behavior are unchanged — only their *dispatch*, i.e. how the model decides to call them, changes with `update_invoice_status`'s removal).
- A general N-to-N document-linking mechanism.

## Clarifications

### Session 2026-07-29
- Q: 020 and 021 already shipped and cover most of what this spec originally proposed (linkedDocumentIds already used internally; create_credit_note/create_receipt already require an explicit reference doc id). How should 023 be scoped now? → A: Narrow to the one confirmed remaining gap — `create_combo_document` cannot link to an existing document. Build a standalone tool/capability for that specifically, rather than closing the spec as obsolete or expanding it to a general non-payment-linking pattern.
- Q: Implementing `close_transaction_account` surfaced a `vatType` bug shared with `update_invoice_status`'s existing type-300 branch (`_build_combo_closing_payload`) — fix narrowly, or use it as the trigger to reconsider `update_invoice_status` itself? → A: Remove `update_invoice_status` entirely, as part of this feature. Status is not a real Morning concept — only document creation is — and hardcoding status-word→document-type inference in code is "ambiguity and double meaning in the code," to be replaced by the model resolving intent deterministically via the existing read tools (`get_invoice_details`/`list_invoices`), asking the user when genuinely uncertain (VAT-inclusion, ambiguous type) rather than the code guessing.
- Q: How should VAT-inclusion be decided for `close_transaction_account`, given the original type-300 document carries no VAT field to infer from? → A: `vat_included: bool = True` parameter (matching `create_combo_document`'s existing convention), with the constitution instructing the model to ask the user ("האם כולל מע\"מ?") when it isn't clearly stated, rather than silently defaulting.
- Q: How is duplicate-document creation (e.g. double receipt) prevented without `update_invoice_status`'s code-level idempotency guard? → A: Verified live that Morning does not itself reject this. Replaced with a mandatory model-side check (constitution rule): fetch `get_invoice_details` on the target before any document-creating call that could duplicate an existing linked document, and skip the call (reporting existing state) if it already exists.

## Functional Requirements

- Add `close_transaction_account(original_invoice_id, amount=None, description=None, vat_included=True)`: a standalone MCP tool creating a type-320 combo document that explicitly references an existing type-300 ("חשבון עסקה") document via `linkedDocumentIds`, closing it as paid (in full by default, or partially via `amount`). Rejects (clear error) any original whose type is not 300.
- Remove `update_invoice_status` (MCP tool), and its now-unused internal helpers `_mark_invoice_paid`/`_mark_invoice_unpaid`/`_cancel_invoice`, from both `tools.py` and `server.py`.
- `runtime_constitution.md`'s invoice-management section is rewritten: no more status-word → document-type dispatch table. Instead: the model resolves the target document's real type itself before choosing which create/close tool to call (never guesses from conversation phrasing alone), asks the user when genuinely uncertain (VAT-inclusion, ambiguous document type/reference), treats "mark unpaid"/reversal requests as explicitly unsupported (no tool call), and checks `get_invoice_details` for an existing linked document before any call that could create a duplicate.
- No feature flag: this is a net-neutral tool-count change (removes 1 tool, adds 1 tool) with a corresponding constitution rewrite — not a gated, backward-compatible addition. Existing behavior for "mark as paid"/"cancel" phrasing changes (now dispatches to direct tools via model judgment instead of `update_invoice_status`), which is the explicit intent of this change, not something to hide behind a flag.

## Relationship to bugfix-014

Emerged directly from bugfix-014's Flow 2/3/4 investigation into Morning's `linkedDocuments` mechanism (the same structured, bidirectional field bugfix-014 added read-side support for via `get_invoice_details`).

## References

- `specs/bugfixes/bugfix-014-list-invoices-only-returns-one-of-many.md` (linkedDocuments investigation, Flows 2-4)
- `specs/done/020-flexible-invoice-payment-methods/spec.md` — shipped; its `update_invoice_status`/`_mark_invoice_paid` type-branching is the mechanism this feature removes and replaces with model-side dispatch to direct tools
- `specs/done/021-flexible-document-creation/spec.md` — shipped; `create_credit_note`/`create_receipt` are the direct precedent this feature's new `close_transaction_account` mirrors, and are now also the direct dispatch targets for "mark as paid"/"cancel" phrasing
- `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py` (`create_combo_document`, `_build_combo_document_payload`, `_build_combo_closing_payload`, `create_credit_note`, `create_receipt`, `update_invoice_status` (removed))
