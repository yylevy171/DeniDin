# Feature Specification: Mandate Client Resolution Before Any Ledger Event Creation

**Feature Branch**: `feature/069-mandatory-client-resolution-before-ledger-event`
**Created**: 2026-08-30
**Status**: Placeholder — not yet clarified/specced. Captured from the 2026-08-30 conversation
(item 7, added alongside the 2026-08-29 dev "DeniDin improvements" list). Run `speckit.specify` +
`speckit.clarify` before implementation.

## Input

User description: **no ledger event may be created until the client has been resolved** — the
`client_name` on a ledger event must be a real, resolved client (matched against Morning's
client list, or a deliberate new-client decision), never a raw OCR string, a debited-account
name, or an institution name lifted off a transfer slip.

## Notes captured so far

- Directly motivated by the August 2026 ledger audit (`065-august-ledger-audit-apply`): of 33
  `בנק` events, a large share had `client_name` set to the debited-account holder, an
  institution ("Citibank Israel", "Mekorot", a community centre), or an OCR fragment — because
  the extractor stored whatever it read, with no resolution step. The audit's change-set is
  16 manual name corrections.
- The fix is a **gate**: recognition of a ledger-relevant event (deposit, agreement, hours,
  Bit/PayBox transfer) must run client resolution first; if it can't resolve confidently, it
  asks the operator rather than persisting a guessed name.
- Touches: `ledger_event_manager.py` (Feature 033), the `runtime_constitution.md` "Ledger Event
  Recognition" rules, the Morning `resolve_client_name` / `list_clients` MCP tools, and the
  approval-gate machinery.
- Interacts with `066` (Bit/PayBox) and item 1's screenshot→action flow — both create events
  and would inherit this gate.

## Open questions for `speckit.clarify`

- What counts as "resolved" — an exact Morning client match, a high-confidence fuzzy match, or
  an explicit operator confirmation each time.
- Behaviour on no match / multiple matches: always ask, or allow "create as new client" inline.
- Does this apply retroactively (a migration/cleanup pass over existing events) or forward-only
  (`065` already covers the August backfill).
- `הסכם` (agreement) and hours events too, or deposits only.
- Where the gate lives — constitution guidance, code-level check in `ledger_event_manager`, or
  both.
