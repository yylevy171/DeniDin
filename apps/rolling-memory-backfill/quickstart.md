# Rolling 14-Day Memory Backfill — Operator Runbook (Feature 070, US4)

Standalone, operator-run pipeline that fills the ChromaDB `daily_summary` gap for
every calendar day older than the nightly roll's catch-up reach
(`memory.roll.catchup_lookback_days`, default 21). Mirrors
`apps/prod-ledger-backfill/`. Runs with **host `python3`** (the documented
containers-only exception, same as the ledger backfills).

The migration reuses the **exact** nightly roll code path
(`daily_summary_roll_service._roll_one_chat_day`) — a backfilled summary is
byte-for-byte a nightly one except `source="migration"` in its metadata. The
roll-marker DB under `<data-root>/memory_rolls/` is the shared dedup key: after a
successful backfill, the app's nightly roll and startup catch-up sweep skip every
day it committed.

---

## One-time setup

```bash
cd apps/rolling-memory-backfill
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

`apps/denidin-app` is **not** pip-installed — it is reached via `sys.path`
insertion in `_denidin_loader.py` / `conftest.py` (see `requirements.txt`'s note).
The heavy transitive deps it needs (`openai`, `chromadb`, `tiktoken`, `requests`)
are declared here directly.

## Tests (no approval needed — non-billed only)

```bash
source venv/bin/activate
python3 -m pytest tests/ -q            # unit + integration, OpenAI mocked at the boundary
```

There are **no billed tests in this sub-app**. The one real-OpenAI run is the
backfill invocation itself (Phase 9 for dev, Phase 10 read-only checks for prod).

---

## CLI

```
python3 backfill_daily_summaries.py \
    --data-root  <TARGET env's data/ directory>       # required
    --config     <TARGET env's config.json>           # required (ai_api_key, ai_embedding_model, memory.*)
    --since      YYYY-MM-DD                            # required, no default — you type it
    [--until     YYYY-MM-DD]                           # optional; default = today_local - 14d, inclusive
    [--chat      <whatsapp_chat>] ...                  # repeatable; default = all chats under --data-root
    [--yes]                                            # skip the typed-'yes' confirmation
```

- No `--env` — the environment is entirely `--data-root` / `--config` (061/062 convention).
- No `--dry-run`.
- `--until` may never fall inside the live 14-day verbatim window — that is the
  nightly roll's job; the CLI refuses it.
- Preconditions fail closed (`⚠️ …` to stderr, exit 1) **before any network call**.
- A mid-run per-item failure aborts the whole run loudly (exit 1). Re-run to
  resume — committed roll markers are skipped.
- Exit `0` = completed (including a fully-idempotent "0 new items" re-run);
  exit `1` = precondition failure or mid-run abort.

---

## Part 1 — Dev backfill (Phase 9)

1. **Get explicit human approval for this specific run.** Every run against a real
   environment's data is its own approval gate — never a deploy side effect.
2. Optionally stop the dev containers (`./scripts/stop_all.sh dev`) so nothing
   writes sessions concurrently. Not strictly required — the backfill only reads
   raw messages and writes `daily_summary` records + roll markers — but it makes
   the before/after integrity check unambiguous.
3. Run against the dev `data/` (or `dev_data/`) root:

   ```bash
   source venv/bin/activate
   python3 backfill_daily_summaries.py \
       --data-root ../denidin-app/dev_data \
       --config    ../denidin-app/config/config.dev.json \
       --since     <dev go-live date>
   ```

   Review the printed plan (`--data-root`, chat list, date range, upper-bound
   billed-call count), then type `yes`.
4. Read the per-chat report and grand total. `assert_message_integrity` runs for
   every session before and after — a failure aborts before any write.
5. Deploy the new-model code to dev when ready (separate, explicit human
   decision). The startup catch-up sweep + nightly roll take over from there and
   skip everything the backfill committed.

### Executed run — dev, 2026-09-04

- **Cleanup first**: dev `sessions/` had 1 active + 10 `expired/` dirs. 8 stale test sessions
  for `972522968679@c.us` (reconcile would pick the 240-msg one over the live 22-msg one), a
  test number, and a 2-emoji group dir — all moved to
  `dev_data/_pre070_sessions_archive_20260903/` (kept). The real user+Ayala group session
  (`504112c0`, `120363410226011645@g.us`) promoted from `expired/2026-08-19/` to an active dir,
  stale `storage_path` cleared. End state: exactly 2 persistent chats.
- **Run**: `--since 2026-08-19 --until 2026-08-21` → 1 summary (group Aug 19), 5 empty markers,
  1 billed call, integrity held before + after.
- **Post-deploy**: dev rebuilt on `feature/070`; startup catch-up sweep produced 12 daily
  summaries total, 21 committed markers/chat, 0 "Created new session"; a real `docker restart`
  showed the startup sweep fully idempotent (0 calls, 1 s).

## Part 2 — Prod backfill (Phase 10)

Same as Part 1 but against the prod `data/` root
(`~/denidin-winprod-data` read-only mount is **not** writable — the backfill must
run where prod's `data/` is actually writable, i.e. on the prod host or against a
copy, per the Phase 10 plan). Phase 10's own tasks are limited to **read-only,
non-intrusive** verification (T100/T101): confirm the roll-marker DB and
`daily_summary` counts look right, no message file was touched. Prod go-live is
`2026-08-05`; the operator types that as `--since`.
