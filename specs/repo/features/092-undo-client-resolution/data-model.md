# Data Model: Feature 092

All files live in the webapp's own writable `clients_data_root`
(`{webapp_data_root}/clients/`), never in denidin-app's read-only ledger mount. They're written
with the existing `_save_json` helper (UTF-8, `ensure_ascii=False`, indent 2) and read with
`_load_json` (missing or corrupt → empty).

## New files

### `client_status.json` — per-line explicit status
```json
{ "<official_name>": "closed" | "check" | "active" }
```
- An absent key means the section is computed from the numbers.
- Allowed values are exactly those three. An unknown value is ignored on read, with a WARNING.

**State transitions (button actions, spec R5–R8):**

| Current section | לסגור | לפתוח | לבדוק | לקוח פעיל |
|---|---|---|---|---|
| `check` | → `closed` | — | (hidden) | → `active` |
| `active` | → `closed` | — | → `check` | (hidden) |
| `debt` / `missing_agreement` | → `closed` | — | → `check` | → `active` |
| `settled` (closed **or** computed) | — | agreed==paid → `active`; else delete key | → `check` | → `active` |
| `past` | no buttons | no buttons | no buttons | no buttons |

### `hidden_unmatched.json` — names dropped from the resolve list
```json
[ "<raw_name>", ... ]
```
A sorted list of unique names. It's append-only from the UI, and there is no unhide by spec.

### `migrations.json` — one-shot migration markers
```json
{ "092_comment_line_status": "2026-10-04T09:12:00+03:00" }
```

## Unchanged files

- `client_comments.json` — still read for delete/merge/agreement/`להוריד`/amount-colour
  parsing. **No longer** read for `לסגור`, `לבדוק` or `לקוח פעיל` routing. It's never written
  by the migration.
- `client_mapping.json` — unchanged shape. Gains a **delete** operation (unlink). Keys may now
  be `Unknown-<event_id>`.
- `mapping_notes.json` — unchanged. A note survives unlinking, which is what restores the
  resolve-list line "with its note".

## Derived (report payload) changes

`GET /api/clients` → `clients[]` rows gain:

| Field | Type | Meaning |
|---|---|---|
| `line_status` | `"closed" \| "check" \| "active" \| null` | The stored override, if any |
| `mapped_aliases` | `string[]` | The subset of `raw_names` that are explicit `client_mapping.json` keys → this client; only these show "unlink" |

- `is_manually_settled` stays and now means `line_status == "closed"`.
- `agreed_status` / `paid_status` no longer get the `*_inferred` YELLOW set by closing.

`unmatched[]` rows: no shape change. A no-name event now appears as its own row
(`raw_name = "Unknown-<event_id>"`, `event_count = 1`).
