# Feature Specification: Automated Daily Prod Backups — full state (data, logs, config, shared)

**Feature Branch**: `feature/078-prod-daily-backups`
**Created**: 2026-09-06
**Status**: DRAFT — problem statement only. Needs the full `speckit.specify` → `speckit.clarify`
→ `speckit.plan` → `speckit.tasks` pipeline before any implementation.
**Input**: User request 2026-09-06, immediately after a partial prod outage (Green API de-auth +
`morning-mcp-app-prod` watchdog self-termination + manual container recovery) and while staging
the Feature 070 prod migration, which relies entirely on ad-hoc `cp -r` / `rsync` backups taken
by hand at migration time. There is **no standing backup of prod**. A disk failure, a bad
deploy, a botched migration, or accidental deletion would be unrecoverable.

---

## Why this is needed

- **Zero-incident is the project standard** (CLAUDE.md). A standing, automated, verified backup
  is table stakes for that claim and is currently missing.
- **Prod lives on a single Windows laptop** (Feature 035) with a single local disk. No RAID, no
  replication. One hardware failure = total loss of every session, ledger event, memory
  embedding, reminder, and media file.
- **Every risky operation today assumes a hand-made backup.** The Feature 070 migration runbook,
  the 2026-09-06 bleed-stopgap (marking 90 sessions), any future `deploy_release.sh` to prod —
  each one currently depends on the operator remembering to `cp -r` first. That is fragile and
  was nearly skipped during the 2026-09-06 incident.
- **Restore has never been tested.** Per the 2026-08-25 reboot-recovery incident lesson
  ("verified end-to-end, not just 'the process ran'"), a backup that has never been restored is
  not a backup.

## What must be backed up (to be finalised in `speckit.clarify`)

| source | contents | notes |
|---|---|---|
| `denidin-app-prod` `data/` | `sessions/`, `events/` (ledger), `memory/` (ChromaDB — the 256 MB `chroma.sqlite3` + segments), `media/`, `reminders/reminders.db`, `accounting_reconciliation/` | the irreplaceable state; ChromaDB may need a consistent snapshot (see open questions) |
| container logs | `logs/prod/` for both apps | for post-incident forensics — the 2026-09-06 root-cause work depended on `docker logs` that would have rolled off |
| config + credentials | `config/config.prod.json` (both apps), `creds/DeniDin Prod Creds.txt` | secrets — backup destination must be access-controlled / encrypted |
| shared state | `shared/active_env.json`, `shared/mcp-status-prod/` | small, but part of a coherent restore |
| Docker images | the running `:latest` tags | **probably out of scope** — cut releases already live in `/Users/yaron/Projects/DeniDin/artifacts/`; a restore redeploys from there |

## Open questions for `speckit.clarify`

1. **Destination(s).** Options: pull nightly to the Mac (`~/denidin-backups/`, mirrors the
   existing `~/denidin-winprod-data` mount + `~/denidin-migration/` patterns); an external drive
   on the Windows box; a cloud object store (adds a new credential + network dependency +
   encryption question). One destination or two (local fast + offsite)?
2. **Trigger + schedule.** Cron/Task Scheduler on the Windows box, or a LaunchAgent on the Mac
   (like `com.denidin.winprod-mount.plist`)? Daily at what hour (must not collide with the 02:00
   Feature 070 roll or the hourly reconciliation sweep)? Plus an **on-demand** invocation the
   migration/deploy runbooks call as their step 3a.
3. **Retention.** Grandfather-father-son (e.g. 14 daily + 8 weekly + 6 monthly), or flat N-day?
   Disk budget on the destination.
4. **Consistency.** ChromaDB / SQLite files while `denidin-app-prod` is running — is an online
   `rsync` acceptable (SQLite WAL), or does the backup need a brief `docker pause` / stop? The
   Feature 070 migration already stops prod; a nightly backup should not.
5. **Encryption at rest.** The config/creds files contain live production secrets. Age/gpg?
   Or exclude creds and document that they are restored by hand from a password manager?
6. **Integrity + restore verification.** Per-file checksums; a periodic automated restore into a
   throwaway location that boots `denidin-app` against it and confirms a real turn works.
7. **Failure alerting.** A silent backup failure is as bad as no backup. Ties into
   `specs/backlog/028-monitoring-and-alerting`.
8. **Reachability.** The Mac is only connected to the Windows box over Tailscale when home. A
   Mac-pull design must tolerate the Mac being away/asleep and catch up, and must alert if N
   consecutive nights are missed.

## Non-goals

- Real-time replication, HA, or automatic failover.
- Point-in-time / transaction-log recovery for ChromaDB or SQLite.
- Backing up the dev or test environments (dev data is already a cross-clone singleton on the
  Mac; test data is ephemeral).
- Replacing `cut_release.sh`'s image artifacts as the source of truth for deployable code.

## Constraints (CLAUDE.md / CONSTITUTION.md)

- No environment variables — any config for the backup job comes from a config file.
- Israel local time (`now_local()`), timezone-aware timestamps in backup folder names.
- `pathlib.Path`, not string paths.
- If any Python is involved it follows the same lint/type/test gates; if it is pure shell it
  lives under `scripts/` (an "external helper script", like `run_all.sh` / the watchdogs — not
  inside `apps/*/src`), per the watchdog/scripts boundary.
- Restore procedure must be a written, **tested** runbook, not just "rsync it back".

## Relationship to other features

- **Feature 035** (Windows always-on prod) — this extends its operational tooling under
  `scripts/windows_prod/`.
- **Feature 028** (monitoring & alerting, backlog) — backup-failure alerts belong to whatever
  alerting channel 028 establishes.
- **Feature 070** (rolling memory window) — its migration runbook should call this feature's
  on-demand backup as its pre-flight step once this ships, replacing the hand-written `cp -r`.
