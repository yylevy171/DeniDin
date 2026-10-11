# Data Model: Feature 068

No new persisted domain data is introduced by this feature except the password-hash file — the
webapp is a pure read layer over `denidin-app`'s existing data.

## Reused, unmodified (source of truth remains `denidin-app`)

### `LedgerEvent` (dict, `apps/denidin-app/src/managers/ledger_event_manager.py`)

Full persisted field set (from `record = {...}`), all already present on disk today:

```
event_id, event_datetime, source_type, event_subtype, client_name, payer_name, description,
amount, reference, agreement_id, component_id, component_label, trigger_condition, percent,
percent_base, hours, hourly_rate, txn_date, vat_status, split_partner, split_percent,
accounting_document_display_number, accounting_document_status, accounting_document_status_code,
accounting_document_status_label, accounting_document_payment_method, session_id, message_id,
captured_at, reference_hint, bank_number, bank_branch, bank_account, schema_version
```

### `Session` / `Message` (dataclasses, `apps/denidin-app/src/managers/session_manager.py`)

`Session`: `session_id, whatsapp_chat, message_ids, message_counter, created_at, last_active,
total_tokens, transferred_to_longterm, storage_path`.

`Message`: `message_id, session_id, role, content, ai_required_role, sender, sender_name,
recipient, recipient_name, timestamp, received_at, was_received, order_num, image_path,
extracted_text, ledger_event_ids`.

**On-disk message layout** (2026-09-05 — corrected after a real gap): a session's messages
live in **two** sibling dirs — `sessions/{sid}/messages/{mid}.json` (recent, still in the live
token window) and `sessions/{sid}/archived/{mid}.json` (pruned out of the window by
`SessionManager`, still full session history). A ledger event's source message is usually in
`archived/` by the time the UI looks. `context_reader` reads both (live copy wins on a
`message_id` collision). This is distinct from whole **expired sessions** under
`sessions/expired/{YYYY-MM-DD}/{sid}/` (which have the same `messages/` + `archived/` split
inside).

**Resolution is by `message_id`, not `session_id`** (2026-09-06, after Feature 070). Feature
070's session **consolidator** merges every historical session for a chat into one canonical
`sessions/{sid}/` dir and moves the originals under `sessions/_pre070_raw_<YYYYMMDD>/` (also
`_pre070_sessions_archive_<date>/` on dev), so an event's stored `session_id` is usually stale
after migration. `message_id` is stable and the message is carried into whichever session now
owns it. `context_reader` builds a `message_id → session dir` index across: canonical
`sessions/{sid}/`, legacy `sessions/expired/{day}/{sid}/`, and the raw backup
`sessions/_pre070_raw_<date>/` (dirs directly, or under `active/` / `expired/{day}/`) —
canonical wins on collision. The `/context` response returns `session_id` = the resolved
(real) session and `event_session_id` = the event's original stored value.

## New: password hash file (webapp-owned, not shared with denidin-app)

`apps/webapp/backend/{data_root_for_auth}/password.hash` — plain text file, one line:
`sha256(salt + password).hexdigest()`. Created/rotated by an operator (mechanism: a small CLI
script or manual write — decided in `tasks.md`; not exposed via any HTTP endpoint, since this
feature is read-only end-to-end and password rotation is an operator action, not a user one).
Password comparison is **literal, no trimming** of the submitted password (2026-09-05
decision) — a stray leading/trailing space causes a genuine mismatch, not silently corrected.
**If this file is missing or corrupted at startup, the backend still starts** (2026-09-05
decision) — every login attempt simply fails (invalid_password or a distinct error) until the
file is fixed, rather than the whole app refusing to start over just the auth gate.

## Derived response shapes (webapp-backend → frontend, new for this feature)

### `EventRow` (list view — `GET /events`)

```json
{
  "event_id": "A0409261234",
  "date": "04/09/2026",
  "source_type": "הסכם",
  "event_subtype": "יצירה",
  "client_name": "...",
  "amount": 5000,
  "description": "..."
}
```
`date` = `txn_date` if present, else `event_datetime`'s date portion, else `event_date` (the
pre-Phase-11 field, still on older הסכם/בנק events that have no `event_datetime`). Each is
parsed leniently (`DD/MM/YYYY` **or** `YYYY-MM-DD`) — formatted `DD/MM/YYYY`
server-side (backend owns date formatting, not the frontend, to keep the "always DD/MM/YYYY"
rule enforced in one place).

### `EventDetail` (expand — right panel, `GET /events/{event_id}` or embedded in `/context`)

**Revised 2026-09-05**: not all `LedgerEvent` fields verbatim — a curated, per-type field list
per `contracts/field-manifests.md` (some fields ALWAYS shown even when null, some only
IF-EXISTS, some NEVER shown, internal/bookkeeping fields excluded entirely). Each returned
field carries its Hebrew label so the frontend doesn't hardcode translations:

```json
{
  "fields": [
    {"key": "event_datetime", "label": "תאריך אירוע", "value": "..."},
    {"key": "bank_number", "label": "מספר בנק", "value": null}
  ]
}
```
The BFF computes which fields to include/exclude and whether a null value still gets emitted
(ALWAYS) or is dropped (IF-EXISTS with no value) — this logic lives in `ledger_reader.py`, not
the frontend, so the manifest rules are enforced once, server-side.

### `EventContext` (expand — left panel, `GET /events/{event_id}/context?lookback_minutes=N`)

```json
{
  "session_id": "...",
  "messages": [
    {
      "message_id": "...",
      "role": "user",
      "side": "right",
      "content": "...",
      "timestamp": "...",
      "sender_name": "...",
      "media_url": "/media/<opaque-token>"   // present only if this message has image_path
    }
  ],
  "lookback_minutes_used": 10
}
```
`side` (2026-09-05 decision, WhatsApp-style chat rendering): `"right"` for `role="user"` (the
human), `"left"` for `role="assistant"` (the bot) — computed server-side so the frontend never
re-derives chat-bubble alignment from `role` itself. A message with `media_url` renders as a
clickable thumbnail; clicking opens a larger view dismissed with "OK" (closes back to the chat,
no navigation away from the expanded row).
`messages` = every `Message` in the same session whose `timestamp` falls within
`[linked_message.timestamp - lookback_minutes, linked_message.timestamp]`, inclusive, sorted
chronologically. If `session_id`/`message_id` can't be resolved (archived session missing,
file gone), returns `{"error": "context_unavailable", "message": "..."}` rather than a 500 —
a real, expected edge case (old data, manual cleanup) that the UI must render gracefully, not
crash on.

### Session token (server-held, in-memory, not persisted to disk)

```json
{"token": "<opaque>", "issued_at": "...", "last_active_at": "...", "expires_after_hours": 168}
```
`last_active_at` is refreshed on every authenticated request; a token is rejected once
`now - last_active_at` exceeds `expires_after_hours` (default 168h = 1 week, server-
configurable). Expiry is against **last activity, not first login** (confirmed 2026-09-05) —
using the app resets the clock, so a session in continuous use never expires. Multiple tokens
can be valid simultaneously (concurrent sessions allowed — see `research.md` §6a); a new login
does not invalidate any other active token. Expiry is verified manually at acceptance time, not
by an automated test (explicit user decision, 2026-09-05). Client-side, the token is held in
**`localStorage`** (survives tab/browser close, 2026-09-05 decision) rather than
`sessionStorage`.

### `/auth/login` response

```json
{"token": "<opaque-session-token>"}
```

### Login audit log line (backend log file, not a new persisted store)

`[timestamp] LOGIN success|failure` — no password/hash value ever logged, per the standing
"technical detail to logs only, never secrets" discipline. One line per attempt.

### Settings (frontend-only, `localStorage`/`sessionStorage` — never sent to backend as
persisted state beyond being passed as query params per-request)

```json
{
  "theme": "light|dark",
  "sort_order": "newest_first|oldest_first",
  "days_back": 7,
  "lookback_minutes": 10
}
```
No backend persistence of settings in v1 — matches "no login/accounts," each browser holds its
own preferences.
