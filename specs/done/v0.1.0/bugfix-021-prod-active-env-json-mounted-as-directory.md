# Bugfix Spec: `shared/active_env.json` bind-mounted as a directory on the Windows prod box, silently disabling both apps' watchdog safety check

## Bug ID
bugfix-021-prod-active-env-json-mounted-as-directory

## Title
On the Windows-hosted `prod` host (Feature 035), `/app/active-env/active_env.json` was a directory
instead of a file inside every prod container, so `watchdog.py`'s environment-mismatch safety
check silently no-op'd on every cycle for both `denidin-app-prod` and `morning-mcp-app-prod`

## Priority
P1 — no user-facing functional impact (confirmed: ngrok tunnel, MCP tool calls, and a real
WhatsApp round-trip all worked correctly through this), but the specific safety mechanism built
after the 2026-07-21 incident (a wrong-environment container reachable and serving traffic) was
non-functional on the only host that mechanism exists to protect.

## Status
**Done** — root cause confirmed, box remediated, script fix implemented, and verified live
against real production (see "Verification" below).

## Date Opened
2026-08-03

## Reported By
Discovered while monitoring live prod logs after Feature 035's per-step-verified deploy pipeline
went live (`deploy_release.sh` remote-prod path, PR #167).

## Affected Area
- `docker/docker-compose.prod.yml` (and `docker-compose.dev.yml`) — both declare
  `./shared/active_env.json:/app/active-env/active_env.json:ro`, a bind mount of a *specific file*.
- `scripts/deploy_release.sh`'s remote-prod path (Feature 034/035 reconciliation, PR #167) — never
  wrote `shared/active_env.json` on the box before calling `docker compose up -d`.
- The now-retired `scripts/windows_prod/deploy_and_verify.sh` had the identical gap — this is not
  a regression introduced by PR #167, it predates it.
- The Windows box's own `shared/` directory — was a plain directory (Docker auto-created it),
  never the symlink `env_lock.sh` expects, and `config/shared_state.local.json` declared a
  self-referential `shared_state_dir` (pointing at the same path the symlink itself would need to
  occupy) — a second, related misconfiguration found while fixing this (see "Root Cause").
- `apps/denidin-app/watchdog.py` / `apps/morning-mcp-app/watchdog.py` — both read this same path
  every 30s and silently `continue` their check loop when the read fails.

## Description
Tailing live prod logs (both apps) after a real deploy showed, every ~30 seconds, on **both**
`denidin-app-prod` and `morning-mcp-app-prod`:
```
watchdog - ERROR - Could not read /app/active-env/active_env.json: [Errno 21] Is a directory: '/app/active-env/active_env.json'
```
This persisted across a manual container restart, ruling out a transient startup race.

## Root Cause (confirmed via both code reading and live remediation)

`docker/docker-compose.prod.yml` mounts `./shared/active_env.json` (a specific file, not a
directory) into every prod container. Docker's bind-mount behavior: **if the host source path
does not exist at all when the container is first created, Docker silently creates it as an empty
directory** rather than failing loudly.

Every script that has ever started containers on this box (the retired `deploy_and_verify.sh`,
and its replacement `deploy_release.sh`'s remote-prod path) calls `docker compose up -d` directly
— **neither one ever wrote `shared/active_env.json` first**. Compare with
`scripts/run_denidin.sh`/`run_morning_mcp.sh`, which correctly call `env_lock.sh`'s
`env_lock_acquire()` (writes `{"active_env": ..., "owner": ..., "updated_at": ...}`) *before*
starting anything. Since the box's containers had only ever been started through the deploy
pipeline (never `run_all.sh prod` directly on the box — that's task T017 in
`specs/035-windows-always-on-prod/tasks.md`), this write step was simply never in the deploy path
at all, so Docker auto-vivified a directory on the very first `docker compose up -d` ever run
there.

**A second, compounding misconfiguration was found while fixing this**: `env_lock.sh` requires
`./shared` to be a *symlink* to a canonical directory declared in `config/shared_state.local.json`
(the multi-clone-lock model every Mac clone uses). On the box, `shared/` was a plain directory
(Docker had auto-created it for the *other* bind mounts too, e.g. `mcp-status-prod/`), and
`config/shared_state.local.json` declared `shared_state_dir` as the *same path* `./shared` itself
would need to occupy — a self-referential value left over from the retired `deploy_and_verify.sh`'s
config-generation logic. This meant `env_lock_acquire` (and thus `run_denidin.sh`/`run_all.sh`)
could never succeed on the box at all until this was corrected — confirmed directly: the operator
hit `ERROR: .../shared already symlinked to '.shared_canonical', not '/home/.../\.shared_canonical'`
and, before that, `ERROR: .../shared exists and is not a symlink` when first attempting
`stop_all.sh prod` on the box.

`watchdog.py`'s `_read_active_environment()` (both apps, identical code) catches the resulting
`IsADirectoryError`, logs it, and returns `None`. The caller's loop
(`if active_env is None or own_env is None: continue`) then skips the entire mismatch-check cycle
every time — never reaching the internal or external `/health` checks. Confirmed by reading the
code (`apps/morning-mcp-app/watchdog.py:159-161`), not just inferred from the log line.

## Why existing tests/checks didn't catch this
`scripts/tests/test_deploy_release.py` only exercises `env=dev` (scratch repo, local Docker) —
`dev`'s path already correctly calls `env_lock_acquire`, so this gap is specific to the
remote-prod path, which has no automated test coverage at all (by design — it targets a real
SSH host, verified manually against the real box per Feature 035's established pattern, e.g.
`verify_windows_prod.sh`). `verify_windows_prod.sh` itself did not check watchdog log output for
this error pattern, only container `Up` status and `/health` — a container can be fully `Up` and
`/health`-passing while its watchdog is silently non-functional, so this failure mode was
invisible to every existing automated check.

## Fix

**One-time box remediation** (already applied, 2026-08-03): reorganized `shared/` on the box into
the symlink structure `env_lock.sh` expects — real content moved to `.shared_canonical/`, `shared`
recreated as an absolute-path symlink to it, the empty `active_env.json/` directory removed, and
`config/shared_state.local.json` corrected to point at `.shared_canonical` instead of the
self-referential path.

**Script fix** (`scripts/deploy_release.sh`, remote-prod path): added a new verified step
immediately before `docker compose up -d` that ensures `shared/active_env.json` exists as a real
file (not a directory) on the box, declaring `{"active_env": "prod", "owner": null, "updated_at":
"<UTC ISO>"}` — the same schema `env_lock.sh`'s `_env_lock_write` uses (`owner` is always `null`
for `prod`, which is never owner-locked, per `CLAUDE.md`'s multi-clone lock section).
- If the path doesn't exist yet: creates it directly as the file.
- If it's already a directory and **empty**: removes the empty directory first, then creates the
  file (self-healing on the next deploy, no separate manual step needed for *this specific*
  failure mode going forward).
- If it's a directory and **non-empty**: refuses to touch it automatically and fails loudly,
  naming the exact path — an unexpected state that needs a human to look at.
- Verifies afterward that the path is now a regular file, per this repo's per-step-verification
  discipline.

This step runs on every deploy (idempotent — just refreshes `updated_at`), matching how the local
path's `env_lock_acquire` call already behaves on every local deploy. `dev`'s path is unaffected —
it already correctly calls `env_lock_acquire` and was never subject to this bug.

**Not in scope for this script fix**: the `shared/`-symlink misconfiguration itself (the
"non-symlink"/self-referential `shared_state.local.json` errors) — that was a one-time box
provisioning defect, already corrected by hand, not something `deploy_release.sh` needs to
detect or repair on every call (a healthy box's `shared/` symlink doesn't change between
deploys).

## Verification
Confirmed live against the real box, 2026-08-03:
1. Root cause independently reconfirmed by the operator hitting the exact predicted symlink
   errors when running `stop_all.sh prod` directly.
2. Box remediated (symlink structure + config fix).
3. `stop_all.sh prod` → `run_all.sh prod` run directly on the box (satisfies task T017) — clean,
   no errors, both containers `Up`.
4. Watchdog logs on both `denidin-app-prod` and `morning-mcp-app-prod` checked across multiple
   30s+ cycles post-restart — zero `active_env.json` errors, `watchdog starting` /
   `spawned <process>` lines present and clean on both.
5. Repeated the full `stop_all.sh prod` → `run_all.sh prod` cycle a second time from a clean
   state (after removing incidental junk directories created by an unrelated operator mistake
   during remediation) — same clean result, confirming this isn't a one-off.
6. Script fix (the new verified step in `deploy_release.sh`) tested via a real `deploy_release.sh
   <app> prod 0.0.2-test` run for both apps — see commit history for the specific confirmation
   this bugfix's PR includes.
