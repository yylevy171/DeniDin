# Feature 070 — Migration Tooling Spec (consolidate / finalize / purge)

**Status**: DRAFT for human review (Stage 0.1 of `MIGRATION-CHECKLIST.md`). Blocks all Stage 0
code. Companion to `MIGRATION-SCOPE.md` (why) and `MIGRATION-CHECKLIST.md` (when/where).

Three new operator tools in `apps/rolling-memory-backfill/`, run **in this order** as the offline
migration pipeline, each `--report-only`-capable, each host-`python3` (the documented
containers-only exception), each `main(argv=None) -> int` + `sys.exit(main())`, preconditions
**fail closed before any write**:

```
1. consolidate_sessions.py   — N session dirs per chat  →  1 canonical session dir
2. backfill_daily_summaries.py (EXISTS)  — one daily_summary per (chat, pre-window day)
3. finalize_migration.py     — physically archive every >14-day message  (messages/ → archived/)
4. purge_legacy_summaries.py — delete the 20,949 legacy session_summary records
```

Nothing here touches `events/`, `media/`, `reminders/`, or `accounting_reconciliation/` — per
`MIGRATION-SCOPE.md` §4 the only session/message references outside `sessions/` are ledger events'
`session_id`/`message_id`, which are traceability-only and never dereferenced.

---

## 1. `consolidate_sessions.py`

### 1.1 Problem it solves

Prod `sessions/` holds **93 dirs for 2 chats** (1 active + 92 under `expired/<date>/`). Feature
070's `SessionManager._reconcile_chat_index` collapses each chat to the single dir with the
greatest `message_counter` and logs one WARNING — every other dir's messages become unreachable
(they're never in `chat_index.db`, so `get_session` never loads them, so `get_rolling_window`
never sees them). Result on prod as-is: the bot's working memory shrinks to **one mid-August day
per chat**, silently. The consolidator merges every dir per chat into **one** canonical session
*before* any 070 code runs.

### 1.2 CLI

```
consolidate_sessions.py
  --data-root <dir>          required. The env's data/ dir; sessions under <data-root>/sessions/.
  --report-only              dry run: print the plan + projected integrity, write nothing, exit 0.
  --chat <id>                repeatable; default = every chat found under sessions/.
  --raw-archive-name <name>  default "_pre070_raw_<YYYYMMDD>" (today, Israel-local). Where every
                             source dir is MOVED (never deleted).
  --resume                   permit running when a canonical dir already exists (crash recovery).
```

### 1.3 Discovery

Scan `<data-root>/sessions/`:
- top-level `<uuid>/session.json` — **skip** the reserved names `expired`, `_pre070_raw_*`,
  `_pre070_sessions_archive_*`, and any name starting `.consolidate_tmp_`.
- `<data-root>/sessions/expired/<date>/<uuid>/session.json`.

Parse each `session.json` with the **same tolerant rule** as `SessionManager._session_from_dict`
(keep only keys that are `Session` dataclass fields; a dropped key like `pending_ledger_events` is
logged, never fatal). Group by `whatsapp_chat`.

### 1.4 The canonical session

**One per chat.** Built fresh in a temp dir, then swapped in, so every original is preserved
byte-for-byte in the raw archive and the canonical dir is clean:

1. `mkdir <data-root>/sessions/.consolidate_tmp_<sha1(chat)[:12]>/messages/`
2. **Choose the canonical `session_id`**: the source session with the greatest `message_counter`
   (matches what `_reconcile_chat_index` would have kept, so a pre-existing `chat_index.db` row
   stays valid). Tie → lexicographically smallest `session_id`. *Reusing* an id, not minting a
   new one, keeps it human-traceable back to the pre-migration state.
3. **Merge messages**: read every file in every source dir's `messages/` **and** `archived/`.
   - **De-dup by `message_id`**: sources are processed in `(created_at || session_start, session_id)`
     order; the **first** occurrence of an id wins, later copies are skipped with a WARNING naming
     both source dirs. (Expected count on prod: 0 — but a crash-retried pre-070 write could have
     produced one.)
   - **Sort** the merged set by, in order: parsed `timestamp` → `received_at` → original
     `order_num` → `message_id`. Log the count of messages that fell back past `timestamp` (no
     parseable value) — expected 0 on prod (verified: all 200 sampled prod files have both
     `timestamp` and `received_at`).
   - **Renumber**: assign `order_num` `1..N` in sorted order. Rewrite each message file's
     `order_num` **and** its inner `session_id` (→ canonical id). Everything else in the file —
     `content`, `timestamp`, `received_at`, `sender*`, `recipient*`, `ai_required_role`,
     `image_path`, `extracted_text`, `ledger_event_ids`, … — is copied **unchanged**.
   - Write all N files into `.consolidate_tmp_*/messages/`. **`archived/` is created empty** —
     nothing is archived at this step; `finalize_migration.py` (pipeline step 3) does that.
4. **Write `.consolidate_tmp_*/session.json`** (`json.dump(..., indent=2, ensure_ascii=False)`,
   UTF-8 — matches `SessionManager._save_session`):

   | field | value |
   |---|---|
   | `session_id` | canonical id (from 4.2) |
   | `whatsapp_chat` | the chat |
   | `message_ids` | the N ids, sorted order |
   | `archived_message_ids` | `[]` |
   | `message_counter` | `N` |
   | `created_at` | earliest `created_at`/`session_start` across sources |
   | `last_active` | latest source `last_active`, or the newest message's `timestamp` if greater |
   | `total_tokens` | `0` — non-authoritative under 070 (`get_rolling_window` recomputes per turn); self-heals as new messages are added. |
   | `storage_path` | `null` |
   | `transferred_to_longterm` | omitted (dead field; tolerant load ignores it either way) |
   | *(any other persisted key)* | **dropped** (`pending_ledger_events` etc.) |

5. **Move every source dir** (whole `<uuid>/` tree — including the max-counter one whose id we
   reused, and its now-consumed `messages/`) into `<data-root>/sessions/<raw-archive-name>/`,
   preserving provenance:
   - a top-level source → `<raw-archive-name>/active/<uuid>/`
   - an expired source → `<raw-archive-name>/expired/<date>/<uuid>/`
6. `mv .consolidate_tmp_* → <data-root>/sessions/<canonical id>/`.
7. `assert_message_integrity(<canonical dir>)` — the tool asserts and **exits 1** if it fails,
   leaving the temp/partial state in place for inspection (every original is already safe in the
   raw archive).

### 1.5 Preconditions — fail closed (`⚠️` + exit 1) *before any write*

- `--data-root` exists and contains `sessions/`.
- Every target chat has ≥ 1 source dir.
- No canonical dir already exists for a target chat **unless `--resume`**.
- `<raw-archive-name>` does not already exist **unless `--resume`**.
- **Every** source `session.json` parses. A corrupt one is reported by path and **aborts the run**
  — never silently skipped (a skipped session = silent message loss, the exact failure mode this
  tool exists to prevent).
- Projected `N_merged ≤ Σ(source message_counter)` (equality minus dups). `N_merged` greater ⟹
  logic bug ⟹ abort.

### 1.6 `--report-only`

Per chat, print: source dir count + full paths; `Σ` source messages; `N_merged`; duplicate-id
count; `timestamp`-fallback count; chosen canonical `session_id`; projected
`assert_message_integrity` PASS/FAIL. **Writes nothing.** Exit 0.

### 1.7 Idempotency & `--resume`

- **Fresh run twice** (no `--resume`): the second run hits "canonical dir already exists" and
  fails closed. Correct — forces the operator to decide.
- **`--resume`**: allowed with a canonical dir present. Re-scans for source dirs **not yet** in
  the raw archive (a crash between steps 5 and 6): none → no-op, exit 0; some → merge them into
  the existing canonical session (re-sort + re-number the *entire* set), then move them to the
  archive. A subsequent `--resume` with nothing pending → no-op.

### 1.8 What it does NOT create

Not `chat_index.db`, not `roll_markers.db`. The first real `SessionManager` construction
(`finalize_migration.py`, then app start) builds `chat_index.db` — and now finds exactly one dir
per chat, so **zero** "maps to N session dirs" WARNING. `roll_markers.db` is the backfill's. A
stale one from a prior partial run must be deleted by the operator first (checklist 2.3 / 3.x).

---

## 2. `finalize_migration.py`

### 2.1 Purpose

Bring each consolidated session to the on-disk **steady state** — all >14-day messages in
`archived/` — *before the app ever starts*, so `run_startup_daily_roll_sweep` has only the ≤ 2
un-rolled leftover days (between the backfill's `--until` and the live window) to touch, not a
bulk archive of ~850 files on first boot.

### 2.2 CLI & behaviour

```
finalize_migration.py
  --data-root <dir>   required
  --report-only       project the per-chat move count, write nothing, exit 0
  --chat <id>         repeatable; default = every chat in chat_index.db / sessions/
  --now <ISO>         test seam; default now_local()
```

Per chat: construct a real `SessionManager(storage_dir="<data-root>/sessions")` (this also
**creates `chat_index.db`** — assert 0 "maps to N session dirs" WARNING here), `get_session(chat)`,
then:

```python
session_manager.archive_aged_and_backstopped_messages(
    session, now=<--now>, window_days=14, max_backstop_tokens=100000,
)
```

then `assert_message_integrity(<canonical dir>)`.

### 2.3 Ordering — **must run after the backfill**

`daily_summary_roll_service._roll_one_chat_day` reads a day's messages via
`get_messages_for_local_date`, which reads **both** `messages/` and `archived/` — so archiving
first would not lose a day. But running the backfill first means (a) every pre-window day is
already a committed `daily_summary` before we start moving files, and (b) the roll's own per-chat
archive step and this tool converge on the same on-disk result with the simplest possible
reasoning. Pipeline order is fixed: consolidate → backfill → **finalize** → purge.

### 2.4 Verify

- `messages/` holds only messages whose Israel-local date is within 14 days of `--now`;
  everything older is under `archived/`.
- `session.json`: `message_ids` shrunk, `archived_message_ids` populated, `message_counter`
  unchanged (`== len(message_ids) + len(archived_message_ids)`).
- Every message file still exists (moved, never `unlink`ed).
- **Idempotent**: a second run moves 0 files, exit 0.
- A chat entirely within 14 days → 0 moves, exit 0.
- With T064 landed: `get_rolling_window(chat, max_tokens=<godfather limit>)` returns the same
  message set before and after finalize (the per-turn read never touches `archived/`).

---

## 3. `purge_legacy_summaries.py`

### 3.1 Purpose

Delete the **20,949** legacy `session_summary` / `session_summary_fallback` ChromaDB records
(only 84 real sessions, each re-summarized ~250× by the pre-070 hourly cleanup thread —
`MIGRATION-SCOPE.md` §1.1). After the backfill has written one clean `daily_summary` per (chat,
day), these add only noise and ~238 MB to the two per-chat collections `recall` reads from.

### 3.2 CLI & behaviour

```
purge_legacy_summaries.py
  --data-root <dir>   required
  --report-only       count matching records per collection, write nothing, exit 0
  --chat <id>         repeatable; default = every collection under <data-root>/memory/
```

Per chat: `MemoryManager` (composed against `<data-root>/memory/`) →
`get_or_create_collection(collection_name_for_chat(chat))` →

```python
collection.delete(where={"$or": [
    {"type": {"$eq": "session_summary"}},
    {"type": {"$eq": "session_summary_fallback"}},
]})
```

(the `$eq`/`$or` idiom matches `daily_summary_roll_service`'s existing `where` clauses). Prints
before/after record counts per collection.

### 3.3 Guard — refuses to run before the backfill

Fails closed (`⚠️` + exit 1) unless the collection **already contains ≥ 1 `daily_summary`
record**. Purging before the backfill would leave the chat with no long-term memory at all.

### 3.4 Single-process ChromaDB

`chroma.sqlite3` is a single-writer store — the app **must be stopped** while this runs, and it
runs on the host with a read-write `data/` (the Mac's prod mount is read-only sshfs and would fail
the write anyway). The tool documents this; it cannot enforce it.

### 3.5 Verify

- Report shows ~20,949 records to delete across the 2 collections.
- After: each collection holds **only** `daily_summary` records (~40–50 total).
- `MemoryManager.recall()` on a mid-August query still returns that day's `daily_summary`.

---

## 4. Test plan (Stage 0.4 / 0.5 / 0.3b of the checklist)

| Tool | Unit (synthetic tmp trees, RED→👤→GREEN) | Integration (real `SessionManager`/`MemoryManager`, OpenAI mocked at boundary) |
|---|---|---|
| `consolidate_sessions.py` | N dirs → 1; `order_num` 1..N contiguous & timestamp-sorted; dup `message_id` → one copy + WARNING; empty source dir skipped from merge but still archived; missing `timestamp` → `received_at` fallback + WARNING; `pending_ledger_events`/`storage_path`/`transferred_to_longterm` gone from canonical; every precondition fails closed *before* writing; `--report-only` writes nothing; `--resume` no-op / crash-recovery; run-twice idempotent | seed **multiple** sessions/chat across many days for a `@c.us` + a `@g.us` chat, some hand-moved to `expired/`; run `main([...])`; real `SessionManager` → 0 "maps to N" WARNING; `get_rolling_window` returns the true last-14-days; `assert_message_integrity` clean; `Σ in == Σ out` (stated numerically); real `_sweep_daily_roll` (mocked OpenAI) → one `daily_summary`/non-empty day, second sweep no-op; `_pre070_raw_*` byte-identical to originals |
| `finalize_migration.py` | multi-day session → after: `messages/` ≤14 days only, `archived/` the rest, counter unchanged, integrity clean, idempotent (0 moves on re-run); all-in-window chat → 0 moves | via real `SessionManager` on a consolidated fixture; `chat_index.db` created with no multi-dir WARNING; `get_rolling_window` set unchanged pre/post (T064) |
| `purge_legacy_summaries.py` | — | seed a real ChromaDB with N `session_summary` + M `daily_summary` via `MemoryManager`; purge; only the M `daily_summary` remain; `recall()` still returns them; the ≥1-`daily_summary` guard rejects a collection with 0 |

Full non-billed sub-app suite green is the Stage 0 exit gate, alongside **T064** landed in
`apps/denidin-app` (`get_rolling_window` never reads `archived/`; SC-007 budget back to 150 ms).
