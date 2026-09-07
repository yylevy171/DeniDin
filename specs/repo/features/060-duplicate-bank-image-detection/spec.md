# Feature Specification: Duplicate Bank-Deposit Image Detection

**Feature Branch**: `feature/060-duplicate-bank-image-detection`
**Created**: 2026-08-24
**Status**: Placeholder — not yet clarified/specced. Captured from a 2026-08-24 request, raised
directly during the interactive `needs_clarification.jsonl` review of the Feature 043 player
replay; run `speckit.specify` + `speckit.clarify` before starting implementation.

## Input

User description: "open a new feature 60 - handle duplicate bank images" — raised after the
review pass (item 23/86) found real duplicate ledger events caused by the same physical bank
transfer being photographed/sent more than once.

## Context that prompted this

Item 23/86 of the review traced a batch of ~5 bank-transfer screenshots sent in one WhatsApp
session (`player_data/_review_decisions.jsonl`, item 23/86). Two of those screenshots turned out
to be repeat photos of transfers already captured earlier, producing genuine duplicate ledger
events:

- **Cluster A** — same `bank_account`/`bank_branch`/`bank_number` (`94968`/`123`/`4`), same
  `amount` (2,000₪), same `txn_date` (06/08/2026): captured twice (`B09082606000`,
  `B09082606290`), with the payer's account-holder name OCR'd two different (garbled) ways each
  time ("איצר זהבה" vs "אוצר הזהב").
- **Cluster B** — same bank_account/branch/bank (`2821044`/`837`/`10`), same amount (3,000₪),
  same `מספר אסמכתה` (bank reference number) `3312`, same `txn_date` (04/08/2026): captured
  **three** times (`B05082605310`, `B09082606040`, `B09082606280`), across messages sent on two
  different days (05/08 and again twice in a 09/08 batch).

Manually corrected during the review: the first deposit captured in each cluster was kept as-is;
every later duplicate had `event_subtype` changed to `מבוטל` in place, with an explanatory note
appended to `description` (`"מבוטל - מסמך זהה למסמך קודם שכבר נרשם"`), originals backed up to
`events/_originals/` first, no other field touched. See `_review_decisions.jsonl` item 23/86 for
the full record. This spec is about the underlying capture mechanism that let it happen, not
about that manual fix.

## Problem

`capture_ledger_event` (Feature 033) has no notion of "this bank deposit was already captured" —
every image that OCRs into a `בנק`/`הפקדה` event becomes a new ledger event unconditionally, with
no check against existing events for the same underlying real-world transfer. A client re-sending
or re-photographing the same transfer confirmation (for any reason — blurry first photo, batch
re-send, asking again days later) currently produces a second (or third) ledger event for money
that was only ever deposited once, silently inflating recorded income unless caught by manual
review, as it was here.

## Open Questions (for `speckit.clarify`)

- What counts as "the same transfer" — is `מספר אסמכתה` (bank reference number) reliable enough
  to be the sole dedup key when present, or does it need corroboration (amount + account +
  date)? Cluster B shows the same reference number across all 3 duplicate captures; Cluster A's
  duplicates had no reference number captured on the first copy at all, so amount+account+date
  matching would have been needed instead.
- Detection scope: same session only, or across all history (a re-send weeks later)?
- On a detected duplicate, should capture be blocked outright, captured but auto-flagged
  `מבוטל`, or should the model ask the user to confirm before capturing (mirroring how checks/
  Bit/PayBox already prompt for unsupported cases)?
- OCR name variance (the same real payer account name read two different garbled ways across
  duplicate images) means exact string matching on `client_name`/payer text is not viable as
  part of the dedup key — needs a design that doesn't depend on it.

## Next Steps

1. `speckit.specify` — write full user stories (Given-When-Then) for the duplicate-detection
   behavior once the open questions above are resolved.
2. `speckit.clarify` — resolve the dedup-key and on-detection-behavior questions above.
3. `speckit.plan` / `speckit.tasks` / `speckit.implement` per the standard pipeline.
