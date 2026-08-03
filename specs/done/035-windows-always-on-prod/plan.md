# Implementation Plan: Windows Always-On Production Host

**Branch**: `035-windows-always-on-prod` | **Date**: August 2, 2026 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/035-windows-always-on-prod/spec.md`

---

**IMPORTANT**: This plan complies with:
- **CONSTITUTION.md** (§I-III): NO environment variables, UTC timestamps, git workflow — see Constitution Check below for how each applies (or doesn't) to an infra/ops feature with no application code changes.
- **METHODOLOGY.md** (§II, IV, VII): Template structure, phased planning, Integration Contracts.

Like `spec.md`, this plan deviates from the generic template where it
assumes application code (data-model.md, REST/GraphQL contracts,
`src/`-style project structure) — this feature adds no application code at
all (FR8: no feature flag, no `apps/denidin-app`/`apps/morning-mcp-app`
change). Precedent: `specs/backlog/028-monitoring-and-alerting`'s plan.md
and `specs/done/019-env-separation`'s quickstart.md-centric approach, both
ops-facing specs that skip data-model/API-contract sections entirely.

---

## Summary

Move production onto a dedicated, always-on Windows laptop, reachable and
fully operable from the operator's Mac via Tailscale + key-based SSH +
Docker remote context — start/stop, deploy new versions, tail logs, check
health/uptime — with production self-recovering after a reboot (Scheduled
Task + Windows auto-logon, without touching the existing `restart: "no"`
compose policy). No application code changes; the deliverable is OS-level
configuration (documented as a runbook), plus a small set of operator-side
verification/deploy scripts. Acceptance tests and the scripts implementing
the automatable ones were already produced during the `/speckit.clarify`
session (`acceptance-tests.md`, `scripts/*.sh`) at the operator's explicit
request — this plan's Phase 2 promotes them from spec-local drafts to
their permanent home in the main repo tree.

## Technical Context

**Language/Version**: Bash (operator-side scripts, already POSIX-`bash`-syntax-checked) + Windows-native configuration (PowerShell/`netplwiz`/Task Scheduler/`netsh`/`powercfg`/registry) — no application-language code.
**Primary Dependencies**: Tailscale (free Personal plan), Windows' built-in OpenSSH Server optional feature, Docker Desktop with WSL2 backend (Windows box, runtime only — see below), Docker `buildx` (Mac, build-only), macFUSE + `sshfs` (Mac, FR6a data mount). All already-standard tooling; no new third-party dependency added to `apps/denidin-app` or `apps/morning-mcp-app` themselves.
**Storage**: N/A for this feature's own artifacts — `config/config.prod.json` follows the existing, unmodified pattern (FR6), and `apps/denidin-app/data` is the existing app-level persisted data, now pinned as a singleton on the Windows box (FR6a) rather than newly introduced by this feature.
**Testing**: `acceptance-tests.md` (already drafted) is the test plan. Automated checks are the three shell scripts already written (`verify_windows_prod.sh`, `deploy_and_verify.sh`, `verify_reboot_recovery.sh`) plus the new `build_and_package.sh`; manual checks are the item list in that same file. No `pytest` involvement — this feature doesn't touch either app's request-handling code, so the existing Python test suites are entirely unaffected and out of scope for this plan.
**Target Platform**: A Windows 10/11 laptop, x86_64 (edition — Home vs. Pro — not yet known; see research.md), as the production **runtime-only** host — no source code or build tooling on it (corrected 2026-08-02); macOS as the operator's control **and build** client (images are built there, per FR3a/research.md).
**Project Type**: Infrastructure/operations (runbook + operator tooling), not a web/mobile/API project.
**Performance Goals**: N/A — no throughput/latency target; success is measured operationally (Success Criteria in spec.md), not by a performance benchmark.
**Constraints**: No new secrets-management tooling (FR6); no compose `restart:` policy change (FR2a); no cross-machine lock enforcement beyond a manual runbook checklist (FR7); no source code or build step ever runs on the Windows box (FR1/FR3a, corrected 2026-08-02); the deploy artifact never contains secrets or persisted data (FR3a/FR6a) — all per explicit clarifications in spec.md.
**Scale/Scope**: One Windows box, one Mac operator, two existing containers (`denidin-app-prod`, `morning-mcp-app-prod`) — no multi-tenant or multi-host scope.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — no changes since this feature's shape doesn't touch application code.*

| Gate | Applies? | Status |
|------|----------|--------|
| No environment variables (§I) | Partially — new Windows-side config is registry/OS settings, not app config | **Pass**: `config/config.prod.json` (the only app-facing config this feature touches) follows the existing file-based pattern unchanged (FR6); nothing new reads from `os.getenv`/`os.environ`. |
| UTC timestamps (§I) | No new timestamp-producing code | **N/A** — no code added; existing app logging (already UTC) is untouched. |
| Git workflow: feature branch, no direct `master` commits (§II) | Yes | **Pass** — working on `035-windows-always-on-prod`, not `master`. |
| No monkey-patching (§...) | No app code touched | **N/A**. |
| `pathlib.Path` not string concatenation (§...) | Scripts are Bash, not Python | **N/A** — Bash path handling isn't governed by this Python-specific rule; scripts use standard quoted-variable path handling. |
| Feature flags for new behavior, default `false` (§...) | No app behavior change | **N/A** — FR8 already states no feature flag; nothing in `config.feature_flags` is touched. |
| Retry policy / user-facing error format (§...) | No request-handling code touched | **N/A**. |
| Integration Contracts required for multi-component features (METHODOLOGY §VII) | Yes — Mac/Windows/Tailscale/SSH/Docker all interact | **Addressed** — see Integration Contracts section below. |

No violations; **Complexity Tracking section omitted** (nothing to justify).

## Project Structure

### Documentation (this feature)

```text
specs/035-windows-always-on-prod/
├── spec.md                      # Feature spec (done)
├── user-stories.md              # Mandatory user stories (done)
├── checklists/requirements.md   # Spec-quality checklist (done)
├── acceptance-tests.md          # Test plan: automated + manual (done, pre-built during clarify)
├── plan.md                      # This file
├── research.md                  # Phase 0 output (this plan)
├── quickstart.md                # Phase 1 output (this plan) — the actual runbook FR1 requires
└── tasks.md                     # Phase 2 output (/speckit.tasks — not created by this command)
```

`data-model.md` and `contracts/` (Phase 1 outputs in the generic template)
are **N/A** for this feature: there are no data entities and no REST/GraphQL
API being added. `quickstart.md` *is* produced by this plan, since FR1
explicitly requires a runbook and `acceptance-tests.md` already references
it by name.

### Source Code (repository root)

This feature's lasting changes to the main repo tree are a **new
top-level `scripts/windows_prod/` directory** (promoting the operator-tool
scripts already drafted in `specs/035-windows-always-on-prod/scripts/`
during `/speckit.clarify`, at the operator's request, to sit alongside this
repo's other cross-cutting ops scripts — `scripts/run_all.sh`,
`scripts/stop_all.sh`, `scripts/killall_containers.sh`,
`scripts/env_lock.sh` — matching how `028-monitoring-and-alerting` placed
its real deliverable code in `apps/*/` rather than under `specs/`) and a
**new top-level, gitignored `artifacts/` directory** (build output only —
never committed, per the build-once-on-Mac correction in
spec.md/research.md).

```text
scripts/
├── run_all.sh, stop_all.sh, killall_containers.sh, env_lock.sh   # existing, unmodified
└── windows_prod/                                                  # new (this feature)
    ├── build_and_package.sh         # new (2026-08-02 correction): Mac-side build + docker save + tar.gz into artifacts/
    ├── deploy_and_verify.sh         # rewritten (2026-08-02): scp the artifact + remote extract/load/up, not remote git pull/build
    ├── verify_windows_prod.sh       # updated (2026-08-02): drops git-clone checks, adds deploy-dir + sshfs mount checks
    ├── verify_reboot_recovery.sh    # promoted, unmodified (only a REPO_DIR→DEPLOY_DIR rename for clarity)
    ├── tail_logs.sh                 # new (2026-08-03): wraps the Docker-remote-context log-tail command (FR4/FR5)
    ├── mount_data.sh                # new (2026-08-03): idempotent sshfs mount of apps/denidin-app/data (FR6a)
    └── unmount_data.sh              # new (2026-08-03): unmounts it

artifacts/                                                          # new (this feature), gitignored
└── denidin-prod-<git-sha>-<timestamp>.tar.gz                       # build_and_package.sh output; never committed, never contains secrets
```

No changes anywhere under `apps/denidin-app/` or `apps/morning-mcp-app/`.
The Windows box's own directory layout (the extracted deploy directory) is
**not** part of this repo's tree at all — it's a plain, non-git directory
that only exists on that machine; see `quickstart.md` for its exact
contents.

**Structure Decision**: Ops-runbook structure (spec-local `quickstart.md` +
`acceptance-tests.md`, matching `019-env-separation`'s precedent for
runbook docs) plus a small promoted `scripts/windows_prod/` directory for
tooling meant for repeated real use, plus a gitignored `artifacts/`
build-output directory — not the generic `src/`+`tests/` application
layout, which doesn't apply here.

## Integration Contracts

*Per METHODOLOGY.md §VII — this feature is multi-component (Mac client,
Windows box, Tailscale mesh, SSH transport, Docker daemon, the existing
wrapper scripts) even though no application code is involved.*

### Operator's Mac ↔ Windows Box (SSH transport) Contract

**Mac MUST**:
- Have Tailscale installed, running, and joined to the same tailnet as the
  Windows box before attempting to reach it.
- Have an `ssh-keygen`-generated key pair, with the public key already
  installed in the Windows box's `authorized_keys` (one-time setup step,
  `quickstart.md`).
- Reference the box via a `~/.ssh/config` `Host` alias pointing at its
  Tailscale hostname (`*.ts.net`) with the correct `IdentityFile` — all
  three operator scripts take this alias as their first argument rather
  than a raw hostname.

**Windows Box PROVIDES**:
- An OpenSSH Server reachable **only** over the Tailscale network
  interface (Windows Firewall rule scoped accordingly — FR1), never the
  LAN or any other interface.
- Key-based authentication only; password authentication is disabled in
  `sshd_config` — a connection attempt with only a password fails, not
  falls back.
- A shell session under the operator's own account (not a separate service
  account), with the same permissions the operator would have sitting at
  the machine.

**Windows Box EXPECTS**:
- The Mac's public key already present in `authorized_keys` before any
  connection is attempted — no self-service enrollment flow.

### Windows Scheduled Task ↔ `scripts/run_all.sh prod` Contract (reboot recovery, FR2a)

**Scheduled Task MUST**:
- Trigger at system startup (or user logon — whichever proves reliable for
  an unattended reboot; determined empirically once the box exists, not a
  spec-time decision) under the auto-logon account's session (FR2b).
- Invoke `scripts/run_all.sh prod` with the working directory set to the
  **deploy directory** (the extracted artifact — not a git repo root,
  corrected 2026-08-02) — the same invocation a human would type over SSH.
- Not modify, wrap, or duplicate any logic inside `run_all.sh` itself.

**`run_all.sh` PROVIDES** (unchanged by this feature):
- The same `env_lock.sh`-gated startup guarantees, `docker compose up -d`
  for both services, and status-file writes it already provides when
  invoked manually — the Scheduled Task gets no special treatment and no
  special code path. It works unmodified inside the extracted deploy
  directory precisely because that directory has the same relative
  structure (`scripts/`, `docker/`, `shared/`) as a real repo checkout,
  even though it isn't one.

**`run_all.sh` EXPECTS** (unchanged preconditions, now satisfied by the
FR3a deploy artifact rather than a one-time FR1 setup step, and
re-satisfied on every deploy rather than once):
- `docker/docker-compose.prod.local.yml` (generated no-op stub) and
  `config/shared_state.local.json` (generated, canonical to this
  machine) present in the deploy directory — both now part of every
  `build_and_package.sh` artifact, not a manually-created file that could
  drift or go stale between deploys.

### Mac Build/Package ↔ Windows Deploy Directory Contract (FR3a, added 2026-08-02)

**Mac (`build_and_package.sh`) MUST**:
- Build both prod images via `docker compose ... build`, forcing
  `docker buildx build --platform linux/amd64` regardless of the Mac's
  own CPU architecture (research.md).
- Produce a single `.tar.gz` under `artifacts/` containing: both images
  (`docker save`), `docker/docker-compose.prod.yml`, a generated no-op
  `docker/docker-compose.prod.local.yml`, a generated
  `config/shared_state.local.json`, the unmodified wrapper scripts
  (`scripts/run_all.sh`/`stop_all.sh`/`killall_containers.sh`/`env_lock.sh`,
  `apps/*/run_*.sh`/`stop_*.sh`), and
  `apps/denidin-app/config/runtime_constitution.md`.
- **Never** include `config/config.prod.json`/`apps/*/config/config.prod.json`
  (secrets) or `apps/*/data`/`apps/*/logs`/`shared/` (persistent state) in
  the artifact.

**Windows deploy directory PROVIDES** (after `deploy_and_verify.sh`
extracts + loads the artifact):
- The same relative file layout `run_all.sh`/`stop_all.sh`/the Scheduled
  Task/`env_lock.sh` all already expect (see contract above) — extraction
  is a plain `tar xzf` over the existing directory, so paths *not* present
  in the archive (`data/`, `logs/`, `shared/active_env.json`,
  `config/config.prod.json`) are left completely untouched by every
  redeploy.
- Both images already `docker load`-ed under the exact name/tag
  `docker-compose.prod.yml` expects, before `docker compose up -d` ever
  runs — so that command never falls through to `build:`.

**Windows deploy directory EXPECTS** (one-time, FR1, not re-done per
deploy):
- `config/config.prod.json` and `apps/*/config/config.prod.json` already
  present, created by hand from `creds/DeniDin Prod Creds.txt` before the
  very first `deploy_and_verify.sh` run — a deploy that runs before this
  exists fails at container startup (missing required config), not
  silently.

### Mac `sshfs` Mount ↔ Windows `apps/denidin-app/data` Contract (FR6a, added 2026-08-02)

**Mac MUST**:
- Have macFUSE and `sshfs` installed (one-time, manual macOS security
  approval required — see quickstart.md).
- Mount via the same SSH transport/key-auth already established for FR1
  (`sshfs <user>@<tailscale-hostname>:<deploy-dir>/apps/denidin-app/data
  ~/denidin-winprod-data -o reconnect,ro,volname=denidin-winprod-data`) —
  no separate credential or trust relationship.

**Windows deploy directory PROVIDES**:
- `apps/denidin-app/data` as a stable path, never relocated or renamed by
  any deploy (see the Build/Package contract above) — the mount point on
  the Mac side stays valid across every redeploy without re-mounting.

**Windows deploy directory EXPECTS**:
- Nothing additional beyond the existing SSH contract — `sshfs` is just
  another SSH client from the box's point of view, subject to the same
  key-based-auth-only, Tailscale-interface-only firewall scoping as
  everything else in FR1.

### Mac's Docker Remote Context ↔ Windows Docker Daemon Contract (FR4/FR5)

**Mac MUST**:
- Create the Docker context (`docker context create <name> --docker
  "host=ssh://<user>@<tailscale-hostname>"`) before first use, and
  explicitly switch to it (`docker context use <name>`) before running any
  command intended for the remote box.
- Switch back to `default` afterward — no command in this feature's
  scripts leaves the Mac's own local Docker context selected as a side
  effect (each script is self-contained via `docker --context <name> ...`
  rather than relying on ambient `docker context use` state, precisely to
  avoid this failure mode).

**Windows Docker Daemon PROVIDES**:
- The standard Docker Engine API, tunneled over the SSH transport
  contract above — no behavioral difference from local Docker use; `docker
  compose ps`/`logs`/`build`/`up -d` all behave identically to running
  them directly on the box.

**Windows Docker Daemon EXPECTS**:
- The SSH transport contract already holds (reachable, key-auth
  succeeds) — the Docker context has no independent auth mechanism of its
  own; it rides entirely on SSH.

## Phase 0: Outline & Research

See [research.md](research.md). One item remains an intentionally deferred
decision rather than a resolved unknown (Windows edition → update-reboot
mitigation) — documented there with why that doesn't block this plan.

## Phase 1: Design & Contracts

- `data-model.md`: **N/A** — no data entities.
- `contracts/` (API contracts): **N/A** — no REST/GraphQL API added.
- `quickstart.md`: **produced by this plan** — see
  [quickstart.md](quickstart.md), the actual runbook FR1 requires, covering
  one-time Windows-box setup end to end (Tailscale, SSH, firewall, Docker
  Desktop, config files, power/lid/auto-logon/Scheduled-Task settings,
  Docker remote context, cutover checklist).
- Agent-context auto-update (`update-agent-context.sh`): **skipped
  deliberately** — this repo's `CLAUDE.md` is hand-maintained prose (see
  its own extensive, narratively-written content), not a
  template-generated file with auto-update markers; no other spec in this
  repo's history shows evidence of this script being used. Running it
  risks introducing a mismatched section style into a carefully
  hand-curated file. Any `CLAUDE.md` updates this feature warrants (e.g. a
  short mention of the Windows-hosted production option) are left for the
  `/haleluya` "update docs" step once implementation is actually done and
  approved, done by hand like every other doc update in this repo's
  history.

## Phase 2 (tasks.md — not produced by this command)

Handed off to `/speckit.tasks`. Expected shape, so the reader isn't
surprised: mostly Windows-box **setup/configuration tasks** (from
`quickstart.md`) rather than Task-A/Task-B (write-tests-then-code) pairs,
since there's no application code being written — the "tests" for this
feature are the acceptance checks already built. The one genuine
code-producing task is promoting the three scripts from
`specs/035-windows-always-on-prod/scripts/` to `scripts/windows_prod/` per
the Project Structure decision above (a `git mv` + path-reference update,
not new code).
