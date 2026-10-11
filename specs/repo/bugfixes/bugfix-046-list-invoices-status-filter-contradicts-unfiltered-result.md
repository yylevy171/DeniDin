# Bugfix Spec: `list_invoices` status filter contradicts its own unfiltered result

## Bug ID
bugfix-046-list-invoices-status-filter-contradicts-unfiltered-result

## Title
`list_invoices(client_name=..., status="שולם")` (paid-only filter) returns "no matching
invoices found" for a client that an immediately-preceding, unfiltered `list_invoices(client_name=...)`
call — in the very same conversation — just showed several `שולם` (paid) documents for.

## Priority
**Not yet triaged.** Recorded as reported; no root cause investigation done yet.

## Status
**Open — root cause NOT YET investigated.** Per Bug-Driven Development (METHODOLOGY.md §VII),
this spec records only the reported symptom for now. No code has been read or changed for this
bug. Root cause is to be investigated and presented for explicit human approval before any
test-gap analysis or fix work begins.

## Date Opened
2026-08-26

## Reported By
yaronlev171, filed via a batch of 3 findings ("bugfix is 46") during Feature 044's closing
regression sweep.

## Symptom (as reported, verbatim)
> "File a new bug: Morning's `list_invoices` status filter returns an empty/contradictory
> result."

## Evidence (pulled 2026-08-26, from a real billed E2E test run — verbatim MCP call/output pairs,
per CLAUDE.md's "SHOW ME THE FULL CONVERSATION" rule)

Uncovered by
`tests/billed/test_denidin_morning_list_invoices_e2e.py::test_client_explicit_everything_request_gets_the_complete_picture`
during the 2026-08-26 random-20-billed-test regression sweep, against the real Morning sandbox
client `דורית אשכנזי` (the fixture's `_GROUND_TRUTH_CLIENT_NAME`, invoices `#50854`-`#50859`).

**Call 1 — unfiltered, same turn's tool-call sequence:**
```
name: list_invoices
arguments: {"client_name":"דורית אשכנזי","name_resolved":true}
output: מוצגות 7 מתוך 8 חשבוניות שנמצאו:

חשבונית #80205
לקוח: "דורית אשכנזי"
סכום: ₪38.00
סוג מסמך: קבלה
תיאור: תשלום עבור חשבונית מספר 50855
סטטוס: שולם
תאריך הפקה: 28/07/2026
...
[several more documents, multiple with סטטוס: שולם]
```

**Call 2 — same client, `status="שולם"` filter added, moments later:**
```
name: list_invoices
arguments: {"status":"שולם","client_name":"דורית אשכנזי","name_resolved":true}
output: לא נמצאו חשבוניות התואמות את החיפוש.
error: None
```

No error was raised on either call — both returned HTTP-success-shaped tool output, just
contradictory content. `error: None` on both rules out a request-level failure; this is either a
parameter-encoding mismatch (e.g. `status="שולם"` not matching Morning's actual expected status
value/enum for the filtered endpoint) or a status-value/document-type interaction specific to the
filtered query path.

## Root Cause Hypothesis (unconfirmed — needs code review, not yet done)
Not yet investigated. Candidates to check once approved:
- `apps/morning-mcp-app`'s `list_invoices` tool implementation — how the `status` parameter is
  translated into the actual Morning API request (a Hebrew UI-facing status string vs. Morning's
  real status code/enum could easily mismatch).
- Whether the *unfiltered* call's `שולם` documents are a mix of document types (e.g. transaction
  accounts/receipts alongside invoices) that the filtered endpoint silently excludes for a reason
  unrelated to "paid" status at all.

## Affected Area (candidate, pending code review)
- `apps/morning-mcp-app/src/denidin_mcp_morning/` — `list_invoices` tool and whatever Morning API
  parameter it maps `status` to.

## Next Steps
1. Present these findings for explicit human approval before any code is read for a fix or any
   test-gap analysis begins.
2. Once approved: read `list_invoices`'s actual implementation and Morning's status
   filter/query-parameter contract to confirm (or correct) the hypothesis above against real code
   — not yet done.
3. Only after that: test-gap analysis → failing test → human approval → minimal fix → verify,
   per METHODOLOGY.md §VII.
