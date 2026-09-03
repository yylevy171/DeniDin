# Feature 070 — Migration Execution Checklist

**Companion to `MIGRATION-SCOPE.md`.** Ordered, gated steps to migrate dev and prod to the
rolling-memory model. **Governing rule: nothing runs against prod until the exact same tool, at
the exact same version, has run successfully against (a) synthetic fixtures and (b) a byte-copy
of real prod data on the Mac.** Prod is the *fourth* environment each tool touches, never the
first.

```
STAGE 0  Build + unit/integration-test the consolidator        (pure local, synthetic data)
STAGE 1  Full dress rehearsal against a PROD SNAPSHOT on the Mac (real prod bytes, offline, disposable)
STAGE 2  Dev migration                                          (real dev data, low stakes, reversible)
STAGE 3  Prod migration                                         (live, night, downtime, monitored)
```

Each stage must be **fully green** before the next starts. Every `👤` line is its own explicit
human go-ahead.

---

## Working area (Mac, outside the clone)

```
~/denidin-migration/
├── snapshots/
│   ├── prod-YYYYMMDD/            # read-only byte copy of ~/denidin-winprod-data
│   └── dev-YYYYMMDD/             # byte copy of apps/denidin-app/dev_data
├── rehearsal/
│   └── prod-YYYYMMDD/            # WRITABLE working copy for Stage 1 (disposable)
└── reports/                     # every dry-run + validation report, timestamped
```

---

# STAGE 0 — Build the consolidator (no environment, synthetic data only)

### 0.1 Spec addendum for the consolidator
- **Do**: add `specs/in-progress/070-rolling-memory-window/consolidator-spec.md` — the canonical-session
  rules: one active dir per chat; messages from every source dir (active + `expired/**`) merged;
  sort key = `timestamp` then `received_at` then file mtime (log which); `order_num` renumbered
  `1..N`; `message_ids` rebuilt in that order; `message_counter = N`; `archived_message_ids = []`;
  `storage_path = null`; `transferred_to_longterm` and `pending_ledger_events` dropped; each moved
  message file's inner `session_id` rewritten to the canonical id; duplicate `message_id` across
  dirs → keep the first occurrence, log; empty dirs skipped; source dirs **moved** (never deleted)
  to `sessions/_pre070_raw_<date>/`.
- **Test this step**: `speckit.analyze`-style read-through — every rule above has a matching
  assertion planned in 0.4/0.5. No code yet.
- **Rollback**: n/a (doc only).
- **👤 approve the consolidator design before writing code.**

### 0.2 Pull the prod + dev snapshots (read-only copy — safe, no env action)
- **Do**:
  ```bash
  mkdir -p ~/denidin-migration/snapshots
  rsync -a --delete ~/denidin-winprod-data/ ~/denidin-migration/snapshots/prod-$(date +%Y%m%d)/
  rsync -a --delete /Users/yaron/Projects/DeniDin/apps/denidin-app/dev_data/ ~/denidin-migration/snapshots/dev-$(date +%Y%m%d)/
  chmod -R a-w ~/denidin-migration/snapshots/          # make the snapshots immutable
  ```
- **Test this step**:
  - `du -sh` both snapshots vs source; file counts match (`find … | wc -l`).
  - `sessions/` has 93 dirs (prod), `memory/chroma.sqlite3` present and same size.
  - Open `memory/chroma.sqlite3` **read-only** with `mode=ro&immutable=1` — collections list
    matches (`memory_120363210094632983_at_g.us`, `memory_972522968679`); `type` counts match
    the SCOPE doc (~20,868 `session_summary`).
- **Rollback**: delete and re-`rsync`.
- Note: `chroma.sqlite3` is a *live* file; the copy is a crash-consistent point-in-time. Good
  enough for rehearsal; the real prod run (Stage 3) snapshots with prod **stopped**.

### 0.3 Write the consolidator
- **Do**: `apps/rolling-memory-backfill/consolidate_sessions.py` (sibling to
  `backfill_daily_summaries.py`, reuses `_denidin_loader` + `conftest`), `main(argv) -> int`:
  ```
  --data-root   <env data/ dir>        required
  --report-only                        dry run: print the plan + projected integrity, write nothing
  --raw-archive-name  _pre070_raw_<date>   (default) where source dirs are moved
  --chat  <id>  (repeatable)            default: all chats found under sessions/
  --resume                             allow running when a canonical dir already exists
  ```
  Fails closed (`⚠️` + exit 1) before any write if: `--data-root` missing / no `sessions/`;
  a canonical dir exists without `--resume`; total-in ≠ total-out projection; any source
  `session.json` unparseable (report which, abort).
- **Test this step**: `python3 -c "import consolidate_sessions"` from the sub-app; `pylint`
  ≥ 9.0, `mypy` clean.
- **Rollback**: n/a (new file).

### 0.4 Unit tests — synthetic fixtures (RED → 👤 → GREEN)
- **Do**: `apps/rolling-memory-backfill/tests/unit/test_consolidate_cli.py` (mirrors
  `test_backfill_cli.py`). Cover, with hand-built tmp session trees:
  - N dirs for one chat (varied `message_counter`, interleaved timestamps) → 1 canonical dir,
    `order_num` `1..N` contiguous, sorted by `timestamp`, `message_counter == N`.
  - duplicate `message_id` in two source dirs → one copy in the result, WARNING logged.
  - a source dir with 0 messages → skipped, not in the merge, still moved to `_pre070_raw`.
  - a message missing `timestamp` → `received_at` used; missing both → file mtime, WARNING.
  - `pending_ledger_events` / `transferred_to_longterm` / stale `storage_path` present on a
    source `session.json` → absent / `null` on the canonical one.
  - every precondition branch fails closed **before** writing (assert nothing created on abort).
  - `--report-only` writes nothing; exit 0; report totals correct.
  - `--resume` semantics: second run over an already-canonical chat is a no-op (or merges only
    genuinely-new source dirs), exit 0.
  - idempotency: run twice → identical result, source dirs already in `_pre070_raw` are not
    re-processed.
- **Test the tests**: they must be RED against an empty `consolidate_sessions.py` stub first.
- **👤 approve the unit tests, then implement to GREEN.**

### 0.5 Integration test — real `SessionManager`, synthetic multi-session data
- **Do**: `apps/rolling-memory-backfill/tests/integration/test_consolidate_integration.py`:
  seed (via the real `add_message_with_tokens(timestamp=…)` seam) **multiple** sessions per chat
  across many days for a `@c.us` and a `@g.us` chat, then archive some to `expired/` by hand to
  mimic the 0.5.3 cleanup; run `consolidate_sessions.main([...])`; then:
  - construct a **real `SessionManager`** on the result → `_reconcile_chat_index` maps each chat
    to the single canonical dir, **0** "maps to N session dirs" WARNING.
  - `get_rolling_window(chat, window_days=14)` returns the true last-14-days across the whole
    merged history (not one day).
  - `assert_message_integrity` clean on each canonical dir.
  - total message count in == out (minus dupes/empties), stated numerically.
  - run the real `daily_summary_roll_service._sweep_daily_roll` (OpenAI mocked at boundary) over
    a pre-window range → one `daily_summary` per non-empty (chat, date); a second sweep is a
    no-op.
  - `_pre070_raw_<date>/` holds every original dir, checksummed identical.
- **Test this step**: full non-billed sub-app suite green (`pytest -m "not billed"`).
- **👤 approve the integration test, then GREEN.**

### 0.6 (Optional, decision §5.3) `session_summary` purge tool + test
- **Do**: `apps/rolling-memory-backfill/purge_legacy_summaries.py` — `--data-root`, `--report-only`,
  deletes `where type IN (session_summary, session_summary_fallback)` from every
  `collection_name_for_chat(chat)` collection; prints before/after counts per collection.
- **Test this step**: integration test — seed a ChromaDB with N `session_summary` + M
  `daily_summary` via the real `MemoryManager`; purge; assert only the M `daily_summary` remain
  and `recall()` still returns them.
- **👤 decision required** on whether to run this at all (see SCOPE §5.3 / §9.3).

### 0.7 Rollback rehearsal helper
- **Do**: a documented one-liner `restore_data_root.sh <backup-dir> <data-root>` = `rsync -a
  --delete <backup>/ <data-root>/`. Verify a restored `data/` loads under **both** 0.5.3-shape
  code (no `chat_index.db` needed) and 070 code.
- **Test this step**: part of Stage 1.

### STAGE 0 EXIT GATE
- [ ] consolidator + (optional) purge tool: `pylint` ≥ 9.0, `mypy` clean
- [ ] full non-billed sub-app suite green
- [ ] every rule in 0.1 has a passing assertion in 0.4 / 0.5
- [ ] 👤 sign-off that Stage 1 may begin

---

# STAGE 1 — Full dress rehearsal against a PROD SNAPSHOT (Mac, offline, disposable)

**This is the "first real run against real prod bytes" — but a throwaway copy, offline, no
container, no OpenAI unless explicitly noted.** Every command here is the *exact* command that
Stage 3 will run against the live box, only the `--data-root` differs.

### 1.1 Make a writable rehearsal copy
```bash
rsync -a ~/denidin-migration/snapshots/prod-YYYYMMDD/ ~/denidin-migration/rehearsal/prod-YYYYMMDD/
chmod -R u+w ~/denidin-migration/rehearsal/prod-YYYYMMDD/
```
- **Verify**: `sessions/` has 93 dirs; no `chat_index.db`; no `memory_rolls/`.

### 1.2 Consolidator dry run
```bash
cd apps/rolling-memory-backfill
<venv>/python3 consolidate_sessions.py \
  --data-root ~/denidin-migration/rehearsal/prod-YYYYMMDD \
  --report-only | tee ~/denidin-migration/reports/consolidate-dryrun-$(date +%Y%m%d_%H%M%S).txt
```
- **Verify before proceeding**: report shows exactly 2 chats; per chat: N source dirs → 1,
  message-count-in == message-count-out, duplicate-id count, timestamp-fallback count; projected
  `assert_message_integrity` PASS. Nothing was written (`git status`-equivalent: dir unchanged;
  `find … -newer` shows no new files).

### 1.3 Consolidator real run
```bash
<venv>/python3 consolidate_sessions.py \
  --data-root ~/denidin-migration/rehearsal/prod-YYYYMMDD \
  | tee ~/denidin-migration/reports/consolidate-run-$(date +%Y%m%d_%H%M%S).txt
```
- **Verify**:
  - [ ] `sessions/` now has exactly 2 canonical dirs + `_pre070_raw_<date>/` (93 dirs inside).
  - [ ] `assert_message_integrity` clean on each canonical dir (the script asserts; re-assert manually).
  - [ ] each canonical `session.json`: `storage_path == null`, no `pending_ledger_events`,
        `message_counter` == live file count, `order_num` `1..N` contiguous, messages sorted by `timestamp`.
  - [ ] `_pre070_raw_<date>/` dirs checksum-identical to the snapshot's `sessions/` dirs.
  - [ ] total messages across the 2 canonical dirs == (926 + 127 − dupes − empties); state the exact number.

### 1.4 Reconcile check (real `SessionManager`, no app)
```bash
<denidin venv>/python3 - <<'PY'
from src.managers.session_manager import SessionManager
from src.managers.message_integrity import assert_message_integrity
from pathlib import Path
sm = SessionManager(storage_dir="~/denidin-migration/rehearsal/prod-YYYYMMDD/sessions".replace("~", str(Path.home())))
import logging; # capture WARNINGs
for chat in sorted(sm.known_chats()):
    s = sm.get_session(chat)
    print(chat, "->", s.session_id, "counter", s.message_counter, "storage_path", s.storage_path)
    assert_message_integrity(Path(sm.storage_dir) / (s.storage_path or s.session_id))
PY
```
- **Verify**: 2 chats, each → its canonical dir, `storage_path=None`, **no "maps to N session
  dirs" WARNING in the output**, integrity clean, `chat_index.db` created with 2 rows.

### 1.5 Backfill dry run + real run (against the consolidated rehearsal copy)
```bash
<denidin venv>/python3 backfill_daily_summaries.py \
  --data-root ~/denidin-migration/rehearsal/prod-YYYYMMDD \
  --config    <a config.json with a REAL ai_api_key + text-embedding-3-large + memory block> \
  --since 2026-08-03 --until <today−14>            # NO --yes first: read the plan
# then, on go-ahead:
… --since 2026-08-03 --until <today−14> --yes  | tee ~/denidin-migration/reports/backfill-rehearsal-*.txt
```
- **Cost note**: this makes real OpenAI summary calls (~1 per non-empty pre-window day per
  chat, ≤ ~50 total, cheap `billed`-tier). It is the single deliberate real-OpenAI step in the
  rehearsal, and it exercises the exact call the prod run will make. **👤 go-ahead for this one
  billed run.**
- **Verify**:
  - [ ] `memory_rolls/roll_markers.db`: one row per (chat, date) in range, **all `committed`**, `source='migration'`.
  - [ ] ChromaDB: one `daily_summary` per non-empty pre-window (chat, date); metadata correct;
        recallable via `MemoryManager.recall`.
  - [ ] `assert_message_integrity` still clean; raw message files byte-unchanged (checksum).
  - [ ] a **second** `--yes` run → `billed_calls=0`, `summaries=0`, exit 0.

### 1.6 (If decided) purge rehearsal
```bash
<denidin venv>/python3 purge_legacy_summaries.py --data-root ~/denidin-migration/rehearsal/prod-YYYYMMDD --report-only
… (no --report-only)
```
- **Verify**: both collections drop to only `daily_summary` records; `recall()` still returns them.

### 1.7 Offline "turn" simulation against the consolidated + backfilled rehearsal copy
```bash
<denidin venv>/python3 - <<'PY'
from openai import OpenAI
from src.handlers.ai_handler import AIHandler
from src.models.config import AppConfiguration
from src.models.message import WhatsAppMessage
# build AppConfiguration pointing memory.session.storage_dir / longterm.storage_dir at the rehearsal copy
# real ai_api_key; then:
h = AIHandler(OpenAI(api_key=cfg.ai_api_key), cfg)
for chat, q in [("972522968679@c.us", "מה דיברנו לאחרונה?"),
                ("120363210094632983@g.us", "כמה שעות נרשמו לענבר בן סימון?"),
                ("120363210094632983@g.us", "<a question only a mid-August day answers>")]:
    m = WhatsAppMessage(message_id="q", chat_id=chat, sender_id=chat, sender_name="test",
                        text_content=q, timestamp=0, message_type="text")
    r = h.get_response(h.create_request(m, chat_id=chat, user_phone=chat),
                       chat_id=chat, user_phone=chat, sender="test", recipient="DeniDin")
    print(chat, "=>", r.response_text)
PY
```
- **Cost note**: 3 real OpenAI turns. **👤 go-ahead.**
- **Verify**:
  - [ ] recent-context question → answer reflects **September** activity (not just Aug 9).
  - [ ] `get_rolling_window` for the group returns the true last-14-days (log line
        `Retrieved N messages`, N in the hundreds, spanning the recent dates).
  - [ ] the mid-August question → answered from that day's `daily_summary` (recall log shows the
        `daily_summary` record in the `RECALLED MEMORIES` block).
  - [ ] **0** "Created new session".

### 1.8 Rollback rehearsal
```bash
rsync -a --delete ~/denidin-migration/snapshots/prod-YYYYMMDD/ ~/denidin-migration/rehearsal/prod-YYYYMMDD/
```
- **Verify**: the restored copy is byte-identical to the snapshot (93 dirs, no `chat_index.db`,
  no `memory_rolls/`); a `SessionManager` on it behaves exactly as the pre-migration state; a
  `PersistentClient` opens `memory/` cleanly.

### 1.9 Time + transcript capture
- Record wall-clock time for each of 1.2–1.7 (informs the downtime window).
- Save the **exact commands that worked** into `MIGRATION-RUNBOOK-prod.md` — Stage 3 executes
  that runbook verbatim, only swapping `--data-root` and running on the Windows host.

### STAGE 1 EXIT GATE
- [ ] every checkbox in 1.2–1.8 ticked, against real prod bytes
- [ ] downtime estimate produced (sum of 1.3 + 1.4 + 1.5, plus deploy)
- [ ] `MIGRATION-RUNBOOK-prod.md` written from the actual rehearsal transcript
- [ ] 👤 sign-off that Stage 2 may begin

---

# STAGE 2 — Dev migration (real dev data)

Dev is the first *live* run — reversible, low stakes, and it exercises the multi-session path
that the Phase 9 hand-cleanup skipped.

### 2.1 👤 acquire dev + stop it
```bash
./scripts/stop_all.sh dev            # owner is already "Avi" from Phase 9; -force only if not
```
- **Verify**: both dev containers down; `shared/active_env.json` dev entry cleared or owned by us.

### 2.2 Snapshot dev
```bash
rsync -a --delete /Users/yaron/Projects/DeniDin/apps/denidin-app/dev_data/ ~/denidin-migration/snapshots/dev-$(date +%Y%m%d)/
```

### 2.3 Reunite dev's moved-aside sessions, then consolidate
- **Do**: move `dev_data/_pre070_sessions_archive_20260903/*` back under `dev_data/sessions/`
  (so the consolidator sees the *whole* dev history), **remove** the Phase-9 `chat_index.db` and
  `memory_rolls/` (they were built on the partial state), then:
  ```bash
  <venv>/python3 consolidate_sessions.py --data-root .../dev_data --report-only   # review
  <venv>/python3 consolidate_sessions.py --data-root .../dev_data                 # real
  ```
- **Test this step**: same checklist as 1.3–1.4 but against dev; **0** "maps to N session dirs"
  WARNING; integrity clean; `_pre070_raw_<date>/` holds everything.
- **Rollback**: `rsync -a --delete ~/denidin-migration/snapshots/dev-YYYYMMDD/ .../dev_data/`.

### 2.4 Backfill dev
```bash
<venv>/python3 backfill_daily_summaries.py --data-root .../dev_data --config config/config.dev.json \
  --since <earliest dev message date> --until <today−14> --yes
```
- **Test this step**: 1.5's checklist against dev; idempotent second run.

### 2.5 (If decided) purge dev's `session_summary` records — same tool, same checks as 1.6.

### 2.6 Validate dev offline (the 1.4 + 1.7 scripts, dev paths) — **👤 for the billed turn sim.**

### 2.7 Rebuild + start dev on `feature/070`
```bash
docker compose --project-directory . -f docker/docker-compose.dev.yml -f docker/docker-compose.dev.local.yml build denidin-app-dev morning-mcp-app-dev
./scripts/run_all.sh dev
```
- **Test this step**: startup log — `_reconcile_chat_index` **no** WARNING; `run_startup_daily_roll_sweep`
  completes; roll scheduler armed 02:00; **0** "Created new session"; `roll_markers.db` all committed.

### 2.8 Real WhatsApp turns in dev (👤 send)
- 1:1 and group each: a recent-context question + a backfilled-day question.
- **Verify** from logs: `Retrieved N messages` (N large, recent dates), backfilled `daily_summary`
  in the `RECALLED MEMORIES` block, correct answers, **0** "Created new session".

### 2.9 Restart dev, confirm no-op
```bash
docker restart denidin-dev-denidin-app-dev-1
```
- **Verify**: startup sweep does 0 OpenAI calls, 0 new records, 0 new sessions.

### 2.10 Let the real 02:00 nightly roll fire once; next morning check
- **Verify**: `daily-roll` log for last night's date, one `daily_summary` per non-empty
  (chat, date), markers committed, archive step moved the now-out-of-window files to `archived/`,
  `assert_message_integrity` still clean.

### STAGE 2 EXIT GATE
- [ ] every 2.x verify passed
- [ ] dev has run for **at least 24h** on 070 including one real nightly roll and one restart
- [ ] 👤 sign-off that Stage 3 (prod) may begin

---

# STAGE 3 — Prod migration (live, night, downtime)

Executes `MIGRATION-RUNBOOK-prod.md` (written in Stage 1.9) verbatim on the Windows prod host.
Every step already run twice (snapshot + dev). **👤 for every numbered step.**

### 3.1 Pre-flight
- [ ] 👤 downtime window agreed (estimate from Stage 1.9 + deploy time + buffer).
- [ ] `scripts/windows_prod/tail_logs.sh denidin-winprod denidin-app-prod` — confirm no client
      conversation in progress right now.
- [ ] Feature 070 branch is merged-ready: PR green, `speckit.analyze` clean, all Stage 0/1/2
      gates signed off.

### 3.2 Stop prod
```bash
./scripts/stop_all.sh prod
```
- **Verify**: both prod containers down (`docker --context denidin-winprod ps`); watchdog not
  respawning; `shared/active_env.json` prod entry cleared.

### 3.3 Snapshot prod (with prod STOPPED — this one is the rollback artifact)
- On the host: full copy of `data/` → `data_pre070_backup_<date>/`.
- Pull a second copy to `~/denidin-migration/snapshots/prod-<date>-COLD/` on the Mac.
- **Verify**: file counts + `du -sh` match; `chroma.sqlite3` copied whole; 93 session dirs.

### 3.4 Consolidator — dry run, then real (on the host, against `data/`)
- Same two commands as Stage 1.2 / 1.3, `--data-root <host data/>`.
- **Verify**: the full 1.3 checklist. **Abort and restore (3.9) if any check fails.**

### 3.5 Backfill (on the host)
- Same as Stage 1.5, `--since 2026-08-03 --until <today−14> --yes`.
- **Verify**: the full 1.5 checklist.

### 3.6 (If decided) purge `session_summary` — Stage 1.6, host paths.

### 3.7 Validate — prod still STOPPED
- Run the 1.4 reconcile script + the **full MIGRATION-SCOPE §8 checklist** against the host
  `data/`. Every box must tick.

### 3.8 Deploy 0.5.4
- 👤 `/haleluya` (merge Feature 070 as one PR).
- 👤 `scripts/cut_release.sh denidin-app <VERSION>` — **human supplies the exact version.**
- 👤 `scripts/cut_release.sh morning-mcp-app <VERSION>` if it changed (it did — logger).
- 👤 `scripts/deploy_release.sh morning-mcp-app prod <VERSION>` **then** `… denidin-app prod <VERSION>`
  (morning-mcp first, per CLAUDE.md ordering).
- **Verify**: `deploy_release.sh`'s own health/log verification passes for each; both containers Up.

### 3.9 Post-deploy validation
- Startup log: `_reconcile_chat_index` **no** WARNING; `run_startup_daily_roll_sweep` completes;
  roll scheduler armed 02:00 Asia/Jerusalem; **0** "Created new session"; MCP tunnel `running`.
- 👤 real WhatsApp turns: godfather 1:1 (recent context + a mid-August recalled day); the
  collections group (recent Sep work-hours context + a mid-August recalled day). Confirm from
  logs: `Retrieved N messages` (recent dates), `daily_summary` in `RECALLED MEMORIES`, correct
  answers, **0** "Created new session".
- 👤 one more `docker restart denidin-app-prod` → startup sweep no-op (0 calls, 0 records, 0 sessions).

### 3.10 Monitor
- [ ] Watch the **first live 02:00 nightly roll**: one `daily_summary` per non-empty (chat, date),
      markers committed, archive step ran, integrity clean.
- [ ] 24–48h: no recurring errors; `get_rolling_window` latency (from logs / a timed probe)
      within budget; no unexpected "Created new session".
- [ ] If the Windows box reboots in this window (Feature 035), confirm recovery + the startup
      sweep no-op.

### 3.11 Keep the rollback artifact
- `data_pre070_backup_<date>/` and `~/denidin-migration/snapshots/prod-<date>-COLD/` stay in
  place indefinitely (rollback + audit). `sessions/_pre070_raw_<date>/` likewise.

### ROLLBACK (any point in 3.4–3.7, before deploy)
```bash
# on the host, prod still stopped:
rsync -a --delete data_pre070_backup_<date>/ data/
./scripts/deploy_release.sh denidin-app prod <CURRENT 0.5.3 VERSION>   # or just start the existing 0.5.3 image
./scripts/run_all.sh prod
```
- **Verify**: prod back on 0.5.3, `data/` byte-restored, a real turn works.

### ROLLBACK (after deploy, if 3.9 fails)
- `scripts/deploy_release.sh denidin-app prod <0.5.3 VERSION>` (rollback is the same script),
  then restore `data/` from `data_pre070_backup_<date>/` (0.5.3 ignores `chat_index.db` /
  `memory_rolls/` — but restoring is cleaner), `run_all.sh prod`, verify a turn.
- File a bugfix, do **not** retry the migration the same night.

---

## Summary of what runs where, in order

| Tool | Synthetic (0.4/0.5) | Prod snapshot (Stage 1) | Dev live (Stage 2) | Prod live (Stage 3) |
|---|:--:|:--:|:--:|:--:|
| `consolidate_sessions.py` | ✅ unit + integ | ✅ 1.2 dry, 1.3 real | ✅ 2.3 | ✅ 3.4 |
| `backfill_daily_summaries.py` | ✅ (T040a/T041a exist) | ✅ 1.5 (1 billed) | ✅ 2.4 | ✅ 3.5 |
| `purge_legacy_summaries.py` *(if used)* | ✅ 0.6 | ✅ 1.6 | ✅ 2.5 | ✅ 3.6 |
| `_reconcile_chat_index` (SessionManager) | ✅ test_consolidate_integration | ✅ 1.4 | ✅ 2.7 | ✅ 3.9 |
| nightly roll on migrated data | ✅ 0.5 (mocked) | ✅ 1.5 second sweep | ✅ 2.10 real 02:00 | ✅ 3.10 real 02:00 |
| offline AIHandler turn on migrated data | — | ✅ 1.7 (billed) | ✅ 2.6/2.8 | ✅ 3.9 |
| rollback (`rsync` restore) | — | ✅ 1.8 | ✅ 2.3/2.4 rollback | ✅ 3.9 ROLLBACK |

**No tool's first execution is against prod.** Each has run against synthetic data, then a
byte-copy of real prod data, then live dev, before it touches the live prod box.
