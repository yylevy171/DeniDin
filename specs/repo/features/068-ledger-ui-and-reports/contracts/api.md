# API Contract: webapp-backend (Feature 068, v1)

Base path: `/api` (frontend and backend served behind the same tunnel; exact routing —
same-origin vs separate host — decided in `tasks.md`). All endpoints except `/health` and
`/auth/login` require `Authorization: Bearer <token>`.

## `GET /health`
Unauthenticated. `200 {"status": "ok", "environment": "dev"|"prod", "version": "<VERSION>"}`.

## `POST /auth/login`
Body: `{"password": "<plain text>"}`.
- `200 {"token": "<opaque session token>"}` on match — token is added to the server's active
  set with `issued_at`/`last_active_at` now; other already-active tokens are unaffected
  (concurrent sessions allowed, see `data-model.md`/`research.md` §6a).
- `401 {"error": "invalid_password"}` on mismatch.
- Every call, success or failure, appends one audit log line (`data-model.md`).

## `POST /auth/logout`
Requires bearer token. Invalidates it server-side. `204 No Content`.

## Token expiry (applies to every authenticated endpoint)
A token whose `last_active_at` is more than `expires_after_hours` (server-configured, default
168h = 1 week) in the past is rejected as if it never existed: `401 {"error":
"session_expired"}`. Every successful authenticated request refreshes `last_active_at`.
Verified manually at acceptance time — no automated test (explicit user decision, 2026-09-05).

## `GET /events`
Requires bearer token. Query params:
- `days_back` (int, optional — default 7): trailing-window load filter, applied against `date`
  (`txn_date` else `event_datetime`'s date portion), **inclusive of the boundary day** — an
  event dated exactly `days_back` days before today is included, computed in Israel local time
  per the repo's standing time-handling rule (`now_local()`, never bare UTC/naive datetime).
  The frontend re-calls this endpoint immediately whenever the user changes "days back" in
  settings, not only on an explicit refresh press.

Returns the **full** set of `EventRow` (see `data-model.md`) within that window — no other
query params are accepted here; every other filter (date-range-within-window, event type,
event subtype, client name, free text) is applied **client-side** by the frontend over this
response (see `research.md` §2 for why). Each `EventRow` also carries `search_blob` — every
string/number found anywhere in the full underlying `LedgerEvent` record, lowercased and
space-joined — so the client-side free-text filter matches text outside the six display
columns. When a free-text or client-name query is entered, the frontend re-requests `/events`
with a `days_back` large enough to reach the picker's floor (2024-01-01) so the search covers
full history, not just the trailing default window.

`200 {"events": [EventRow, ...], "days_back": 7, "count": N}`

## `GET /clients/search?prefix=<2+ chars>`
Requires bearer token. Prefix search (case-insensitive) over every distinct `client_name` that
has ever appeared in the ledger — **full history**, not limited to the currently-loaded
days-back window (2026-09-05 decision). Called by the frontend on every keystroke once the
client-name filter field has 2+ characters.

`200 {"clients": ["ישראל ישראלי", "ישראל כהן", ...]}` (matches only, no fuzziness here — this
is a prefix search for autocomplete convenience; the actual client-name *filter* applied on
Apply is a separate fuzzy match against loaded events, not this endpoint).

## `GET /events/{event_id}`
Requires bearer token. Returns the **curated** right-panel view — NOT the raw record:
`{"event_id", "source_type", "event_subtype", "fields": [{"key", "label", "value"}, ...]}`,
where `fields` is computed server-side from `contracts/field-manifests.md` (per-type order,
Hebrew labels, ALWAYS/IF-EXISTS/NEVER rules; internal/bookkeeping fields absent entirely).
An unrecognised `source_type` returns `{"event_id", "source_type", "event_subtype",
"unsupported": true, "message": "..."}` with no `fields`. `404 {"error": "not_found"}` if
the id is unknown. (Raw records are used only internally for session/message resolution via
`LedgerReader.raw_event`, never served.)

## `GET /events/{event_id}/context?lookback_minutes=N`
Requires bearer token. `lookback_minutes` optional, default 10, server clamps to `[0, 60]`
regardless of what's requested (defense-in-depth against the frontend's own setting cap ever
being bypassed). The window is **bidirectional around the anchor message** —
`[anchor − lookback_minutes, anchor + lookback_minutes]`, inclusive both ends (2026-09-05
feedback: the bot's capture/confirmation reply lands *after* the triggering message, so a
backward-only window hid the half of the exchange that explains the capture). Boundary
inclusivity matches Component 2's load-window rule.

`200 EventContext` (see `data-model.md`) | `404 {"error": "not_found"}` (event itself missing)
| `200 {"error": "context_unavailable", "message": "..."}` (event found, but its
session/message data could not be resolved — a real, non-fatal edge case).

## `GET /media/{token}`
Requires bearer token. `token` is an opaque reference returned inside an `EventContext`
response's `media_url` field (never a raw filesystem path). Streams the file's bytes with the
correct `Content-Type` (image/*, etc.). `404` if the token is unknown/expired or the resolved
path fails the `data_root`-containment check (see `research.md` §3).

## Error shape (all endpoints, non-2xx)
```json
{"error": "<machine_code>", "message": "<human-readable, no stack trace>"}
```
Matches the repo's standing "friendly user-facing errors, technical detail to logs only" rule.
