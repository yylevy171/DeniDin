# Script Contracts (Feature 078)

Per METHODOLOGY.md §VII, this is a multi-component feature (Windows-side backup script ↔
Mac-side pull/retention script ↔ Windows Task Scheduler ↔ existing prod SSH/mount
infrastructure) — each interaction is documented below.

---

### `run_daily_backup.sh` (Windows/WSL2) ↔ Windows Task Scheduler

**Windows Task Scheduler MUST**:
- Trigger `run_daily_backup.sh` (via `wsl.exe`, same pattern as
  `register_prober_schedule.sh`) at exactly 03:00 Israel time, daily, regardless of
  `denidin-app-prod`/`morning-mcp-app-prod` container health.
- Not retry automatically on failure (single daily attempt; a missed/failed run is surfaced via
  exit code + log, not silently retried into overlapping runs — see below).

**`run_daily_backup.sh` PROVIDES**:
- Exit code `0` only if: a complete, valid `.tgz` was written to the Windows daily-backup folder,
  every SQLite `.backup` sub-step succeeded, and (if applicable) the monthly promotion/purge
  succeeded. Any partial failure exits non-zero (CONSTITUTION §XVI) and leaves no partially-written
  `.tgz` in the target folder (writes to a `.tgz.partial` path first, `mv` into place only on full
  success — so a failed run never produces a file that looks complete but isn't).
- One line per major step to its own log file (`logs/backup_prod/run_daily_backup_<date>.log`,
  mirroring the existing `logs/health_monitoring/<env>/verify.log` precedent) — never stdout-only,
  since this runs unattended under Task Scheduler with no live terminal to read.

**`run_daily_backup.sh` EXPECTS**:
- Read access to `data/`, `config/`, `logs/prod/` under prod's real paths on the Windows host
  (the same paths `docker-compose.prod.yml`/`.local.yml` bind-mount into the containers).
- A config file (`scripts/backup_prod/config.json` or equivalent, gitignored per this repo's
  "config is code, no env vars" rule) naming the daily/monthly backup folder paths on this host —
  never hardcoded inline in the script.
- The `sqlite3` CLI available in the WSL2 environment (already relied on implicitly elsewhere in
  this repo's WSL/bash tooling).

---

### `run_daily_backup.sh` (Windows) ↔ `pull_backups.sh` (Mac)

**`pull_backups.sh` MUST**:
- Only ever read from the Windows host over the existing `denidin-winprod` SSH alias (never write
  to it, never touch the live `data`/`config` prod paths) — strictly a pull of already-finished
  `.tgz` files out of the two backup folders.
- Tolerate zero, one, or many new archives since its last run (Mac may have been asleep across
  several 03:00 windows) and pull all of them, oldest first.
- Run its own retention purge (research.md R5) locally after a successful pull, independent of
  whatever the Windows side already purged.

**`run_daily_backup.sh` PROVIDES** (as the thing being pulled from):
- Fully-written `.tgz` files only — `pull_backups.sh` never observes a `.tgz.partial` file (see
  above: atomic rename means partial files never appear under the real folder names `rsync`/`scp`
  lists).
- Stable folder paths (`denidin daily backups/`, `denidin monthly backups/`) that don't change
  shape between runs.

**`pull_backups.sh` EXPECTS**:
- The `denidin-winprod` SSH host alias already configured (Feature 035 quickstart §2) and
  Tailscale-reachable — if unreachable, exits non-zero with a clear log line and does nothing
  destructive (no partial local purge on a failed pull).

---

### `verify_restore.sh` (Mac, manual) ↔ Backup Archive

**`verify_restore.sh` MUST**:
- Never run against a live/real data path — always un-tars into a fresh temp directory.
- Run `PRAGMA integrity_check` against every `.db` file found in the extracted archive and report
  each file's result individually (not just an overall pass/fail), so a single corrupt store is
  identifiable.

**Backup Archive PROVIDES**:
- A self-contained tree (`data/`, `config/`, `logs/prod/`) sufficient to boot `denidin-app`
  against it via an ephemeral compose override pointed at the temp directory, per SC-002/UAT-3.
