# Bugfix Spec: `shared/active_env.json` bind-mounted as a directory on the Windows prod box, silently disabling both apps' watchdog safety check

## Bug ID
bugfix-021-prod-active-env-json-mounted-as-directory

## Title
On the Windows-hosted `prod` host (Feature 035), `/app/active-env/active_env.json` is a directory
instead of a file inside every prod container, so `watchdog.py`'s environment-mismatch safety
check silently no-ops on every cycle for both `denidin-app-prod` and `morning-mcp-app-prod`

## Priority
P1 — no user-facing functional impact (confirmed: ngrok tunnel, MCP tool calls, and a real
WhatsApp round-trip all worked correctly through this), but the specific safety mechanism built
after the 2026-07-21 incident (a wrong-environment container reachable and serving traffic) is
currently non-functional on the only host that mechanism exists to protect.

## Status
Fix implemented (2026-08-03), pending real-deploy verification (about to run as part of closing
this bugfix — see "Verification" below).

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
- `apps/denidin-app/watchdog.py` / `apps/morning-mcp-app/watchdog.py` — both read this same path
  every 30s and silently `continue` their check loop when the read fails.

## Description
Tailing live prod logs (both apps) after a real deploy showed, every ~30 seconds, on **both**
`denidin-app-prod` and `morning-mcp-app-prod`:
```
watchdog - ERROR - Could not read /app/active-env/active_env.json: [Errno 21] Is a directory: '/app/active-env/active_env.json'
```
This persisted across a manual container restart (`docker compose restart morning-mcp-app-prod`),
ruling out a transient startup race and confirming it's a persistent host-filesystem state issue,
not a one-off.

## Root Cause (confirmed, not just suspected)

`docker/docker-compose.prod.yml` mounts `./shared/active_env.json` (a specific file, not a
directory) into every prod container. Docker's bind-mount behavior: **if the host source path
does not exist at all when the container is first created, Docker silently creates it as an empty
directory** rather than failing loudly.

Every script that has ever started containers on this box (the retired
`deploy_and_verify.sh`, and its replacement `deploy_release.sh`'s remote-prod path) calls
`docker compose up -d` directly — **neither one ever wrote `shared/active_env.json` first**.
Compare with `scripts/run_denidin.sh`/`run_morning_mcp.sh`, which correctly call
`env_lock.sh`'s `env_lock_acquire()` (writes `{"active_env": ..., "owner": ..., "updated_at": ...}`
via `python3`'s `open(path, 'w')`, which itself raises `IsADirectoryError` if the target is
already a directory — the exact same failure shape) *before* starting anything. Since the box's
containers have only ever been started through the deploy pipeline (`run_all.sh prod` on the box
itself is task T017 in `specs/035-windows-always-on-prod/tasks.md`, still open/not yet done), this
write step was simply never in the deploy path at all, so Docker auto-vivified a directory on the
very first `docker compose up -d` ever run there — and once created, that directory persists
across every subsequent redeploy/restart (Docker does not repair a pre-existing bind-mount source
type mismatch on its own).

`watchdog.py`'s `_read_active_environment()` catches the resulting `IsADirectoryError`, logs it,
and returns `None`. The caller's loop (`if active_env is None or own_env is None: continue`) then
**skips the entire check for that cycle** — never reaching the internal `/health` check, the
external ngrok-tunnel `/health` check, or the mismatch comparison. Confirmed via code reading
(`apps/morning-mcp-app/watchdog.py:159-161`) — this is not a guess.

## Why existing tests/checks didn't catch this
`scripts/tests/test_deploy_release.py` only exercises `env=dev` (scratch repo, local Docker) —
`dev`'s path already correctly calls `env_lock_acquire`, so this gap is specific to the
remote-prod path, which has no automated test coverage at all (by design — it targets a real
SSH host, verified manually against the real box per Feature 035's established pattern for that
path, e.g. `verify_windows_prod.sh`). `verify_windows_prod.sh` itself does not currently check
watchdog log output for this error pattern, only container `Up` status and `/health` — a container
can be fully `Up` and `/health`-passing while its watchdog is silently non-functional, so this
specific failure mode was invisible to every existing automated check.

## Fix (implemented)

Added a new verified step to `scripts/deploy_release.sh`'s remote-prod path, immediately before
`docker compose up -d`: ensure `shared/active_env.json` exists as a real file (not a directory)
on the box, declaring `{"active_env": "prod", "owner": null, "updated_at": "<UTC ISO>"}` — the
same schema `env_lock.sh`'s `_env_lock_write` uses (`owner` is always `null` for `prod`, which is
never owner-locked, per `CLAUDE.md`'s multi-clone lock section).

- If the path doesn't exist yet: creates it directly as the file.
- If it's already a directory and **empty**: removes the empty directory first, then creates the
  file (this is exactly the currently-broken state on the box; the fix is self-healing on the next
  deploy, no separate manual remediation step needed).
- If it's a directory and **non-empty**: refuses to touch it automatically and fails loudly,
  naming the exact path — an unexpected state that needs a human to look at, not something to
  silently delete.
- Verifies afterward that the path is now a regular file, per this repo's per-step-verification
  discipline (2026-08-03, same PR as this fix).

This step runs on every deploy (idempotent — just refreshes `updated_at`), matching how the local
path's `env_lock_acquire` call already behaves on every local deploy.

`dev`'s path is unaffected — it already correctly calls `env_lock_acquire` and was never subject
to this bug.

## Verification
Since the fix runs as part of the normal deploy sequence (before `docker compose up -d`, which
already recreates the container on every deploy due to the image tag changing), simply running
the next real deploy against the box is the fix verification — no separate manual remediation
step against the currently-broken containers is needed. Plan: deploy the next cut version (or
redeploy `0.0.2-test`) to `prod` for both apps, then confirm via `docker --context denidin-winprod
compose -f docker/docker-compose.prod.yml logs` that the `Could not read
/app/active-env/active_env.json` error no longer appears after the redeploy, and that `docker
--context denidin-winprod compose -f docker/docker-compose.prod.yml exec <service> ls -la
/app/active-env/` shows a regular file, not a directory.
