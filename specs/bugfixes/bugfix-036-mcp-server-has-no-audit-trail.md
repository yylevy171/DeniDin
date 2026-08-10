# Bugfix Spec: The MCP server keeps no audit trail of the documents it issues

## Bug ID
bugfix-036-mcp-server-has-no-audit-trail

## Title
`morning-mcp-app` — the component that actually creates tax documents in Morning — logs
essentially nothing. Its entire production log for the 7–9 Aug 2026 window is 88 lines and
contains **no record of any document being created**.

## Priority
**P2** — no user-facing impact and no data corruption, but it is the reason forensic review of
a financial incident has to be reconstructed second-hand.

## Status
**Open — backlogged.** No fix designed. Per Bug-Driven Development (METHODOLOGY.md §VII), next
step is human approval of the root cause before test-gap analysis.

## Date Opened
2026-08-09

## Reported By
yaronlev171, from the 7–9 Aug 2026 production review
([`docs/production-analysis/2026-08-09-aug7-9-review.md`](../../docs/production-analysis/2026-08-09-aug7-9-review.md), P2-14).

> **Shared session context** — how this review was run, the read-only access paths, the full
> map of bugfix-028…037, the triage decisions (including what was closed as *not* a bug), and
> the open verification items:
> [`bugfix-028` § Session Context](../in-progress/bugfixes/bugfix-028-invoicing-and-approval-gate-p0-cluster.md#session-context-2026-08-09-production-review) (moved to `specs/in-progress/bugfixes/` 2026-08-10).
> All ten bugs in that set are **fix-forward only** — existing production documents are being
> left as they are by explicit user decision.

## Affected Area
- `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py` — all 11 tools, in particular the
  document-creating ones (`create_invoice`, `create_transaction_account`,
  `create_combo_document`, `create_credit_note`, `create_receipt`,
  `close_transaction_account`)
- `apps/morning-mcp-app/src/denidin_mcp_morning/server.py` — request/response logging
- `apps/morning-mcp-app/src/denidin_mcp_morning/morning_client.py` — outbound HTTP calls

## Description
`~/denidin-prod/apps/morning-mcp-app/logs/prod/morning-mcp.log` for the entire review window
is **88 lines**, consisting almost entirely of:
- four `Starting denidin-morning-prod …` startup lines (one per deploy), and
- a batch of `Skipping unparseable invoice …` warnings from 2026-08-04 (see bugfix-033),
- one phone-validation warning from 2026-08-09.

Documents **100012, 100013, 100014, 100015 and 90195** were all created through this server
during the window. **None of them appears in its log.** Neither does the payload sent, the
response received, nor the three failed `create_transaction_account` attempts for
הסתדרות כללית חדשה.

Reconstructing what was actually sent to Morning — including the evidence for
bugfix-028 A2 (the ₪2,360 → ₪2,784.80 VAT defect) and B4 (the failed client resolution) — was
only possible from **`denidin-app`'s** logs, which happen to record MCP call arguments and
outputs as a side effect of logging OpenAI responses.

That is a fragile accident, not an audit trail. If the calling app's logging changes, or if a
document is ever created by any other caller, there would be no record at all.

## Expected
Every document-creating tool call logs, at minimum: correlation id, tool name, resolved
client id and name, the **payload sent**, the **response received** (including the document
number and Morning's own computed total), and the outcome. Enough that "what did we send
Morning, and what did it return?" is answerable from this app alone.

Note this also directly supports bugfix-028 A4 (report the document's *real* total rather than
the requested amount) — both need Morning's actual response to be captured rather than
discarded.

## Related Work
- `specs/done/018-denidin-morning-mcp-integration/` — audit logging was already listed there as
  outstanding polish. This bug is the evidence that it matters.
- `specs/in-progress/bugfixes/bugfix-028-invoicing-and-approval-gate-p0-cluster.md` — A4 needs the same
  response data this bug is about capturing.
