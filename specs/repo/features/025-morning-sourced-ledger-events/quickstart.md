# Quickstart: Verifying Morning-Sourced Ledger Events

**Feature**: 025-morning-sourced-ledger-events

**Revised 2026-08-21 (round 3/4 of `spec.md`'s Clarifications)** — supersedes the original
version, which described the pre-redesign 5-field/hard-refusal/no-config-gate shape. Manual
verification scenarios, to run against a running `dev` container for both apps (per CLAUDE.md's
environment rules — starting `dev` needs its own explicit approval, every time). This feature has
**no WhatsApp-visible behavior at all** (the sweep is silent, per
`contracts/accounting-reconciliation-service.md` step 8) — verification is entirely file-based
plus log inspection.

## Prerequisites

- `denidin-app-dev` + `morning-mcp-app-dev` both running (`scripts/run_all.sh dev`).
- **`config.dev.json`'s `accounting_ledger_update_freq` set to a real positive minute value** (not
  `0`) — the scheduler is inactive entirely when unset/`0` (a human-picked value, task T030; ask
  before assuming a number is already set).
- Access to create at least one new document in the Morning **sandbox** (dev's Green Invoice
  account) not created through DeniDin conversation — e.g. directly in the Green Invoice sandbox
  UI — so it genuinely exercises "a document that shows up in Morning with no matching DeniDin
  conversation" (spec.md's Problem Statement).
- `apps/denidin-app/dev_data/events/` and `apps/denidin-app/dev_data/accounting_reconciliation/`
  — note what's already there before starting, to make new files easy to spot.

## US1 — First-ever sweep on a fresh environment (no prior חשבונית events)

1. Create one new document directly in the Morning sandbox (bypassing DeniDin entirely).
2. Wait for one sweep tick (interval = `accounting_ledger_update_freq` minutes).
3. `logs/dev/denidin-app.log` — confirm a sweep ran, used the fallback lookback window (no prior
   `חשבונית` events yet to derive a watermark from), and found the new document. Also confirm the
   log line naming how many `mcp_call`s Morning MCP tools attached, and that no safety-cap
   ERROR was logged.
4. `ls apps/denidin-app/dev_data/events/` — one new `H{DDMMYY}{HHMM}0.json` file (the `HHMM`
   portion reflects the document's own real creation time, not the sweep's processing time).
5. `cat` that file — `source_type` is `"חשבונית"`, `event_subtype` is `"הפקה"`, all **four**
   `accounting_document_display_number`/`_type`/`_status`/`_creation_date` fields are populated
   and match the real document (cross-check `accounting_document_display_number` and
   `accounting_document_creation_date`'s exact HH:MM against the Morning sandbox UI directly, not
   just internal consistency — there is no `accounting_document_id` field at all, that concept was
   merged into `_display_number`), every הסכם/בנק-only field is `null`, `schema_version` is `2`,
   `session_id` is `"accounting-reconciliation"`, `message_id` is `null`.

## US2 — Second sweep does not re-capture the same document

1. Wait for a second sweep tick, with no new documents created in between.
2. Confirm no new file appears under `dev_data/events/` for the same document.
3. Confirm the log shows an INFO line naming the re-poll as a "true duplicate... discarding" (not
   a WARNING/ERROR — a plain re-poll of an unchanged document is a normal, expected no-op, not an
   error) — distinguish "ran, found nothing new" from "didn't run at all."

## US3 — Two new documents in one window

1. Create two new documents in the Morning sandbox before the next sweep tick.
2. After that tick: confirm **two** new `H...json` files, one per document, each with the correct
   distinct `accounting_document_display_number` — proves the reconciliation handler's
   multi-call-per-turn path (`contracts/accounting-reconciliation-service.md` step 6) actually
   persists all of them, not just the first (this is exactly the shape the old
   `_handle_ledger_event_capture`'s "one call per turn" rule would have wrongly rejected — this
   scenario is the concrete proof the new handler is genuinely separate).

## US4 — Ordinary conversational turn is unaffected

1. From the godfather phone, ask a real Morning question in normal conversation (e.g. "מה כל
   התשלומים של X?" — the same shape as the original 2026-07-28 incident this feature descends
   from).
2. Confirm the reply is correct and complete (the original bug's symptom — an empty reply — does
   NOT reproduce).
3. Confirm **no** new `dev_data/events/` file was created by this conversational turn (the
   existing `_handle_ledger_event_capture` suppression for same-turn `mcp_call` still applies
   here, unchanged — this is the regression check for `contracts/ledger-event-manager-extension.md`'s
   "UNCHANGED" section).

## US5 — A sweep failure never silently skips a window

1. Temporarily make one sweep tick fail (e.g. briefly point `config.mcp.morning_status_file` at a
   nonexistent path, or stop `morning-mcp-app-dev` for one tick, then restore/restart it).
2. Confirm `logs/dev/denidin-app.log` shows an ERROR for that tick, and no new file was written.
3. Let the next tick run normally. Confirm it still covers the full window back to the last real
   captured document's timestamp — i.e. the failed tick did not narrow or skip any part of the
   window (the watermark is derived from what's actually persisted, never a separately-advanced
   counter, so a failure can't silently lose ground).

## Anomaly case (round 3 — not a numbered user story, but real, observable behavior)

If a document's `accounting_document_display_number` is ever seen again with a **different**
creation timestamp than before (should never happen for a real Morning document — flagged as a
genuine anomaly, not a normal dedup case):

1. `logs/dev/denidin-app.log` shows a WARNING naming the display number and both timestamps.
2. A **new** `H...json` file is created (the original file is untouched, never overwritten).
3. `apps/denidin-app/dev_data/accounting_reconciliation/pending_review.json` gains one new entry
   naming both event_ids/timestamps, for later human review — no WhatsApp notification.

## Safety cap (round 3/4 — 5 days / 100 documents)

Not practical to trigger routinely in a dev sandbox (needs either a genuinely stale watermark or
100+ real candidate documents) — if verifying deliberately: force a large gap (e.g. temporarily
back-date a persisted `חשבונית` event's `accounting_document_creation_date` far into the past,
restart the process to reset the in-memory cache) and confirm the sweep logs an ERROR and skips
the tick entirely with no OpenAI call attempted at all (5-day half), or construct a search with
100+ real matching sandbox documents and confirm the sweep logs an ERROR and persists nothing from
that tick (100-document half, checked from the real `list_invoices` tool output after the one
OpenAI+MCP call completes).
