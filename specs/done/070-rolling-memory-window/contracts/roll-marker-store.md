# Contract: `RollMarkerStore`

**Module (new)**: `apps/denidin-app/src/managers/roll_marker_store.py`
**Consumers**: `daily_summary_roll_service`, `apps/rolling-memory-backfill`.
**DB**: `{data_root}/memory_rolls/roll_markers.db` (D7 — the caller passes
`str(Path(config.data_root) / "memory_rolls")`; the store never reads `AppConfiguration`).

Idiom: mirror `ReminderManager` — one long-lived `sqlite3.connect(str(path),
check_same_thread=False)`, `row_factory=sqlite3.Row`, opened in `__init__`, held on `self._conn`,
never closed; `_init_schema()` idempotent `executescript`; `execute` + immediate `commit()`; no
`with conn:` blocks; `Path(storage_dir).mkdir(parents=True, exist_ok=True)` in `__init__`.

## Schema

```sql
CREATE TABLE IF NOT EXISTS roll_markers (
    chat               TEXT NOT NULL,
    date               TEXT NOT NULL,          -- 'YYYY-MM-DD' Israel-local
    status             TEXT NOT NULL,          -- 'claimed' | 'committed'
    message_count      INTEGER,
    summary_memory_id  TEXT,
    source             TEXT NOT NULL,          -- 'daily-roll' | 'catch-up' | 'migration'
    claimed_at         TEXT NOT NULL,          -- Israel-local ISO-8601
    committed_at       TEXT,
    PRIMARY KEY (chat, date)
);
```

## `__init__(self, storage_dir: str) -> None`

- Composes `self._db_path = Path(storage_dir) / "roll_markers.db"`, opens the connection, runs
  `_init_schema()`.
- MUST NOT take `AppConfiguration` (a unit test pins this).

## `try_claim(self, chat: str, date: str, source: str) -> bool`

| Case | Behavior | Returns |
|---|---|---|
| No row for (chat, date) | `INSERT (chat, date, 'claimed', NULL, NULL, source, now_local().isoformat(), NULL)` | `True` |
| `INSERT` raises `sqlite3.IntegrityError` **and** existing row is `status='committed'` | no-op | `False` |
| `IntegrityError` **and** existing row is `status='claimed'` with `claimed_at` **younger** than `stale_claim_minutes` | no-op | `False` |
| `IntegrityError` **and** existing row is `status='claimed'` with `claimed_at` **older** than `stale_claim_minutes` | `UPDATE ... SET status='claimed', source=?, claimed_at=now, message_count=NULL, summary_memory_id=NULL, committed_at=NULL` | `True` |

- `stale_claim_minutes` is passed to `__init__` or `try_claim` (implementer's choice — keep it a
  plain arg, default from `memory.roll.stale_claim_minutes` = 120, composed by the caller).
- `source` values: `'daily-roll'` (scheduler tick), `'catch-up'` (startup sweep), `'migration'`
  (backfill).

## `commit(self, chat: str, date: str, message_count: int, memory_id: Optional[str]) -> None`

- `UPDATE roll_markers SET status='committed', message_count=?, summary_memory_id=?,
  committed_at=now_local().isoformat() WHERE chat=? AND date=?`.
- Called **only** by the racer that won `try_claim`, and **only after** the summary is durably
  stored (REQ-MEM-025) or the day is confirmed empty (`message_count=0`, `memory_id=None`).
- If no matching `claimed` row exists (shouldn't happen), log `WARNING` and no-op.

## `is_rolled(self, chat: str, date: str) -> bool`

- `True` **iff** a row exists with `status='committed'`. A `claimed`-only row → `False` (retry).

## `list_markers(self, chat: str) -> List[sqlite3.Row]`  *(optional helper for the backfill report)*

- All rows for `chat`, ordered by `date`. Read-only.

## Concurrency guarantee

`PRIMARY KEY(chat, date)` + `IntegrityError` is the only synchronization. Valid across:
- two scheduler ticks — prevented from overlapping by the job's `max_instances=1`;
- the scheduler vs. a hand-run backfill/roll in a **separate process** — the primary-key `INSERT`
  is atomic in SQLite regardless of process.

No app-level mutex, no lockfile.
