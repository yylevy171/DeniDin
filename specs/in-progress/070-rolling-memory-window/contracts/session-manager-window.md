# Contract: `SessionManager` — rolling window, canonical store, tolerant load

**Module**: `apps/denidin-app/src/managers/session_manager.py`
**Consumers**: `AIHandler` (per-turn window + canonical store), `daily_summary_roll_service`
(per-day gather), `apps/rolling-memory-backfill` (per-day gather).

`SessionManager` **never reads `AppConfiguration`** — every path/limit is a constructor arg or a
call arg (existing discipline; a unit test pins the ctor signature).

---

## Constructor changes

- **Removed** param: `session_timeout_hours`. Callers that still pass it must be updated;
  `ai_handler.py:~1461` (`session_timeout_hours=session_config.get('session_timeout_hours', 24)`)
  drops the kwarg.
- `__init__` now also opens `{storage_dir_parent}/chat_index.db` and runs
  `_reconcile_chat_index()` once (see below).

## `get_session(whatsapp_chat: str) -> Session`  *(behavior change)*

- MUST resolve via `chat_index.db` (`SELECT session_id WHERE chat = ?`), falling back to the
  in-memory `chat_to_session` cache only as a read-through.
- If no row exists: create one `Session`, `INSERT OR IGNORE` into `chat_index.db`, populate the
  cache. This is the **only** path that creates a session.
- MUST be stable across a fresh `SessionManager` on the same `data_root` (restart): a second
  construction resolves the same `session_id`, emits **no** "Created new session" log for that chat.
- MUST NOT expire, archive, or recreate a session for any reason (no `session_timeout_hours`).

## `_reconcile_chat_index() -> None`  *(new, private, called once in `__init__`)*

- Scan `{storage_dir}/*/session.json` and `{storage_dir}/expired/**/session.json`.
- For each, `INSERT OR IGNORE (whatsapp_chat, session_id, now_local().isoformat())`.
- A chat mapping to >1 directory: keep the `session_id` with the greatest `message_counter`, log
  **one** `WARNING` naming both, delete nothing.
- Idempotent — safe to run every construction.

## `_session_from_dict(data: dict) -> Session`  *(new, private; REQ-MEM-010)*

- `valid = {f.name for f in fields(Session)}`; `Session(**{k: v for k, v in data.items() if k in valid})`.
- If `data` had keys outside `valid`: log **one** `WARNING` (`level=WARNING`, not `ERROR`, not one
  per sweep) naming the dropped keys.
- Used by `_load_session` and `_load_sessions`. Never raises `TypeError` on an unknown key.
- Generic — not an allowlist for `pending_ledger_events`. A future field removal must not strand
  older `session.json` files.

## `get_rolling_window(whatsapp_chat, *, now=None, window_days=14, max_tokens=None) -> List[Dict]`  *(new; REQ-MEM-001, 003, 004, 006, 007, 024b)*

| Aspect | Contract |
|---|---|
| Return shape | Byte-identical to `get_conversation_history_for_session(...)` output today — same dict keys, same ordering semantics (oldest-first), same Feature 039 `[sender_name]` prefix for group user turns. |
| `now` | Test-only seam. Production leaves it `None` → `now_local()`. |
| `window_days` | Caller passes `config.memory['session']['window_days']` (default 14). |
| In-window rule | Message's Israel-local calendar date `>= n_calendar_days_ago(window_days - 1, now)`. Inclusive. Uses `time_utils` helpers (Contract: time-utils-daybucket). Consistent with the roll job's bucketing. |
| Message source | `messages/<id>.json` if present, else `archived/<id>.json`. A missing file → skip + `WARNING`, never raise. |
| Clock skew | A future-dated message is included (never returns an empty window because of one bad timestamp). |
| `max_tokens` | If set: accumulate `count_tokens(content)` newest→oldest; stop once the next message would push the total over `max_tokens`. **Excluded = oldest.** The single newest message is always returned even if it alone exceeds `max_tokens`. Terminates. |
| Side effects | **None.** Read-only. Moves/deletes nothing. |
| Empty chat | Returns `[]`, no error. |

## `get_messages_for_local_date(session: Session, date: datetime.date) -> List[Dict]`  *(new; Contract 3, REQ-MEM-036)*

- Returns every message of `session` whose Israel-local calendar date `== date`, from **both**
  `messages/` and `archived/`, oldest-first, same item shape as `get_rolling_window`.
- Same day-bucketing as `get_rolling_window` — a message belongs to exactly one day.

## `add_message_with_tokens(...)`  *(replaces `add_message_with_token_limit`; REQ-MEM-005, 033)*

- Same signature and persistence behavior as `add_message_with_token_limit` **minus** any
  write-time pruning. Appends the message, updates `message_ids` / `message_counter` /
  `last_active`, `INSERT OR IGNORE` / `UPDATE updated_at` on the chat index. Does **not** call any
  prune/archive path.
- Call sites to update: `ai_handler.py:~3099, ~3115, ~3763, ~3768`;
  `reminder_delivery_service.py:~128`.

## `archive_aged_and_backstopped_messages(session, *, now, window_days, max_backstop_tokens) -> int`  *(new; Phase 3, D10, REQ-MEM-032)*

- `rename` (never `unlink`) into `{session_dir}/archived/`:
  - messages whose Israel-local date is older than `n_calendar_days_ago(window_days - 1, now)`, **and**
  - in-window messages beyond `max_backstop_tokens` (caller passes `100000` — the largest role
    limit, role-independent) counting newest→oldest.
- Move each id from `session.message_ids` to `session.archived_message_ids`; persist `session.json`;
  `message_counter` unchanged.
- Returns the count moved. Idempotent (a second call moves nothing new).

## Deleted symbols  *(SC-011 — `test_retired_paths_removed.py` asserts 0 live references)*

`_prune_until_under_limit`, `prune_to_limit`, `clear_session`, `find_expired_active_sessions`,
`find_untransferred_archived_sessions`, `get_sessions_needing_cleanup`, `is_session_expired`,
`remove_from_index`, and the `session_timeout_hours` constructor param / `self.session_timeout_hours`
attribute.
