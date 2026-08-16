# Phase 1 Data Model: Reminders — Functionality and Management

**Feature**: 054-reminders-functionality-mgmt · **Date**: 2026-08-16

## Storage

`{data_root}/reminders/reminders.db` — one SQLite database (stdlib `sqlite3`, no new dependency
for storage itself), chosen over a per-entity-JSON-file layout (the `LedgerEventManager` pattern
elsewhere in this codebase) because reminders are mutable and query-heavy (the delivery sweep
needs "what's due right now," `list_reminders` needs "all active reminders," modify/delete need
efficient lookup) in a way JSON-file-plus-directory-glob does not serve well — unlike ledger
events, which are write-once/append-only and file-per-record is the right shape for.

**The schema is genuine iCalendar (RFC5545) data, not a lookalike.** A reminder's recurring
schedule is stored as a real VEVENT (`RRULE`/`DTSTART`/`UID`), and single-occurrence
modifications/cancellations are stored as real per-occurrence override VEVENTs sharing the
master's `UID`, keyed by a real `RECURRENCE-ID` — the same mechanism every real calendar app
(Google/Outlook/Apple Calendar) uses for "edit just this occurrence." This is deliberately not
reinvented: `icalendar` (RFC5545 (de)serialization) and `recurring_ical_events` (built on
`icalendar`, computes concrete due occurrences for a time window, correctly resolving
`RECURRENCE-ID` overrides and `STATUS=CANCELLED` exceptions) are new dependencies added for this.
A stored reminder could in principle be exported/imported as a real `.ics` file, though no such
feature is being built now.

## Table: `reminders` (the master VEVENT)

| Column | Type | iCal mapping | Population rule |
|---|---|---|---|
| `reminder_id` | `TEXT PRIMARY KEY` | `UID` | `uuid4()` at creation, immutable |
| `message_text` | `TEXT` | `SUMMARY` | the text delivered when this reminder (or an occurrence without its own override) fires |
| `rrule` | `TEXT \| NULL` | `RRULE` | a literal RFC5545 RRULE string (e.g. `FREQ=WEEKLY;BYDAY=MO,TH;COUNT=5`); `NULL` for a one-time reminder |
| `dtstart` | `TEXT` (ISO-8601, Asia/Jerusalem) | `DTSTART` | for one-time: the single due datetime; for recurring: the first occurrence's datetime — always rounded to the nearest 5 minutes (ties round up) before storage, so the approval summary shown to the user already reflects the exact time that will fire |
| `status` | `TEXT` (`active`\|`cancelled`) | — (DeniDin-internal) | `active` at creation; `cancelled` only via a whole-series delete |
| `created_at` | `TEXT` (ISO-8601) | — | `time_utils.local_isoformat()` at creation |
| `created_by_phone` | `TEXT` | — | whoever (godfather or admin) actually performed the create action — traceability only, never used for ownership/access decisions (see "Ownership" below) |
| `created_by_role` | `TEXT` (`GODFATHER`\|`ADMIN`) | — | same traceability purpose |

## Table: `reminder_exceptions` (per-occurrence override VEVENTs, sharing the master's `UID`)

| Column | Type | iCal mapping | Population rule |
|---|---|---|---|
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | — | row id |
| `reminder_id` | `TEXT` (FK → `reminders.reminder_id`) | shared `UID` | which series this exception belongs to |
| `recurrence_id` | `TEXT` (ISO-8601) | `RECURRENCE-ID` | the original occurrence datetime (per the plain `rrule`) that this row overrides — the key identifying *which* occurrence |
| `dtstart_override` | `TEXT \| NULL` (ISO-8601) | `DTSTART` (on the override VEVENT) | the new due datetime, if rescheduled; rounded to the nearest 5 minutes same as the master; `NULL` if this row is a pure cancellation |
| `summary_override` | `TEXT \| NULL` | `SUMMARY` (on the override VEVENT) | the new message text, if changed; `NULL` to inherit the master's `message_text` |
| `status` | `TEXT` (`CONFIRMED`\|`CANCELLED`) | `STATUS` | `CONFIRMED` = this occurrence still fires, at its overridden time/text; `CANCELLED` = this occurrence is suppressed entirely, matching real calendar apps' single-occurrence-delete convention |

**Permanence rule**: once a row exists here for a given `recurrence_id`, it is permanent relative
to the series — a later whole-series edit (changing `reminders.rrule`/`message_text`) never
touches or removes an existing exception row. An occurrence that has been detached "has a life of
its own and can never return to the rule" (user's framing, 2026-08-16) — exactly RFC5545's own
`RECURRENCE-ID` override semantics.

## Table: `fired_occurrences` (DeniDin-internal delivery history — not an iCalendar concept)

| Column | Type | Population rule |
|---|---|---|
| `id` | `INTEGER PRIMARY KEY AUTOINCREMENT` | row id |
| `reminder_id` | `TEXT` (FK) | which series this firing belongs to |
| `occurrence_datetime` | `TEXT` (ISO-8601) | the due datetime that actually fired (post any override) |
| `delivered_at` | `TEXT` (ISO-8601) | when the send actually completed |
| `message_text_sent` | `TEXT` | the exact text delivered (post any override) — kept verbatim even if the series' `message_text` is edited later |

Append-only, one row per actual past firing — naturally bounded by elapsed time regardless of
whether the series' end condition is `never`, since a row is only ever written for an occurrence
that has genuinely already happened, never pre-computed for the future. This is what makes
`FR-009`'s "each occurrence individually trackable" requirement possible without needing to
materialize an unbounded future.

## Sweep resolution logic (unified for one-time and recurring — no special-casing)

Each 5-minute sweep tick (triggered by APScheduler's `CronTrigger(minute='*/5')`, see
`contracts/reminder-delivery.md`), for every `reminders` row with `status = 'active'`:

1. Reconstruct an `icalendar.Calendar` containing the master VEVENT (`UID`, `RRULE`, `DTSTART`,
   `SUMMARY` from the `reminders` row) plus one override VEVENT per matching `reminder_exceptions`
   row (`UID` shared, `RECURRENCE-ID`, `DTSTART`/`SUMMARY` if overridden, `STATUS`).
2. Call `recurring_ical_events.of(cal).between(window_start, window_end)` for the current sweep
   window — the library resolves `RRULE` expansion, `RECURRENCE-ID` overrides, and
   `STATUS=CANCELLED` suppression internally; nothing about that resolution is hand-rolled.
3. A one-time reminder (`rrule IS NULL`) is just a VEVENT with no `RRULE` — the same library call
   handles it identically (a single-instance calendar event), so there is exactly one code path
   for both reminder types, not two.
4. For whatever concrete occurrence(s) the library returns as due in this window: deliver (see
   `contracts/reminder-delivery.md`), then insert a `fired_occurrences` row. No cached
   "next due" pointer is maintained on the `reminders` table — recomputed fresh every tick,
   trading a small amount of per-tick CPU (negligible at this app's scale — a cap of 20 reminders
   total) for never letting a cache drift out of sync with the exceptions table.

**On the `pending` status (spec.md FR-009/Terminology Glossary)**: `pending` is a **derived**
state, never a literal stored column value anywhere in this schema. An occurrence is `pending` iff
`recurring_ical_events` would currently generate it as a future/imminent occurrence of an active
reminder AND no `reminder_exceptions` row for its date has `status='CANCELLED'`. It becomes
`fired` the instant a `fired_occurrences` row is inserted for it (step 4 above), and `cancelled`
only by an explicit `reminder_exceptions` row (single occurrence) or the whole reminder's own
`status='cancelled'` (whole series). No table has a `pending` value in a `status` column — code
implementing FR-009's "each occurrence individually inspectable" requirement (e.g. for
`list_reminders`, FR-013) must compute this three-way state on read, not look it up.

## Ownership

There is conceptually **one** reminder list, owned by "the godfather" (`config.godfather_phone`
today; forward-compatible with `specs/backlog/055-multiple-clients-godfathers/` if that ever
ships — a future multi-godfather world would scope this per-godfather, not per-acting-user).
GODFATHER manages it directly; ADMIN can too, but only as an instance of this app's *existing*
"ADMIN has access to everything" blanket-access pattern — **not** a reminder-specific cross-user
override. `created_by_phone`/`created_by_role` record who actually performed each action for
traceability, but neither field gates access, ownership, or the FR-006 active-reminder cap — the
cap (20) is scoped to the one reminder list as a whole, not per acting identity.

**Delivery target is a fixed heuristic, not "the chat it was created from."** Every reminder
always fires to the godfather's own direct 1:1 WhatsApp chat with DeniDin
(`{godfather_phone}@c.us`, resolved from config), regardless of what chat (1:1 or a group) the
create/modify/delete conversation actually happened in, and regardless of whether godfather or
admin performed the action. No `chat_id` column exists on `reminders` — it is computed at
delivery time from `config.godfather_phone`, never stored per-row, so a future config change to
that value is picked up automatically rather than requiring a data migration. A general
"let the creator pick an arbitrary target chat/group" capability (via Green API's `getContacts()`)
was explicitly considered and deferred — not built now.

## Validation rules

- `reminder_id` MUST be unique (enforced by the `PRIMARY KEY` constraint, `uuid4()` collision not
  independently defended against beyond birthday-bound probability).
- `created_by_phone` MUST resolve (via `UserManager.get_user`) to role `GODFATHER` or `ADMIN` at
  creation/modification/deletion time (FR-001) — not re-validated at delivery time (role changes
  after the fact don't affect firing — delivery is keyed to the fixed godfather chat, not to
  whoever created the reminder).
- One-time reminder (`rrule IS NULL`): `dtstart` MUST NOT be in the past at creation, after
  rounding (FR-005).
- Recurring reminder: the RRULE string MUST NOT encode a yearly frequency (`FREQ=YEARLY` is
  rejected at construction — FR-007 excludes it structurally, not just by convention); `dtstart`
  (the first occurrence) MUST NOT be in the past after rounding; if the RRULE has an `UNTIL`
  component, that date MUST NOT be in the past at creation.
- A `reminders` row with `status = 'cancelled'` MUST NOT count against the FR-006 active-reminder
  cap, and MUST be excluded from `list_reminders` results by default.
- `reminder_exceptions.status = 'CANCELLED'` rows MUST still be included when reconstructing the
  calendar for sweep purposes (so `recurring_ical_events` correctly suppresses that occurrence) —
  never simply deleted from the table, since deleting one would let the plain `rrule` regenerate
  that occurrence again, silently un-cancelling it.

## Entity: `PendingLocalToolApproval` (new, in-memory only — see `contracts/local-tool-approval-gate.md`)

Not disk-persisted (same rationale as the existing `PendingApproval`: losing one on restart just
means the user re-issues the request). Full contract in the linked document; field summary:
`tool_name` (`create_reminder`\|`modify_reminder`\|`delete_reminder`), `arguments` (already-parsed
dict, not a JSON string), `created_at`, `sent_message_id` (`Optional[str]`, for button-tap
staleness binding, same mechanism as Feature 047's `PendingApproval.sent_message_id`).
