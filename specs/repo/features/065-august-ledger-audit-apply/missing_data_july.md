# Missing Data — July 2026 Ledger (`בנק` cache)

## Root cause (confirmed by operator, 2026-08-30)

Bank-deposit screenshots only started being forwarded to the WhatsApp group **late July** —
before that, no bank slips were ever sent, so there is nothing for the player replay (or a live
bot) to have captured. This is **not** a recoverable gap like August's pre-onboarding week
(where the screenshots existed but the bot wasn't in the group yet) — for most of July the
underlying source data (a forwarded slip) never existed at all.

## What the player replay actually captured for July

Only 3 `בנק` events for the entire month (vs. 29 for August), all from 28–30 July — consistent
with "started late July." Matched 1:1 against Morning documents (all dated 31/07/2026, 1-day
posting lag from the bank `txn_date`):

| Player event | txn_date | Amount (₪) | Player-extracted name | Morning doc # | Morning name (verbatim) |
|---|---|---|---|---|---|
| B31072614342 | 28/07 | 5,000 | אדלר דוד | 112280 | דודי אדלר |
| B31072614341 | 30/07 | 10,620 | גלי ואיתן ברוך | 112281 | גדי אדלר |
| B31072614340 | 30/07 | 3,000 | אוהב עמי יחיאל | 130116 | יחיאל אוהב עמי |

All 3 corrected (Morning name substituted, `morning_document_id` set) and staged in
`backfill_events_july/*.json`, ready to replace/populate prod's July `בנק` events for these 3
dates.

**Note on `112281`/10,620 ₪**: the same recurring amount appears in August too (`מתנס שורק`
`90192`-style transaction account, and `מתנ"ס נחל`→`מתנס שורק` name-corrected in the August
audit) — likely one recurring monthly-retainer client whose real identity keeps getting
re-guessed per month from bank-slip account-holder names rather than resolved once against
Morning's client list. Candidate real-world instance of the gap `069-mandatory-client-
resolution-before-ledger-event` is meant to close. Not resolved here — flagging only.

## Everything else in July: no bank-slip source at all

The Morning screenshots for July show roughly 30+ other income documents (הראל חברה לביטוח,
מקורות ×2, עו"ד יועד יובל, רן אורפני, אביתר כהן, etc.) with **no** corresponding player-replay
`בנק` event, and per the root cause above, none is expected — no slip was ever forwarded. This
is the July equivalent of August's Category 3 ("recorded in Morning, no bank slip") but for
nearly the whole month, not a handful of documents.

**This is a design decision, not a bug**: unlike August's cache, which is expected to cover most
of the month's deposits, July's `בנק` cache should be expected to cover only late July — the
rest of the month's real income is fully tracked in Morning, just never mirrored into the manual
`בנק` cache, because there was no bank-slip conversation to capture it from. Recorded here so
that isn't later mistaken for a data-quality gap.

## Screenshot list is partial — full CSV still needed

The July comparison above was built from two mobile screenshots (56 of the reported 62 total
July documents visible), not a full export. Before treating July as "done," pull the full
Green Invoice July CSV export (same shape as `august_morning.csv`) to confirm nothing in the
6 unseen rows changes this picture — likely low-risk since the 3 matched events already account
for the only late-July `בנק`-relevant documents visible, but not yet confirmed exhaustively.
