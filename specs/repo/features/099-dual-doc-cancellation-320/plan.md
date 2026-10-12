# Implementation Plan: Dual-Document Cancellation of a 320 (Feature 099)

**Spec**: `spec.md` · **Scenarios**: `acceptance-scenarios.md` (approved) · **Design approved 2026-10-09**: extend `create_receipt` - **no new tool** (human decision); mechanism verified against the real Morning sandbox.

## Technical context
`apps/morning-mcp-app/src/denidin_mcp_morning/{tools.py,server.py,formatters.py}` and `apps/denidin-app/config/prompts/{flows,capabilities}`, `src/capabilities/toolsets.py` (fixed allowed-tools lists). Morning-side change -> container rebuild before any test of it.

## Constitution check
No mocking; real-sandbox integration tests; no flag; single `create_receipt` tool; approval-gate discipline (Backbone approvals are stateless prompt-level); audit logging for every Morning mutation (existing `log_mutation`/`log_refusal`).

## Design
1. `create_receipt` gains a branch: when `original_internal_morning_id` resolves to a document of type **320**, it creates a **cancelling receipt**: type 400, `linkedDocumentIds=[<320 id>]`, one payment line with `price = -(320 total)` using the **first** payment line's type/appType/bank-or-cheque details (via `_build_payment_line`), description `ביטול חשבונית מס קבלה <number>`, client = the 320's linked client; refuses (no document, `log_refusal`) if the 320's `linkedDocuments` already contains a 330 or a negative 400, or if it is not linked to a client. The caller cannot pass an amount for this branch (full cancellation only); read-back via `get_invoice` and a Hebrew confirmation. Other originals behave exactly as today (305 only; 300 -> use the reference tool).
2. Formatter: confirmation text states it is a cancelling receipt (negative amount, original number) - never says "paid".
3. Backbone: `flow_cancel_document_with_credit_note.md` - for a 320 target: refuse if already credited (from fresh `get_invoice_details`); approval #1 -> `create_credit_note` (330); then approval #2 (fresh data: client, amount, method, original number) -> `create_receipt(original=<320 id>)`; decline of #2 -> say the cash side is still not reversed; failure of #2 -> say what happened and offer retry (no dedicated test). 305 target: unchanged (330 only). `cap_invoicing_write.md` documents the new branch; `toolsets.py` allowed-tools unchanged (same tool name).
4. `get_invoice_details` already exposes linked documents (verify field) so the flow can detect "already cancelled".

## Out of scope
Partial credits, 300 cancellation, mixed-payment fidelity (first payment's method is the decided rule), a test for failure of the 400.

## Tests
Acceptance (approved): 99-1 (sanity), 99-2, 99-3, 99-4 `billed`. Unit: payload builder (negative price, link, description, method copy), refusal when already credited, wrong-type behaviour unchanged. Integration (real sandbox): 320 -> 330 -> cancelling receipt; refusal on second attempt; 305 unaffected.
