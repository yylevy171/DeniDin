# Research: Automated Daily Prod Backups (Feature 078)

## R1: Where the backup job runs and how it's scheduled

**Decision**: A new bash script, `scripts/backup_prod/run_daily_backup.sh`, invoked via a
**Windows Scheduled Task** (`schtasks.exe`) at 03:00 Israel time, registered/managed by a sibling
`register_backup_schedule.sh` — the same mechanism bugfix-043's health-monitoring prober already
uses (`scripts/health_monitoring/register_prober_schedule.sh`): platform-detected via `uname`,
Darwin → LaunchAgent (for dev-box testing only), Linux/WSL2 (the real prod box, per Feature 035)
→ `schtasks.exe` running `wsl.exe` against this repo's own path. No new scheduling primitive is
introduced.

**Rationale**: Feature 035 established WSL2 + `schtasks.exe` as prod's only real scheduler
(there is no host-level cron on the Windows box, and Task Scheduler survives reboots without
manual re-arming — required by REQ-078-04's "after Feature 070's own nightly 02:00 roll" framing,
which itself already relies on the container-internal `APScheduler`/`CronTrigger`, a *different*
mechanism scoped to code running *inside* a container). This backup job explicitly runs
**outside any app container** (REQ-078-03), so it cannot reuse `APScheduler` — it needs an
OS-level trigger independent of whether `denidin-app-prod`/`morning-mcp-app-prod` are even
healthy, which is also why it must not be blocked by, or block, container health.

**Alternatives considered**:
- A `CronTrigger` job inside `denidin-app-prod` itself — rejected: REQ-078-02/03 require the
  backup to be external to the app container and to survive/be unaffected by an app crash or
  restart; coupling backup liveness to app container health defeats the point of a disaster
  recovery mechanism.
- Windows native Task Scheduler GUI configuration (no script) — rejected: every other prod-side
  scheduled mechanism in this repo (`prober.py`'s LaunchAgent/Task) is provisioned by a checked-in,
  re-runnable script, not a manual one-off GUI step, so state is reproducible and diffable.

## R2: Hot-backup consistency for SQLite and ChromaDB (REQ-078-02)

**Decision**: Use each store's native **online-backup facility**, never a raw file copy of a live
database:
- **SQLite** (`chat_index.db`, `memory_rolls/roll_markers.db`, `reminders/reminders.db`): use the
  SQLite CLI's `.backup` command (`sqlite3 <db> ".backup '<dest>'"`), which uses SQLite's own
  Backup API — safe against concurrent writers, produces a fully consistent snapshot without
  requiring `WAL` checkpointing tricks or locking out the app.
- **ChromaDB** (`data/memory/`, the persistent-client on-disk store — DuckDB+Parquet or SQLite
  depending on ChromaDB's configured backend in this repo): confirmed via `grep` that this repo's
  `MemoryManager` uses `chromadb.PersistentClient` with the default (SQLite-backed as of the
  ChromaDB version pinned in `apps/denidin-app/requirements.txt`) — so it is covered by the same
  SQLite `.backup` treatment; the on-disk Parquet/binary blob files ChromaDB also writes are
  ordinary files, safe to include in the same `tar` pass as everything else since they are
  written-once/append-only per collection segment, not rewritten in place.
- Everything else under `data/`/`config/`/`logs/prod/` (JSON event files, media, reminders'
  non-DB assets, logs) is already append-only or write-once per file (see CLAUDE.md's
  `LedgerEventManager`/`daily_summary_roll_service.py`/`reminder_manager.py` notes — no in-place
  rewrite of an existing JSON file anywhere in this codebase) — an ordinary `tar` read mid-write
  can at worst catch a file that is still being appended to, which `tar` handles as a truncated
  read of that one file, never as corruption of the archive itself or of unrelated files.

**Rationale**: matches CLAUDE.md's own explicit call-out ("Engineers must ensure database
consistency for SQLite/ChromaDB during a hot backup") and SC-002 ("no SQLite corruption").
`.backup` snapshots are the documented, supported hot-backup mechanism for SQLite and require no
new dependency (the `sqlite3` CLI is already present in the prod WSL2 environment other scripts
in this repo rely on — e.g. `scripts/windows_prod/*.sh`'s own WSL/bash assumptions).

**Alternatives considered**:
- Plain `cp`/`tar` directly on the live `.db` files — rejected: a concurrent writer mid-transaction
  can produce a torn/inconsistent copy; this is exactly the failure mode SC-002 exists to rule out.
- `VACUUM INTO` — rejected: rewrites/compacts on every run (slower, unnecessary I/O for a daily
  job) where `.backup` already gives a consistent snapshot without compaction.

## R3: Archive format & naming (REQ-078-03)

**Decision**: `tar czf` producing `denidin-prod-backup-YYYY-MM-DD.tgz`, built in a **staging
directory** (SQLite backups + a `tar`-friendly snapshot of everything else) so the final `tar czf`
invocation only ever reads already-consistent, static files — never a live path under `data/`
directly for the three SQLite stores.

**Rationale**: REQ-078-03's literal filename example (`YYYY-MM-DD`) plus needing one atomic,
single-file artifact per SC-001/SC-002 (a restore test un-tars one file into an isolated
environment).

## R4: Windows→Mac transfer (REQ-078-05/06, UAT 2/5)

**Decision**: **Pull**, not push — the Mac side (`scripts/backup_prod/pull_backups.sh`) runs
`rsync`/`scp` over the already-established `denidin-winprod` SSH host alias (same one
`scripts/windows_prod/tail_logs.sh`/`mount_data.sh` already use, per CLAUDE.md's "Quick reference
for reading prod data/logs" section) to copy new files from the Windows host's
`denidin daily backups`/`denidin monthly backups` folders into matching local folders. Triggered
on the Mac side by the existing sshfs-backed persistent-mount LaunchAgent's cadence-equivalent
pattern (a lightweight new LaunchAgent that runs `pull_backups.sh` on a schedule, since the Mac —
unlike the Windows box — is not always on, so the pull must be resilient to "Mac was asleep at
03:00" by simply pulling whatever is new whenever it next runs, not depending on a precise
same-minute handoff).

**Rationale**: Reuses the exact transport (`denidin-winprod` SSH alias, Tailscale-reachable) and
directionality precedent (`tail_logs.sh` already reads *from* the Windows box; sshfs mount already
reads `data`/`logs` *from* the Windows box) instead of introducing a new push credential/secret
*from* Windows *to* the Mac, which would need its own new key and open a new inbound attack
surface on the Mac. Pull-on-a-schedule also naturally tolerates the Mac being asleep/off at exactly
03:00 — a push at that instant would simply fail with no automatic catch-up window.

**Alternatives considered**:
- Push from Windows via `scp` to the Mac — rejected: Mac must be always-reachable at exactly
  03:00 for this to work, which it explicitly is not (unlike the Windows box, the Mac sleeps);
  also requires provisioning a new Windows→Mac credential where none currently exists in either
  direction (today's SSH trust is Mac→Windows only).
- Cloud storage (S3/Backblaze/etc.) as the sole redundant copy — explicitly out of scope per
  REQ-078-06 ("A third undefined cloud-storage location will be managed manually for now").

## R5: Retention/purge mechanics (REQ-078-05/06, UAT 4/5)

**Decision**: Retention purging runs on **both** sides independently, driven by each archive's own
filesystem mtime / filename date, not a separate manifest:
- Windows side: `run_daily_backup.sh` purges `denidin daily backups/*.tgz` older than 30 days at
  the end of every run, and promotes (copies) the run's own archive into
  `denidin monthly backups/` + purges monthly archives older than 36 months, but **only when
  today is the 1st of the month** (REQ-078-06).
- Mac side: `pull_backups.sh` runs the identical purge logic locally after a successful pull, so a
  Mac that was offline for several days and pulls a backlog in one run still converges to the same
  30-day/36-month retention window as the Windows side, rather than accumulating unpruned extras.

**Rationale**: Two independent, identically-defined purge passes (same day-count math, same
filename-date parsing) avoid needing a shared source of truth for "what has been purged" across
two machines connected only by an unreliable link (Mac may be asleep for the actual purge moment);
each side is self-consistent purely from what's on its own disk.

## R6: Zero-downtime guarantee (REQ-078-02, UAT 1)

**Decision**: The backup script never touches `docker compose stop/restart` and never sends any
signal to the running containers — it operates purely as an external filesystem reader against the
Windows host paths already used as bind-mount sources for `denidin-app-prod` (per CLAUDE.md's
`docker-compose.prod.local.yml` volume mapping). A pre-flight check confirms `denidin-app-prod`/
`morning-mcp-app-prod` are healthy via the same `/health`-style check `verify_windows_prod.sh`
already performs, purely for **incident visibility** (log a warning if the app is unhealthy at
backup time) — never as a gate that skips or blocks the backup itself, since a backup is most
valuable exactly when something may already be wrong.

**Rationale**: Directly satisfies REQ-078-02/UAT-1 ("MUST NOT be paused or stopped" /
"MUST continue responding... without any delay or downtime").

## R7: Restore-test tooling (SC-002, UAT 3)

**Decision**: A `scripts/backup_prod/verify_restore.sh` helper (Mac-side, run manually/on-demand,
never automatically) that un-tars a named archive into an isolated temp directory and runs a
`sqlite3 <db> "PRAGMA integrity_check;"` against every `.db` file found, plus a lightweight
"does `denidin-app` boot against this data root" smoke check reusing the existing local-container
run path (`docker compose ... --project-directory <temp> ...` against an ephemeral compose
override), never against real prod ports/credentials. This directly operationalizes SC-002/UAT-3
without requiring a human to hand-roll the restore steps each time.

**Rationale**: SC-002 explicitly requires a **provable** restore test, not just "the archive
exists" — `PRAGMA integrity_check` is SQLite's own supported corruption-detection query, and an
actual boot is the strongest available assertion the archived data is usable.
