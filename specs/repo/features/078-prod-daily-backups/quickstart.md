# Quickstart: Automated Daily Prod Backups (Feature 078)

One-time setup + how to verify it's working. Both `run_daily_backup.sh` (Windows) and
`pull_backups.sh`/`verify_restore.sh` (Mac) are checked-in, re-runnable scripts under
`scripts/backup_prod/` — no manual GUI-only steps, consistent with this repo's existing
Feature 035 / bugfix-043 scheduling precedent.

## Prerequisites

- Feature 035's Windows always-on prod box already set up (Tailscale, `denidin-winprod` SSH
  alias, WSL2) — this feature adds a new scheduled task alongside the existing health-monitoring
  prober, it does not set up the box itself.
- `sqlite3` CLI available in the Windows box's WSL2 environment.
- `jq` CLI available in the Windows box's WSL2 environment (and on the Mac) — used by
  `lib/load_config.sh` to parse `config.json`; not previously required by any other prod-side
  script, so verify with `jq --version` rather than assuming it's already present.
- Two new folders created on the Windows host (outside the repo, alongside where prod data
  already lives): `denidin daily backups/`, `denidin monthly backups/`.
- Two matching folders created on the Mac: `denidin daily backups/`, `denidin monthly backups/`.

## 1. Windows box: configure and register the backup job

1. Copy `scripts/backup_prod/config.example.json` → `scripts/backup_prod/config.json` (gitignored,
   per this repo's "config is code" convention) and fill in the real absolute paths for the two
   backup folders and prod's `data`/`config`/`logs/prod` source paths on this host.
2. `./scripts/backup_prod/register_backup_schedule.sh prod enable` — registers the 03:00
   Israel-local Windows Scheduled Task (mirrors
   `scripts/health_monitoring/register_prober_schedule.sh`'s enable/disable/trigger-once
   interface).
3. **Verify**: `./scripts/backup_prod/register_backup_schedule.sh prod trigger-once`, then check
   `logs/backup_prod/run_daily_backup_<today>.log` on the Windows host and confirm a new `.tgz`
   landed in `denidin daily backups/`.

## 2. Mac: configure and schedule the pull

1. Copy `scripts/backup_prod/config.example.json` → `scripts/backup_prod/config.json` on the Mac
   side too, filling in the Mac-local backup folder paths (the Windows-side source paths are
   discovered via the existing `denidin-winprod` SSH alias, not repeated here).
2. Register the Mac-side pull LaunchAgent (script name TBD in tasks.md — same
   `launchctl load`/`unload` shape as `scripts/windows_prod/install_persistent_mount.sh`).
3. **Verify**: run `./scripts/backup_prod/pull_backups.sh` once by hand and confirm the archive
   from step 1.3 now also exists locally under the Mac's `denidin daily backups/`.

## 3. Prove zero-downtime (UAT 1)

While `denidin-app-prod` is live and being messaged on WhatsApp, run
`./scripts/backup_prod/register_backup_schedule.sh prod trigger-once` and confirm the bot keeps
responding throughout with no observable delay.

## 4. Prove restore integrity (SC-002 / UAT 3)

`./scripts/backup_prod/verify_restore.sh "denidin daily backups/denidin-prod-backup-<date>.tgz"`
— confirms every SQLite store passes `PRAGMA integrity_check` and that `denidin-app` boots against
the extracted data in an isolated, throwaway environment (never real prod ports/credentials).

## 5. Prove retention purge (UAT 4/5)

Not exercised live on a 30-day/36-month cadence during initial rollout — covered by unit tests
against synthetic filename-dated fixtures (tasks.md), plus a documented manual spot-check any time
after the feature has been live for 30+ days.
