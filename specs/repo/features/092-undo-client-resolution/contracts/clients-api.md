# API Contract: Feature 092 — new/changed Clients endpoints

- All endpoints are behind the existing bearer session auth. They return `401` without it, as
  every `/api/*` route does today.
- Errors use the existing `_error(code, message, status)` shape:
  `{"error": code, "message": "<Hebrew, friendly>"}`.
- Every successful write invalidates the report cache (`self._report_cache = None`), the same
  as `save_comment`/`save_mapping`. The frontend then re-fetches `GET /api/clients` (without
  `refresh=1`, so there's no Morning round-trip) to re-route lines.

---

## `POST /api/clients/{client_id}/status` — line-status button (spec R5–R8)

Request:
```json
{ "action": "close" | "reopen" | "check" | "active" }
```

| Case | Response |
|---|---|
| OK | `200 {"client_id": "...", "line_status": "closed" \| "check" \| "active" \| null}` |
| `action` missing or not one of the four | `400 bad_request` |
| `client_id` not an official (non-merged-away) client in the current report | `404 not_found` |
| line is `past` | `409 not_allowed` — "לא ניתן לשנות סטטוס ללקוח עבר." |

Semantics:
- `close` → `closed`.
- `check` → `check`.
- `active` → `active`.
- `reopen` → computed with the status cleared. If that's `settled` (agreed == paid > 0), store
  `active`; otherwise delete the key and return `null` (research R-3).
- A no-op action, such as `check` on a line already `check`, is accepted and idempotent.
  The UI hides that button anyway.

## `POST /api/clients/mapping/unlink` — undo a name mapping (spec R3)

Request:
```json
{ "raw_name": "Yisrael I" }
```

| Case | Response |
|---|---|
| OK (the key existed and was removed) | `200 {"raw_name": "...", "unlinked_from": "<official_name>"}` |
| `raw_name` missing or empty | `400 bad_request` |
| no such key in `client_mapping.json` | `404 not_found` |

- It removes only the `client_mapping.json` key. `mapping_notes.json` is untouched, so the
  note comes back with the line.

## `POST /api/clients/unmatched/hide` — "הסר מהרשימה" (spec R1)

Request:
```json
{ "raw_name": "..." }
```

| Case | Response |
|---|---|
| OK | `200 {"raw_name": "...", "hidden": true}` (idempotent) |
| `raw_name` missing or empty | `400 bad_request` |

## `GET /api/clients` — payload additions only

See `data-model.md` → "Derived (report payload) changes". This is additive only: existing
fields keep their names and types.

## Unchanged

- `POST /api/clients/{client_id}/comments` keeps the same contract, but its text no longer
  drives `לסגור`/`לבדוק`/`לקוח פעיל` routing.
- `POST /api/clients/mapping` is unchanged.
