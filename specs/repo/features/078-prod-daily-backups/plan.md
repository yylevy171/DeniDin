# Implementation Plan: Automated Daily Prod Backups

**Branch**: `078-prod-daily-backups` | **Date**: 2026-09-14 | **Spec**: `specs/repo/features/078-prod-daily-backups/spec.md`
**Input**: Feature specification from `specs/in-progress/078-prod-daily-backups/spec.md`

**Acceptance-scenario approval**: `user-stories.md`'s 5 UATs were drafted and merged
(`7a17c98`, "docs(078): finalize PM spec and UATs with 2-Tier retention policy") and explicitly
re-confirmed approved by the human operator in this planning session (2026-09-14), per
METHODOLOGY.md §VI.a's pre-plan gate.

---

## Summary

Add a zero-downtime, external-to-container, nightly (03:00 Israel-local) backup pipeline for prod's
`data/`, `config/`, and `logs/prod/` trees on the Windows always-on prod box (Feature 035),
producing one timestamped `.tgz` per day with hot-consistent SQLite/ChromaDB snapshots
(`sqlite3 .backup`, never a raw copy of a live `.db`). A 2-tier retention policy (30 daily / 36
monthly) is enforced independently on both the Windows host and a pulled Mac-side redundant copy,
using the same Windows Scheduled Task + `denidin-winprod` SSH-alias infrastructure bugfix-043's
health-monitoring prober and Feature 035's data mount already established — no new transport,
credential, or scheduling primitive.

## Technical Context

**Language/Version**: Bash (matching every other `scripts/`/`scripts/windows_prod/`/
`scripts/health_monitoring/` script in this repo), WSL2 on the Windows box.
**Primary Dependencies**: `sqlite3` CLI (hot SQLite backup), `tar`/`gzip`, `rsync` or `scp`
(Windows→Mac pull over the existing `denidin-winprod` SSH alias), `schtasks.exe` (via `wsl.exe`,
mirroring `register_prober_schedule.sh`), `launchctl` (Mac-side pull LaunchAgent).
**Storage**: Filesystem only — `.tgz` archives in two folders per host (`denidin daily backups/`,
`denidin monthly backups/`); no new database, no new app-level persisted model (see
`data-model.md`).
**Testing**: Bash script unit tests under `scripts/backup_prod/tests/` (retention-purge date math,
filename parsing, dry-run archive assembly against synthetic fixtures) — same pattern as
`scripts/health_monitoring/tests/`. The Windows-real / SSH-real / live-Task-Scheduler paths have
no automated coverage (same documented gap as `deploy_release.sh`'s remote path and
`register_prober_schedule.sh`'s `schtasks.exe` branch) — verified manually against the real box
per `quickstart.md`.
**Target Platform**: Windows/WSL2 (backup producer, real prod), macOS (pull + local redundant
copy + manual restore verification).
**Project Type**: Single — ops/infra scripts at repo root (`scripts/backup_prod/`), no app code
changes in `apps/denidin-app` or `apps/morning-mcp-app`.
**Performance Goals**: N/A (a nightly batch job; no latency budget beyond "does not visibly delay
live WhatsApp traffic," which REQ-078-02/R6 satisfies structurally by never touching the running
containers).
**Constraints**: Zero-downtime (REQ-078-02); ~330MB per archive (spec's own estimate) — no
explicit size cap enforced by the script itself, purely a sizing expectation to watch for drift.
**Scale/Scope**: One prod environment (dev is explicitly out of scope per spec's "production data
folder" framing); ~30 daily + up to 36 monthly archives resident at steady state per host.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

- **No environment variables / config is code (§I)**: PASS — all paths (backup folders, source
  data roots) live in a new gitignored `scripts/backup_prod/config.json` (`config.example.json`
  committed as the template), loaded by the scripts, never `os.getenv`/shell env vars. Matches
  the existing `config/shared_state.local.json`/`docker-compose.*.local.yml` per-host-config
  precedent.
- **Israel local time everywhere (§II)**: PASS — the 03:00 trigger and every filename/log
  timestamp is Israel-local, matching Feature 070's nightly roll and every other scheduled job in
  this repo; no `datetime.now()`/UTC anywhere (these are bash scripts using `date` with an
  explicit `TZ=Asia/Jerusalem`, not Python, so the Python-specific `now_local()` helper doesn't
  apply directly, but the *rule* — Israel local, never UTC, never system-default — is upheld).
- **No monkey-patching**: N/A — no Python runtime code touched.
- **Zero mocking policy**: PASS — script unit tests exercise real `sqlite3`/`tar` against real
  temp-directory fixtures, never mocked subprocess calls; the SSH/Task-Scheduler real-environment
  paths are explicitly left as manual-verification gaps (same documented pattern as
  `deploy_release.sh`), not faked with mocks to claim false coverage.
- **Exit code standards (§XVI)**: PASS — every script exits 0 only on full success, non-zero
  otherwise, no partial-success ambiguity (see `contracts/script-contracts.md`).
- **Git workflow**: PASS — working on `078-prod-daily-backups` (feature branch off `master`, per
  CLAUDE.md's `feature/###-description`-style requirement — never on `master` directly).
- **"NEVER START AN ENVIRONMENT... WITHOUT EXPLICIT APPROVAL"**: Registering the Windows Scheduled
  Task in `quickstart.md` step 1.2/1.3 and the Mac LaunchAgent in step 2.2 are both real
  prod-environment-affecting actions (they run against the real prod box / real prod data paths)
  — flagged here explicitly so `speckit.implement` and any human operator running the quickstart
  treat them as requiring their own fresh, explicit approval, same as any other environment
  start/scheduled-task registration in this repo. **This plan does not itself perform those
  actions** — it only documents the steps for a human to run later, with approval, same as every
  other quickstart in this repo (e.g. Feature 035's).

No violations requiring the Complexity Tracking table below.

## Project Structure

### Documentation (this feature)

```text
specs/repo/features/078-prod-daily-backups/
├── spec.md              # already exists (PM requirements)
├── user-stories.md       # already exists (approved UATs)
├── plan.md               # this file
├── research.md           # Phase 0 output
├── data-model.md         # Phase 1 output
├── contracts/
│   └── script-contracts.md   # Phase 1 output
└── quickstart.md         # Phase 1 output
(symlinked from specs/in-progress/078-prod-daily-backups/ while active)
```

### Source Code (repository root)

```text
scripts/backup_prod/
├── config.example.json        # committed template (paths, no secrets)
├── run_daily_backup.sh        # Windows/WSL2: builds the .tgz, hot SQLite backups, monthly promote+purge
├── register_backup_schedule.sh  # enable/disable/trigger-once, mirrors register_prober_schedule.sh
├── pull_backups.sh            # Mac: rsync/scp pull over denidin-winprod SSH alias + local retention purge
├── verify_restore.sh          # Mac, manual: un-tar + PRAGMA integrity_check + throwaway boot smoke test
└── tests/
    ├── test_retention_purge.py    # date-math/filename-parsing unit tests, synthetic fixtures
    ├── test_run_daily_backup.sh   # archive-assembly dry run against a temp fixture tree
    └── test_pull_backups.py       # pull-and-purge logic against a fake local pair of folders
```

**Structure Decision**: New top-level `scripts/backup_prod/` directory, sibling to the existing
`scripts/health_monitoring/` and `scripts/windows_prod/` — same "ops script family gets its own
subfolder with its own `tests/`" convention already established by those two, rather than a new
top-level app under `apps/` (this is infra tooling, not a service either app calls into).

## Complexity Tracking

*No Constitution Check violations — table intentionally empty.*
