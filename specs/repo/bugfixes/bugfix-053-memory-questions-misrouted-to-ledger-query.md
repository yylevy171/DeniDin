# Bugfix Spec: Model fails to recognize a plain memory/conversation-recall question, routes it to `query_ledger_events` instead — and that misroute then hard-errors

## Bug ID
bugfix-053-memory-questions-misrouted-to-ledger-query

## Title
Asked a pure conversation-history question ("who did I ask you about on Aug 15") that Feature
070's own recall correctly surfaced (`daily_summary` recalled, right window loaded), the model
misidentified it as a `query_ledger_events` request instead of answering directly from recalled
memory. That misroute then cascaded into a hard, user-visible `400 context_length_exceeded` for
a single-date question that should have matched almost nothing. There are three distinct causes
here, in chronological order — an earlier one being wrong is what let each later one fire at all
— and severity runs the same direction: cause #1 is both the first domino and the worst bug.

## Priority
**P1.** The primary cause (#1) is a real, silent misclassification that will keep firing on
ordinary conversational questions, not just the one that happened to also error out (#2/#3 are
this instance's downstream symptom, not the only way #1 can go wrong).

## Status
**Open.** Root cause identified 2026-09-04 during Feature 070 (rolling memory window) Stage 2
dev-migration validation — unrelated to Feature 070 itself (see "How this was found" below) and
does not block that migration. Awaiting human approval of root cause before test-gap analysis,
per Bug-Driven Development (METHODOLOGY.md §VII).

## Date Opened
2026-09-04

## Reported By
yaronlev171, live in dev during Feature 070 Stage 2 validation (real WhatsApp turn, godfather
1:1 chat).

## How this was found (and what it is NOT)
While validating Feature 070's rolling-window/`daily_summary` recall against real dev data, a
mid-August recall question triggered this bug. Feature 070's own mechanics worked exactly as
designed in this turn — the logs confirm the right `daily_summary` was recalled
(`Added 10 recalled memories to system prompt`) and the live window was loaded correctly
(`Retrieved 28 messages from session history`). Feature 070 is not implicated anywhere in this
bug; it is filed separately because the failure surfaced during that validation, not because it
belongs to it.

## The three causes, in order (chronological AND severity)

### Cause #1 — ROOT CAUSE: the model cannot tell a memory/conversation-recall question from a ledger-data question
The user's message was **"עבור מי ביקשתי ממך לבדוק חשבוניות ב-15 באוגוסט?"** ("who did I ask you
to check invoices for, on Aug 15?") — a question about **what was discussed/asked in the
conversation on that date**, answerable directly from the already-recalled `daily_summary`
(confirmed present in context, per the logs above). The model instead called
`query_ledger_events`, apparently pattern-matching the words "לבדוק חשבוניות" (check invoices)
against `runtime_constitution.md`'s "Ledger Event Querying" instruction to "check the ledger
FIRST" for amounts/client names/invoice status — even though nothing about the actual question
was a request for current ledger/invoice data.

This is the real defect: a `runtime_constitution.md` scoping/boundary gap between conversational
recall (answer from what's already in context) and `query_ledger_events` (a live tool call),
in the same family CLAUDE.md already flags for every tool-bearing feature ("EVERY NEW
TOOL-BEARING FEATURE NEEDS EXPLICIT CONSTITUTION BOUNDARIES"). Nothing downstream — the error,
the missing cap — would ever have fired if this classification had been correct. **This is cause
#1 and the one that actually needs fixing first**; #2 and #3 below are what its failure exposed,
not independent problems of equal standing.

### Cause #2 — a single narrow (one date) criterion should never have produced an oversized result in the first place
Even granting the misroute, the query itself was about **one specific date** ("15 באוגוסט") —
a narrow, single-criterion lookup that should have matched a small number of candidate events,
not enough to overflow a context window on its own. That it apparently did (or at least
contributed enough, stacked onto the turn's existing rolling-window context, to blow the limit)
is itself worth investigating: does `LedgerEventManager.query_events`'s scoring genuinely surface
an outsized number of matches for a single date-hinted criterion against a large index (dev:
4,170 events), or is the real payload size coming from something else in the same follow-up call
(the full event objects being large individually, not just numerous)? **This needs its own
investigation** as part of this bugfix's test-gap analysis — the fix can't be scoped correctly
without knowing which one it is.

### Cause #3 — `query_events` has no result-count cap, and the follow-up call has no size check before calling OpenAI
Least severe, but a real contributing factor and the most mechanically direct cause of the actual
`400`: `LedgerEventManager.query_events` (`apps/denidin-app/src/managers/ledger_event_manager.py`)
was deliberately designed with no upper bound on match count (2026-08-24 redesign: "retrieve
broadly, let the model reason over the raw returned events" — needed for OR/NOT/aggregation
support) and `AIHandler._call_openai_query_ledger_events_followup_api`
(`apps/denidin-app/src/handlers/ai_handler.py`, ~line 2536-2604) serializes every returned event
into the follow-up call with no token-budget check first. The surrounding `try/except Exception`
(line ~2601) does catch the OpenAI rejection rather than crash the process, but has no better
fallback than the fully generic "I hit an error, try again" message — no indication to the user
that their query matched too much, nothing suggesting how to narrow it.

**Precedent for the intended fix shape**: Morning's own `list_invoices` tool already handles this
exact class of problem gracefully — the same dev session's logs show it returning, for a broad
query: *"נמצאו 169 חשבוניות התואמות את החיפוש - יותר מדי להצגה כרשימה אחת. אנא צמצם/י את החיפוש
(למשל לפי טווח תאריכים, לקוח, או סטטוס)"* ("found 169 matching invoices - too many to list,
please narrow your search e.g. by date range/client/status") — friendly, actionable, no API
error. `query_ledger_events` has no equivalent guard. (Feature 025's
`accounting_reconciliation_service` has a related but differently-shaped cap — 5 days/100 docs,
skips the entire sweep tick, logs `ERROR ... needs admin intervention` — but that's a **silent
background sweep**, so a loud log-only failure is correct there; `query_ledger_events` is a
**live, user-facing** tool call and needs an in-conversation graceful message instead, closer to
`list_invoices`' pattern.)

## Affected Area
- `apps/denidin-app/config/runtime_constitution.md` — "Ledger Event Querying" section (cause #1):
  needs an explicit boundary distinguishing "what did we discuss/who was named on date X"
  (conversational recall, answer from context, no tool call) from "what's the current
  ledger/invoice status" (a real `query_ledger_events`/Morning lookup) — mirroring the existing
  "Contexts of Operation" ambiguous-short-reply pattern this file already uses for other tool
  families.
- `apps/denidin-app/src/managers/ledger_event_manager.py::query_events` (cause #2 investigation +
  cause #3 fix) — scoring/result-size behavior for a single narrow criterion against a large
  index; whether a count/size cap is warranted.
- `apps/denidin-app/src/handlers/ai_handler.py::_handle_query_ledger_events` /
  `_call_openai_query_ledger_events_followup_api` (cause #3 fix) — needs a size/token check before
  calling OpenAI, with a graceful degraded response instead of letting a `400` propagate to the
  generic fallback.

## Root cause (for approval)
Cause #1 (the model's failure to distinguish a conversational-recall question from a
`query_ledger_events`-shaped one) is the actual root cause — it is what let the turn reach
`query_ledger_events` at all. Causes #2 and #3 are what that misroute's downstream call then
exposed, in the order they'd need to be understood/fixed, not independent defects of equal
weight. **Awaiting human approval of this root-cause framing (all three causes) before test-gap
analysis/fix design**, per Bug-Driven Development (METHODOLOGY.md §VII).
