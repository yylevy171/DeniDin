# Feature Spec: Always Require Explicit Approval Before Creating Any Document

**Feature ID**: 022-explicit-approval-for-document-creation
**Priority**: P1
**Status**: Draft - Needs Clarification
**Created**: July 22, 2026

---

## Problem Statement

Per Feature 018's current runtime constitution, state-changing invoicing actions (including `create_invoice`) proceed immediately in a single turn with no confirmation wait — a deliberate 2026-07-15 decision made to keep E2E tests from needing multi-turn retries (see `test_denidin_morning_mcp_e2e.py`'s module docstring).

As the scope of document creation grows (020, 021 above — multiple payment-marking methods, multiple document types, including a non-tax "חשבון עסקה" and various reference/linked documents), the risk of an incorrect, unwanted, or wrong-type document being created for real money in a real customer's Morning account grows with it. This feature proposes requiring **explicit human approval before ANY document-creating action actually executes** — not just for a subset of "risky" ones.

**Not yet clarified — needs its own spec session**:
- Does this reverse the 2026-07-15 "no confirmation wait" decision entirely, or only for creation (not for status changes on existing documents)?
- What does "approval" look like in a WhatsApp conversation (a yes/no reply, a specific keyword, a timeout/default)?
- How does this interact with the existing E2E test suite's single-turn-only design (`test_denidin_morning_mcp_e2e.py`'s explicit "tests do not retry across turns" decision) — will approval-gated tests need multi-turn scripting after all?
- Does this apply to `add_client` too (also creates a record, though not a financial document)?

## Relationship to bugfix-014

Not directly a finding from bugfix-014's investigation, but raised in the same session while discussing the broader document-creation surface area (020, 021) that bugfix-014's Flow 4 investigation exposed — grouped together for planning purposes.

## References

- `runtime_constitution.md`'s invoicing section (current "no confirmation wait" rule)
- `apps/denidin-app/tests/expensive/test_denidin_morning_mcp_e2e.py` (module docstring, "tests do not retry across turns")
- `specs/backlog/020-flexible-invoice-payment-methods/spec.md`, `specs/backlog/021-flexible-document-creation/spec.md`
