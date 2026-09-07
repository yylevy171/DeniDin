# Quickstart / Runbook: Feature 070 — Rolling 14-Day Memory Window

**Feature**: 070-rolling-memory-window · **Date**: 2026-09-02

This is an **operator runbook**, not a conversational feature guide. Two parts:
1. [US4 — one-time daily-summary backfill](#part-1--us4-one-time-backfill-runbook) (real prod
   write + real billed OpenAI calls — fresh explicit approval per prod-touching step, every run).
2. [US5 — prod log-retention audit finding + verification](#part-2--us5-log-retention-audit-finding).

---

## Part 1 — US4 one-time backfill runbook

### What it does

Creates **one daily summary per non-empty calendar day** for chat history **older than 14 days**
(prod go-live 2026-08-05), and writes a roll marker for every processed `(chat, date)` — including
empty days — into the target environment's own `data/` (the SQLite roll-marker DB under
`data/memory_rolls/` and the ChromaDB collections under `data/memory/`). Raw messages are read
only; nothing is moved, archived, or deleted.

### Why the ordering matters

**Run the backfill against a target env BEFORE deploying the new-model code there** (clarified
2026-09-02, REQ-MEM-048). The new-model code's startup **catch-up sweep** only rolls un-rolled days
within `memory.roll.catchup_lookback_days` (default 21). If you deploy first, then on boot the
sweep faces every day back to go-live at once — a burst of billed calls. Backfill-first means the
sweep finds every historical day already marked and does nothing but the last few genuinely-recent
days.

Also: **stop the target `denidin-app` container first** (a separate explicit approval — it is an
environment stop/start action). Two `chromadb.PersistentClient` instances must not open the same
`data/memory/` path concurrently; the backfill opens one, so the app's must be down. (The backfill
*can* run against a stopped or running env mechanically, but for prod ChromaDB safety, stop it.)

`memory.roll.catchup_lookback_days` is the **safety net** if this ordering is ever violated — it
bounds the automatic damage; the operator still runs the backfill for the older range afterward.

### One-time setup (per clone, once)

```
cd apps/rolling-memory-backfill
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Credentials/config are **not** committed. The backfill takes `--config <path to the target env's
config.json>` directly — for prod that is the file on the Windows box (copy it locally over the
read-only mount, or run the backfill from a machine that has it). Never point `--config` at
`config.dev.json` when backfilling prod.

### Steps (prod)

> Every step marked **[APPROVAL]** needs a fresh, explicit human go-ahead for that specific action,
> that run. Approval for one step never carries to the next.

1. **[APPROVAL]** Announce intent: which env, which chats, `--since 2026-08-05`, `--until`
   (default = today − 14d). Get the go-ahead.
2. **[APPROVAL]** Stop the target `morning-mcp-app-prod` then `denidin-app-prod`
   (`./scripts/stop_all.sh prod` — this is an environment stop, gated).
3. Mount the prod `data/` **read-write** temporarily (mirror Feature 062's
   `~/denidin-winprod-data-rw` sshfs pattern — the standing mount at `~/denidin-winprod-data` is
   read-only). Tear it down after.
4. Dry-check: run with `--since 2026-08-05` and **without** `--yes`. Review the printed target
   `--data-root`, chat list, date range, and estimated billed-call count. If wrong, Ctrl-C.
5. **[APPROVAL]** Confirm the estimate looks right → type `yes` at the prompt (or re-run with
   `--yes`).
6. The script runs: per `(chat, date)` — `is_rolled` skip / `try_claim` / gather / summarize
   (billed) / `remember` / `commit`. A mid-run per-item failure aborts loudly; re-run resumes from
   the markers.
7. Review the **per-chat report** (days processed, summaries created, empty days, billed calls).
   Confirm `SC-005`: every non-empty calendar day 2026-08-05 → cutoff has exactly one summary,
   0 gaps, 0 duplicates.
8. Tear down the read-write mount.
9. **[APPROVAL]** Deploy the new-model code to prod (`scripts/cut_release.sh` +
   `scripts/deploy_release.sh` — Feature 034; `morning-mcp-app` first, then `denidin-app`;
   version string supplied by the human). This is a separate, fully explicit decision — **not**
   part of this feature and **not** part of haleluya.
10. Post-deploy (read-only): confirm the startup catch-up sweep log shows it rolled only the
    genuinely-recent un-rolled days, and that `roll_markers.db` has one row per `(chat, date)`
    since go-live.

### Idempotency

Re-running with the same args after a completed run makes **0 OpenAI calls and writes 0 new
records** (SC-010) — the roll markers are the dedup key and are shared with the app's nightly roll.

### Dev / sandbox (the AC-4 acceptance test)

`apps/rolling-memory-backfill/tests/test_backfill.py` points the real script at a dev chat seeded
with > 14 days of history and runs it for real (billed) — asserts summary/marker coverage, an
idempotent re-run, unchanged raw files, and that a follow-up `_sweep_daily_roll` skips every
migrated day. This is the US4 acceptance tier; it runs in Phase 4.

---

## Part 2 — US5 log-retention audit finding

### Finding (measured live 2026-09-02 via the `denidin-winprod` docker context + the read-only
`~/denidin-winprod-data` mount)

**App-level file logging — `apps/denidin-app/src/utils/logger.py`:**

- `RotatingFileHandler`, **size-based**, `maxBytes = 10 MB`, `backupCount = 5`. No time-based
  rotation, no gzip, no `logging.basicConfig` / `dictConfig`.
- **Every module** gets its **own** handler on the **same** file `logs/denidin.log`, with
  `propagate = False`. Plus a `StreamHandler` (stderr), a `LocalTimeFormatter` (renders
  `Asia/Jerusalem` with `%z`), and a `_VersionFilter`.
- `/app/logs` is a host bind mount (`docker-compose.prod.yml` → `./apps/denidin-app/logs/prod`,
  and on the Windows box under the repo checkout there).
- Byte-identical logger twin in `apps/morning-mcp-app`.

**Live prod `logs/prod/` contents:**

| file | size | mtime |
|---|---|---|
| `denidin.log` | ~6.99 MB (active) | current |
| `denidin.log.1` | 8.4 KB | 2026-08-31 14:59 |
| `denidin.log.2` | 11 KB | 2026-08-31 15:08 |
| `denidin.log.3` | 3.7 KB | 2026-08-31 14:59 |
| `denidin.log.4` | 27 KB | 2026-08-31 14:59 |
| `denidin.log.5` | 9.2 KB | 2026-08-31 14:56 |

- The `.1`–`.5` backups are **KB-sized, not 10 MB**, and **out of chronological order** (`.2` is
  newer than `.1`). **Nothing before 2026-08-31 15:08 survives** — go-live was 2026-08-05, so
  ~26 days of application logs are already permanently gone.
- **Root cause — multi-handler rotation race**: each module's `RotatingFileHandler` holds its own
  fd to `denidin.log`. When one handler crosses 10 MB and does its rename cascade
  (`.4→.5`, `.3→.4`, …, `denidin.log→.1`), the other handlers still hold stale fds and, a few KB
  of writes later, each trips *its own* `shouldRollover` and runs *its own* cascade — five
  near-simultaneous cascades producing five tiny, scrambled fragments and discarding the real
  10 MB of history.

**Docker `json-file` driver (the `docker logs` stream):**

- `Opts = map[]` — **no `max-size` / `max-file`** on either service in either compose file. The
  daemon default applies: a single unbounded `/var/lib/docker/containers/<id>/<id>-json.log` that
  grows for the whole container lifetime and is only reset by a deploy (container recreate).

### Verdict against REQ-MEM-050/051

**Retention is NOT guaranteed today.** Rotation by size silently destroys history (the race), and
the `docker logs` stream is unbounded-then-reset-on-deploy. Neither is a reliable system of record.

### Fix (plan Phase 5 — full fix, plan-mode decision B)

See [`contracts/logger-retention.md`](./contracts/logger-retention.md). In short:

1. **One handler set, on the root logger** — `setup_logger` attaches the file + console handlers
   once to `logging.getLogger()`; `get_logger(name)` returns a propagating child with no handlers.
   One file, one rotation authority → the race is structurally impossible.
2. **`TimedRotatingFileHandler(when="midnight", backupCount=0)` + gzip** — one segment per day,
   `denidin.log.YYYY-MM-DD.gz`, **never** pruned by the app (`backupCount=0`).
   `memory.archive_retention_days`'s sibling for logs is a *documented deliberate* "retain
   forever"; a future pruner is a separate decision.
3. **Compose `logging:` cap** — `json-file` `max-size: "50m"`, `max-file: "5"` on **both**
   `denidin-app-<env>` and `morning-mcp-app-<env>` in **both** `docker-compose.prod.yml` and
   `docker-compose.dev.yml`. The `docker logs` loss is now bounded and **acceptable only because
   the app file handler independently holds full history** (REQ-MEM-053b) — this dependency is
   stated here and in `docker/` review notes.

### Implemented shape (confirmed against the code — T053b)

- `apps/denidin-app/src/utils/logger.py` and `apps/morning-mcp-app/src/denidin_mcp_morning/
  utils/logger.py` share an identical **core** (`_gzip_namer`, `_gzip_rotator`, `_build_file_handler`,
  `setup_logger`, `reconfigure_file_rotation`, `get_logger`, formatter/filter). Documented per-app
  deltas only: module docstring, `log_filename` default, `log_level` default (`INFO` for
  morning-mcp), `DEFAULT_VERSION_FILE` depth, and morning-mcp's extra
  `reconfigure_package_log_level`. `test_logger_retention_integration.py::TestTwinCoreIsMirrored`
  asserts the core stays in sync.
- `setup_logger` attaches one `TimedRotatingFileHandler(backupCount=0)` + gzip rotator + one
  `StreamHandler` to the **root** logger, guarded by handler identity (`rotator is _gzip_rotator`)
  so it never stacks and survives pytest's per-test root-handler churn. `_VersionFilter` is on the
  **handlers** (not the root logger) so `%(version)s` resolves for records propagating up from
  child loggers.
- Every module's import-time `get_logger(__name__)` configures the root with the built-in
  defaults; `denidin.py` then calls `reconfigure_file_rotation(config.logging[...])` right after
  config load to apply the real values (a no-op swap when they match the defaults, the common case).
- The gzip `rotator` is **fail-safe**: on a compression error it leaves the rotated plaintext
  segment in place (never `os.remove`) and re-raises — a segment is never lost. Rotation is
  lossless (within-process handler lock serialises `emit` vs `doRollover`).
- Compose: `logging: {driver: json-file, options: {max-size: "50m", max-file: "5"}}` on all four
  service entries (`denidin-app` + `morning-mcp-app`, dev + prod). `docker compose config` shows
  `max-file: "5"` / `max-size: 50m` on each.

### Forced-rotation verification procedure

**Non-prod** (`test_logger_retention.py`, both apps + `test_logger_retention_integration.py`):
point `setup_logger` at a tmp dir with a sub-second `when`, emit enough lines to force ≥ 3
rotations, assert every `*.gz` segment exists, decompresses, and its content is intact and
ordered; assert the root logger ends with exactly one gzip file handler; assert a multi-thread
burst spanning ≥ 2 rotations loses/duplicates zero records; assert a raising rotator keeps the
plaintext segment.

**Post-deploy prod** (read-only, via the `denidin-winprod` docker context):

```
docker --context denidin-winprod compose -f docker/docker-compose.prod.yml exec denidin-app-prod ls -la /app/logs
docker --context denidin-winprod inspect denidin-app-prod --format '{{.HostConfig.LogConfig.Config}}'
```

Expect: dated `.gz` segments accumulating one per day, chronologically ordered, ~similar sizes; and
`map[max-file:5 max-size:50m]` from the `inspect`. `SC-009`: after the first real midnight
rotation, the prior day's segment is present as a `.gz` on disk.
