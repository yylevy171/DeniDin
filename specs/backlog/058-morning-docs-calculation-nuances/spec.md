# Feature Specification: Morning Document-Status Calculation Nuances

**Feature Branch**: `feature/058-morning-docs-calculation-nuances`
**Created**: 2026-08-19
**Status**: Placeholder — not yet clarified/specced. Captured from a 2026-08-19 request;
run `speckit.specify` + `speckit.clarify` before starting implementation.

## Input

User description: "create a feature 58 for 'calculation nuances based on morning docs'" —
raised directly after discovering, while implementing Feature 056 (T010's billed E2E test),
that Morning's own status-code vocabulary is ambiguous in a way this app's current formatting
logic doesn't resolve. Deliberately deferred (user, 2026-08-19: "dont touch for now") rather than
folded into Feature 056's already-approved scope.

## Context that prompted this

Morning's real `/documents` status codes (confirmed live via `GET /documents/statuses`): `0`
open, `1` closed via payment, `2` manually closed, `3`/`4` cancelling/cancelled document
(reachable only via a linked credit note — i.e. only when a document was actually created).
This app's own canonical mapping (`apps/morning-mcp-app/src/denidin_mcp_morning/models.py`'s
`_MORNING_STATUS_CODES`) collapses codes `1` **and** `2` into a single status, `"paid"`,
rendered in Hebrew as "שולם" by `formatters.py`'s `translate_status`.

That collapse is correct for its original purpose: a tax invoice a bookkeeper manually marks
closed after receiving payment outside Morning (bank transfer, cash) genuinely **was** paid, and
status `2` is the right code for that.

Feature 056's `cancel_transaction_account` (T004b/T005b) also produces status `2` — because
`POST /documents/{id}/close` is the *only* document-less state-mutation Morning's API exposes at
all (confirmed live, `specs/in-progress/056-receipts-without-invoice/research.md`). But for a
transaction account, status `2` can now mean two genuinely different things Morning itself
cannot distinguish by status code alone:
1. It was manually closed because it really was paid (outside Morning).
2. It was cancelled (Feature 056) because the deal fell through — no money moved at all.

`cancel_transaction_account` has its own dedicated confirmation message
(`format_transaction_account_cancelled`) that correctly avoids "שולם" wording for its *own*,
immediate reply. But a **later**, separate lookup (`get_invoice_details`, or any other call that
goes through the shared `translate_status` path) sees only the raw status code `2` and reports
"שולם" (paid) regardless of which of the two real-world reasons produced it — because nothing
persisted anywhere records *why* a given status-2 document was closed. Morning's own API gives
this app no field to check; the only place that distinction ever existed was the one-time
confirmation message and the audit-log line at the moment of cancellation.

## Notes captured so far

- Scope not yet defined — and probably broader than just this one case. The user's framing
  ("calculation nuances based on morning docs") suggests this may be a home for other, similar
  Morning-status/derived-value ambiguities as they're found, not only the status-2 case above.
  Open questions for `speckit.specify`/`speckit.clarify`:
  - **Scope boundary**: is this feature specifically the status-2 paid-vs-cancelled ambiguity
    (transaction accounts only), or a general "Morning-status/calculation edge cases" bucket
    that should stay open to whatever else surfaces later? If the latter, needs an explicit
    process for how new nuances get added to it over time.
  - **Where should "why was this status-2 document closed" actually live?** Candidates: encode
    it in the document's own `description` field (a real, if slightly hacky, way to make it
    recoverable from Morning itself on a later read); track it in `apps/denidin-app`'s own
    ledger-event system (Feature 033) as a side record keyed by `internal_morning_id`; some
    other persisted mapping this app owns. Each has different implications for what
    `get_invoice_details` would need to look up and how reliable that lookup is (e.g. a
    transaction account cancelled directly via Morning's own UI, bypassing this app entirely,
    would have no such record no matter which mechanism is chosen).
  - **Does `get_invoice_details`/`translate_status` need a transaction-account-aware branch at
    all**, or is a narrower fix possible (e.g. only `cancel_transaction_account`'s own tool
    output/audit trail needs to be trustworthy, and a generic follow-up status lookup reporting
    "paid" for an abandoned deal is an acceptable, documented limitation)?
  - **Are there other Morning-status/calculation nuances already known but not yet written
    down** that belong in this same feature once scoped (e.g. anything else discovered during
    Feature 021/027/028/038's own live-sandbox research that was deferred rather than fixed)?

## References

- `specs/in-progress/056-receipts-without-invoice/research.md` — the original live-sandbox
  finding (Finding 2) that a manually-closed (status 2) document renders as "שולם" regardless of
  cause.
- `apps/morning-mcp-app/src/denidin_mcp_morning/models.py` (`_MORNING_STATUS_CODES`),
  `formatters.py` (`translate_status`, `format_transaction_account_cancelled`).
