# User Stories: Receipts Without Invoice (+ Transaction Account Cancellation)

**Feature**: 056-receipts-without-invoice
**Format**: Given-When-Then (Gherkin/BDD), per METHODOLOGY.md §I — MANDATORY, blocks spec
approval until present.
**Status**: CLARIFIED (2026-08-18) — three open questions resolved via direct user decision
(see spec.md's Clarifications section). Ready for `plan.md`.

---

## Background (why this feature exists)

Two related Morning (Green Invoice) accounting-rule gaps, captured together as one feature per
explicit user decision (2026-08-17): (1) there is no way to record a receipt for money that
isn't tied to any prior invoice — a deposit, a loan repayment, or an advance payment ahead of
the real transaction — and (2) there is no way to cancel/abandon an open transaction account
(חשבון עיסקה) without incorrectly creating a real financial document for money that never moved.

## User Story 1 — Recording a standalone receipt for a deposit, loan repayment, or advance
payment (Priority: P1)

A godfather/admin tells DeniDin, in natural Hebrew, that they received money that is not
business income yet needs to be documented — e.g. a refundable deposit, a loan repayment, or an
advance payment ahead of a transaction that hasn't completed. DeniDin resolves the real client
(same name-resolution flow every other create tool already uses), confirms the amount and a
description with the user if not already clear, asks for approval, and — once approved — issues
a standalone receipt with no invoice behind it at all. No tax invoice is created for this
movement.

**Why this priority**: This is the primary, more common of the two reasons given for this
feature (deposits/loan repayments), and the one with the clearest real-world trigger.

**Independent Test**: A `create_receipt` call omitting `original_internal_morning_id` but
supplying `client_name`/`name_resolved=True`/`amount`/`description`/`payment_date` creates a
real type-400 receipt in the Morning sandbox with no `linkedDocumentIds` reference and no
invoice created alongside it — independently verifiable via `list_invoices`/`get_invoice_details`
against the sandbox, with no dependency on User Story 2.

**Acceptance Scenarios**:

1. **Given** a real, existing client and no prior invoice, **When** a godfather asks DeniDin to
   record a refundable deposit received from that client, **Then** DeniDin asks for approval,
   and on "כן" creates a standalone receipt (no invoice) referencing that real client, with a
   Hebrew confirmation naming the client and amount.
2. **Given** the same setup, **When** the godfather instead describes an advance payment
   received ahead of a not-yet-completed transaction, **Then** the same standalone-receipt flow
   applies — a receipt is issued immediately, with no invoice created yet.
3. **Given** a standalone receipt has already been issued for an advance payment, **When** the
   godfather later asks DeniDin to create the real tax invoice for that now-completed
   transaction, **Then** a normal `create_invoice` call succeeds and is NOT required to
   reference the earlier receipt in any way (Clarification Q3 — independent documents).
4. **Given** the client name given by the godfather does not resolve to exactly one real client,
   **When** the standalone-receipt call is attempted, **Then** it behaves exactly like every
   other create tool's non-exact-match case (refuses / asks for disambiguation via
   `resolve_client_name`) — no receipt is ever created for an unresolved client.
5. **Given** `original_internal_morning_id` IS supplied, **When** `create_receipt` is called,
   **Then** every existing behavior (type-305-only validation, idempotent no-op on an
   already-closed original, REQ-INV-013 refusal for an unlinked original) is unchanged — this
   feature adds a new path, it does not alter the existing one.

## User Story 2 — Cancelling a transaction account creates no document (Priority: P2)

A godfather/admin has an open transaction account (חשבון עיסקה) for a deal that fell through —
no money changed hands, and nothing should be recorded as income. They ask DeniDin to cancel it.
DeniDin asks for approval, and — once approved — marks the transaction account as
cancelled/abandoned internally in Morning, without creating any document at all (no credit note,
no combo document, no receipt).

**Why this priority**: A real but less frequent need than User Story 1 (fulfillment via
`create_combo_document_as_reference` already exists and handles the common case); cancellation
is the unfulfilled/abandoned case, needed to prevent an incorrect document being forced into
existence for a deal that never closed.

**Independent Test**: Against a real type-300 transaction account created in the Morning
sandbox, the new cancellation capability changes its state to reflect cancellation/abandonment
with zero new documents created — independently verifiable via `list_invoices` before/after
(document count unchanged) and `get_invoice_details` on the transaction account itself (status
changed) — with no dependency on User Story 1.

**Acceptance Scenarios**:

1. **Given** an open, unfulfilled transaction account, **When** a godfather asks DeniDin to
   cancel it (the deal fell through), **Then** DeniDin asks for approval, and on "כן" the
   transaction account is marked cancelled with NO new Morning document created of any kind.
2. **Given** the same transaction account has already been cancelled, **When** the godfather
   repeats the cancellation request, **Then** it is idempotent — no error, no duplicate
   mutation, consistent with this app's existing idempotency convention on similar no-op paths.
3. **Given** the same transaction account has already been fulfilled (closed as paid via
   `create_combo_document_as_reference`), **When** the godfather asks to cancel it instead,
   **Then** the call is idempotent / a clear no-op — it must never un-do or contradict a real
   payment document that already exists.
4. **Given** a document that is NOT a type-300 transaction account (e.g. a tax invoice),
   **When** a godfather asks DeniDin to cancel it via this capability, **Then** the request is
   rejected with a clear error — tax-invoice cancellation continues exclusively through
   `create_credit_note`'s existing, document-producing flow (REQ-INV-022), never through this
   document-less path.

---

## Explicitly Out of Scope

- Structured reason-code tracking for standalone receipts (Clarification Q2) — free text only.
- Auto-linking a later invoice back to an earlier advance-payment receipt (Clarification Q3).
- Any change to tax-invoice cancellation (`create_credit_note`) behavior.
- Fully client-less standalone receipts — a real, resolved client is still required.
- Ledger-event auto-recognition of a standalone receipt as a deposit/loan event
  (`apps/denidin-app`'s Feature 033) — a plausible follow-up, not part of this feature.
