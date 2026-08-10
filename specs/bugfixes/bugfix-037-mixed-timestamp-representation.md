# Bugfix Spec: Timestamps are stored in mixed representations across stores

## Bug ID
bugfix-037-mixed-timestamp-representation

## Title
The same moment in time is recorded in UTC in some places and Israel local time (IDT, UTC+3)
in others, with nothing in the field names or the data model saying which is which.

## Priority
**P3** — nice to have. No incorrect behaviour observed; this is a correctness-of-interpretation
hazard for humans and for any future code that compares across stores.

## Status
**Open — backlogged.** No fix designed. Per Bug-Driven Development (METHODOLOGY.md §VII), next
step is human approval of the root cause before test-gap analysis.

## Date Opened
2026-08-09

## Reported By
yaronlev171, from the 7–9 Aug 2026 production review
([`docs/production-analysis/2026-08-09-aug7-9-review.md`](../../docs/production-analysis/2026-08-09-aug7-9-review.md), P3-4).

> **Shared session context** — how this review was run, the read-only access paths, the full
> map of bugfix-028…037, the triage decisions (including what was closed as *not* a bug), and
> the open verification items:
> [`bugfix-028` § Session Context](../in-progress/bugfixes/bugfix-028-invoicing-and-approval-gate-p0-cluster.md#session-context-2026-08-09-production-review) (moved to `specs/in-progress/bugfixes/` 2026-08-10).
> All ten bugs in that set are **fix-forward only** — existing production documents are being
> left as they are by explicit user decision.

## Affected Area
- `apps/denidin-app/src/managers/ledger_event_manager.py` — `event_id`, `event_date`,
  `event_time` generation
- `apps/denidin-app/src/models/` — session/message/event timestamp fields
- Log formatter configuration (both apps)
- Any future doc under `docs/` describing the event data model

## Description
Three representations coexist, all correct in isolation, none labelled:

| Field / source | Representation | Example (same event) |
|---|---|---|
| Log lines (both apps) | **UTC** | `2026-08-09 03:00:27` |
| `captured_at`, `message_timestamp` | **UTC**, explicit offset | `2026-08-09T03:00:27.399417+00:00` |
| `event_time`, `event_date`, `event_id` | **Local IDT (UTC+3)**, no offset | `06:00`, `09/08/2026`, `B09082606000` |

So event `B09082606000` reads as "06:00" while its own `captured_at` says `03:00:27+00:00` and
the log line for it says `03:00:27`. All three describe the same instant.

CONSTITUTION requires `datetime.now(timezone.utc)` everywhere, which the UTC fields honour.
The ledger's local-time fields are a deliberate human-readability choice (an Israeli user
reading `06:00` wants their own morning), but nothing records that decision in the data or the
model.

**Concrete hazard, already hit during this review:** comparing an `event_id` timestamp against
a log timestamp appears to show a 3-hour discrepancy that does not exist. Any future
reconciliation code that joins events to log entries or to Morning documents by time will get
this wrong unless it happens to know.

## Expected
Either:
- carry an explicit offset on the local-time fields, or
- rename them so the representation is unambiguous (`event_time_local` / `event_date_local`), or
- store UTC and render local only at display time.

Whichever is chosen, document it in the ledger-event data model so the next reader doesn't have
to derive it.

## Related Work
- `.github/CONSTITUTION.md` — the UTC-everywhere rule the UTC fields already follow.
- `specs/bugfixes/bugfix-034-ledger-bugs.md` — **L7** (`event_date` is the capture date, not
  the transaction date) is a *different* problem in the same fields; if both are fixed, do them
  together.
- `docs/production-analysis/README.md` — the read-only runbook already warns reviewers about
  this mismatch.
