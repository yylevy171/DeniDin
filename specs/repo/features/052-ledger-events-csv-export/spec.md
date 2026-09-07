# Feature Specification: Export Events Ledger as CSV

**Feature Branch**: `feature/052-ledger-events-csv-export`
**Created**: 2026-08-13
**Status**: Placeholder — not yet clarified/specced. Captured from a 2026-08-13 backlog
conversation; run `speckit.specify` + `speckit.clarify` before starting implementation.

## Input

User description: "export events ledger as csv" — let a user (likely godfather/admin) export
the stored ledger events (`{data_root}/events/*.json`, Feature 033) as a CSV file.

## Notes captured so far

- Distinct from the existing backlog item `044-ledger-event-querying` (AI querying past events
  via function-call for conversational answers) — this is a human-facing bulk export/download,
  not a query tool. No scope conflict, but worth cross-referencing during planning so the two
  don't duplicate a "read all events" code path independently.
- Open questions for `speckit.clarify`: delivery mechanism (WhatsApp document attachment vs.
  some other channel), scope of one export (all events vs. date-range/entity filters), RBAC
  gating (presumably godfather/admin only, matching other ledger/Morning-adjacent
  capabilities).
