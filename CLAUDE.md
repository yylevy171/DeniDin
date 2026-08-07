# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Personality dispatch
Read and follow @.claude/personalities/<basename of current working directory>.md
The original/top-level clone (directory name `DeniDin`) maps to `root` instead of `DeniDin`.
If no matching file exists, use @.claude/personalities/default.md

## 🚨 CONFINED TO YOUR OWN CLONE — NO EXCEPTIONS 🚨

**You are confined to the files and folders inside your own clone's directory
ONLY.** Per the multi-clone setup described below, this repo is checked out
in multiple sibling locations at once (this original/`root` clone plus dev
clones like `coder1`, `coder2`, ...), each a fully independent `git` clone
with its own working tree — **not** git worktrees of one shared repo. Do not
read, list, `grep`, `cd` into, or otherwise inspect any sibling clone or the
parent directory containing them, and do not read, edit, move, or run
anything there — **even read-only inspection is off limits** — unless the
user explicitly asks you to look at that specific other location in that
specific request. Approval to work in one clone does not carry over to any
other clone, including the root clone, even for something as innocuous as
"just checking `git status`." A sibling clone may have another
session/coder actively working in it at any time, with uncommitted
in-progress changes on disk that you have no way to know are safe to
observe or touch — treat every path outside your own clone's directory as
opaque and off limits by default.

**NO CROSSING OF CLONES. YOU WORK ONLY ON YOUR CLONE!** — this extends past
file access to shell *state*: never run, activate, or invoke another
clone's virtualenv/interpreter/binaries, and never trust a bare command
(`python3`, `pytest`, etc.) without first confirming what your shell's
`PATH`/active venv actually resolves it to. A stale or leaked `PATH` from
a prior command in the same session can silently point a "plain" command
at a sibling clone's venv (e.g. `coder1`'s or `coder2`'s) — running
anything through it, even a read-only test run, is the same violation as
`cd`-ing into that clone directly. Always resolve/activate your own
clone's own venv explicitly before running project commands, and verify
(`which python3`, etc.) rather than assume. Same "unless the user
explicitly asks" exception as above — no exception carries over from a
prior request.

## 🚨 ENVIRONMENT ISOLATION & LOCKING 🚨

**Dev and prod may now run concurrently (2026-08-05 — ban lifted; see "Environments
(dev/prod)" below for the full history).** Each environment now has fully
separate WhatsApp/Green API/Green Invoice infrastructure (2026-08-03
asymmetry update), so the original reason they couldn't safely coexist
(`GreenAPIBot` polling the same Green API instance from two containers at
once) no longer applies. What's still true, unchanged:
- **`denidin-app` and `morning-mcp-app` are bundled at the hip within one
  environment** — neither app's container may run alone. Use
  `scripts/run_all.sh`/`scripts/stop_all.sh <env>`, not the per-app scripts,
  unless specifically starting/stopping just one app. **Order matters
  (2026-08-07): `morning-mcp-app` starts first, `denidin-app` second** —
  `denidin-app` depends on `morning-mcp-app` (discovers/calls its MCP
  tunnel), never the other way around, so `morning-mcp-app` must already be
  up before `denidin-app` starts. `run_all.sh` follows this order;
  `stop_all.sh` follows the reverse (`denidin-app` stops first). The same
  ordering applies when deploying both apps via `scripts/deploy_release.sh`
  (one call per app) — deploy `morning-mcp-app` first.
- **`dev` is locked to whichever clone acquired it**, until that same clone
  releases it (`stop_*.sh dev`) or someone force-overrides
  (`-force`) — see "Multi-clone lock" below. This is a *different* concern
  from the old dev/prod exclusivity (two clones' dev containers colliding
  with each other, e.g. on data volumes) and was never affected by the
  dev/prod ban in the first place.
- **`prod` is never owner-locked** — any clone may start/stop it.

There is no exception carved out for `morning-mcp-app` running independently
of the *bundling* rule above — an earlier version of this document said
`morning-mcp-app-dev`/`-prod` could run together with no restriction at all;
that was wrong and was corrected 2026-07-21 (a `morning-mcp-app-prod`
container was left running unattended after a deploy, with real production
Green Invoice credentials, and a stale test-config path (`config.test.json`'s
`morning_status_file`, never updated after the 019-env-separation migration)
caused the expensive E2E test suite to silently create real invoices in
production instead of the sandbox — this incident was about credential/config
isolation, not dev/prod instance-sharing, and stays fully relevant).

**Enforcement mechanism (2026-07-21, post-incident; schema updated 2026-08-05
for concurrent dev+prod)**:
- **`./scripts/killall_containers.sh`** — tears down every container in
  every environment, both apps, unconditionally, and resets
  `shared/active_env.json` to `{"active_envs": {}}` (nobody active). An
  unconditional full-reset hammer for whenever you're not sure what's
  running or want a clean slate — no longer something you must run before
  switching environments, since there's no longer anything to switch away
  from.
- **`shared/active_env.json`** — schema: `{"active_envs": {"dev": {"owner":
  "<clone>"|null}, "prod": {"owner": null}}, "updated_at": "..."}`. An
  environment's key is present iff it's currently active — either, both, or
  neither may be present at once. `run_denidin.sh`/`run_morning_mcp.sh`
  (via `env_lock.sh`) set/clear only their own environment's key, leaving
  the other's entry untouched. This file is mounted read-only into every
  container.
- **`watchdog.py`** (one per app, runs as the container's PID 1, spawns the
  real app/server as a child process) — periodically checks that its own
  container's declared `config.environment` is still listed as active in
  `shared/active_env.json`'s `active_envs`. `morning-mcp-app`'s watchdog
  checks this two ways: internally (`http://127.0.0.1:<port>/health`) and
  externally, through its own live ngrok tunnel — the check that would have
  caught the 2026-07-21 incident (both also independently verify the live
  server reports its own declared environment, catching cross-environment
  contamination regardless of the active-set question). On any mismatch,
  the watchdog kills its own app subprocess and does **not** respawn it —
  the container stays "Up" (so Docker's restart policy, `restart: "no"` on
  every service, can't silently recreate it) but does nothing further until
  a human runs `scripts/killall_containers.sh` and starts the correct
  environment explicitly. No automatic retry, by design.

Do not leave a `-prod` container "just running" for convenience or
verification once you're done with it — and don't rely on memory/habit to
track what's live; `scripts/killall_containers.sh` + the watchdogs exist
specifically so a slip here fails loudly instead of silently.

**Multi-clone lock (2026-07-23)**: this repo may be checked out in more than
one place at once — this original/`root` clone plus sibling dev clones
(`coder1`, `coder2`, ...), each with its own [Personality dispatch](#personality-dispatch)
identity. `scripts/env_lock.sh` (sourced by `run_denidin.sh`,
`run_morning_mcp.sh`, `stop_denidin.sh`, `stop_morning_mcp.sh`, and
`scripts/killall_containers.sh`) enforces this across all of them: `dev` is
locked to whichever clone's personality (by name — e.g. `Ruth`, `Avi`,
`Bina`) acquired it, until that same personality releases it via
`stop_*.sh dev`; `prod` is never owner-locked.
A non-owner can override with `-force` on any `stop_*.sh`/`scripts/killall_containers.sh`
call. This only works because `./shared` is a symlink (not a real directory)
to one canonical path shared by every clone on the machine — **every clone,
including any new one you set up, needs its own gitignored
`config/shared_state.local.json`** (same idea as `creds/DeniDin Dev/Prod
Creds.txt` — not committed, created once per clone by hand):
```json
{"shared_state_dir": "/absolute/path/to/one/canonical/shared-state/dir"}
```
All clones on the same machine must point at the *same* canonical path, or
the lock isn't actually shared and the whole mechanism silently no-ops.

**dev/prod data is also a singleton across clones (2026-07-23; made MANDATORY and
enforced 2026-07-30 after a real incident — see below)**: real
session/memory data (`apps/denidin-app/data`, `dev_data`) and container logs
(`apps/denidin-app/logs/{dev,prod}`, `apps/morning-mcp-app/logs/{dev,prod}`)
must not fragment depending on which clone last started dev/prod.
`docker/docker-compose.dev.yml`/`docker/docker-compose.prod.yml` themselves are untouched
(plain relative paths, identical across clones, as always). Instead, every
clone gets its own gitignored **`docker/docker-compose.dev.local.yml`** /
**`docker/docker-compose.prod.local.yml`** (same idea as
`config/shared_state.local.json`/`creds/DeniDin Dev/Prod Creds.txt` — plain files, not
committed, created once per clone by hand), layered in automatically by
`run_denidin.sh`/`run_morning_mcp.sh`/`stop_denidin.sh`/`stop_morning_mcp.sh`/
`scripts/killall_containers.sh` via a second `-f` flag. These are plain Docker Compose
override files — no environment variables, no symlinks — containing only the volume
lines that need to differ from the base file, as literal relative paths. The root
clone's copy is a no-op (`services: {}`) since its own paths in the base
file are already canonical. Every `coderN` clone's copy should instead
override the data/log volumes to point one level up at the root clone's
paths, e.g. (`docker/docker-compose.dev.local.yml`):
```yaml
services:
  denidin-app-dev:
    volumes:
      - ../apps/denidin-app/dev_data:/app/dev_data
      - ../apps/denidin-app/logs/dev:/app/logs
  morning-mcp-app-dev:
    volumes:
      - ../apps/morning-mcp-app/logs/dev:/app/logs
```
(and the equivalent `docker/docker-compose.prod.local.yml` for `data`/`logs/prod`).
Compose merges each service's `volumes:` list by matching *target* mount
point across files, so only the lines that actually change need to be
listed — the config-file mount and anything else not mentioned here is
inherited from the base file untouched (verified via `docker compose
config`, not assumed). All `run_*.sh`/`stop_*.sh`/`scripts/killall_containers.sh`
invocations pass `--project-directory` (the repo root) explicitly, so
relative paths in every compose file — base and override alike — always
resolve against the repo root, never against `docker/` (where the files
themselves now live) or wherever `docker compose` happened to be invoked
from. So `../apps/denidin-app/dev_data` in a `coderN` clone's override
still correctly means "one level up from this clone." `test_data`/
`logs/test_logs` are NOT part of this — tests run via host `pytest`, never
through Docker, so they're already naturally isolated per clone and should
stay that way.

🚨 **These two files are MANDATORY, not optional, and must NEVER be deleted** 🚨
(2026-07-30 incident: a `coderN` clone was missing `docker-compose.dev.local.yml`
entirely — no error, no warning — so `docker-compose.dev.yml`'s own plain relative
volume paths silently resolved against that clone's own directory instead of being
overridden to the shared root-clone paths; the dev container ran for a while
writing session/log data into the clone's own `apps/denidin-app/dev_data` instead of
the real, shared history, completely unnoticed until manually inspected).
**Enforcement (2026-07-30)**: `scripts/env_lock.sh`'s `env_lock_require_local_override`
is now called by `run_denidin.sh`/`run_morning_mcp.sh` *before* building compose args —
if `docker/docker-compose.<env>.local.yml` doesn't exist for the current clone, the
script refuses to start at all (loud `ERROR`, exit 1), rather than silently falling
back to this clone's own paths. `stop_*.sh`/`scripts/killall_containers.sh` do NOT
enforce this (stopping doesn't touch volume config, and requiring the file just to
*stop* a misconfigured environment would be backwards). If you ever see this error,
the fix is to create the missing file (copy another clone's and adjust, or use a
no-op `services: {}` stub if this is the root clone) — **never** to delete or bypass
the check, and never to delete an existing one of these files for any reason (there
is no scenario where removing it is the correct fix to anything).

## 🚨 AI AGENTS: NEVER START AN ENVIRONMENT OR EDIT CONFIG WITHOUT EXPLICIT APPROVAL 🚨

Two hard rules for any AI coding agent (Claude Code or otherwise) working in this repo, added 2026-07-21 after both were violated in the same session:

- **Never run `run_denidin.sh`, `run_morning_mcp.sh`, `docker compose up`, or anything else that starts a container in `dev` or `prod` for either app, without asking first and getting explicit approval for that specific start — every single time.** Approval for a different action (e.g. "you're approved to edit the test config for these tests") does **not** imply approval to also start the environment those tests need. Each start is its own decision point.
- **Config is code.** Once a test run has started, config files (`config.dev.json`, `config.test.json`, `config.prod.json`, `config.json`, etc.) are frozen for the duration of that run — do not edit them to unblock a failing or skipped test mid-run, even for a narrowly-scoped, apparently-mechanical fix (restoring a placeholder credential, syncing an auth token between apps). A config change discovered as a blocker mid-run must be surfaced to the human and applied *before* (re)starting the run, never patched in silently while it's in progress — otherwise a pass/fail no longer reflects a known, fixed state.

## 🚨 AI AGENTS: VERSION AND RELEASE DECISIONS ARE HUMAN-ONLY, EVERY TIME 🚨

Added 2026-08-02, per explicit user instruction, at the same enforcement bar as the environment-start rule above — this is not a suggestion. Applies to both apps' versioning/release/rollback tooling (Feature 034, `specs/in-progress/034-versioning-release-mgmt/`), whether or not that feature has finished shipping yet, because it governs agent *behavior*, not just a feature's code:

- **Never pick, compute, suggest, or default a version number — not even as a "recommended, just say yes" suggestion.** After finishing a feature (the `haleluya`/`/haleluya` flow), always ask explicitly whether to cut a release for each app touched, and if yes, always ask the human for the **exact** version string to use. Wait for it. Do not propose one first.
- **Never run a release-cutting or deploy script (`scripts/cut_release.sh`, `scripts/deploy_release.sh`) on your own initiative, and never infer/guess a target version "the previous one" or "the one just cut" even when it seems obvious from context.** Both scripts may only be invoked with an app (and, for deploy, an environment) and an exact version explicitly supplied by the human in that specific request. `scripts/deploy_release.sh` covers initial deploy to `dev`, promotion to `prod`, and rollback alike — one script, same rule for all three (there is no separate "rollback script"). Approval for one release/deploy never carries over to the next — same rule as every other "ask every time" gate in this document. Every `deploy_release.sh` call is **also, separately**, an environment-start action under the "NEVER START AN ENVIRONMENT... WITHOUT EXPLICIT APPROVAL" rule above (it recreates a running container in `dev` or `prod`) — both gates apply to every call; neither substitutes for the other, and cutting a version never by itself authorizes deploying it anywhere.
- **Once a version is cut, it is immutable.** Its release image/tarball, git tag, `CHANGELOG.md` entry, and `RELEASES.md` entry must never be modified or overwritten afterward, and no later commit is retroactively part of that version. A bug found in a cut version is fixed by cutting a **new** version — never by mutating the old one.

## Repository Layout

This repo is split into two independently deployable apps under `apps/`, plus SpecKit governance docs:

- **`apps/denidin-app/`** — the production WhatsApp AI assistant (main application). All app development happens here; it has its own `.pylintrc`, `mypy.ini`, `pytest.ini`, `requirements.txt`, `Dockerfile`, and virtualenv expectations.
- **`apps/morning-mcp-app/`** — a standalone app for the Morning/Green Invoice API (Israeli invoicing): a client library (`MorningClient`, `MorningAuth` under its own `src/denidin_mcp_morning/`), a FastMCP server (`server.py`, 11 invoice-management tools, streamable-HTTP, bearer-auth, `/health` endpoint) exposed to `apps/denidin-app` over a real ngrok tunnel, plus its sandbox-backed integration test suite. It has its own `requirements.txt`, `pytest.ini`, `Makefile`, `Dockerfile`, and config files — fully independent of `apps/denidin-app/` (`denidin-app` reaches it only over HTTP via the tunnel, never by importing its code). Remaining polish work (audit logging, run-both-apps docs) tracked under `specs/done/018-denidin-morning-mcp-integration/`.
- **`specs/`** — SpecKit-style feature specifications, organized by status: `in-progress/`, `backlog/`, `done/`, `obsolete/`, `bugfixes/`. See "Spec-Driven Workflow" below.
- **`.github/`** — the project's constitution/methodology docs (see "Governance Docs" below) — these are binding rules for how work is done here, not just background reading.
- **`docker/docker-compose.dev.yml`** / **`docker/docker-compose.prod.yml`** — one compose file per environment (019-env-separation), each with a `denidin-app-<env>` + `morning-mcp-app-<env>` service pair; each app also builds/runs standalone via its own `Dockerfile` (`docker build`/`docker run` from within the app's own directory, no dependency on the other app or on compose). Containers are the *only* supported way to run either app now — see "Environments (dev/prod)" below.

**Almost all day-to-day commands below assume `cd apps/denidin-app` first**, unless working on the morning app (`cd apps/morning-mcp-app`).

## Environments (dev/prod)

Both apps run **exclusively as Docker containers**, in one of two environments — `dev` or `prod` — never as a local host process (019-env-separation). Each environment has its own config file (`config.dev.json`/`config.prod.json`), data root (`dev_data/` vs `data/` for denidin-app), log path (`logs/dev/` vs `logs/prod/`), and — for morning-mcp-app — its own ngrok account/tunnel running *inside* the container.

**Asymmetry update (2026-08-03): dev and prod now have fully separate WhatsApp/Green API/Green
Invoice infrastructure.** There are now **two** paid WhatsApp Business numbers, **two** Green API
instances, **two** ngrok tunnels (one per `morning-mcp-app-<env>`), and **two** Green Invoice
accounts (dev uses the Morning **sandbox**, prod uses the **real production** Green Invoice
account) — one full set per environment, no longer shared. **OpenAI is the only credential/service
still shared between `dev` and `prod`**, and that's fine: OpenAI calls are stateless per-request,
so both environments hitting the same account concurrently causes no cross-environment
interference.

This resolves the *original* reason `denidin-app-dev`/`denidin-app-prod` couldn't safely run
concurrently (`GreenAPIBot` polling the same Green API instance/WhatsApp number from two
containers at once risked duplicate-reply bugs) — that specific conflict no longer exists, since
each environment now polls its own number/instance.

**Review completed, ban lifted (2026-08-05).** The explicit human review this section used to say
was still pending happened: dev and prod may now run **concurrently**. The other motivating
incidents behind the old "ONE ENVIRONMENT SET AT A TIME" rule (e.g. 2026-07-21's stale-test-config-path
incident) were about credential/config isolation, not instance sharing, and remain fully addressed
by this same per-environment-infra separation — nothing about them depended on dev/prod being
mutually exclusive in time. See "Environment isolation & locking" below for what's enforced now
(dev is still locked to whichever clone acquired it; the two apps within one environment are still
bundled) versus what's no longer true (dev and prod no longer need to be torn down to switch
between them). `env_lock.sh`, `watchdog.py`, and `killall_containers.sh` were all updated in
lockstep with this change — `shared/active_env.json`'s schema moved from a single `active_env`
scalar to an `active_envs` dict keyed by environment, so either, both, or neither environment can
be recorded as active independently. See `specs/019-env-separation/quickstart.md` for the
(still-current, if now optional) manual hand-off procedure, and role-mapping details (dev's
godfather/admin assignment is operator-switchable by editing `config.dev.json` and restarting,
since there's only one real tester).

**Merging a code fix to `master` does not redeploy it.** `docker compose up -d`/`restart` does not rebuild on its own when source changed on disk — a running container keeps executing whatever image it was last built from. After merging any code change (not a config/mounted-data change — those *are* picked up live, e.g. `runtime_constitution.md`'s mtime-based hot-reload), rebuild and recreate every environment container currently running that app: `docker compose --project-directory . -f docker/docker-compose.<env>.yml build <service> && ... up -d <service>` (or the `run_*.sh <env>` script, but note it does not rebuild by itself either — build first). A merged RBAC fix once had zero effect on a running prod container for hours because of exactly this (2026-07-20). Note `/haleluya` itself never performs this rebuild/redeploy (see its definition below) — deploying, to any environment, is always a separate, explicit human-initiated request.

**`prod` for both apps runs on a dedicated, always-on Windows laptop (Feature 035)**, reachable from the Mac over Tailscale/SSH — never a local host process and never the machine this session is running on. Day-to-day operation (start/stop, read logs, browse the read-only `data` mount) is done entirely from the Mac; see `specs/done/035-windows-always-on-prod/quickstart.md` for the full runbook and `scripts/windows_prod/*.sh` for the read-only/disruptive-check operational scripts (`verify_windows_prod.sh` for read-only connectivity/health checks, `verify_reboot_recovery.sh` for the one deliberately disruptive reboot-recovery check). **Deploying** to this box (or to `dev`, locally) is `scripts/cut_release.sh` + `scripts/deploy_release.sh` (Feature 034) — see "Versioning & Release Management" below; `scripts/windows_prod/build_and_package.sh`/`deploy_and_verify.sh` were retired 2026-08-03, fully superseded by that pair (they rebuilt from source on every deploy, which conflicts with the "build once, deploy anywhere" principle `cut_release.sh`/`deploy_release.sh` now implement). Every start/stop/deploy against this box is still subject to the same per-action approval rule as any other environment start (see "NEVER START AN ENVIRONMENT... WITHOUT EXPLICIT APPROVAL" above).

## Versioning & Release Management (Feature 034)

Each app (`denidin-app`, `morning-mcp-app`) has its own independent semantic version — `dev` and `prod` routinely run *different* versions at any given time (e.g. prod on `1.4.5` while dev is already on `1.4.6` during the next release's UAT); this is the normal, expected state, not drift to fix. See the "VERSION AND RELEASE DECISIONS ARE HUMAN-ONLY" banner above for the binding agent-behavior rule — this section is the reference for where things live and how the mechanics work.

- **`apps/<app>/VERSION`** — plain-text current version (git-tracked, one source of truth per app). Surfaced via `apps/morning-mcp-app`'s `/health` endpoint (`version` field) and every log line in both apps (`[v<version>]` prefix). `apps/denidin-app` can also answer "what version are you running?" directly over WhatsApp (ungated by RBAC).
- **`apps/<app>/CHANGELOG.md`** — terse, one line per release. **`apps/<app>/RELEASES.md`** — fuller prose notes per release. Both append-only, written only by `scripts/cut_release.sh`, never hand-edited.
- **Git tags**: `<app>-v<version>` (e.g. `denidin-app-v1.4.2`) — one per app, since the two apps version independently.
- **Artifacts folder**: `/Users/yaron/Projects/DeniDin/artifacts/<app>/<app>-v<version>.{tar,json}` — a shared, hardcoded-path directory outside any single clone's exclusive ownership (same idea as `shared/`), holding every cut release's exported Docker image (`docker save`) plus a JSON manifest (version/date/git commit/image ID). Not a container registry.
- **`scripts/cut_release.sh <app> <version>`** — builds, tags, and exports the release artifact; updates `VERSION`/`CHANGELOG.md`/`RELEASES.md`; applies the git tag. Deploys nothing. Refuses to re-cut an already-existing version (immutable once cut).
- **`scripts/deploy_release.sh <app> <env> <version>`** — the one script for initial deploy to `dev`, promotion to `prod`, and rollback alike (all mechanically identical: load the artifact, redeploy it, verify it — never rebuild). Retags the loaded image to `<compose-project-name>-<service-name>:latest` and runs `docker compose up -d --no-build`, so the environment's existing config/logs/data volume mounts are preserved. Blocks on automatic verification (`/health` poll for morning-mcp-app, `docker logs` grep for denidin-app) before reporting success — a container that merely started is not a success.
- Full spec: `specs/in-progress/034-versioning-release-mgmt/` (`spec.md`, `plan.md`, `contracts/` for the exact CLI contracts).

## Commands

### Setup
```bash
cd apps/denidin-app
cp config/config.example.json config/config.dev.json    # then fill in real dev credentials + dev-specific values
cp config/config.example.json config/config.prod.json   # then fill in real prod credentials + prod-specific values
```

### Run
```bash
./scripts/run_all.sh dev|prod            # (repo root) starts BOTH denidin-app and morning-mcp-app for that env
./scripts/stop_all.sh dev|prod [-force]  # stops both - use this pair by default
```
`denidin-app` and `morning-mcp-app` are bundled — neither app's container may run alone (see "Environment isolation & locking" above) — so `scripts/run_all.sh`/`scripts/stop_all.sh` are the default way to start/stop an environment. Only use the per-app scripts below if specifically asked to start/stop just one app:
```bash
cd apps/denidin-app
./run_denidin.sh dev|prod       # start that environment's container (docker compose wrapper)
./stop_denidin.sh dev|prod [-force]  # stop it (docker compose stop — never affects the other environment)
```
No local/foreground run mode exists anymore — see the environments note above for why (containers-only, per 019-env-separation).

### Test
```bash
cd apps/denidin-app
python3 -m pytest tests/ -v --tb=short          # full suite (billed + expensive tests skipped by default)
python3 -m pytest tests/unit/ -v                # unit only
python3 -m pytest tests/integration/ -v         # integration only
python3 -m pytest tests/unit/test_session_manager.py::test_function -xvs   # single test
python3 -m pytest tests/ --cov=src --cov-report=html   # coverage (htmlcov/index.html)
```
Also runnable from repo root via `make test` (wraps the same pytest invocation from `apps/denidin-app/`).

Two real-OpenAI-call test tiers exist (split by Feature 029, 2026-07-30, from one overloaded `expensive` marker), **in both apps** — `apps/denidin-app` AND `apps/morning-mcp-app` each register these markers independently in their own `pytest.ini`/`conftest.py` (morning-mcp-app currently has 2 `billed` tests and 0 `expensive` — the tier is still registered there for if/when it ever adds a vision-based tool). Both tiers are excluded by default (`addopts = -m "not billed and not expensive"`) but with very different run rules:

- **`billed` tests** (`tests/billed/`, marked `@pytest.mark.billed`) make real, **text-only** OpenAI calls (chat completions, MCP tool-call turns) — cheap per run. **They can be run freely: no per-run approval needed, no one-at-a-time restriction, no log-reading requirement.** 🚨 **Do NOT stop to ask before running a `billed` test — the approval gate below is `expensive`-only and does not apply to `billed` at all.** Run with `pytest tests/billed/ -m billed -v` (or target a single file/test the same way).
- **Expensive tests** (`tests/expensive/`, marked `@pytest.mark.expensive`) make real **vision/image/PDF/DOCX** OpenAI calls — meaningfully costlier (multiple sequential calls per test, e.g. `PDFExtractor` delegating to `ImageExtractor` per page) — and keep the full strict discipline below, unchanged. Don't run them repeatedly — read `logs/test_logs/` for a prior run's output before re-running, and only re-run after a code change you're confident fixes the issue.

🚨 **"Stop on failure" means stop on failure — every single time, no exceptions, regardless of tier.** When the user gives an explicit sequential-run instruction ("run all N tests one by one, on pass continue, on fail stop"), EVERY failure is its own stop point requiring a full report and fresh, explicit user input before doing anything else — investigating, fixing, re-running, or moving on to the next test. Approval to fix-and-continue past one failure does NOT carry over to the next failure later in the same sweep, even one that looks structurally identical or trivially fixable. Real incident (2026-08-02): after the user approved a specific fix for one test's confusing fixture, that got silently generalized into "fix-and-continue is now this sweep's standing behavior" — a later, similarly-shaped failure got investigated, fixed, re-run, and committed with no pause to report or ask, and the sweep just kept going through the remaining tests. The user caught it: *"you must NEVER generalize like that. When I say STOP AT FAILURE YOU MUST STOP AT FAILURE."* Keeping an accurate test-tracking log (see `TEST_RUN_LOG.md`) does NOT substitute for actually stopping at the gate — logging what happened after the fact is not the same as pausing before acting.

**Expensive test rules (strict — `billed` is fully exempt from every rule below; never apply these to a `billed` test):**
- **User approval is required before running any expensive test, every single time** — no exceptions, even for a single test, even as part of a larger approved task.
- **Never run expensive tests all together.** Go one at a time (`pytest tests/expensive/test_X.py::test_name -v -m expensive`), never a bare `-m expensive` sweep.
- **Read existing logs in `logs/test_logs/` before re-running anything.** A prior run's log may already answer the question.
- **Only re-run a previously-failed expensive test once you're confident a fix addresses the failure** — don't re-run speculatively to "see what happens."
- **Never re-run an expensive test yourself once it has actually reached OpenAI** (whether it passed or failed) — that always requires a fresh, explicit approval from the user for that specific run, no exceptions, including "just to double-check" or "just to read the output." Re-running a failure that errored *before* reaching OpenAI is fine without re-asking.
- **`apps/morning-mcp-app` runs as a separate long-lived container for these cross-app tests** (`./run_morning_mcp.sh dev` / `./stop_morning_mcp.sh dev`), not something pytest starts. Rebuilding is not automatic: any code or config change in `apps/morning-mcp-app` (tools, formatters, server, `config.dev.json`) has **no effect on an already-running container**. Whenever you edit anything in `apps/morning-mcp-app` for the sake of a denidin-app E2E test, you **must** `./stop_morning_mcp.sh dev` then `./run_morning_mcp.sh dev` (which rebuilds the image; verify the new tunnel URL lands in that environment's status file with `"status": "running"`) **before** retrying the test — otherwise the test silently exercises stale code and any observed failure/pass is not meaningful.

**Never redirect test output to `/tmp` or other ad-hoc log files.** Each app's `conftest.py` already writes per-test-file logs to `logs/test_logs/{test_file}.log` automatically (see `pytest_runtest_setup` in `apps/denidin-app/conftest.py`); read from there instead of teeing to a custom path. This applies to both apps under `apps/`.

### Lint & Type-check
```bash
cd apps/denidin-app
python3 -m pylint src/ --fail-under=7.0 --rcfile=.pylintrc   # or: make lint (from repo root)
python3 -m mypy src/ --config-file=mypy.ini
```

### morning-mcp-app (self-contained, own Makefile)
```bash
cd apps/morning-mcp-app
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt   # for local test-running only — the server itself runs containerized, see below
cp config/config.example.json config/config.dev.json    # then fill in real Morning sandbox credentials + dev ngrok authtoken
cp config/config.example.json config/config.prod.json   # then fill in real Morning production credentials + prod ngrok authtoken
make test            # or: python3 -m pytest tests/ -v --tb=short
./run_morning_mcp.sh dev|prod    # start that environment's container (ngrok runs inside it)
./stop_morning_mcp.sh dev|prod   # stop it
```

## Governance Docs — Read Before Non-Trivial Work

This project enforces its workflow through docs in `.github/`, which are authoritative and take precedence over generic conventions:

- **`.github/CONSTITUTION.md`** — binding coding standards (config handling, UTC timestamps, git workflow, no monkey-patching, logging format, retry/error-handling rules, file formats, exit codes). This is "WHAT we enforce."
- **`.github/METHODOLOGY.md`** — binding process (spec-first development, TDD with human approval gates, Bug-Driven Development for bug fixes, folder movement rules for `specs/`). This is "HOW we work."
- **`.github/quick-ref-constitution.md`** — condensed cheat-sheet of the two docs above; read this first if short on time.
- **`.github/agents/*.agent.md`** and **`.github/prompts/*.prompt.md`** — SpecKit agent definitions (`speckit.specify`, `speckit.plan`, `speckit.tasks`, `speckit.implement`, `speckit.analyze`, `speckit.clarify`, `speckit.constitution`, `speckit.checklist`, `speckit.taskstoissues`).

Note: `CONSTITUTION.md` opens with an absolute "ZERO MOCKING POLICY" banner claiming it overrides every other section, but later sections in the same file (§I, §V) explicitly permit mocking external services (OpenAI, Green API) in tests while forbidding mocking of *internal* application components (routers, handlers, managers, models). In practice, follow the more detailed §I/§V rule: real internal code paths always, mocks only for third-party network services, and never `unittest.mock` inside `tests/integration/` — use real sandbox endpoints, local HTTP fixture servers, or `@pytest.mark.expensive` for real API calls instead.

### Rules that matter most for code changes here
- **Never work on `master` directly.** Check `git branch --show-current`; if on master, create `feature/###-description` or `bugfix/###-description` first.
- **No environment variables** — `os.getenv()`/`os.environ` are forbidden. All config comes from `config/config.json` (or `config/config.test.json` in tests), loaded via `AppConfiguration` and passed by dependency injection.
- **UTC everywhere** — always `datetime.now(timezone.utc)`, never bare `datetime.now()`.
- **No monkey-patching** — no runtime method replacement or dynamic attribute injection; use dependency injection, strategy, template-method, or observer patterns instead (see CONSTITUTION §XVII for the canonical examples).
- **`pathlib.Path`**, not string concatenation or `os.path`.
- **Feature flags** for new behavior, under `config.feature_flags`, default `false`; when disabled, code path must be byte-for-byte identical to before. Unit tests may set flags; integration tests must never set flags (they test default production behavior).
- **Integration tests** simulate a real external entry point (e.g. a Green API webhook JSON dispatched through `bot.router`), not direct method calls into internal components — see CONSTITUTION §V for the distinction between true "integration" and "component integration" tests, and why routing/dispatcher coverage matters (a real production bug — missing `imageMessage` router — is the running example in these docs).
- **Tests are immutable once approved** — new phases add tests, they don't rewrite existing ones, without explicit human sign-off.
- Retry policy: retry once on 5xx/timeout after 1s; never retry 4xx. User-facing errors are friendly (`"[emoji] [what happened]. [what to do next]."`); technical detail goes to logs only.

## Architecture (`apps/denidin-app/`)

DeniDin is a WhatsApp bot (Green API) that forwards messages to OpenAI (GPT-4o-mini) with a two-tier memory system, RBAC, and media processing. Full diagrammed architecture: `.github/ARCHITECTURE.md`.

### Message flow
```
Green API webhook → denidin.py @bot.router.message(type_message=...) handlers
  → WhatsAppHandler (validate/parse notification into WhatsAppMessage)
  → GroupMembershipResolver (group messages only: most-permissive member's role governs the turn)
  → UserManager (role: admin/godfather/client/blocked → token limit + memory scope)
  → SessionManager (load/create session, append message, prune to token budget)
  → AIHandler
      → MemoryManager.recall() (ChromaDB semantic search, only if enable_memory_system)
      → builds system prompt (constitution + role context + memories + history)
      → OpenAI call (retry: 3 attempts, 2s wait; rate-limit: 3 attempts, 5s wait)
      → [[NO_REPLY]] sentinel check (should_reply)
  → SessionManager (store response, update token count)
  → if should_reply: WhatsAppHandler.send_response() (truncates >4000 chars); else no reply sent
```
Non-text messages (`imageMessage`, `documentMessage`, `videoMessage`, `audioMessage`) route through the same dispatcher pattern in `denidin.py` to `WhatsAppHandler.handle_media_message()` → `MediaHandler` → the extractor pipeline below. A shared WhatsApp contact card (`contactMessage`, Feature 030) instead routes into the same *conversational* pipeline `textMessage` uses (`_process_conversational_message`, shared by both) — its vCard content is framed into `text_content` and the model reads it directly, so a godfather/admin sharing a contact proposes an `add_client` call exactly as typed text would, inheriting the existing approval gate and missing-field behavior unchanged. Sharing **multiple** contacts at once arrives as a distinct type (`contactsArrayMessage`) and is declined outright with a friendly message, no AI call at all. There is also a catch-all `@bot.router.message()` handler so no message type is silently dropped.

**Group conversations (Feature 039)**: group messages are no longer gated by an `@mention` check — DeniDin is addressed by default in a group, same as 1:1, and instead relies on the model's own judgment (guided by `config/runtime_constitution.md`'s "Group Conversation Etiquette" section) to recognize when a message clearly names someone else and reply with the literal sentinel `[[NO_REPLY]]` instead of a substantive answer. `AIHandler._finalize_response` checks `response_text.strip() == NO_REPLY_SENTINEL` and threads the result as `AIResponse.should_reply`; `denidin.py`'s `_process_conversational_message` still persists the user's message either way but skips `WhatsAppHandler.send_response()` when `should_reply` is `False` — a deliberate no-reply, not an error path. RBAC for a group turn is resolved separately by `GroupMembershipResolver` (`src/managers/group_membership_resolver.py`, via `denidin.py`'s `_resolve_group_user_phone`): the most-permissive role among the group's real members (fetched via a real Green API `getGroupData` call, in-memory cached per `chat_id`) governs the turn's token limit and tool attachment, not just the individual sender — this is separate machinery from the no-reply sentinel above and never touches `Message` storage. `Message.sender`/`Message.recipient` now hold resolved human-readable display names (Green API's `senderContactName` → `senderName` → raw id fallback chain) rather than phone numbers or the old `"AI"` sentinel; `SessionManager.add_message` enforces this centrally (`recipient=None` for `role="user"`, `sender=None` for `role="assistant"`) regardless of what any caller passes. Media messages are explicitly out of scope for all of this — `WhatsAppHandler.handle_media_message()` never routes through `AIHandler.get_response`, so no mention-gate, no-reply sentinel, or group-RBAC resolution ever applies to images/documents.

### Key components (`apps/denidin-app/src/`)
- **`denidin.py`** (repo root of the app, not under `src/`) — entry point; owns the global `bot` (GreenAPIBot) and `denidin_app` (a `DeniDin` instance holding `ai_handler`, `config`, `whatsapp_handler`, `cleanup_thread`); registers all `@bot.router.message(...)` handlers; `initialize_app(config_dict)` is the shared bootstrap used by both `__main__` and integration tests (constructs `AIHandler` → `WhatsAppHandler` → `MediaHandler`, wires memory startup recovery + cleanup thread if `enable_memory_system`).
- **`handlers/whatsapp_handler.py`** — Green API integration, message-type validation, response sending/truncation. No longer does group-mention filtering (Feature 039 removed the `@mention` gate — see "Message flow" above).
- **`handlers/ai_handler.py`** — OpenAI integration via the Responses API, system-prompt construction, memory recall integration, session-to-long-term-memory transfer, RBAC-aware token limits, current-date injection into `instructions`, and Morning MCP remote-tool attachment for godfather/admin roles (see "Morning MCP integration" below). `instructions` is assembled in a fixed order — constitution text, then recalled memory context (appended to the constitution string), then a `---` separator, then today's UTC date computed fresh per call (`ai_handler.py:363-368`) — never templated into the constitution file itself. This ordering is also what makes the constitution (`config/runtime_constitution.md` — a single file shared identically by dev/prod/test as of 2026-07-23, not per-environment data; ~4.0K tokens as of 2026-07-23, measured via `tiktoken`'s `o200k_base`) eligible for OpenAI's automatic prompt caching: it's the stable, byte-identical prefix of every call (everything that varies — memories, date — comes after it), and OpenAI caches on the longest identical prefix for prompts ≥1024 tokens at a 50% discount on the cached portion, with no code changes required. Keeping any per-call-dynamic content appended *after* the constitution (not prepended or interleaved) preserves this.
- **`handlers/media_handler.py`** + **`handlers/extractors/`** — `MediaExtractor` abstract base with `ImageExtractor` (vision model per `config.ai_vision_model`, default `gpt-4o-mini`, single call for text+analysis), `PDFExtractor` (PyMuPDF page-to-image, delegates to `ImageExtractor`, aggregates per-page analysis, max 10 pages), `DOCXExtractor` (python-docx + optional AI analysis via `config.ai_model`). All extractors return a common contract: `extracted_text`, `document_analysis` (`document_type`/`summary`/`key_points`), `extraction_quality`, `warnings`, `model_used`.
- **`managers/session_manager.py`** — Tier-1 (short-term) memory: UUID sessions, JSON persistence under `data/sessions/`, per-role token limits, 24h expiration, archival to `data/sessions/expired/YYYY-MM-DD/`.
- **`managers/memory_manager.py`** — Tier-2 (long-term) memory: ChromaDB collections (`memory_{entity_id}`, `_public`, `_private`, `memory_system_context`), OpenAI embeddings per `config.ai_embedding_model` (default `text-embedding-3-large`), scope-filtered semantic recall.
- **`managers/user_manager.py`** — RBAC: role resolution (Admin > Godfather > Client > Blocked) from phone number, permission/token-limit/memory-scope lookups.
- **`managers/group_membership_resolver.py`** (Feature 039) — resolves a WhatsApp group's most-permissive member (phone + `Role`) via a real Green API `getGroupData` call, in-memory cached per `chat_id` (no disk persistence — a restart simply re-fetches on next use). Used only to pick which phone's role governs a group turn's RBAC; independent of the no-reply/etiquette machinery (see "Message flow" above).
- **`managers/media_file_manager.py`**, **`managers/media_manager.py`** — media file lifecycle and orchestration supporting `MediaHandler`.
- **`managers/ledger_event_manager.py`** (Feature 033) — persists structured ledger events (fee agreements, bank deposits) recognized by the runtime constitution's "Ledger Event Recognition" rules, one immutable JSON file per event under `{data_root}/events/{event_id}.json` (`event_id` format: a source-type letter + `DDMMYY` + `HHMM` + a same-minute sequence digit, e.g. `A02022604480`) — moved out of `session.json` (Feature 024's original location) so events survive session archival/expiry independently. Called via `AIHandler`'s `capture_ledger_event` local tool wiring, never invoked directly by the model against Morning.
- **`services/cleanup_service.py`** — `SessionCleanupThread` (hourly background sweep) and `run_startup_cleanup` (recovers orphaned sessions on boot). 4-step cleanup per expired session: archive → transfer to ChromaDB → remove from active index → mark `transferred_to_longterm`.
- **`models/config.py`** — `AppConfiguration` dataclass; `from_file()`/`from_dict()` loading + `validate()`; this is the single source of truth for all runtime config (no env vars).
- **`models/`** (message, user, media, media_attachment, document, green_api, state) — typed data models for messages, media attachments, document analysis, RBAC users.
- **`constants/error_messages.py`** — centralized user-facing error strings (friendly, no stack traces).

### Data & config
- `config/config.dev.json` / `config/config.prod.json` (gitignored, real per-environment secrets) vs `config/config.example.json` (single safe-placeholder template shared by both envs, committed — copy it to `config.dev.json`/`config.prod.json` and fill in the env-specific values) vs `config/config.test.json` (used by pytest, its own ephemeral `test_data/` root — decoupled from the persistent `dev_data/` environment, per 019-env-separation) — all loaded via `AppConfiguration.from_file`, no env vars. Real secrets for a given environment live in `creds/DeniDin Dev Creds.txt` / `creds/DeniDin Prod Creds.txt` (gitignored) — the single source of truth to paste from when (re)populating a config file, rather than any config file itself.
- `data/sessions/`, `data/memory/` (ChromaDB) — gitignored runtime state, isolated from test data via the `data_root` config field. `config/runtime_constitution.md` is NOT part of this (2026-07-23) — it's shared, git-tracked config content, identical for dev/prod/test, resolved via `constitution_config.base_dir` (default `'config'`, overridable — e.g. tests pointing at a tmp dir) rather than `data_root`. Previously lived under `{data_root}/constitution/`, duplicated per environment; that let dev's and prod's copies silently drift out of sync (a real incident, 2026-07-23 — dev's copy was missing bugfix-014's guidance for weeks).
- `logs/denidin.log` (production) and `logs/test_logs/{test_file}.log` (per-test-file, auto-configured by `conftest.py`) — check these logs instead of re-running expensive tests to get more diagnostic detail.

### Morning MCP integration (`apps/denidin-app` ↔ `apps/morning-mcp-app`)
Godfather/admin users manage invoices in natural Hebrew: `AIHandler` calls OpenAI's **Responses API** with the Morning server attached as a **remote MCP tool** (`type: "mcp"`, bearer-auth header), reached over a real ngrok tunnel — no local import of `denidin_mcp_morning` code, no mocking of the MCP round-trip. The tunnel URL is discovered via a per-environment shared status file (`shared/mcp-status-dev/`, `shared/mcp-status-prod/` — see "Environments (dev/prod)" above; must show `"status": "running"`); `apps/denidin-app`'s own `config.mcp.morning_status_file` points at its own environment's copy, never the other's. RBAC-gated: only godfather/admin roles get the tool attached. Current date is injected into `instructions` at reply time (UTC, computed per call — not templated into the constitution file) so the model resolves relative dates correctly instead of guessing a wrong year.

### `apps/morning-mcp-app/` (separate app, own package/tests/config/Docker)
Standalone `MorningClient`/`MorningAuth` for the Morning (Green Invoice) sandbox API — token-managed HTTP client with retry/backoff (`requests` + urllib3 `Retry`). Own package at `apps/morning-mcp-app/src/denidin_mcp_morning/`, imported as `from denidin_mcp_morning.morning_client import MorningClient` (its `conftest.py` puts its own `src/` on `sys.path` — no cross-app imports, no `sys.path` reach-through into `apps/denidin-app/`). `server.py` builds a FastMCP server exposing 11 tools (`create_invoice`, `create_transaction_account`, `create_combo_document`, `create_credit_note`, `create_receipt`, `list_invoices`, `get_invoice_details`, `update_invoice_status`, `add_client`, `get_financial_summary`, `download_invoice_pdf` — the 4 `create_*` document-type-specific tools added by Feature 021, alongside `create_invoice`) over streamable-HTTP, wrapped in `BearerTokenMiddleware` (single shared secret, not OAuth) plus an unauthenticated `/health` liveness route. `./run_morning_mcp.sh dev|prod` / `./stop_morning_mcp.sh dev|prod` run it as a Docker container per environment (019-env-separation — no host-level PID-file process anymore; Docker itself prevents duplicate starts), with ngrok running *inside* the container, writing that environment's status file (`shared/mcp-status-<env>/`) for `apps/denidin-app` (and its own expensive tests, via `discover_running_server()` in `tests/expensive/e2e_helpers.py`) to discover the live URL — reusing an already-warm tunnel instead of spinning up a fresh one avoids an ngrok cold-start flake (`424 Failed Dependency` on the first request). Exercised by `apps/morning-mcp-app/tests/integration/test_morning_sandbox_*.py`, which hit the real Morning sandbox (constitution: no mocking). Config lives in its own `config/{config.example.json,config.test.json,config.dev.json,config.prod.json}` (flat shape: `api_key_id`/`api_key_secret`/`api_url`, plus an `mcp` block: `auth_token`/`ngrok_authtoken`/`status_file`) — no longer shares config files with `apps/denidin-app/`. `config.test.json` holds real sandbox secrets (plus `openai_api_key`/`mcp.ngrok_authtoken` for the OpenAI/ngrok-driven tests) and, like `config.dev.json`/`config.prod.json`, is gitignored rather than committed (only `config.example.json` is tracked).

## Spec-Driven Workflow

Non-trivial features and bugfixes follow a SpecKit pipeline (full detail in `.github/METHODOLOGY.md`):
```
speckit.specify → spec.md (+ MANDATORY user-stories.md, Given-When-Then, BLOCKING gate)
  → speckit.clarify (resolve ambiguities)
  → speckit.plan → plan.md, research.md, data-model.md, contracts/, quickstart.md
  → speckit.tasks → tasks.md (Task A = tests, Task B = implementation, B blocked until A approved)
  → speckit.analyze (cross-artifact consistency check)
  → speckit.implement → incremental delivery, one user story at a time
```
- New/updated specs belong under `specs/in-progress/` (drafting/pre-clarification through active implementation) or `specs/backlog/` (post-clarification, not currently being worked — replaces the old `specs/P0/`/`P1/`/`P2/` split as of 2026-07-21; priority is now tracked via each spec's own `Priority` field, not by folder); `specs/done/` and `specs/obsolete/` are historical archives — never delete from them (`specs/obsolete/` also replaces the old `specs/not-doing/`, and now covers specs whose described issue no longer applies against current code, not just cancelled features). Bugfix specs go in `specs/bugfixes/bugfix-###-description.md` while open, and move to `specs/done/bugfixes/` or `specs/obsolete/bugfixes/` once resolved or found stale. `specs/not_reproducible/bugfixes/` (added 2026-07-21) is a fourth closure destination, distinct from both: use it for a bug where a root cause was investigated and a human decision was made to close it, but nothing was actually fixed — e.g. the behavior is accepted as inherent/non-deterministic model risk rather than an app-level bug (see `bugfix-013` for the first example). Don't conflate with `done/` (implies a fix landed) or `obsolete/` (implies the issue no longer applies or was rejected outright).
- Bug fixes follow Bug-Driven Development instead: root cause → human approval → test-gap analysis → failing test → human approval → minimal fix → verify. See `.github/METHODOLOGY.md` §VII.
- Branch naming: `feature/###-description`, `bugfix/###-description`, or `docs/`/`chore/` prefixes.
- 🚨 **NEVER RUN HALELUYA ON YOUR OWN.** 🚨
- **"haleluya"** (or any spelling variant — "halleluja", "halelluia", etc.), said any time the actual work is already done and approved, is shorthand for: **first verify a spec file for the current feature/bugfix is actually committed under `specs/`** (feature 024 was fully merged with no spec ever committed at all — confirmed via full git history search, 2026-07-30 — so this check now runs before anything else, and haleluya stops and asks rather than proceeding if no spec is found), then update docs and move the spec to its correct `specs/` folder **as part of the same commit as the code** (2026-08-07 — no longer a separate follow-up PR; the whole thing ships as one PR, the spec's `Status` line gets the real PR number filled in via one small addendum commit on the same branch once the PR exists), commit, push, open a PR, and merge it. **Haleluya never deploys anything, to any environment, scripted or ask-first** (2026-08-07 — the old "test-deploy, ask first" step was removed entirely, not just gated) — which environment(s) run what is always a separate, fully explicit human decision made outside this flow; merging to `master` does NOT redeploy by itself regardless (see "Environments (dev/prod)" above). Also available as `/haleluya`. **Branches are never deleted as part of this flow** — the merged branch is left in place; only the user deleting one explicitly is a deletion. See `.github/METHODOLOGY.md`'s "Finish-Feature Trigger Phrase" for the full definition — it doesn't skip any gate, it's just shorthand for the finish-up mechanics.
