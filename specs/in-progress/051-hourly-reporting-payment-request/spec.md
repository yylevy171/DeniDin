# Feature Specification: Hourly Reporting & Payment Request Creation

**Feature Branch**: `feature/051-hourly-reporting-payment-request`
**Created**: 2026-08-13
**Status**: Placeholder — not yet clarified/specced. Captured from a 2026-08-13 backlog
conversation; run `speckit.specify` + `speckit.clarify` before starting implementation.

## Input

User description (clarified 2026-08-13): support hourly reporting documentation and creation of
a payment request. Flow confirmed: **user reports hours via chat** (e.g. "worked 3 hours
today") — DeniDin logs this, and a payment request (Morning invoice/receipt via the existing MCP
integration) can later be created covering the logged hours.

## Notes captured so far

- Likely builds on the existing ledger event machinery (Feature 033, `ledger_event_manager.py`)
  as a new recognized event type/source, rather than inventing separate storage — needs
  plan-stage confirmation.
- Open questions for `speckit.clarify`: what counts as a valid hour report (rate,
  project/client tagging, date it applies to if not "today")? Who can trigger the
  payment-request step — the same user who logged the hours, or only godfather/admin
  (consistent with existing Morning MCP RBAC gating)? Is an hourly rate configured somewhere, or
  supplied per report?
