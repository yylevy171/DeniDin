# Data Model: 089 Agreements DB

SQLite file `{data_root}/agreements/agreements.db` (created on first start). All timestamps are
timezone-aware Israel local ISO strings from `now_local()`. Money is integer shekels, as in the
ledger (`_normalize_amount`).

## Tables

### `agreements`
| Column | Type | Notes |
|---|---|---|
| `row_id` | TEXT PK | Internal uuid hex, never exposed. |
| `agreement_id` | TEXT NOT NULL | Public id `MMYY-<client slug>-<title slug>` (`_slugify`), derived at creation; unique only among ACTIVE rows (partial unique index), so the id of a deleted agreement can be reused. Migrated rows keep their ledger value. |
| `is_active` | INTEGER NOT NULL DEFAULT 1 | `0` = soft-deleted; nothing is ever physically deleted and every query filters `is_active = 1`. |
| `title` | TEXT NOT NULL | Short agreement title (human decision 2026-10-09), part of the id. |
| `client_name` | TEXT NOT NULL | Official Morning client name (resolved upfront; migration resolves from the Clients-tab mapping). |
| `payer_name` | TEXT NULL | Only when different from the client. |
| `partner_name` | TEXT NULL | |
| `partner_percent` | REAL NULL | 0-100. |
| `status` | TEXT NOT NULL | `Active` / `Completed` / `Cancelled`. A new agreement is `Active`. |
| `created_at`, `updated_at` | TEXT NOT NULL | |

### `components`
| Column | Type | Notes |
|---|---|---|
| `component_key` | TEXT PK | Immutable uuid hex; the identifier used in API paths. |
| `component_id` | TEXT NOT NULL | Ledger convention (`agreement_id` + label slug). **Labels are unique within an agreement** (human decision 2026-10-09), so this is unique per agreement. |
| `agreement_id` | TEXT NOT NULL | The public agreement id (no FK: it is not unique across deleted rows). |
| `is_active` | INTEGER NOT NULL DEFAULT 1 | `0` = soft-deleted; every query filters `is_active = 1`. Nothing is ever physically deleted. |
| `label` | TEXT NOT NULL | |
| `description` | TEXT NULL | The wording. |
| `amount` | INTEGER NULL | |
| `percent` | REAL NULL | |
| `percent_base` | TEXT NULL | |
| `trigger_condition` | TEXT NULL | Non-empty means the component starts `Pending`. |
| `vat_status` | TEXT NULL | Same vocabulary as the ledger. |
| `txn_date` | TEXT NULL | |
| `status` | TEXT NOT NULL | `Pending` / `Active` / `Completed` / `Cancelled`. |
| `origin_event_id` | TEXT NULL | Event id of the component's first ledger event; target of a delete's `reference`. |
| `sort_order` | INTEGER NOT NULL | Display order. |

A component must have an `amount` or a `percent` (a fee has a value). Hours-worked lines never
enter this table (REQ-089-13).

### Revisions - removed (human decision 2026-10-13)
The earlier `revisions` table (an append-only log of every write) no longer exists: no table, no API route, no UI
view. A write that changes nothing is still a no-op (no ledger event). The ledger events are the only history. A
database created before this decision may still carry an unused `revisions` table; nothing reads or writes it.

## State rules (REQ-089-05/06)

Component status:

```
create:  trigger_condition set -> Pending ; otherwise -> Active
Pending   --mark active-->  Active
Active    --mark completed-> Completed        (locks the component)
Pending|Active --cancel-->  Cancelled         (locks the component)
Completed|Cancelled --reopen--> Active        (unlocks; only if the agreement is Active)
```

Agreement status: `Active` <-> `Completed` | `Cancelled` (any closed -> `Active` by reopen).

Agreement close cascade (human decision 2026-10-09), applied in the same transaction:

| Agreement action | Each component that is... | ...becomes |
|---|---|---|
| Mark Completed | Active | Completed |
| Mark Completed | Pending | Cancelled |
| Mark Completed | Completed / Cancelled | unchanged |
| Cancel | Pending or Active | Cancelled |
| Cancel | Completed / Cancelled | unchanged |
| Reopen | any | unchanged (agreement only -> Active) |

**Locked** = the component is Completed/Cancelled, or its agreement is not Active. A write to a
locked component other than Reopen-of-the-component (when allowed) fails with `locked`.

## Ledger events produced by a write

| Write | Events | Content |
|---|---|---|
| create agreement | 1 per component, `הסכם`/`יצירה` | full component state + agreement-level values; `original_client_name` empty |
| add component | 1 | the new component |
| edit component (any field, incl. wording) | 1 | the component's full new state |
| set component status | 1 | the component, with `component_status` |
| edit agreement (payer/partner/partner %) | 1 per component | each component's full state + new agreement-level values |
| set agreement status (close / reopen) | 1 per component (after the cascade) | each component's full state + `agreement_status` |
| delete component | 1, `הסכם`/`ביטול` | `reference` = component's `origin_event_id` |

Event field mapping: `client_name`, `payer_name`, `split_partner` <- `partner_name`,
`split_percent` <- `partner_percent`, `agreement_id`, `component_id`, `component_label` <- `label`,
`description`, `amount`, `percent`, `percent_base`, `trigger_condition`, `vat_status`, `txn_date`,
and the new `component_status`, `agreement_status` (schema v4). `source_type` = `הסכם`,
`hours` = null, `session_id`/`message_id` = null for UI and migration writes (the bot supplies its
own). **Field list approved by the human, 2026-10-09 (research.md R5).**

## Ledger schema v4 (REQ-089-10), for reference

Adds `original_client_name`, `component_status`, `agreement_status` to `LEDGER_EVENT_FIELDS`;
`split_partner` / `split_percent` become populated for agreement-component events.
`CURRENT_SCHEMA_VERSION` 2 -> 4 and the matching `SCHEMA_VERSION_HISTORY` entry in the same commit.
Only agreement-component `הסכם` events are rewritten by the migration; hours-worked, bank and
invoice events keep their schema version. New v4 events from non-agreement sources are written
with the new keys null.

## Name-resolution handoff file (`name_resolution.json`)

```json
{
  "generated_at": "2026-10-09T12:00:00+03:00",
  "clients": {
    "<raw ledger client name>": {
      "official_name": "<Morning name>" | null,
      "line_closed": true,
      "agreed": 12000,
      "paid": 12000
    }
  }
}
```
