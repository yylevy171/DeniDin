# Missing Data — August 2026 Ledger (`בנק`/`הסכם` cache)

**2026-08-30 update**: the 10 recovered pre-onboarding events (see `spec.md`'s cross-check
table) are no longer a gap — they've been prepared as ready-to-apply ledger events, with
client_name corrected to Morning's verbatim name, in
`backfill_events_pre_onboarding/*.json`. Not yet written to the live prod ledger (no write
path/apply mechanism has been exercised yet — the local mount is read-only); this is the
staged, human-approved input for that write. This file's totals below cover only what remains
genuinely unresolved after that batch.

One row per gap the August reconciliation (manual audit + player-replay cross-check, see
`spec.md`) could not close. This file is the durable record so a gap is tracked, not silently
absorbed into "the ledger is now correct." Update it whenever a gap is closed or a new one is
found — never delete a row, mark it resolved instead.

| # | Item | Amount (₪) | Status | Reason | Next step |
|---|---|---|---|---|---|
| 1 | Morning #112282, תניה סנקין | 4,000 | Open | Pre-onboarding (2–4 Aug); no matching player-replay event found | Targeted look at player raw log around 03/08 before concluding unrecoverable |
| 2 | Morning #112295, אפרת הלוי | 3,776 | Open | Pre-onboarding (2–4 Aug); no matching player-replay event found | Same as above |
| 3 | Morning #112290, עמליה אור | 3,776 | Open | Pre-onboarding (2–4 Aug); no matching player-replay event found | Same as above |
| 4 | Morning #112289, אור משאלי 2020 | 10,000 | Open | Pre-onboarding (2–4 Aug); no matching player-replay event found | Same as above |
| 5 | Category 3 — 8 Morning docs (נואז-טק פתרונות #112298 23,000; ריכטר דיין שולמית 6,000; ל.מ פאות קאולה ×2; +4 more) | ~53,436 | By design | Real closed Morning income with no forwarded bank slip at all — correctly absent from the `בנק` cache; not a defect | None — record as permanent, expected non-coverage |
| 6 | `B06082606161`, אסולין אסתר | 554 | Open | Ledger event exists, no matching Morning document | Human decision: keep as expense-reimbursement-style event, or flag for a manual Morning receipt check |
| 7 | Morning #112297 (רונית יעקובסון) / #112299 (רן סופר) Bit transfers | 6,136 | Open | Removed from cache as unsupported Bit (`ממתין`), but both have real closed Morning documents | Human decision after `066-support-bit-and-paybox` scoping: restore now with corrected payment-method, or leave `מבוטל` until 066 ships |
| 8 | Morning #112307 (רומן ציקל, 3,000) vs #112308 (רומן אלטשולר) | 3,000 | Open (Morning-side) | Possible duplicate/mis-issue in Morning itself, not a ledger-cache problem | Flag to operator; out of scope for this feature to fix |

**Totals**: 4 open pre-onboarding gaps (21,552 ₪) + 1 open no-Morning-doc event (554 ₪) + 1 open
Bit-removal-with-real-doc pair (6,136 ₪) + 1 open Morning-side possible duplicate (3,000 ₪) =
**31,242 ₪ genuinely unresolved** as of 2026-08-30. Category 3 (53,436 ₪) is intentionally
excluded from that total — it's expected non-coverage, not a gap.
