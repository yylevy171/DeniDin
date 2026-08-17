# Feature Specification: Receipts Without Invoice (+ Transaction Account Cancellation)

**Feature Branch**: `feature/056-receipts-without-invoice`
**Created**: 2026-08-17
**Status**: Placeholder — not yet clarified/specced. Captured from a 2026-08-17 request;
run `speckit.specify` + `speckit.clarify` before starting implementation.

## Input

User description: two related Morning (Green Invoice) accounting-rule logic changes, captured
together as one feature ("open a feature 56 - receipts without invoice ... create a new feature
56 to encompass the 2 new logic changes required for accounting rules in morning"):

### 1. Receipts not attached to any prior invoice

Today, `create_receipt` (`apps/morning-mcp-app/src/denidin_mcp_morning/tools.py`) requires an
`original_internal_morning_id` and rejects any original whose type isn't 305 (tax invoice) — there
is currently no way to create a standalone receipt with no prior invoice at all. The system needs
to allow that exception. Two real-world reasons given, sourced from a shared Gemini conversation
(https://gemini.google.com/share/71cf5b3afa2e — not machine-readable by this session, content
relayed by the user):

- **קבלת פיקדונות או החזרי הלוואה** (receiving deposits or loan repayments) — the primary reason.
  When a payment is received that is not business income — e.g. a monetary deposit that will
  later be returned to the client, a guarantee payment, or a loan repayment — the nature of the
  activity is a cash movement, not income generation. It must be documented with a receipt, but
  carries no tax event requiring an invoice.
- **פער זמנים (מקדמות)** (timing gap — advances) — can also happen. When a business owner
  (licensed dealer or company) receives an advance payment before the transaction is completed or
  goods are delivered, the law requires a receipt to be issued immediately for the money received;
  the tax invoice is issued (or completed) later, on delivery/completion, per that business's VAT
  liability timing.

### 2. Transaction account (חשבון עיסקה) cancellation requires no document

Cancelling a transaction account (Morning document type 300) must NOT create any document (unlike
tax-invoice cancellation, where `create_credit_note` issues a linked type-330 credit invoice —
Israeli law forbids voiding an issued tax invoice outright, see
`_build_cancellation_payload`'s docstring). For a transaction account, cancellation only
(optionally) marks it as "done"/closed internally in Morning — no credit note, no combo document,
no other linked document. This is distinct from *fulfilling* a transaction account
(`create_combo_document_as_reference`, which deliberately does create a type-320 combo document) —
cancellation is the unfulfilled/abandoned case.

## Notes captured so far

- Scope not yet defined. Open questions for `speckit.specify`/`speckit.clarify`:
  - **Standalone receipts**: What does "not attached to any prior invoice" look like as an MCP
    tool contract? A new tool, or a relaxed `create_receipt` (`original_internal_morning_id`
    becomes optional, with a client/description/amount/payment-date supplied directly instead)?
    Does it need a `client_id` still (REQ-INV-013's existing "must be linked to a real client"
    rule), and if the payment isn't tied to any client relationship at all (e.g. a pure guarantee
    deposit), what satisfies that requirement?
  - **Distinguishing the two reasons**: Does the system need to record *which* of the two
    justifications applies (deposit/loan vs. advance-payment timing gap), e.g. as a receipt
    description/category, or is it enough that a standalone receipt can be created at all,
    with the model choosing free-text wording per the runtime constitution?
  - **Advance → later invoice linkage**: For the timing-gap case, when the real tax invoice is
    eventually issued for the completed transaction, should it reference the earlier standalone
    receipt (a `linkedDocumentIds`-style link), or are the two treated as fully independent
    documents in Morning?
  - **Transaction account "mark as done"**: Morning's own status vocabulary already has a
    "manually closed" status (code 2, no document required — see `models._MORNING_STATUS_CODES`)
    distinct from "closed via payment" (code 1). Does "mark as done" map onto that existing
    status update, and does `MorningClient`/`MorningAuth` already expose a status-only update
    call, or does this require a new client method? (feature 023 removed the old
    `update_invoice_status` tool entirely in favor of document-creating tools
    (`create_receipt`/`create_credit_note`) — this would reintroduce a document-less status
    mutation, so needs its own audit-logging treatment per `audit.py`'s existing
    mutation/refusal logging pattern.)
  - **RBAC**: Same godfather/admin-only gating as the rest of Morning MCP tools, or narrower?
  - Cross-reference `specs/done/bugfixes/` and `specs/025-morning-sourced-ledger-events` (backlog)
    for any existing ledger-event interplay — a standalone deposit/loan receipt may also need to be
    recognized as a ledger event (`managers/ledger_event_manager.py`, Feature 033) in
    `apps/denidin-app`, separately from the Morning-side document itself.
