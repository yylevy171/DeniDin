# User Stories: Windows Always-On Production Host

**Feature ID**: 035-windows-always-on-prod
**Created**: August 2, 2026

Per METHODOLOGY.md §I, these stories trace complete end-to-end flows from an
external entry point (the operator, at their Mac) through system behavior to
an observable result. This is an infrastructure/operations feature — the
"system" being exercised is the Windows box + Tailscale + SSH + Docker
stack, not `apps/denidin-app`/`apps/morning-mcp-app` request-handling code
(unchanged by this feature).

---

## US1 (P1): Operator starts/stops production from the Mac without touching the Windows box

**Given** the Windows box is powered on, configured per `quickstart.md`
(Tailscale joined, OpenSSH Server enabled, a deploy directory populated by
at least one `deploy_and_verify.sh` run — **not** a git clone, corrected
2026-08-02 — `config/config.prod.json` in place)
**When** the operator, from their Mac terminal, runs `ssh <user>@<tailscale-hostname>` and then
`./scripts/run_all.sh prod` (or `stop_all.sh prod`) on that remote shell
**Then** production starts (or stops) on the Windows box exactly as it would
if the operator were physically at the machine — the existing wrapper
scripts, compose files, and lock mechanism (`env_lock.sh`,
`shared/active_env.json`) all run unmodified
**And** the operator never opens a remote-desktop session or physically
touches the Windows box to do this

**Independent Test**: From a Mac with Tailscale installed and joined to the
same tailnet, SSH to the Windows box's Tailscale hostname and successfully
run `./scripts/run_all.sh prod`; confirm both containers report "Up" via
`docker compose ps` on that same SSH session.

**Acceptance Criteria**:
- The Windows box is reachable via a stable Tailscale hostname from the Mac,
  regardless of the Mac's network or the Windows box's dynamic IP
- SSH login succeeds using Windows' built-in OpenSSH Server (no third-party
  SSH server needed)
- `scripts/run_all.sh prod` / `scripts/stop_all.sh prod` behave identically
  to running them locally on any other clone — no code change

---

## US2 (P1): Operator reads live and historical logs from the Mac

**Given** production is running on the Windows box
**When** the operator wants to check `logs/prod/` or tail live container
output for either app
**Then** they can do so from the Mac — either over an SSH session (US1) or
via a Docker remote context pointed at the Windows box's Docker daemon over
SSH (`docker context create winbox --docker "host=ssh://<user>@<tailscale-hostname>"`,
`docker context use winbox`, then `docker compose logs -f denidin-app-prod`
run as if local)
**And** at no point does the operator need to open a remote-desktop session

**Independent Test**: With the Docker remote context configured and
selected, run `docker compose -f docker/docker-compose.prod.yml ps` and
`docker compose logs --tail 50 denidin-app-prod` from the Mac; confirm
output matches what running the same commands directly on the Windows box
would show.

**Acceptance Criteria**:
- `docker context create/use` successfully redirects the Mac's local
  `docker`/`docker compose` CLI to the Windows box's daemon over the
  Tailscale + SSH path
- Log output (live `-f` follow and historical `--tail`) is readable from the
  Mac with no meaningful lag beyond normal SSH round-trip
- Switching back to the Mac's own local `default` Docker context is a single
  command (`docker context use default`), so the two never get confused

---

## US3 (P2): Production credentials are provisioned without new tooling

**Given** an operator is doing the one-time Windows-box setup
**When** they need to provision production secrets (Green API token, OpenAI
key, MCP bearer token, etc.)
**Then** they copy `creds/DeniDin Prod Creds.txt`'s values into a
hand-created `config/config.prod.json` on the Windows box, gitignored
exactly as on every other clone
**And** no OS-level credential store, password-manager CLI, or vault
integration is required or introduced

**Independent Test**: Confirm `config/config.prod.json` is listed in
`.gitignore`, is present on the Windows box, and is absent from `git status`
output (untracked-and-ignored) after setup.

**Acceptance Criteria**:
- No secret ever appears in a git commit, PR diff, or any file under
  version control
- `config/config.prod.json` on the Windows box loads successfully via
  `AppConfiguration.from_file` with no code change
- The runbook names this step explicitly rather than leaving it implied

---

## US4 (P2): Windows box stays "always on" through normal interruptions, including its own lid closing

**Given** the Windows box has been configured per `quickstart.md` (sleep/
hibernate disabled on AC power, closed-lid behavior set to "do nothing" on
AC power, network-adapter power management disabled, Docker Desktop set to
start on login, Tailscale set to auto-connect on boot)
**When** the operator's Mac goes to sleep, disconnects from the network, or
is closed entirely — **or** the Windows box's own lid is closed (it runs on
permanent AC power)
**Then** the Windows box and its running containers are completely
unaffected — they keep running and remain reachable the next time the Mac
reconnects to Tailscale

**Independent Test**: With production running, close the Windows box's lid
for at least 10 minutes (it should stay running, network included — check
via `tailscale ping` from the Mac partway through), then separately put the
Mac to sleep for at least 10 minutes, wake it, reconnect Tailscale, and
confirm (via SSH or Docker remote context) that both containers have been
"Up" continuously the whole time (no restart in `docker compose ps` uptime).

**Acceptance Criteria**:
- Container uptime shown by `docker compose ps` is unbroken across both the
  Mac's sleep/wake cycle and the Windows box's lid closing
- The Windows box stays reachable over Tailscale while its lid is closed
- Tailscale reconnects automatically on the Mac without operator action
  beyond normal wake-from-sleep
- No manual step is needed on the Windows box side to "resume" anything

---

## US5 (P1): Production self-recovers after a Windows box reboot, without an operator noticing or acting

**Given** the Windows box has been configured per `quickstart.md`, including
auto-logon under the operator's own admin account (FR2b) and a Scheduled
Task that runs `scripts/run_all.sh prod` at boot/login (FR2a)
**When** the Windows box reboots for any reason — a planned restart, an
unexpected power event, or a Windows-Update-forced reboot
**Then** Windows logs the operator's account in automatically (no one needs
to be physically present), Tailscale reconnects, Docker Desktop starts, and
the Scheduled Task re-runs `scripts/run_all.sh prod`, bringing both
containers back up on its own
**And** no compose file's `restart:` policy was changed to achieve this —
every service is still `restart: "no"` (CLAUDE.md's 2026-07-21 hardening
still holds: a container `watchdog.py` deliberately kills for a real
mismatch still stays dead, since the Scheduled Task only reruns the full
script, not a raw `docker start`)

**Independent Test**: With production running, reboot the Windows box (e.g.
`shutdown /r`), wait for it to come back, and confirm from the Mac (over
SSH or Docker remote context) that both containers are `Up` again without
any manual intervention.

**Acceptance Criteria**:
- Windows boots directly to a logged-in desktop session under the
  operator's own account, with no manual login step
- Production is back up within a reasonable window of the box finishing its
  boot sequence, with no operator action required
- The Scheduled Task invokes the same `scripts/run_all.sh prod` a human
  would run over SSH — no separate/duplicate startup logic
- A container `watchdog.py` intentionally killed for an environment
  mismatch still does not come back on its own outside of this Scheduled
  Task path (i.e. this doesn't quietly reintroduce auto-restart-on-crash)

---

## US6 (P1): Operator deploys a new version from the Mac and confirms it actually works

**Given** a code change has been merged to `master`, and the Mac's own repo
checkout has been updated to that commit (`git pull`)
**When** the operator, from the Mac, runs
`scripts/windows_prod/deploy_and_verify.sh` — which builds both prod
images **on the Mac** (`docker buildx build --platform linux/amd64`),
packages them plus the non-secret runtime files into a `.tar.gz` under
`artifacts/`, `scp`s it to the Windows box, then SSHes in to extract it,
`docker load` the images, and `docker compose up -d`
**Then** the Windows box's containers are recreated with the new code —
**no `git pull`, no build, and no source code of any kind ever touches the
Windows box** (corrected 2026-08-02; the original draft had the box itself
running `git pull` + `docker compose build`, which this feature no longer
does)
**And** the operator confirms the new version is genuinely live — not just
"containers report Up" — by sending a real WhatsApp message to the bot and
receiving a DeniDin response

**Independent Test**: Merge a trivial, observable change (e.g. a tweak to
a response string), `git pull` it on the Mac, run
`deploy_and_verify.sh`, then send a WhatsApp message that would exercise
the changed behavior and confirm the response reflects the new code.

**Acceptance Criteria**:
- The Mac's own repo checkout is at the merged commit before packaging
  (`build_and_package.sh` doesn't itself pull — that's the operator's own
  normal `git pull`, unchanged)
- `build_and_package.sh` produces a `.tar.gz` containing both freshly-built
  `linux/amd64` images plus compose files/wrapper scripts/non-secret
  config, and deliberately **excludes** `config.prod.json` and
  `data`/`logs`/`shared/`
- `deploy_and_verify.sh`'s remote extract + `docker load` + `docker
  compose up -d` completes without error and recreates the container(s) —
  not just restarts the old image — while leaving the Windows box's
  persistent `data`/`logs`/`shared/active_env.json` completely untouched
- A real WhatsApp message sent to the bot after deploy gets a DeniDin
  response, proving the full chain (Mac build → `scp` → Windows load/up →
  Green API → OpenAI → WhatsApp reply) actually works
- This final WhatsApp check is intentionally manual (see
  `acceptance-tests.md`) — it uses the real production number and a real,
  billed OpenAI call, not something to fire automatically on every deploy

---

## US7 (P2): Operator inspects or backs up live production data from the Mac, without SSHing in

**Given** production has been running on the Windows box for a while, and
the Mac has macFUSE + `sshfs` installed (FR6a)
**When** the operator mounts the box's `apps/denidin-app/data` folder
locally (`sshfs <user>@<tailscale-hostname>:<deploy-dir>/apps/denidin-app/data
~/denidin-winprod-data -o reconnect,ro,volname=denidin-winprod-data`)
**Then** they can browse, read, or copy that live session/ChromaDB data
as an ordinary local macOS folder — no SSH session, no `scp` per file, no
new backup/sync tooling
**And** the mount is read-only, so nothing the operator does on the Mac
side can accidentally modify or corrupt the one canonical copy of that
data, which continues to live only on the Windows box

**Independent Test**: With production running and the sshfs mount active,
`ls ~/denidin-winprod-data` from the Mac shows the same session/memory
directory structure as `ssh <windows-host> 'ls ~/<deploy-dir>/apps/denidin-app/data'`
would; attempting to write into the mount fails (read-only).

**Acceptance Criteria**:
- The mount survives a Mac sleep/wake cycle (`-o reconnect`) without
  manual re-mounting in the common case
- `apps/denidin-app/data` is never included in a `build_and_package.sh`
  artifact and is never relocated by a deploy — the mount point stays
  valid across every redeploy
- No write succeeds through the mount (read-only by default, per FR6a)
- Setup uses only `brew`-installed macFUSE + `sshfs` and the existing
  Tailscale/SSH trust relationship from US1 — no new credential, no new
  network exposure beyond what FR1 already opened
- **Status note**: this story's setup (macFUSE + `sshfs` installation) was
  in progress when this feature's earlier work session was interrupted —
  it is designed but not yet verified against the real Windows box.

---

## Out of Scope (per spec.md)

- Changing any compose file's `restart:` policy to achieve reboot recovery
  — FR2a's Scheduled Task gets the same outcome without that.
- Guaranteed prevention of Windows Update forced reboots — left open
  pending the laptop's Windows edition (see spec.md Clarifications).
- Cross-machine enforcement preventing `prod` from running on both the old
  host and the Windows box simultaneously — mitigated only by a runbook
  checklist (FR7), not tooling.
- Remote hard power-cycling if the Windows box becomes fully unresponsive.
- Any OS-level or third-party secrets management beyond the existing
  config-file pattern.
- `specs/backlog/028-monitoring-and-alerting`'s shared health-check work —
  tracked separately.
- Any build tooling or source code presence on the Windows box itself —
  it is a pure runtime target (corrected 2026-08-02).
- Any file-sync/backup tooling for the data folder beyond the read-only
  sshfs mount (US7) — no scheduled job, no versioning, no second copy.
- A private Docker registry or any image push/pull — artifact transfer is
  a direct `scp` of a `docker save` tarball.
