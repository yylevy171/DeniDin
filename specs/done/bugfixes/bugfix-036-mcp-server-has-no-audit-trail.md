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
**Done - Merged to master (PR #210)** — branch
`bugfix/036-037-mcp-audit-trail-and-timestamp-representation`, fixed together with bugfix-037
(2026-08-10). Root cause approved by the user; the failing-test gate (METHODOLOGY.md §VII
steps 3-5) was **explicitly waived by the user** for both bugs in this branch, so the fix went
straight from root-cause approval to implementation.

### Root Cause (approved 2026-08-10)
The tool-call path had no success-path logging at all:
1. `server.py::_call_with_error_boundary` — the single choke point all 14 tools pass through —
   minted a `correlation_id` per call but used it only in the `except` branch. On success it
   logged nothing: not the tool name, not the arguments, not the result.
2. Therefore **only raised exceptions ever reached the log** (via
   `errors.friendly_error_message`). The three failed `create_transaction_account` attempts for
   הסתדרות כללית חדשה were *refusals*, not exceptions —
   `_resolve_client_for_document_creation` returns a friendly message and the tool returns it —
   so nothing recorded them.
3. `MorningClient`/`tools.py` read the payload sent and the response received into local
   variables and discarded both. `add_client` discarded Morning's response outright, so the id
   Morning assigned a new client existed nowhere in this app.

The 88-line log is exactly what this code can emit; nothing was misconfigured.

### Fix (option C of three considered)
Correlated, two-layer audit trail:
- `utils/correlation.py` — a `ContextVar` carrying one correlation id per tool call, so the
  boundary's lines and the tools' lines can be joined without threading a parameter through
  every signature (a read of an explicitly-scoped context value, not monkey-patching).
- `server.py::_call_with_error_boundary` — logs `TOOL CALL` (tool name + caller-facing
  arguments, with the injected `MorningClient` dropped: it carries the credentials and is
  identical every call) and `TOOL OK`/`TOOL ERROR`. Result **length** only, never the body.
- `audit.py::log_mutation` — one line per Morning mutation, from all six document-creating
  tools plus `add_client`/`update_client`: resolved client id and name, payload sent, full
  response received, and an at-a-glance document summary (`id`/`number`/`total`/`status`/`type`).
- `audit.py::log_refusal` — the previously-silent decisions: client not found, ambiguous
  client, original not linked to a client.

Read tools are covered by the boundary lines only, deliberately without response bodies — a
`list_invoices` result can carry 100 documents and would bury the mutations this trail exists
to preserve.

Verified by exercising the real boundary with a fake client at the `MorningClient` seam: a
create logs requested `2360.0` alongside Morning's own `total: 2784.8` — i.e. the trail now
captures exactly the evidence bugfix-028 A2/A4 had to be reconstructed second-hand from
`denidin-app`'s logs. **Capturing** that total is all this bug covers; A4 (reporting the real
total back to the user) remains open and unchanged.

### Verification (2026-08-10)
Real MCP-protocol integration tests exercising the exact instrumented path passed unchanged
(`tests/integration/test_mcp_server_e2e.py`, `test_morning_sandbox_create_invoice_tool.py` —
8/8, including `test_mcp_tool_error_is_friendly_not_a_raw_stack_trace`, which hits the
error-boundary logging branch), morning-mcp-app's full unit suite (243/243), and denidin-app's
full unit suite (733/733) and its `tests/integration/` suite (29/29).

## Date Opened
2026-08-09

## Reported By
yaronlev171, from the 7–9 Aug 2026 production review
([`docs/production-analysis/2026-08-09-aug7-9-review.md`](../../docs/production-analysis/2026-08-09-aug7-9-review.md), P2-14).

> **Shared session context** — how this review was run, the read-only access paths, the full
> map of bugfix-028…037, the triage decisions (including what was closed as *not* a bug), and
> the open verification items:
> [`bugfix-028` § Session Context](bugfix-028-invoicing-and-approval-gate-p0-cluster.md#session-context-2026-08-09-production-review) (also in `specs/in-progress/bugfixes/`, sibling to this file, as of 2026-08-10).
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
- `specs/done/bugfixes/bugfix-028-invoicing-and-approval-gate-p0-cluster.md` — A4 needs the same
  response data this bug is about capturing.
