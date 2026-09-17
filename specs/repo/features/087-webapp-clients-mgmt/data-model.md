# Phase 1 Data Model: Clients Management UI in Webapp

## `ClientRow` (API response shape, `GET /api/clients`)

Ported from `generate_client_status.py`'s per-client `stats[client]` dict +
`mapping_server.py`'s bucket-routing fields, merged into one structure:

```text
ClientRow:
  official_name: str            # resolved/canonical client name
  raw_names: list[str]          # all raw names matched to this client (aliases seen)
  morning_client_id: str | None # from the live Morning client-list fetch; None if unmatched
  phone: str | None
  agreements_total: float
  deposits_total: float
  invoices_net: float
  manual_agreement_amount: float | None   # comment-driven override, if any
  agreed_status: "WHITE" | "YELLOW" | "GRAY"
  paid_status: "WHITE" | "YELLOW" | "GRAY"
  status: "active" | "settled" | "debt" | "missing_agreement" | "follow_up" | "past"
  is_manually_settled: bool
  latest_activity: str           # ISO date, Israel local
  comment: str                    # from client_comments.json
  mapping_note: str | None        # from mapping_notes.json
  events: list[EventRef]          # sorted event summaries backing the totals
```

`status` is the single field the frontend uses to pick a text color (see
Clarifications' color table) — the priority-ordered routing logic from
`mapping_server.py` (`is_check` → `is_active_client` → `is_manually_settled` →
`is_past` → amount-comparison bucket) is preserved as-is inside `clients_reader.py`,
just emitted as this one field instead of driving inline HTML.

## `UnmatchedEntry` (part of the `GET /api/clients` response, separate list)

```text
UnmatchedEntry:
  raw_name: str
  suggested_matches: list[str]   # difflib.get_close_matches candidates, cutoff 0.8
  event_count: int
```

## State files (environment-scoped, `{data_root}/clients/`)

Same shapes as today's analyst-tool files, just relocated:

- `client_mapping.json`: `{raw_name: official_client_name | "Unknown"}`
- `client_comments.json`: `{official_client_name: comment_text}`
- `mapping_notes.json`: `{raw_name: note_text}`
- `removed_clients.json`: write-only output, `{client_name: reason}` (regenerated on every `GET /api/clients`, per preserved side-effect behavior)
- `new_morning_clients.json`: write-only output, `{client_name: detected_at}` (same)

## Request/response bodies for write endpoints

```text
POST /api/clients/{client_id}/comments
  body: { comment: str }
  response: { client_id: str, comment: str, updated_at: str }

POST /api/clients/mapping
  body: { raw_name: str, official_name: str }   # official_name may be "Unknown"
  response: { raw_name: str, official_name: str }
```

`client_id` in the URL is the `official_name` (URL-encoded) — there is no separate
numeric/UUID id in the current data model; this matches how `client_mapping.json`/
`client_comments.json` already key by name.
