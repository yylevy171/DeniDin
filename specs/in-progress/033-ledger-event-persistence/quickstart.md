# Quickstart: Verifying Ledger Event Persistence

**Feature**: 033-ledger-event-persistence

Manual verification scenarios for each user story, to run against a running `dev`
container (per CLAUDE.md's environment rules — starting `dev` needs its own explicit
approval, every time). These complement, not replace, the automated test suite in
`tasks.md`.

## Prerequisites

- `denidin-app-dev` running, real WhatsApp access as a godfather/admin-role phone number.
- `data/events/` does not yet exist, or is empty of relevant test ids (to make new files
  easy to spot).

## US1 — Text-path single-component event

1. Send: `"ישראל ישראלי 5,000₪ כתב הגנה"` from the godfather phone.
2. Confirm a normal conversational reply arrives.
3. On the host: `ls apps/denidin-app/dev_data/events/` — one new `A{DDMMYY}{HHMM}0.json`
   file should exist, dated/timed to just now (Asia/Jerusalem local).
4. `cat` that file — verify all 29 CSV-mapped keys are present (alphabetized), the 7
   nuances-feature fields + 5 invoice fields are `null`, `client_name` is "ישראל ישראלי",
   `amount` is `5000` (integer, not `"5,000₪"`).
5. Find the session's `messages/{message_id}.json` for the just-sent message — confirm
   `ledger_event_ids` contains exactly that one `event_id`.
6. Confirm that session's `session.json` has no `pending_ledger_events` key at all.

## US2 — Image-path event with `message_id`

1. Send a real bank-transfer-confirmation screenshot from the godfather phone.
2. After the reply, find the newly created `B{DDMMYY}{HHMM}{seq}.json` under
   `dev_data/events/`.
3. Confirm `message_id` is a real UUID (not `null`) and matches the media-turn message's
   own `message_id` in `dev_data/sessions/{session}/messages/`.

## US3 — Multi-component split

1. Send a message describing 2-3 distinct conditional fee stages in one text (mirroring
   the גיליאן דוידיאן example from this feature's design discussion).
2. Confirm N separate files appear under `dev_data/events/`, sharing the same
   `{letter}{DDMMYY}{HHMM}` prefix with sequential `seq` (0, 1, 2, ...).
3. Confirm the source message's `ledger_event_ids` lists all N ids, in call order.

## US4 — Migration

1. Run the migration script (see `tasks.md` for its task id) once, with `-dry-run` first
   to review output, then for real.
2. `ls dev_data/events/ | grep -c ''` — should show exactly 6 new files (plus whatever
   already existed from earlier stories' manual testing).
3. Spot-check one file's Hebrew content renders correctly (no double-encoding/mojibake).
4. Confirm `dev_data/sessions/4454746c-350a-4fa7-a5ef-fda2c685b0d5/session.json` no longer
   has `pending_ledger_events`.
