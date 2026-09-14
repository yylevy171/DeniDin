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

`scripts/backup_prod/config.json` (gitignored, one real copy per host) is written on both real
hosts with these values (Windows side placed 2026-09-14, see step 1).

## Prerequisites

- Feature 035's Windows always-on prod box already set up (Tailscale, `denidin-winprod` SSH
  alias, WSL2) — this feature adds a new scheduled task alongside the existing health-monitoring
  prober, it does not set up the box itself.
- `sqlite3` and `jq` CLIs available in the Windows box's WSL2 environment — **confirmed installed**
  (2026-09-14).
- The two backup folders on each host — created on first real run (`run_daily_backup.sh`/
  `pull_backups.sh` both `mkdir -p` their targets); both exist on both hosts as of 2026-09-14.

## 1. Windows box: configure and register the backup job — done, 2026-09-14

1. `config.json` placed on the Windows box (via the real release-scripts bundle mechanism, not
   ad-hoc scp of just this file — see `scripts/lib/release_scripts_manifest.sh`'s header for why
   backup_prod scripts ship on every release like the health-monitoring prober does). **Done.**
2. `./scripts/backup_prod/register_backup_schedule.sh run enable --config scripts/backup_prod/config.json`
   — registered the 03:00 Israel-local Windows Scheduled Task (`DeniDinBackup-run`). **Done** —
   confirmed `Next Run Time` lands at 03:00 IDT (the box's own local time is already Israel per
   Feature 035 setup).
3. **Verified**: `trigger-once` run for real — full archive created (all 5 real SQLite stores hot-
   backed-up, ~347MB, ~50s wall time), landed in `denidin-backups/daily/`, retention purge ran
   clean. Two real bugs were found and fixed only by this live run (both now fixed and verified):
   the box's `date` is `uutils coreutils`, not GNU, which rejected the `@epoch -N days` syntax the
   retention-purge helper originally used; and `register_backup_schedule.sh` was embedding a
   *relative* `--config` path into the scheduled task definition, which silently fails since a
   Windows Scheduled Task's `wsl.exe -e bash -lc` starts in `$HOME`, not the registering shell's
   cwd — fixed by resolving `--config` to an absolute path before either platform branch builds
   its task/plist.

## 2. Mac: configure and schedule the pull — done, 2026-09-14

1. `scripts/backup_prod/config.json` exists on this Mac with real values. **Done.**
2. `./scripts/backup_prod/register_backup_schedule.sh pull enable --config scripts/backup_prod/config.json`
   — registered the hourly LaunchAgent (`com.denidin.backuppull`). **Done.**
3. **Verified**: `pull_backups.sh` run for real via the LaunchAgent's `trigger-once` — pulled the
   real 347MB daily archive from the Windows box byte-identical, handled the (then-empty) monthly
   tier cleanly, local retention purge ran clean. One real bug found and fixed live: a plain
   `rsync -e "ssh ..."` breaks against this box's cmd.exe SSH DefaultShell on any remote path
   containing a space (the real backup dirs live under `Yaron Levi`, a Windows username with a
   space) — fixed by adding `scripts/backup_prod/lib/rsync_wsl_transport.sh`, which routes the
   actual remote `rsync --server` invocation through WSL2 instead (see that file's header for the
   full mechanism). Also separately verified the monthly tier specifically: manually seeded the
   Windows box's `monthly/` folder with a copy of that day's daily archive (simulating what
   `run_daily_backup.sh`'s own 1st-of-month promotion already does automatically) and confirmed
   the Mac's hourly pull picked it up with no code changes needed.

## 3. Prove zero-downtime (UAT 1)

While `denidin-app-prod` is live and being messaged on WhatsApp, run
`./scripts/backup_prod/register_backup_schedule.sh run trigger-once --config ...` and confirm the
bot keeps responding throughout with no observable delay. Every real `trigger-once` run performed
during this feature's live rollout (2026-09-14) ran purely as an external filesystem
reader/`.backup`-API user, never touching `docker compose` — consistent with the zero-downtime
guarantee, though a live WhatsApp round-trip *during* a run specifically wasn't separately staged
as its own test.

## 4. Prove restore integrity (SC-002 / UAT 3) — integrity half done live, 2026-09-14

`./scripts/backup_prod/verify_restore.sh "denidin-backups/daily/denidin-prod-backup-<date>.tgz"` —
confirms every SQLite store passes `PRAGMA integrity_check` (fully automated, already tested; run
for real against the actual pulled Mac-side archive, 2026-09-14 — all 5 real stores PASS). The
boot-smoke-check half (actually booting `denidin-app` against the extracted data) is **deliberately
left as a manual step, not automated**, per an explicit 2026-09-14 decision — `verify_restore.sh`'s
integrity-check coverage is the real corruption-detection guarantee; automating the boot check too
was judged not worth the added Docker-dependent test-infrastructure complexity for launch. Revisit
if it becomes a recurring manual chore.

## 5. Prove retention purge (UAT 4/5)

Not exercised live on a full 30-day/36-month cadence during initial rollout (there's no aged
backlog yet) — covered by unit tests against synthetic filename-dated fixtures (tasks.md), plus a
documented manual spot-check any time after the feature has been live for 30+ days (UAT 4) / at
the next real 1st-of-month (UAT 5, next occasion 2026-10-01). The purge *codepath* itself has been
exercised live and confirmed to exit cleanly on both hosts as part of every `trigger-once`/pull run
above (2026-09-14) — including a real bug found and fixed there (the Windows box's `date` is
`uutils coreutils`, not GNU, and rejected `retention_purge.sh`'s original `@epoch -N days` syntax;
fixed by applying the relative offset to the plain date string instead). The monthly tier's
pull/purge side was also specifically verified live via a manual seed (see §2.3 above); only the
*automatic 1st-of-month promotion trigger itself* (already covered by unit tests with a frozen
`--today`) remains unobserved on a real calendar date.
