# Bugfix Spec: A Hebrew `status` value in `list_invoices` returns "no invoices found" instead of an error

## Bug ID
bugfix-031-hebrew-status-value-returns-empty-instead-of-error

## Title
`list_invoices`'s `status` filter accepts only English keywords (`paid`/`unpaid`/`overdue`/
`cancelled`/`all`) but is typed as a plain `str` with **no validation**. Passing the Hebrew
label — the same label the tool's own output prints — silently matches nothing and returns a
confident *"no invoices found"* rather than reporting a bad value.

## Priority
**P2** — a wrong, confident answer to a financial question. Self-corrected by the model in the
observed case, but the failure mode is silent.

## Status
**Open — backlogged.** No fix designed. Per Bug-Driven Development (METHODOLOGY.md §VII), next
step is human approval of the root cause before test-gap analysis.

> **Filed despite uncertainty at triage** (Yaron, 2026-08-09: *"I'm not even sure this is a
> bug, don't understand what enum is involved"*). The clarification is in "What the 'enum' is"
> below — it is a real defect, and it is the **same shape as bugfix-028 B4**: our own output is
> not accepted as our own input.

## Date Opened
2026-08-09

## Reported By
yaronlev171, from the 7–9 Aug 2026 production review
([`docs/production-analysis/2026-08-09-aug7-9-review.md`](../../docs/production-analysis/2026-08-09-aug7-9-review.md), P2-3).

> **Shared session context** — how this review was run, the read-only access paths, the full
> map of bugfix-028…037, the triage decisions (including what was closed as *not* a bug), and
> the open verification items:
> [`bugfix-028` § Session Context](../done/bugfixes/bugfix-028-invoicing-and-approval-gate-p0-cluster.md#session-context-2026-08-09-production-review) (now in `specs/done/bugfixes/`).
> All ten bugs in that set are **fix-forward only** — existing production documents are being
> left as they are by explicit user decision.

## Affected Area
- `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py` — `list_invoices` (`status`
  parameter, local status filter)
- `apps/morning-mcp-app/src/denidin_mcp_morning/formatters.py` — `translate_status`,
  `_STATUS_HE`

## What the "enum" is

There is no `Enum` type in the code — that is precisely the problem. `list_invoices` declares:

```python
def list_invoices(
    client: MorningClient,
    status: Optional[str] = None,        # ← plain str, unvalidated
    ...
```

with the permitted values living **only in the docstring**:

> `status: Optional filter — "paid", "unpaid", "overdue", "cancelled", or "all".`

So "the enum" means: *the fixed set of five English keywords this parameter is supposed to
accept, which nothing actually enforces.*

## The loop that produces the bug

1. `formatters.translate_status` (`_STATUS_HE`) renders results for the user in Hebrew:
   `unpaid` → **`לא שולם`**.
2. The model reads its own earlier output and, reasonably, passes that Hebrew label back as a
   filter value.
3. `status="לא שולם"` matches none of the five English keywords, the local filter excludes
   everything, and the tool answers **`לא נמצאו חשבוניות התואמות את החיפוש.`**

Observed live, Aug 9 (prod log):

```
list_invoices {"status":"unpaid","from_date":"2026-08-01","to_date":"2026-08-31"}
  → נמצאו 5 חשבוניות: …                                    ← correct

list_invoices {"from_date":"2026-08-01","to_date":"2026-08-31","status":"לא שולם"}
  → לא נמצאו חשבוניות התואמות את החיפוש.                    ← wrong: says none exist
```

The model then retried without the status filter and recovered — but a user reading only the
middle answer would conclude there are no unpaid invoices, which is false.

## Expected
An unrecognised `status` value must be **rejected explicitly** (a friendly error naming the
accepted values), never answered with an empty result set. Ideally the Hebrew labels the tool
itself emits should also be accepted as input, closing the output→input loop.

## Related Work
- `specs/done/bugfixes/bugfix-028-invoicing-and-approval-gate-p0-cluster.md` — **B4** is the same
  class of defect on `client_name`: `list_clients` prints a display label that `create_*`
  then refuses. Worth fixing with a shared principle: *anything we print must be accepted back,
  or must be clearly not-an-identifier.*
