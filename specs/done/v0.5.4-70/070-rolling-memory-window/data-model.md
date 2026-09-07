# Phase 1 Data Model: Rolling 14-Day Memory Window

**Feature**: 070-rolling-memory-window · **Date**: 2026-09-02 · **Plan**: [plan.md](./plan.md) ·
**Research**: [research.md](./research.md)

Entities the feature adds, changes, or newly relies on. Timestamps are timezone-aware
`Asia/Jerusalem` ISO-8601 (CONSTITUTION §II); "calendar date" means the Israel-local date.

---

## 1. `Session` (existing dataclass — one field added, lifecycle changed)

**Location**: `apps/denidin-app/src/managers/session_manager.py`.

**Changed lifecycle**: one long-lived `Session` per `whatsapp_chat`. It **never expires** — the
`session_timeout_hours` field, `is_session_expired`, `find_expired_active_sessions`, and the hourly
expire→transfer→`transferred_to_longterm` cycle are removed. A `Session` is created only the first
time a chat is seen and is thereafter always resolved (never recreated) via the chat index
(entity 2).

| Field | Type | New? | Notes |
|---|---|---|---|
| `session_id` | `str` (UUID) | no | Directory name stays UUID-based (D2). |
| `whatsapp_chat` | `str` | no | `…@c.us` or `…@g.us`. The chat-index key. |
| `message_ids` | `List[str]` | no | Ordered; ids of messages currently in `messages/`. |
| `archived_message_ids` | `List[str] = field(default_factory=list)` | **YES** | Ids moved to `{session_dir}/archived/`. Disjoint from `message_ids`. |
| `message_counter` | `int` | no | Monotonic; `== len(message_ids) + len(archived_message_ids)` (integrity invariant). |
| `last_active` | ISO str | no | Still updated per message; no longer drives expiry (kept for observability / tie-break in `_reconcile_chat_index`). |
| `transferred_to_longterm` | `bool` | no | **Dead** under the new model — no code reads or writes it. Left on the dataclass as a harmless no-op field (removing it is optional cleanup; tolerant deserialization per REQ-MEM-010 would drop it from old `session.json` files either way, so its presence is not what keeps old files loadable). |
| *(any unknown persisted key)* | — | — | **Dropped on load** with one WARNING (REQ-MEM-010). Tolerance is generic (`{f.name for f in fields(Session)}` filter), not an allowlist. |

**Deserialization rule (REQ-MEM-010, bugfix-035 H2)**: `_session_from_dict(data)` filters `data`
to known dataclass field names before `Session(**filtered)`, logs exactly one WARNING naming the
dropped keys, and is used by `_load_session` / `_load_sessions`. Per-message reads use
`.get("content", "")` and `.get("ai_required_role") or .get("role") or "user"` — no `KeyError` on
pre-2026-08-19 legacy message files.

**Integrity invariant (asserted by `tests/helpers/message_integrity.py`)**:
`len(messages/ on disk) + len(archived/ on disk) == message_counter == len(set(message_ids) ∪
set(archived_message_ids))`. No feature code path may `unlink` / `os.remove` / `shutil.rmtree` a
message or `session.json`.

---

## 2. `chat_sessions` — SQLite chat index (NEW)

**Store**: `{data_root}/sessions/chat_index.db`, owned by `SessionManager` (D2).
**Connection idiom**: one long-lived `sqlite3.connect(str(path), check_same_thread=False)`,
`row_factory=sqlite3.Row`, opened in `__init__`, `_init_schema()` idempotent `executescript`,
`execute` + immediate `commit()`. `SessionManager` never reads `AppConfiguration` — the caller
composes `storage_dir`.

```sql
CREATE TABLE IF NOT EXISTS chat_sessions (
    chat        TEXT PRIMARY KEY,   -- whatsapp_chat, verbatim (…@c.us / …@g.us)
    session_id  TEXT NOT NULL,      -- the UUID directory name
    updated_at  TEXT NOT NULL       -- Israel-local ISO-8601, last write to this mapping
);
```

| Operation | When |
|---|---|
| `INSERT OR IGNORE` | On first message for a new chat (after `Session` dir is created). |
| `SELECT session_id WHERE chat = ?` | Every `get_session(chat)` — authoritative resolution. The in-memory `chat_to_session` dict is a read-through cache populated from this. |
| `UPDATE updated_at` | On each append to that chat's session (cheap; keeps the tie-break field fresh). |
| `_reconcile_chat_index()` | Once per `SessionManager.__init__`: scan `*/session.json` (+ `expired/`), `INSERT OR IGNORE` each `(whatsapp_chat, session_id)`. A chat mapping to >1 dir → keep the one with `max(message_counter)`, log one WARNING, delete nothing. Migrates the 2 prod sessions on first construction. |

**Relationship**: 1 `chat` → exactly 1 `session_id`. Stable across a fresh `SessionManager` on the
same `data_root` (restart simulation) — this is the bugfix-044 fix.

---

## 3. `roll_markers` — SQLite roll-marker store (NEW)

**Store**: `{data_root}/memory_rolls/roll_markers.db` (D7 — deliberately not under
`{data_root}/memory/`). Class `RollMarkerStore(storage_dir)` — caller passes
`str(Path(config.data_root) / "memory_rolls")`; never reads config. Same connection idiom as
entity 2.

```sql
CREATE TABLE IF NOT EXISTS roll_markers (
    chat               TEXT NOT NULL,
    date               TEXT NOT NULL,          -- 'YYYY-MM-DD' Israel-local calendar date
    status             TEXT NOT NULL,          -- 'claimed' | 'committed'
    message_count      INTEGER,                -- NULL until commit; 0 for an empty day
    summary_memory_id  TEXT,                   -- ChromaDB record id; NULL for an empty day or while 'claimed'
    source             TEXT NOT NULL,          -- 'daily-roll' | 'catch-up' | 'migration'
    claimed_at         TEXT NOT NULL,          -- Israel-local ISO-8601
    committed_at       TEXT,                   -- Israel-local ISO-8601; NULL while 'claimed'
    PRIMARY KEY (chat, date)
);
```

### State transitions (D6)

```
(no row) --try_claim(chat,date,source)--> [claimed]        (atomic INSERT; IntegrityError => claim lost, caller skips)
[claimed] --commit(chat,date,count,memory_id)--> [committed]   (summary durably stored, or day confirmed empty)
[claimed] (age > memory.roll.stale_claim_minutes) --try_claim--> [claimed]   (re-taken after a crash between claim and commit)
[committed] --try_claim--> (rejected, IntegrityError)          (caller skips: is_rolled already true)
```

| Method | Contract |
|---|---|
| `try_claim(chat, date, source) -> bool` | `INSERT` a `status='claimed'` row. Returns `True` on success; `False` on `sqlite3.IntegrityError` **unless** the existing row is `status='claimed'` and `claimed_at` older than `stale_claim_minutes` (then it re-claims and returns `True`). Never overwrites a `committed` row. |
| `commit(chat, date, message_count, memory_id) -> None` | `UPDATE ... SET status='committed', message_count=?, summary_memory_id=?, committed_at=?`. Called only by the racer that holds the claim. |
| `is_rolled(chat, date) -> bool` | `True` iff a row exists with `status='committed'`. A `claimed`-only row is **not** rolled (so a crashed run is retried). |

**Concurrency**: `PRIMARY KEY(chat, date)` + `IntegrityError` is the cross-process guarantee
(app scheduler vs. standalone backfill). The scheduler job's `max_instances=1` prevents overlap
within the app. No app-level mutex.

**Empty day**: `try_claim` → gather messages → none → `commit(chat, date, message_count=0,
memory_id=None)`. No OpenAI call. `is_rolled` true afterwards (REQ-MEM-023).

---

## 4. Daily-summary ChromaDB record (NEW record type in an EXISTING collection)

**Collection**: `collection_name_for_chat(chat)` — one per chat, the **same** collection the legacy
`session_summary` records already live in. Written via `MemoryManager.remember(summary,
collection_name, metadata)`; **never** via a raw `client.get_collection()` (bugfix-035 H1).

**Content**: the AI-generated (or fallback raw-transcript) summary text for one chat for one
calendar day.

**Metadata**:

```json
{
  "type": "daily_summary",
  "chat": "<whatsapp_chat>",
  "date": "YYYY-MM-DD",
  "scope": "PRIVATE",
  "user_phone": "<whatsapp_chat>",
  "message_count": 12,
  "source": "daily-roll",
  "created_at": "<Israel-local ISO-8601>"
}
```

- `scope="PRIVATE"` + `user_phone=<chat>` match the existing `session_summary` RBAC convention so
  `recall_with_rbac_filter` returns the record (Contract 5). For a group chat, `user_phone` is the
  group id — consistent with how group `session_summary` records are keyed.
- `source ∈ {"daily-roll", "catch-up", "migration"}` records which mechanism wrote it.
- `created_at` comes from `MemoryManager.remember`'s existing default (`now_local().isoformat()`).

**Idempotent overwrite**: before `remember`, the roll calls
`collection.delete(where={"type": "daily_summary", "chat": chat, "date": date})` so a manual
marker reset + re-roll replaces rather than duplicates. (Normal operation never re-rolls a
`committed` day — the marker check prevents it.)

**Recall**: unchanged path. `daily_summary` and legacy `session_summary` records rank together;
the per-chat multi-week recall call uses `top_k = memory.longterm.daily_summary_top_k` (10).

---

## 5. Rolling window (DERIVED — not persisted)

Per chat, computed fresh every turn by `SessionManager.get_rolling_window(whatsapp_chat, *,
now=None, window_days=14, max_tokens=None) -> List[Dict]`:

1. Resolve the chat's single `Session` via the chat index.
2. For each message id in `message_ids ∪ archived_message_ids`, load from `messages/` else
   `archived/`. A missing file is skipped with a WARNING (never raises).
3. **In-window** iff the message's Israel-local calendar date `>= n_calendar_days_ago(window_days - 1)`
   (inclusive lower bound; "last 14 calendar days" = today + the 13 prior dates). A future-dated
   (clock-skew) message is treated as in-window (never excludes everything).
4. Sort in-window messages oldest-first; apply Feature 039 `[sender_name]` prefix to group user
   turns (identical to `get_conversation_history_for_session`).
5. If `max_tokens` is set: walk newest→oldest accumulating `count_tokens(content)`; stop once the
   running total would exceed `max_tokens`. Excluded messages are **always the oldest**; the single
   newest message is always included even if it alone exceeds `max_tokens` (terminates — no
   infinite loop, REQ-MEM-024b edge case).

Output item shape is byte-identical to today's `get_conversation_history` output (the golden-file
integration test pins it). Read-only: moves and deletes nothing.

---

## 6. Archived message (physical, NEW location)

A message file `{session_dir}/messages/<uuid>.json` moved by `rename` to
`{session_dir}/archived/<uuid>.json` by `archive_aged_and_backstopped_messages(session, *, now,
window_days, max_backstop_tokens)` during the nightly sweep, when:

- its Israel-local calendar date is older than `n_calendar_days_ago(window_days - 1)`, **or**
- it is in-window but beyond the **largest** role limit (`max_backstop_tokens` = 100000,
  role-independent — D10) counting newest→oldest.

The id moves from `session.message_ids` to `session.archived_message_ids`; `message_counter`
unchanged. Never `unlink`. `get_messages_for_local_date` and `get_rolling_window` both read
`archived/` as well as `messages/`, so archival is invisible to summarization and to any
higher-role turn.

`memory.archive_retention_days` default `0` = retain forever; no pruner is built (D4).

---

## 7. Config keys (NEW)

**Under `memory` (nested `Dict`, `config.py` `memory_defaults`)**:

| Key | Default | Purpose | Req |
|---|---|---|---|
| `memory.session.window_days` | `14` | Rolling verbatim window length (calendar days). | REQ-MEM-008 |
| `memory.longterm.daily_summary_top_k` | `10` | `top_k` for the single per-turn conversational recall call (the one over the chat's own collection, now surfacing daily summaries). No second recall call. `MemoryManager.recall`'s own default + every other call site stay at `top_k_results`=5. See `contracts/ai-handler-recall.md`. | REQ-MEM-047 |
| `memory.archive_retention_days` | `0` | `0` = retain archived messages forever (no pruner built). | REQ-MEM-034 |
| `memory.roll.hour` | `2` | `CronTrigger(hour=…)` for the nightly roll (Israel local). | REQ-MEM-020, REQ-MEM-061 |
| `memory.roll.catchup_lookback_days` | `21` | Startup catch-up sweep bound; older days are the US4 backfill's job. | REQ-MEM-028, REQ-MEM-061 |
| `memory.roll.stale_claim_minutes` | `120` | A `claimed` roll marker older than this may be re-taken. | REQ-MEM-026 |

The token backstop `N` is **not** a new key — it reuses `memory.session.max_tokens_by_role`
(REQ-MEM-024b / REQ-MEM-047). `memory.session.session_timeout_hours` may still appear in a config
file; it is ignored (tolerated) and drives nothing.

**New top-level field** (`AppConfiguration` dataclass + `from_file` defaults + `denidin.py`
`config_dict`):

| Key | Default | Purpose | Req |
|---|---|---|---|
| `logging.rotation_when` | `"midnight"` | `TimedRotatingFileHandler(when=…)`. | REQ-MEM-051, REQ-MEM-052 |
| `logging.backup_count` | `0` | `0` = keep every rotated (gzipped) segment. | REQ-MEM-051 |

**Compose (not app config)** — `docker/docker-compose.{prod,dev}.yml`, both `denidin-app-<env>`
and `morning-mcp-app-<env>` services:

```yaml
logging:
  driver: json-file
  options: { max-size: "10m", max-file: "5" }
```

REQ-MEM-053b: the `json-file` loss is acceptable only because the app file handler now retains
full history — stated in the runbook.

---

## 8. Log segment (physical, US5)

`logs/denidin.log` rotated by `TimedRotatingFileHandler(when=<logging.rotation_when>,
backupCount=<logging.backup_count=0>)` attached **once to the root logger** (not per-module). A
gzip `rotator` + `namer` compress each rotated segment to `denidin.log.YYYY-MM-DD.gz`. `backupCount=0`
means no segment is ever deleted by the handler. One handler = one rotation authority = the
multi-handler race (KB-sized, out-of-order `.1`–`.5` fragments measured in prod 2026-09-02) is
structurally gone. Byte-identical twin in `apps/morning-mcp-app`.

---

## Entity → requirement map

| Entity | Requirements |
|---|---|
| 1 `Session` (+ `archived_message_ids`, tolerant load, no expiry) | REQ-MEM-002, REQ-MEM-005, REQ-MEM-010, REQ-MEM-011, REQ-MEM-032, SC-008, SC-011 |
| 2 `chat_sessions` index | REQ-MEM-014, REQ-MEM-015, REQ-MEM-016, SC-006 |
| 3 `roll_markers` | REQ-MEM-024, REQ-MEM-025, REQ-MEM-026, REQ-MEM-046, SC-010 |
| 4 daily-summary record | REQ-MEM-021, REQ-MEM-022, REQ-MEM-023, REQ-MEM-029, SC-002, SC-003, SC-005 |
| 5 rolling window (derived) | REQ-MEM-001, REQ-MEM-003, REQ-MEM-004, REQ-MEM-006, REQ-MEM-007, REQ-MEM-024b, SC-001, SC-007 |
| 6 archived message | REQ-MEM-032, REQ-MEM-033, REQ-MEM-034, REQ-MEM-035, REQ-MEM-036, SC-004 |
| 7 config keys | REQ-MEM-008, REQ-MEM-028, REQ-MEM-060, REQ-MEM-061 |
| 8 log segment | REQ-MEM-050, REQ-MEM-051, REQ-MEM-052, REQ-MEM-053b, SC-009 |
