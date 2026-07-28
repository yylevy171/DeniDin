# Feature Spec: Morning-Sourced Ledger Events

**Feature ID**: 025-morning-sourced-ledger-events
**Priority**: P2
**Status**: Draft
**Created**: July 28, 2026

---

## Problem Statement

Feature 024 (Ledger Event Recognition) captures fee-agreement and bank-deposit events
from conversational text/images via a `capture_ledger_event` function tool, always
attached alongside Morning MCP tools for godfather/admin turns
(`AIHandler._assemble_tools`). Discovered live (2026-07-28, `test_yossi_all_payments_gets_the_complete_picture`):
a real godfather turn asking to "list all payments" for a client triggered
`list_invoices`, and the model then read its own tool output back and mistook
pre-existing Morning documents for new fee-agreement text, calling
`capture_ledger_event` on data that already lives in Morning. Worse, the follow-up
round-trip (`_call_openai_ledger_followup_api`) still had `capture_ledger_event`
available and called it *again* instead of finally answering, so the user got a
completely empty reply despite `list_invoices` having successfully returned the
correct, complete data.

**The underlying insight (user, 2026-07-28) is real and worth building on
purpose**: Morning documents can be created outside DeniDin entirely (directly in
Green Invoice, or by another integration) - `list_invoices`/`get_invoice_details`
are effectively the *only* way DeniDin can ever discover that those events happened.
A document a godfather created by talking to DeniDin already flows into ledger
tracking via the conversational capture path; a document that shows up in Morning
with no matching DeniDin conversation never does, and today has no path into the
ledger at all. This is a real gap, not just a misfire to patch around.

**Immediate mitigation shipped ahead of this spec** (bugfix-adjacent, not a full
fix): `AIHandler._handle_ledger_event_capture` now detects when the same turn's
`response.output` contains a real `mcp_call` item (Morning MCP genuinely produced
this turn's data) and, if so, does not persist any `capture_ledger_event` call(s)
from that turn, and strips `capture_ledger_event` from the follow-up round's tools
so the model can't repeat the same mistake and is forced to produce its actual
text reply. This restores correct behavior (the user gets their real answer) but
throws the Morning-sourced signal away entirely rather than doing anything useful
with it - exactly the gap this spec should close.

## Open Questions (not yet clarified)

- **What counts as a "new" Morning-sourced event worth capturing?** Every
  `list_invoices`/`get_invoice_details` call returns the full document history
  every time - naively capturing "every document seen in a tool result" would
  massively over-capture (the same 8 documents would be re-proposed on every
  future query about that client). Needs some notion of "already known to the
  ledger" to diff against - by Morning document id, most likely.
- **Where does that "already known" state live?** Options: (a) a new
  small local store (e.g. a set of already-seen Morning document ids) DeniDin
  maintains itself; (b) cross-reference against AHLedger's own `Events.csv`/
  `Agreements.csv`/`Bank.csv` (the actual downstream ledger, in the separate
  `/Users/yaron/Projects/AHLedger` project) directly - but DeniDin has no existing
  integration with that project today, and this app's own architecture keeps
  external systems reached over clean boundaries (MCP/HTTP), not shared files.
- **Should this run proactively or only reactively?** Reactive (only when a
  godfather happens to ask a Morning question that surfaces a not-yet-seen
  document) means real gaps go unnoticed until someone happens to ask. A
  proactive sweep (e.g. periodic `list_invoices` polling, diffed against known
  ids) is a materially different, heavier feature (background job, no
  triggering user message) - probably out of scope for a first version.
- **What ledger-event shape do Morning documents map to?** `capture_ledger_event`'s
  schema (see `runtime_constitution.md`'s "Ledger Event Recognition" section) was
  designed around free-text fee-agreement/bank-deposit statements, not structured
  Morning document fields (client, amount, document type, paid/unpaid, linked
  documents). May need its own dedicated capture path/schema rather than reusing
  `capture_ledger_event` as-is.
- **Does this need a `config.feature_flags` gate?** Given it's new capture volume
  (not a behavior change to existing paths), likely yes, unlike 021's assessment -
  needs an explicit decision.

## Relationship to Feature 024

Direct follow-on. Feature 024 built the capture mechanism and text/image sources;
this spec is about adding Morning MCP tool results as a third source, with real
diffing/dedup logic Feature 024 never needed (conversational text is inherently
"new" each time; Morning tool results are a full history repeated on every call).

## References

- `apps/denidin-app/src/handlers/ai_handler.py` (`_handle_ledger_event_capture`,
  `_call_openai_ledger_followup_api`, `_assemble_tools`) - current suppression logic
  to be replaced/extended by whatever this spec resolves on.
- `apps/denidin-app/tests/expensive/test_denidin_morning_mcp_e2e.py`
  (`test_yossi_all_payments_gets_the_complete_picture` /
  `test_yossi_explicit_everything_request_gets_the_complete_picture`) - where the
  gap was first observed live.
- `config/runtime_constitution.md`'s "Ledger Event Recognition" section.
