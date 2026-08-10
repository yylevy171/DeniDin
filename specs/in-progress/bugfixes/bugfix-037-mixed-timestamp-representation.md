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
**Fixed** — branch `bugfix/036-037-mcp-audit-trail-and-timestamp-representation`, fixed
together with bugfix-036 (2026-08-10). Root cause approved by the user; the failing-test gate
(METHODOLOGY.md §VII steps 3-5) was **explicitly waived by the user** for both bugs in this
branch.

### Root Cause (approved 2026-08-10)
Three representations, only one of them self-describing:
1. **Local, unlabelled** — `event_date`/`event_time` and `event_id`'s `DDMMYY`/`HHMM` derive
   from `local_dt` (Asia/Jerusalem). Deliberate and correct (Events.csv's columns are Israeli
   local time, confirmed 2026-07-29) but the decision lived **only in a source comment**.
2. **UTC, labelled** — `captured_at`/`message_timestamp` carried an explicit `+00:00`.
3. **Logs — UTC only by accident.** Both apps' `logger.py` used `logging.Formatter` with
   `%(asctime)s` and no `converter` override, i.e. `time.localtime`. Nothing sets `TZ` in the
   Dockerfiles or compose files, so containers inherit Docker's UTC default and prod logs
   *happened* to be UTC — while the same code under host `pytest` wrote Asia/Jerusalem times in
   the identical unlabelled format. The "logs are UTC" line in
   `docs/production-analysis/README.md` was true of the prod container, not of the code.

### Fix (user directive, 2026-08-10)
Rather than any of the three options this spec proposed, the user directed a fourth:
**everything is Israel local time now — logs, events, sessions, status files, all of it. No UTC
anywhere.** Rationale: the data the system handles is already local (Morning documents and bank
screenshots state Israeli local times, Events.csv always has), so the representation now matches
the domain instead of being converted at the edges.

- `utils/time_utils.py` — new, one per app (byte-identical twins, same convention as
  `logger.py`): `LOCAL_TZ`, `now_local()`, `to_local()`, `local_from_timestamp()`,
  `local_isoformat()`. Every datetime is timezone-**aware**; naive local values stay forbidden
  (they break comparisons and get DST wrong twice a year).
- All 28 `datetime.now(timezone.utc)` call sites across both apps replaced with `now_local()`.
  Epoch-valued fields are unaffected in meaning — an epoch is an instant, not a representation.
- `LocalTimeFormatter` in both apps' `logger.py` (and both `conftest.py` test-log formatters):
  timestamps are Asia/Jerusalem **by construction, not by container TZ**, and print the real
  offset (`2026-08-09 06:00:27+0300`). A `Formatter` subclass rather than a `converter`
  reassignment: `converter` works on `time.struct_time`, whose `%z` reports the *system* zone —
  precisely the ambiguity being removed — and patching it would be monkey-patching.
- **`.github/CONSTITUTION.md` §II was amended** from "UTC Timestamp Requirement" to "Israel
  Local Time Requirement", plus §IX's logging rule; `quick-ref-constitution.md`, `CLAUDE.md`,
  and `docs/production-analysis/README.md` updated to match. This is a governance change made
  by explicit user decision, recorded here because the constitution is binding.
- Documented in **`.github/ARCHITECTURE.md` §4a** ("Timestamp Representation"), the
  data-model documentation this spec's Expected section asked for.

**Fix-forward, no migration.** Records written before 2026-08-10 keep `+00:00` and still compare
correctly against new ones, since both sides are timezone-aware. Only pre-2026-08-10 *log lines*
remain genuinely ambiguous (they carry no offset at all); the review runbook now says so.

**bugfix-034 L7** (`event_date` is the capture date, not the transaction date) was deliberately
left out of scope — it is a different defect in the same fields. This fix is purely additive to
those fields' meaning, so it does not conflict with L7 being fixed later.

## Date Opened
2026-08-09

## Reported By
yaronlev171, from the 7–9 Aug 2026 production review
([`docs/production-analysis/2026-08-09-aug7-9-review.md`](../../docs/production-analysis/2026-08-09-aug7-9-review.md), P3-4).

> **Shared session context** — how this review was run, the read-only access paths, the full
> map of bugfix-028…037, the triage decisions (including what was closed as *not* a bug), and
> the open verification items:
> [`bugfix-028` § Session Context](bugfix-028-invoicing-and-approval-gate-p0-cluster.md#session-context-2026-08-09-production-review).
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
