# Quickstart: Verifying Morning-Sourced Ledger Events

**Feature**: 025-morning-sourced-ledger-events

Manual verification scenarios, to run against a running `dev` container for both apps (per
CLAUDE.md's environment rules — starting `dev` needs its own explicit approval, every time).
This feature has **no WhatsApp-visible behavior at all** (the sweep is silent, per
`contracts/accounting-reconciliation-service.md` step 6) — verification is entirely file-based
plus log inspection.

## Prerequisites

- `denidin-app-dev` + `morning-mcp-app-dev` both running (`scripts/run_all.sh dev`).
- Access to create at least one new document in the Morning **sandbox** (dev's Green Invoice
  account) not created through DeniDin conversation — e.g. directly in the Green Invoice sandbox
  UI, or via `morning-mcp-app`'s own sandbox test tooling — so it genuinely exercises "a document
  that shows up in Morning with no matching DeniDin conversation" (spec.md's Problem Statement).
- `apps/denidin-app/dev_data/events/` — note what's already there before starting, to make new
  files easy to spot.

## US1 — First-ever sweep on a fresh environment (no prior חשבונית events)

1. Create one new document directly in the Morning sandbox (bypassing DeniDin entirely).
2. Wait for (or manually trigger, if `tasks.md` exposes a way to) one sweep tick.
3. `logs/dev/denidin-app.log` (or wherever this feature's log lines land) — confirm a sweep ran,
   used the fallback lookback window (no prior `חשבונית` events to derive a watermark from), and
   found the new document.
4. `ls apps/denidin-app/dev_data/events/` — one new `H{DDMMYY}{HHMM}0.json` file.
5. `cat` that file — `source_type` is `"חשבונית"`, `event_subtype` is `"הפקה"`, all five
   `accounting_document_*` fields are populated and match the real document (cross-check against
   the Morning sandbox UI directly, not just internal consistency), every הסכם/בנק-only field is
   `null`, `schema_version` is `2`, `session_id` is `"accounting-reconciliation"`, `message_id`
   is `null`.

## US2 — Second sweep does not re-capture the same document

1. Wait for (or trigger) a second sweep tick, with no new documents created in between.
2. Confirm no new file appears under `dev_data/events/` for the same document.
3. Confirm the log shows the sweep ran and found zero new documents (not that it silently didn't
   run at all — distinguish "ran, nothing new" from "didn't run").

## US3 — Two new documents in one window

1. Create two new documents in the Morning sandbox before the next sweep tick.
2. After that tick: confirm **two** new `H...json` files, one per document, each with the
   correct distinct `accounting_document_id`/etc. — proves the reconciliation handler's
   multi-call-per-turn path (`contracts/accounting-reconciliation-service.md` step 5) actually
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

## US5 — Duplicate guard, forced

1. Manually re-run (or wait for a sweep that would otherwise re-see) a document already captured
   in US1 — e.g. by temporarily widening the fallback lookback in a test config, or another
   mechanism `tasks.md` provides for forcing a re-scan.
2. Confirm the log shows a WARNING "Refusing to persist duplicate חשבונית event for
   accounting_document_id=..." and no new file is created — the code-side guard, not just the
   prompt's own date-window framing, is what actually prevented it.
