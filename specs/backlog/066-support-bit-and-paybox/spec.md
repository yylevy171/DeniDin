# Feature Specification: Support Bit and PayBox

**Feature Branch**: `feature/066-support-bit-and-paybox`
**Created**: 2026-08-30
**Status**: Placeholder — not yet clarified/specced. Captured from the 2026-08-29 dev-conversation
"DeniDin improvements" list (item 2). Run `speckit.specify` + `speckit.clarify` before
implementation.

## Input

User description: support **Bit** and **PayBox** transfers, treated the same as a bank transfer —
same recognition from a forwarded screenshot, same ledger event handling, same downstream
document flow.

## Notes captured so far

- Motivated by the August 2026 ledger audit (`065-august-ledger-audit-apply`): Bit transfers
  were captured with a `ממתין` (pending) status line and classified as "unsupported", then
  removed — even though some had real closed Morning documents.
- Bit/PayBox screenshots differ from bank-transfer confirmations: they carry an app confirmation
  number (e.g. `1078-6562-13301`), a pending/settled status line, a sender name, and usually no
  bank account number.
- `ממתין` (pending) vs. settled: a pending transfer is not yet money received — the feature must
  decide whether to record provisionally, wait for a settled screenshot, or ask.

## Open questions for `speckit.clarify`

- New payment-method field on the deposit/ledger event (`bank_transfer` / `bit` / `paybox`) vs.
  a new `source_type`.
- Handling the pending → settled transition (two screenshots for one payment).
- Idempotency: the app confirmation number is a natural dedup key — should the ledger enforce
  uniqueness on it?
- Does "same as bank transfer" mean it flows identically into item 1's screenshot→action flow?
