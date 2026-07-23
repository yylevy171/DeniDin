# Feature Spec: Always Require Explicit Approval Before Creating Any Document

**Feature ID**: 022-explicit-approval-for-document-creation
**Priority**: P1
**Status**: Done - merged PR #129, 2026-07-23 (8 expensive E2E tests passing against real OpenAI + Morning sandbox)
**Created**: July 22, 2026

---

## Problem Statement

Per Feature 018's current runtime constitution, state-changing invoicing actions (including `create_invoice`) proceed immediately in a single turn with no confirmation wait — a deliberate 2026-07-15 decision made to keep E2E tests from needing multi-turn retries (see `test_denidin_morning_mcp_e2e.py`'s module docstring).

As the scope of document creation grows (020, 021 above — multiple payment-marking methods, multiple document types, including a non-tax "חשבון עסקה" and various reference/linked documents), the risk of an incorrect, unwanted, or wrong-type document being created for real money in a real customer's Morning account grows with it. This feature proposes requiring **explicit human approval before any financial-document-creating action actually executes**.

## Clarifications

### Session 2026-07-23

- Q: Does this reverse the 2026-07-15 "no confirmation wait" decision entirely, or only for creation? → A: Only for document creation, including creating a credit/cancellation document (a credit doc is itself a new document being created). There is no "status" concept independent of documents — an invoice's status (paid/unpaid/cancelled) is Morning's own internal calculation reflecting which linked documents exist against it, not a value the bot sets directly. Concretely: `create_invoice` requires approval, and so does `update_invoice_status` as a whole — its `paid` branch creates a Receipt document and its `cancelled` branch creates a Credit Invoice document; both are document creation and both require approval. (`update_invoice_status`'s `unpaid` branch is a pure idempotent no-op with no real reversal mechanism in Morning — it creates nothing — but since OpenAI's approval mechanism can only gate by tool name, not by argument value, the whole `update_invoice_status` tool is gated together; this is an accepted, intentional trade-off, not a gap.)
- Q: What does "approval" look like in a WhatsApp conversation? → A: A free-form yes/no natural-language reply (the AI interprets affirmatives like "yes"/"כן"/"אישור"/"בסדר"/"go ahead" as approval, anything else as decline). No explicit timeout — the pending action stays open until the user responds.
- Q: How does this interact with the E2E test suite's single-turn-only design? → A: The E2E tests are updated to be multi-turn for document-creating requests: after the first turn triggers a pending creation, the test sends a second turn with a Hebrew affirmative reply (e.g. "כן", "אישור", "בסדר") to approve it. The module docstring's "tests do not retry across turns" claim is updated to reflect this.
- Q: Does this apply to `add_client` too? → A: No. The approval gate applies only to actions that create a Morning document (invoices, receipts, credit/cancellation documents, etc.) — `add_client` creates a non-financial record and keeps the current no-wait behavior.

## Relationship to bugfix-014

Not directly a finding from bugfix-014's investigation, but raised in the same session while discussing the broader document-creation surface area (020, 021) that bugfix-014's Flow 4 investigation exposed — grouped together for planning purposes.

## References

- `runtime_constitution.md`'s invoicing section (current "no confirmation wait" rule)
- `apps/denidin-app/tests/expensive/test_denidin_morning_mcp_e2e.py` (module docstring, "tests do not retry across turns")
- `specs/backlog/020-flexible-invoice-payment-methods/spec.md`, `specs/backlog/021-flexible-document-creation/spec.md`
