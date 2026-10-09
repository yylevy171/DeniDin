# Data Model: 089 Agreements DB

SQLite file `{data_root}/agreements/agreements.db` (created on first start). All timestamps are
timezone-aware Israel local ISO strings from `now_local()`. Money is integer shekels, as in the
ledger (`_normalize_amount`).

## Tables

### `agreements`
| Column | Type | Notes |
|---|---|---|
| `agreement_id` | TEXT PK | Same slug convention as the ledger's `agreement_id` (`_slugify`); migrated rows keep their ledger value. |
| `client_name` | TEXT NOT NULL | Official Morning client name (resolved upfront; migration resolves from the Clients-tab mapping). |
| `payer_name` | TEXT NULL | Only when different from the client. |
| `partner_name` | TEXT NULL | |
| `partner_percent` | REAL NULL | 0-100. |
| `status` | TEXT NOT NULL | `Active` / `Completed` / `Cancelled`. A new agreement is `Active`. |
| `created_at`, `updated_at` | TEXT NOT NULL | |

### `components`
| Column | Type | Notes |
|---|---|---|
| `component_id` | TEXT PK | Ledger convention (`agreement_id` + label slug); unique within the DB. |
| `agreement_id` | TEXT FK | |
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

### `revisions`
| Column | Type | Notes |
|---|---|---|
| `revision_id` | INTEGER PK AUTOINCREMENT | Total order = chronological order. |
| `agreement_id` | TEXT NOT NULL | Kept after a component delete. |
| `component_id` | TEXT NULL | Null for agreement-level revisions. |
| `actor` | TEXT NOT NULL | `webapp` / `whatsapp` / `migration`. |
| `action` | TEXT NOT NULL | `create_agreement`, `edit_agreement`, `add_component`, `edit_component`, `set_component_status`, `set_agreement_status`, `delete_component`, `cascade`. |
| `snapshot_json` | TEXT NOT NULL | Full new state of the agreement or component after the change. |
| `changed_json` | TEXT NOT NULL | `{field: [old, new]}` for display. |
| `ledger_event_ids_json` | TEXT NOT NULL | Event ids this write produced (empty list if the ledger write failed; the failure is logged at ERROR). |
| `created_at` | TEXT NOT NULL | |

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
