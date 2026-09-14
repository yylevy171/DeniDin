# Quickstart: Automated Daily Prod Backups (Feature 078)

One-time setup + how to verify it's working. `run_daily_backup.sh` (Windows),
`pull_backups.sh`/`verify_restore.sh` (Mac), and `register_backup_schedule.sh` (both, role-gated)
are checked-in, re-runnable scripts under `scripts/backup_prod/` — no manual GUI-only steps,
consistent with this repo's existing Feature 035 / bugfix-043 scheduling precedent.

## Real values (confirmed live against the actual boxes, 2026-09-14)

| Key | Real value |
|---|---|
| `data_dir` (Windows) | `/mnt/c/Users/Yaron Levi/denidin-prod-data` (native Windows path — `docker-compose.prod.local.yml` overrides it here, not the WSL-relative default, because Windows SFTP/sshfs can't reach into WSL2) |
| `config_dir` (Windows) | `/home/yaron_levi/denidin-prod/apps/denidin-app/config` |
| `logs_prod_dir` (Windows) | `/home/yaron_levi/denidin-prod/apps/denidin-app/logs/prod` |
| `daily_backup_dir` / `monthly_backup_dir` (Windows) | `%USERPROFILE%\denidin-backups\{daily,monthly}` → `/mnt/c/Users/Yaron Levi/denidin-backups/{daily,monthly}` in WSL2 |
| `mac_daily_backup_dir` / `mac_monthly_backup_dir` | `/Users/yaron/denidin-backups/{daily,monthly}` |
| `ssh_host_alias` | `denidin-winprod` (existing Feature 035 alias) |
| Mac pull cadence | hourly (`StartInterval` 3600s) |
| `jq` / `sqlite3` on the Windows WSL2 box | installed 2026-09-14 (were missing) |

`scripts/backup_prod/config.json` (gitignored, one real copy per host) is already written for this
Mac with these values. The equivalent Windows-side `config.json` still needs to be placed on that
box — see step 1 below.

## Prerequisites

- Feature 035's Windows always-on prod box already set up (Tailscale, `denidin-winprod` SSH
  alias, WSL2) — this feature adds a new scheduled task alongside the existing health-monitoring
  prober, it does not set up the box itself.
- `sqlite3` and `jq` CLIs available in the Windows box's WSL2 environment — **confirmed installed**
  (2026-09-14).
- The two backup folders on each host — **not yet created** (`register_backup_schedule.sh`'s
  `enable` action creates the log dir but not the backup dirs themselves; `run_daily_backup.sh`
  does `mkdir -p` on both, so the very first run creates them if missing).

## 1. Windows box: configure and register the backup job

1. Place a `scripts/backup_prod/config.json` on the Windows box (same shape as this Mac's copy,
   using this table's Windows-side values) — either `scp` it over, or recreate it by hand from the
   table above. **Not yet done — needs explicit approval, since it writes to the real prod box.**
2. `./scripts/backup_prod/register_backup_schedule.sh run enable --config scripts/backup_prod/config.json`
   — registers the 03:00 Israel-local (system-local time on that box) Windows Scheduled Task.
   **Not yet done — needs explicit approval (environment-start rule).**
3. **Verify**: `./scripts/backup_prod/register_backup_schedule.sh run trigger-once --config ...`,
   then check `logs/backup_prod/run_daily_backup_<today>.log` on the Windows host and confirm a new
   `.tgz` landed in `denidin-backups/daily/`. **Not yet done.**

## 2. Mac: configure and schedule the pull

1. `scripts/backup_prod/config.json` already exists on this Mac with real values (done).
2. `./scripts/backup_prod/register_backup_schedule.sh pull enable --config scripts/backup_prod/config.json`
   — registers the hourly LaunchAgent. **Not yet done — needs explicit approval.**
3. **Verify**: run `./scripts/backup_prod/pull_backups.sh --config scripts/backup_prod/config.json`
   once by hand and confirm the archive from step 1.3 now also exists locally under
   `~/denidin-backups/daily/`. **Not yet done** (depends on step 1 completing first).

## 3. Prove zero-downtime (UAT 1)

While `denidin-app-prod` is live and being messaged on WhatsApp, run
`./scripts/backup_prod/register_backup_schedule.sh run trigger-once --config ...` and confirm the
bot keeps responding throughout with no observable delay.

## 4. Prove restore integrity (SC-002 / UAT 3)

`./scripts/backup_prod/verify_restore.sh "denidin-backups/daily/denidin-prod-backup-<date>.tgz"` —
confirms every SQLite store passes `PRAGMA integrity_check` (fully automated, already tested). The
boot-smoke-check half (actually booting `denidin-app` against the extracted data) is **deliberately
left as a manual step, not automated**, per an explicit 2026-09-14 decision — `verify_restore.sh`'s
integrity-check coverage is the real corruption-detection guarantee; automating the boot check too
was judged not worth the added Docker-dependent test-infrastructure complexity for launch. Revisit
if it becomes a recurring manual chore.

## 5. Prove retention purge (UAT 4/5)

Not exercised live on a 30-day/36-month cadence during initial rollout — covered by unit tests
against synthetic filename-dated fixtures (tasks.md), plus a documented manual spot-check any time
after the feature has been live for 30+ days.
