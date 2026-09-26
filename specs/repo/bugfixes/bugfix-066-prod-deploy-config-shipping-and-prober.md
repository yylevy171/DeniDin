# bugfix-066: prod deploy of v0.7.6 failed - config shipping, prober launch-failure handling (2026-09-25)

**Status**: Fixed on branch `bugfix/066-prod-deploy-config-shipping-and-prober` (fixed without BDD, per operator instruction). Ships in the next release (version chosen by the human).

## Fix summary
- 1: ROOT CAUSE (found later): the compose files bind-mounted `runtime_constitution.md`, `ledger_recognition_prompt.md` and `fee_agreement_templates/` from the box's folder OVER the image's baked copies; prod's constitution was months stale. Fix: the compose files (dev and prod) now mount ONLY `config.<env>.json`; all other config is baked into the release and used as shipped. Config files and compose files are per-env and never bundled/overwritten by a release. `.dockerignore` now excludes any `config.*.json` (except `config.example.json`/`config.schema.json`), `.DS_Store`, log files and test logs (previously a stray `config.json` [environment: test] and `config.player_prod.json` were baked into the denidin-app image).
- 3/4: `scripts/lib/prepare_compose_service.sh` (sourced by all three run scripts) refuses to start on a missing/wrong-type config bind source and removes `created`-state containers.
- 2: `prober.py` captures the launch script's output, logs `launch_error`, (no give-up/backoff, by decision). `run_all_and_verify_healthy.sh` prints each container's Docker `State.Error` on launch failure.
- 5: `deploy_release.sh` R9 prints `State.Error` and a prober warning.
- 6: `provision_webapp.sh` never touches `password.hash`, recognises `to-paste-here`, correct closing syntax, checks config assets in [4/4].
- 7: webapp `/health` gains `morning_connectivity` (part of overall status) and `ledger_complete`; docstring fixed.
- 8: frontend nginx sends `Cache-Control: no-cache` for `index.html`.
- Open: prod's stale `runtime_constitution.md` is shipped by the bundle but the prod update is a human decision.
**Scope**: `scripts/deploy_release.sh prod 0.7.6` (all apps) failed at step R9; prod was left partly
down with the health prober re-bootstrapping in a loop.

## What happened

1. `provision_webapp.sh` (step 1 of the prod prep) replaced the box's `docker-compose.prod.yml` with
   the repo's current file.
2. That file bind-mounts `apps/denidin-app/config/ledger_recognition_prompt.md` and
   `apps/denidin-app/config/fee_agreement_templates/` into `denidin-app-prod`. Neither exists in the
   box's deploy dir. Nothing in provisioning or in a release ships them.
3. On start, Docker silently created both as empty, root-owned **directories**. The file mount then
   failed: `not a directory: Are you trying to mount a directory onto a file`. `denidin-app-prod`
   stayed in state `created` (never started).
4. `deploy_release.sh` failed at R9 ("expected 'running' within 30s, got 'created'"), leaving the
   prober re-enabled.
5. The prober (every 60s, no `last_up_time`) chose `bootstrap` each tick:
   `stop_all -force`, then `run_all_and_verify_healthy.sh`. That script runs under `set -e`;
   `run_all.sh` (bare, line 54) fails as soon as `run_denidin.sh`'s `docker compose up -d` fails, so the
   script exits in seconds and the 10-second poll loop (line 70) is never reached. Each tick also
   restarted `morning-mcp-app` for nothing. It looped 6+ minutes with no progress.
6. Correcting the files on the box was not enough: the container had been created at 10:34, when the
   sources were still directories, and `compose up -d` reuses a `Created` container. It has to be
   removed so compose recreates it. That container has no anonymous volumes (Dockerfile `VOLUME` is
   only `/app/data` and `/app/logs`, both bind-mounted), so removing it loses nothing.

## Why the files were never on the box

- A release ships only the Docker images plus a 27-file ops-scripts bundle. No config assets.
- `provision_webapp.sh` ships only the compose file and the webapp config.
- bugfix-062 (2026-09-16) fixed the repo compose (added the two bind mounts) and hand-`docker cp`'d
  the files into the running prod container, but never put them in the box's deploy dir or updated the
  box's compose. The spec says "live in prod"; that was true only via the hand-copied files.
- Today's provision shipped the new compose for the first time, exposing the gap.

## What needs fixing

### A. Prod recovery (urgent)
- Remove the stale `Created` container (`docker --context denidin-winprod compose -f
  docker/docker-compose.prod.yml rm -f denidin-app-prod`) so the next boot recreates it from the
  fixed files, then verify with `verify_windows_prod.sh denidin-winprod`.
- Real files are already back on the box (checksums matched local): `ledger_recognition_prompt.md`
  and `fee_agreement_templates/` under `~/denidin-prod/apps/denidin-app/config/`.

### 1. Config assets never reach prod
Ship every config asset the compose mounts, together with the compose file, as part of provision or
deploy. The box's compose drifts from the repo with nothing to detect it.

### 2. Prober does not recognise or report a container launch failure
- The 10-second poll is skipped when `run_all.sh` fails.
- The prober re-bootstraps every 60s with `stop_all -force`, taking healthy apps down.
- Docker's error is never logged or reported.
- Needs: a reported launch failure with the Docker error, and a backoff or give-up after N identical
  failures instead of tearing prod down every minute.

### 3. No bind-source existence check before start
`provision_webapp.sh`, `deploy_release.sh` and `run_env.sh` never verify that every compose bind
source exists. A missing file becomes a root-owned directory and a wrong-type mount.

### 4. A stale `Created` container is reused
`compose up -d` reuses a container whose mount source changed type. Deploy/bootstrap should
force-recreate, or remove containers stuck in `created`.

### 5. Deploy failure is under-reported
R9's message omits Docker's `State.Error`, and the deploy leaves prod re-enabled and looping with no
warning. On failure it should print the Docker error and the prober state.

### 6. `provision_webapp.sh` leftovers
- The password fix (never ship/overwrite `password.hash`; only a read-only existence check) is
  **uncommitted** on branch `chore/provision-webapp-no-password`.
- Its "credentials filled in (not placeholder)" check false-positives on `to-paste-here`.
- Its closing text still shows the old `deploy_release.sh webapp prod` syntax.
- Its [4/4] verification only parses the compose file.

### 7. Webapp health check gaps (raised earlier)
`/health` has no Morning connectivity check and only a weak in-memory ledger check. The module
docstring still says there is no Morning dependency (stale since Feature 087).

### Process
bugfix-062 was marked "live in prod" while the box's compose lacked the mounts. Nothing detects box
vs repo drift before a deploy.

## Release note
The v0.7.6 images and artifacts are fine and immutable. Fixes 2 to 7 go into a later release. Items 1
and 3 are tooling/box fixes that do not need a release.
