# Bugfix Spec: Stopping one app of a bundled pair silently kills the sibling app

## Bug ID
bugfix-055-bundled-app-stop-kills-sibling

## Title
Running the per-app `stop_denidin.sh <env>` (or `stop_morning_mcp.sh <env>`) on an environment
where both apps are running clears the **environment-level** active flag in
`shared/active_env.json`. The still-running sibling app's `watchdog.py` then sees its environment
as inactive (`active_envs=[]`), kills its own server subprocess, and — by design — never
respawns. A later per-app `run_*.sh` re-adds the flag but only starts the app it was told to,
leaving the sibling dead until a human runs `killall_containers.sh` + `run_all.sh`. Net effect:
a sanctioned single-app stop/start silently takes down the other app for an unbounded time.

## Priority
**P1** — silent partial prod outage from a documented, sanctioned operation, with no
auto-recovery and detection only by chance. Not P0 because a full `run_all.sh` restores it and
no data is corrupted.

## Status
**Open.** Root cause identified during the 2026-09-06 prod incident response. Per Bug-Driven
Development (METHODOLOGY.md §VII), next step is human approval of the root cause before test-gap
analysis.

## Date Opened
2026-09-06

## Reported By
yaronlev171 — during the 2026-09-06 partial-prod-outage recovery. "I played only with denidin
app, but I also stopped only denidin app. How is it that morning was impacted??? AND that
denidin went down?!?!"

## Root cause

`scripts/env_lock.sh` tracks the active environment in `shared/active_env.json` at **environment
granularity** — a single `prod` (or `dev`) key covering *both* `denidin-app` and
`morning-mcp-app`. There is no per-app notion.

1. `stop_denidin.sh prod` sources `env_lock.sh`, which removes the `prod` key entirely
   (`active_envs` → `{}`) — it cannot express "denidin stopped, morning still up".
2. `morning-mcp-app-prod`'s `watchdog.py` polls `active_env.json` on an interval. It sees
   `active_envs=[]`, concludes its own declared environment (`prod`) is no longer active, and
   **terminates its server subprocess**. Per the 2026-07-21 hardening, the container stays "Up"
   (restart policy `no`) and the watchdog does **not** respawn — it waits for an explicit
   `killall_containers.sh` + start.
3. `run_denidin.sh prod` re-adds the `prod` key but only `docker compose up -d`s the denidin
   service. `morning-mcp-app-prod`'s watchdog, already in its terminal state, does nothing.

## Evidence (2026-09-06, prod)

- `~/denidin-prod/shared/active_env.json` `updated_at` moved `…20:11:51Z` — i.e. a
  `run_denidin.sh prod` at 23:11 IDT wrote the `prod` key back.
- ~3 min earlier, `morning-mcp-app-prod` logged:
  `watchdog - ERROR - ENVIRONMENT MISMATCH: own config.environment='prod' is not currently
  declared active (active_envs=[]) - tearing down the server subprocess (pid=…). Container stays
  up (no auto-restart)`.
- `docker ps`: `morning-mcp-app-prod` "Up 45 hours" (never restarted) while its server was dead.
- `denidin-app-prod` then logged `Error code: 424 - … Error retrieving tool list from MCP
  server: 'morning-invoices'` on every hourly accounting-reconciliation sweep for ~9 hours.
- Detected only when the user asked why Morning connectivity was broken.
- Same failure *shape* as the 2026-08-25 production incident (a live MCP outage silently
  degrading `denidin-app`), reached by a different trigger.

## Affected Area

- `scripts/env_lock.sh` — the environment-granularity active flag.
- `scripts/stop_denidin.sh`, `scripts/run_denidin.sh`, `scripts/stop_morning_mcp.sh`,
  `scripts/run_morning_mcp.sh` — the per-app entry points.
- `apps/denidin-app/watchdog.py`, `apps/morning-mcp-app/watchdog.py` — the active-set check +
  no-respawn behavior.
- CLAUDE.md documents the per-app scripts as usable "if specifically asked to start/stop just one
  app" — so this is a sanctioned path, not misuse.

## Proposed direction (to be refined by clarify / plan) — options

- **(a) Per-app active flags.** `active_env.json` becomes
  `{"prod": {"denidin-app": {...}, "morning-mcp-app": {...}}}`; each watchdog checks its own
  app's entry; the environment is "active" while *either* app is up; stopping one app clears only
  that app's entry.
- **(b) Guard the per-app stop scripts.** `stop_denidin.sh` / `stop_morning_mcp.sh` refuse on a
  bundled environment where the sibling is running, unless an explicit `-only` flag is passed,
  and print "use `stop_all.sh <env>`".
- **(c) Sibling revival.** `run_denidin.sh` / `run_morning_mcp.sh` detect a watchdog-terminated
  sibling for the same environment and bring it back.
- **(d)** Some combination — e.g. (a) for correctness + (b) for operator guidance.

## Relationship to other work

- Same 2026-09-06 incident produced **bugfix-054** (startup message drop) — independent root
  cause.
- Interacts with the "denidin-app and morning-mcp-app are bundled at the hip" rule and the
  multi-clone `env_lock.sh` locking in CLAUDE.md — any fix must preserve the dev owner-lock and
  the concurrent-dev+prod schema (2026-08-05).
- The no-respawn watchdog behavior is deliberate (2026-07-21 incident) and must NOT be weakened;
  the fix is about not falsely tripping it, not about making it auto-recover from a real mismatch.
