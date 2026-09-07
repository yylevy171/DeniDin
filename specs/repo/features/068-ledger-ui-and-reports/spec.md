# Feature Specification: UI and Reports Based on the Ledger

**Feature Branch**: `feature/068-ledger-ui-and-reports`
**Created**: 2026-08-30
**Status**: Placeholder — not yet clarified/specced. Captured from the 2026-08-29 dev-conversation
"DeniDin improvements" list (item 6). Run `speckit.specify` + `speckit.clarify` before
implementation.

## Input

User description: **UI and reports based on the ledger** — produce human-facing views and
reports from the stored records (ledger events, agreements, deposits, hours), beyond answering
one question at a time in chat.

## Notes captured so far

- Broader than `052-ledger-events-csv-export` (raw CSV dump of `{data_root}/events/*.json`).
  This item implies **formatted / summarised reports** — per client, per month, per matter — and
  possibly a **UI** (a web view, a generated document, or richer WhatsApp-delivered summaries).
- Overlaps:
  - `052-ledger-events-csv-export` — the export mechanism; likely a building block here.
  - `051-hourly-reporting-payment-request` — its "monthly billing report" is one such report.
  - `044` ledger querying — the read path over events.
  - Feature 033 (`ledger_event_manager.py`) — the underlying event store.
- The August audit (`065-august-ledger-audit-apply`) produced ad-hoc reconciliation CSVs by
  hand — those are examples of the kind of output this feature would make repeatable.

## Open questions for `speckit.clarify`

- What is the "UI" — a web page, a generated PDF/spreadsheet, or structured WhatsApp messages?
- Which reports are in scope for v1 (client statement, monthly income, outstanding balances,
  hours summary…).
- Delivery / access: who can request a report, and how is it delivered.
- Relationship to Morning's own reporting — does this report only on DeniDin's ledger, or
  reconcile against Morning (as the audit did)?
- Real-time view vs. on-demand generation.
