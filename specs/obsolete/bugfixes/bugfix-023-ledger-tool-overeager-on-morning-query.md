# Bugfix Spec: Model speculatively invokes the ledger-event capture tool on read-only Morning-data queries

## Bug ID
bugfix-023-ledger-tool-overeager-on-morning-query

## Title
The model attempts to call `capture_ledger_event` (Feature 024's Ledger Event Recognition
tool) while answering a purely read-only Morning MCP query (e.g. "give me the amounts paid
on each of the ones that were paid") - a turn with no fee agreement, no bank deposit, no
user-stated payment arrangement at all, just a request to summarize existing invoice data
already fetched via `list_invoices`. The app's existing "Morning MCP was this turn's data
source" guard correctly suppressed both attempted captures before anything was persisted, so
no incorrect data reached disk - but the model's *decision* to reach for that tool on a
query-only turn is itself the bug: intent recognition should not be reaching this point at
all for a turn like this.

## Priority
P1 - no incorrect data was ever persisted this time (confirmed: `dev_data/events/` had zero
new files after the turn), and the existing guard is a real safety net, not a coincidence.
But it's a clear model-intent-recognition mistake, and relying on the suppression guard as
the only line of defense is fragile - a future turn shaped slightly differently might not
trip that specific guard's condition, risking an incorrect ledger event actually persisting.

## Status
Open - root cause investigated live during manual dev testing (2026-08-05); no fix has been
designed or implemented yet. Per Bug-Driven Development (METHODOLOGY.md SVII), next step is
human review/approval of the root cause below before any test-gap analysis or fix design
begins.

## Date Opened
2026-08-05

## Reported By
yaronlev171 (found during manual dev-environment testing of Feature 039 / group conversation
support, immediately after deploying `denidin-app-dev` with the merged Feature 039 code -
unrelated to Feature 039 itself; this tool-attachment/prompting behavior predates it)

## Affected Area
- `apps/denidin-app/src/handlers/ai_handler.py` - `_assemble_tools` (unconditionally
  attaches the ledger-event capture tool - see `_build_ledger_event_tool` - to every
  conversational turn regardless of whether Morning MCP tools are also attached or what the
  turn is actually about), and the existing suppression guard (the `"[024] Suppressing N
  ledger-event capture(s)... Morning MCP was this turn's data source"` log line) that caught
  this specific case.
- `apps/denidin-app/config/runtime_constitution.md` - the "Ledger Event Recognition" section
  that instructs the model on when a ledger event should be captured; likely needs sharper
  negative guidance (when NOT to call the tool), not just positive guidance (when to call
  it).

## Description
Live sequence observed in `denidin-app-dev` logs (chat `120363410226011645@g.us`, a real
WhatsApp group, godfather role):

1. User: "בדוק כמה חשבוניות יש מהיום" (check how many invoices there are today) - model
   correctly called `list_invoices` via Morning MCP and answered with a summary. No ledger
   tool call attempted. Fine.
2. User (same session, next turn): "תן לי את הסכומים ששולמו בכל אחת מאלה ששולמו" (give me
   the amounts paid on each of the ones that were paid) - model called `list_invoices` again
   (correct), but the response (`resp_01bc03e58ef6bc06...`) ALSO included **2 `mcp_call`
   entries for `capture_ledger_event`** alongside the Morning MCP calls. Log line:
   `[024] Suppressing 2 ledger-event capture(s) for request req_b483bb58ca9e - Morning MCP
   was this turn's data source, not yet a supported ledger-event source
   (specs/backlog/025-morning-sourced-ledger-events)`.
3. Verified directly against disk (`dev_data/events/`, not just trusting the log line): no
   new event files were written after the turn - the most recent file predates this session
   by 3 days. The suppression guard worked correctly; nothing incorrect was persisted.

The user's query was purely a **read-only reporting question** about invoices that already
exist in Morning - not a new fee-agreement statement, not a bank-deposit report, nothing
matching the constitution's actual "Ledger Event Recognition" trigger conditions at all. The
model reaching for `capture_ledger_event` here at all indicates it is over-eagerly pattern
matching "message mentions payment amounts" -> "maybe I should log a ledger event", rather
than correctly recognizing that summarizing pre-existing Morning data is categorically
different from a client stating a new agreement/deposit.

## Root Cause
Two contributing factors, not yet fully disentangled - this is what needs human review before
proceeding to a fix:

1. **The ledger-event tool is unconditionally attached to every turn** (`_assemble_tools`
   always appends `_build_ledger_event_tool()`'s single tool, with no gating on whether the
   turn's content resembles a fee-agreement/deposit at all, and no gating on whether Morning
   MCP tools are also attached this turn). The model therefore always has the option
   available, on every single turn, including pure data-lookup turns.
2. **The constitution's "Ledger Event Recognition" guidance is framed positively** (when TO
   capture) without symmetric, equally explicit negative guidance (when NOT to - e.g.
   "summarizing or reporting on data already recorded in Morning is never itself a new
   ledger event, regardless of whether payment amounts are mentioned"). The existing
   suppression guard in code is effectively compensating for a prompting gap, not a
   structural one - the tool is available and the model isn't being told clearly enough that
   read-only Morning-data turns are categorically out of scope for it.

Not yet determined: whether narrowing the constitution's wording alone is sufficient, or
whether the tool's availability should itself become conditional (e.g. never attached on a
turn where Morning MCP tools are also being exercised for a read-only listing operation) -
this is exactly the kind of design decision Bug-Driven Development requires human sign-off
on before any test-gap analysis or fix implementation begins.

## Steps to Reproduce
1. In a group or 1:1 chat as a godfather/admin-role user, with at least a few paid invoices
   existing in the Morning sandbox for today's date.
2. Ask a read-only reporting question that necessarily involves stating a payment amount
   back to the user, e.g. "give me the amounts paid on each of the invoices that were paid
   today" (immediately after already asking "how many invoices are there today").
3. Inspect the `AIResponse.mcp_calls` / raw OpenAI response output for that turn: alongside
   the legitimate `list_invoices` call(s), one or more `capture_ledger_event` call(s) may
   also appear.
4. Confirm via the `"[024] Suppressing N ledger-event capture(s)..."` log line whether the
   guard caught it (as it did here) - the guard firing is not proof the underlying tendency
   is fixed, only that this particular turn didn't slip past it.

Not yet confirmed to be reliably reproducible on demand (single live occurrence so far,
during manual exploratory testing, not a scripted repro).
