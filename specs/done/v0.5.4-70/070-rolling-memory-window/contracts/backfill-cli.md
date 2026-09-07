# Contract: `apps/rolling-memory-backfill/backfill_daily_summaries.py` CLI

**New standalone sub-app**, mirroring `apps/prod-ledger-backfill/` (Features 061/062). Host
`python3` (documented containers-only exception). `main(argv=None) -> int`; `sys.exit(main())`.

---

## CLI

```
python3 backfill_daily_summaries.py \
    --data-root  <path to the TARGET env's data/ directory>      # required
    --config     <path to the TARGET env's config.json>          # required (OpenAI key, embedding model, memory.*)
    --since      YYYY-MM-DD                                        # required, no default
    [--until     YYYY-MM-DD]                                       # optional; default = today_local - 14d, inclusive
    [--chat      <whatsapp_chat>] ...                              # repeatable; default = all chats discovered under --data-root
    [--yes]                                                        # skip the typed-'yes' confirmation
```

- **No `--env` flag** — the environment is entirely determined by `--data-root` / `--config`
  (061/062 convention).
- **No `--dry-run`** (061/062 convention).
- `--since` has no default and no hardcoded date (CONSTITUTION / REQ-MEM-040). Prod go-live is
  `2026-08-05` but the operator types it.

## Behavior

1. **Preconditions (before any network call; fail closed, `⚠️ {msg}` to stderr, `return 1`)**:
   `--data-root` exists and contains `sessions/`; `--config` loads and has `ai_api_key` +
   `ai_embedding_model` + a `memory` block; `--since` ≤ `--until`; `--until` ≤ `today_local - 14d`
   (refuse to backfill into the live window — that is the nightly roll's job).
2. Load real components via `_denidin_loader.py`: `SessionManager` (pointed at
   `<data-root>/sessions`), `RollMarkerStore(str(Path(data_root) / "memory_rolls"))`,
   `MemoryManager` (pointed at `<data-root>/memory`, embedding model from `--config`),
   `collection_name_for_chat`, `summarize_conversation`, `assert_message_integrity`.
3. `assert_message_integrity` for every discovered session **before** starting.
4. Enumerate chats (`--chat` or all). For each chat, for each calendar day in
   `[--since .. --until]`:
   - `roll_marker_store.is_rolled(chat, date)` → skip (idempotent — REQ-MEM-042).
   - `try_claim(chat, date, source="migration")` → `False` → skip.
   - `get_messages_for_local_date(session, date)`:
     - empty → `commit(chat, date, 0, None)` (marker only — REQ-MEM-041).
     - non-empty → `summarize_conversation` (billed) → `collection.delete(where=…)` →
       `remember(...)` with `source="migration"` metadata → `commit(chat, date, count, memory_id)`.
   - A mid-run per-item failure **aborts the whole run loudly** (`⚠️`, `return 1`) — a re-run
     resumes from the markers (061/062 rule).
5. **Reads raw messages only** — never `rename`/`unlink`/`archive` a message or `session.json`
   (REQ-MEM-045). `assert_message_integrity` again **after** — must still balance.
6. Print a **per-chat report** to stdout (REQ-MEM-049): chat id, days processed, summaries created,
   empty days, total billed calls. Then a grand total.
7. Unless `--yes`: before step 4, print `--data-root`, the chat list, the date range, and the
   estimated billed-call count, and require the operator to type `yes`.

## Exit codes

- `0` — completed (including "0 new items" on a fully-idempotent re-run).
- `1` — precondition failure or mid-run abort.

## Idempotency

The roll-marker DB under `<data-root>/memory_rolls/` **is** the dedup key — shared with the app's
nightly roll and catch-up sweep. After a successful backfill, `_sweep_daily_roll` /
`run_startup_daily_roll_sweep` skip every day the backfill committed (REQ-MEM-044).

## Approval

Building the script = normal test approval. **Every run against real prod data = a fresh, explicit,
per-run human approval** (REQ-MEM-048) — never a deploy side effect. The `quickstart.md` runbook
enforces: approve → (optionally) stop the target container → run against its `data/` → deploy the
new-model code → catch-up + nightly roll take over.
