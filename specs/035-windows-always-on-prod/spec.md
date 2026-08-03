# Feature Spec: Windows Always-On Production Host

**Feature ID**: 035-windows-always-on-prod
**Priority**: P1
**Status**: Clarified - Ready for Planning
**Created**: August 2, 2026
**Updated**: August 2, 2026

---

## Problem Statement

Production (`denidin-app-prod` + `morning-mcp-app-prod`) currently runs on a
machine the operator has to physically be at (or otherwise remote into in a
heavyweight way) to start, stop, monitor, or diagnose. `GreenAPIBot` polls
for notifications rather than receiving pushed webhooks, and there is one
paid WhatsApp Business number / one Green API instance (per CLAUDE.md's
"Important asymmetry" note) — so production needs to be up continuously,
not just while a laptop happens to be open.

This feature moves production onto a dedicated Windows laptop that stays
powered on and running continuously ("always on"), and establishes a way to
operate it entirely from the operator's Mac — start/stop, monitor
container/health status, and read logs — **without ever needing to
physically open, log into, or remote-desktop the Windows machine** once it
has been initially configured. It also defines how production credentials
get onto that machine, consistent with this repo's existing "config files
only, no env vars, no new secrets tooling" posture (CONSTITUTION.md §I).

This is an infrastructure/operations feature, not an application code
change — no request-handling code path in `apps/denidin-app` or
`apps/morning-mcp-app` is touched. It follows the same precedent as
`specs/backlog/028-monitoring-and-alerting` and `specs/done/019-env-separation`
(ops-facing specs that mix small scripts/docs deliverables with a runbook).

## Clarifications

### Session 2026-08-02

- Q: How should the operator connect from the Mac to control/monitor the
  always-on Windows box? → A: **Tailscale** (free "Personal" plan — up to 6
  users, unlimited user-owned devices, no cost for this 2-device use case).
  It gives the Windows box a stable private hostname reachable from the Mac
  regardless of network/NAT/dynamic IP, with no port-forwarding and no
  public exposure of the machine.
- Q: What's the actual control mechanism on top of Tailscale (Tailscale
  itself is just network connectivity, not a control channel)? → A: **SSH**
  (Windows' built-in OpenSSH Server optional feature) for running the
  existing `run_denidin.sh`/`run_morning_mcp.sh`/`scripts/run_all.sh`
  wrapper scripts and other host-level commands unchanged, on the Windows
  box, as if sitting at it. For lower-friction routine log-reading/status
  checks, the Mac's own `docker` CLI can additionally be pointed at the
  Windows box's Docker daemon over SSH via a **Docker remote context**
  (`docker context create ... --docker "host=ssh://user@host"`), so `docker
  compose logs -f` / `docker ps` run "as if local" without opening an
  interactive shell. The wrapper scripts themselves (which read/write
  `shared/active_env.json`, `docker-compose.<env>.local.yml`, etc. via
  relative host paths) must still be *executed on the Windows box itself*
  (over SSH) rather than invoked remotely via a Docker context — a Docker
  context only redirects the `docker`/`docker compose` calls themselves,
  not the surrounding bash logic.
- Q: How should production credentials be stored/accessed on the Windows
  box, given the existing "config files only" rule? → A: **Keep the
  existing pattern, unchanged.** `config/config.prod.json` is created once
  by hand on the Windows box (copied from `creds/DeniDin Prod Creds.txt`,
  the existing source of truth), gitignored exactly as it is on every other
  clone today. No OS-level secrets store, no third-party secrets manager —
  those would be new external dependencies this project doesn't have today,
  and the existing pattern already satisfies CONSTITUTION.md §I.
- Q: Should this feature's monitoring/log-access scope build on or merge
  with `specs/backlog/028-monitoring-and-alerting`? → A: **Keep separate.**
  028 is about the shared health-check logic + `run_all.sh`'s startup
  sanity gate (what counts as "healthy," used by both `watchdog.py` and a
  one-shot CLI). This feature is about *where* production physically runs
  and *how an operator reaches it* — orthogonal concerns. This feature
  consumes 028's health-check CLI if/when 028 ships, but does not depend on
  it being done first (falls back to plain `docker ps` / `docker compose
  logs` / reading `logs/prod/` in the meantime).
- Q (self-identified during drafting, documented as an assumption rather
  than asked to the user, since it has an obvious default): does moving
  production to the Windows box risk it running in **two places at once**
  (old host + Windows), given `scripts/env_lock.sh`'s multi-clone lock
  (`shared/active_env.json` + `env_lock.sh`) only coordinates clones that
  share one canonical `shared_state_dir` **on the same machine** — it has
  no cross-machine awareness at all. → **Assumption**: this feature is a
  one-time cutover. The runbook's last step is confirming
  `scripts/killall_containers.sh` has been run on the *old* production
  host and that host is no longer expected to run `prod` again, before
  `prod` is started on the Windows box. The two hosts are never intended to
  both run `prod` concurrently, but nothing in the existing lock mechanism
  can *enforce* that across two separate machines — this is a documented
  operator responsibility, not something this feature builds tooling to
  prevent (see Edge Cases and Out of Scope).
- Q: How should SSH into the Windows box be authenticated? → A: **Key-based
  auth only.** An SSH key pair is generated on the Mac, its public key is
  installed on the Windows box's OpenSSH Server (`authorized_keys`), and
  password authentication is disabled in `sshd_config`. Chosen over
  password auth because the box is reachable 24/7 and the setup cost (one
  `ssh-keygen` + copying a public key) is trivial next to the exposure a
  guessable/reused password would leave open on an always-on machine.
- Q: Windows' OpenSSH Server listens on all network interfaces by default
  once enabled (LAN and Tailscale alike) — should access be restricted to
  the Tailscale interface only? → A: **Yes.** The Windows Firewall rule for
  `sshd` is scoped to the Tailscale network interface only, so the SSH port
  is unreachable from the LAN (or anywhere else) even by another device on
  the same WiFi — closing off that attack surface entirely, on top of (not
  instead of) key-based auth from the previous clarification.
- Q: Should containers auto-start after a host reboot after all (reversing
  the original draft's "out of scope, human must SSH in and restart"
  stance)? → A: **Yes — but via a Windows Scheduled Task that re-invokes
  the existing `scripts/run_all.sh prod` at boot/login, not by changing any
  compose file's `restart:` policy.** Every service in
  `docker-compose.prod.yml` is deliberately pinned to `restart: "no"`
  (CLAUDE.md, 2026-07-21 incident hardening) specifically so a container
  `watchdog.py` kills for a real mismatch stays dead instead of Docker
  silently reviving it — changing that policy to get reboot recovery would
  undo that safety property everywhere, not just for the reboot case. A
  Scheduled Task that reruns the full wrapper script instead gets the same
  practical outcome (production comes back up on its own after a reboot)
  through the exact same code path a human running it over SSH would use —
  same `env_lock.sh` checks, same lock-file writes, same everything —
  without touching `restart:` at all.
- Q: Should the runbook include disabling Windows' automatic update
  reboots? → A: **Left open for now** — whether this is even fully
  achievable depends on the Windows edition (Pro/Enterprise has a Group
  Policy for fully-manual, notify-only updates; Home does not, and can only
  be mitigated via update deferral/active-hours/registry settings, not
  guaranteed prevention). Revisit once the actual laptop (and its edition)
  is in hand — tracked as an open item for `plan.md`/the runbook rather than
  a blocking spec ambiguity, since a reasonable interim default exists
  either way (see FR2).
- Q: Should the "always on" configuration also cover the laptop's lid being
  closed, given it's a laptop (not a desktop) and will be permanently on AC
  power? → A: **Yes.** Windows' default closed-lid behavior is to sleep
  regardless of other power settings — the runbook must explicitly set
  "when I close the lid: do nothing" for the *plugged-in* power profile,
  and disable network-adapter power management ("allow the computer to
  turn off this device to save power" unchecked for the Wi-Fi/Ethernet
  adapter) so networking — and therefore Tailscale reachability — survives
  the lid closing. Battery-power lid behavior is not addressed, since the
  laptop stays permanently plugged in.
- Q: Docker Desktop has historically needed an active, logged-in Windows
  user session to run — a boot-time Scheduled Task alone won't help if
  nobody's there to log in after a reboot. Should the runbook set up
  Windows auto-logon, and if so, under which account? → A: **Auto-logon
  under the operator's own existing admin account** (not a separate
  dedicated account — a second account would make manual/day-to-day
  management harder for one person, per the operator). That account
  already has **no password set**, which conveniently means Windows'
  built-in auto-logon toggle (`netplwiz` → uncheck "users must enter a
  username and password") needs no `DefaultPassword` registry value at
  all — the account already boots straight to desktop. Noted as a residual
  fact rather than a new risk this feature introduces: the passwordless
  local account governs *physical* access to the laptop, which SSH's
  key-based auth (a separate clarification above) and Tailscale's mesh
  don't touch either way — this feature neither improves nor worsens that
  pre-existing condition.

### Session 2026-08-02 (continued — re-established after a conversation loss; corrects FR1/FR3a below)

- Q: Should the Windows box build Docker images itself, the way every
  other clone does (`docker compose build` against a local `git clone`),
  as originally drafted in FR1/FR3a? → A: **No — corrected.** No source
  code and no build tooling on the Windows box at all. Images are built
  **once, on the Mac** (this repo's normal git clone already there), then
  shipped to the Windows box as a pre-built artifact; the box only ever
  runs `docker load` + `docker compose up -d` against images that already
  exist locally on it, never `docker compose build`. This removes the
  Windows box's only real "developer machine" characteristic — it becomes
  a pure runtime target, consistent with the "no code or building on the
  Windows box" framing the operator restated after this session's earlier
  conversation was lost. `docker-compose.prod.yml`'s `build:` context
  section is left completely unchanged (still needed for the Mac's own
  build), since `docker compose up -d` without `--build` never invokes it
  as long as an image matching the compose-generated name/tag
  (`denidin-prod-denidin-app-prod:latest`, etc. — from this file's
  top-level `name: denidin-prod`) is already present, which `docker load`
  guarantees.
- Q: How do the built images — plus everything else the box needs to run
  (compose files, wrapper scripts, non-secret config like
  `runtime_constitution.md`) — actually get from the Mac to the Windows
  box, given there's no `git pull` to bring them in anymore? → A: **A
  single `.tar.gz` artifact, built on the Mac into a new gitignored
  `artifacts/` folder at the repo root, transferred over `scp` on the
  existing Tailscale SSH connection, then extracted into a plain directory
  on the Windows box that is explicitly *not* a git clone.** The artifact
  contains: both images (`docker save`), `docker/docker-compose.prod.yml`,
  a generated no-op `docker/docker-compose.prod.local.yml` stub, a
  generated `config/shared_state.local.json` (this machine's own canonical
  path, same as before), the unmodified wrapper scripts
  (`scripts/run_all.sh`, `stop_all.sh`, `killall_containers.sh`,
  `env_lock.sh`, `apps/*/run_*.sh`, `apps/*/stop_*.sh`), and
  `apps/denidin-app/config/runtime_constitution.md` (git-tracked, hot-reloaded,
  needed on every deploy since it isn't baked into the image). It
  deliberately excludes: `config/config.prod.json`/`apps/*/config/config.prod.json`
  (secrets — created once by hand directly on the box, same as FR6 always
  said, just now explicitly outside the deploy artifact so no secret ever
  transits as a build byproduct), and `apps/*/data`/`apps/*/logs`/`shared/`
  (persistent state — a plain `tar xzf` extraction over an existing
  directory never touches paths absent from the archive, so redeploys
  can't clobber live session/memory data or logs by construction).
  `scripts/windows_prod/build_and_package.sh` (new) produces the artifact;
  `deploy_and_verify.sh` is rewritten to build+package, `scp` it over, then
  SSH in to extract + `docker load` + `docker compose up -d` — no more
  remote `git pull`/`docker compose build`.
- Q: Cross-platform build correctness — the Mac's CPU architecture (Apple
  Silicon/ARM64 vs Intel/x86_64) doesn't necessarily match the Windows
  laptop's (assumed x86_64, per FR1) — a plain `docker compose build` on
  an Apple Silicon Mac produces an ARM64 image that won't run on an x86_64
  Windows box at all. How is this handled? → A: `build_and_package.sh`
  always builds via `docker buildx build --platform linux/amd64` (loaded
  locally with `--load`), regardless of the Mac's own architecture —
  correct and Mac-architecture-agnostic either way, at the one-time cost
  of an emulated (not native) build on an Apple Silicon Mac. If the
  Windows laptop ever turns out to be ARM64 (unlikely, not the case in
  practice for the laptop this feature targets), this platform string
  would need to change — noted as an assumption, not re-verified against
  real Windows-box hardware yet.
- Q: Should the persistent prod data folder (session/ChromaDB long-term
  memory) be reachable from the Mac, not just the Windows box itself? →
  A: **Yes.** It's a singleton that lives only on the Windows box (never
  duplicated, never part of the deploy artifact per the point above), and
  the Mac mounts it locally via **sshfs + macFUSE**
  (`brew install --cask macfuse` — requires a one-time manual macOS
  security approval + reboot for the kernel extension, then
  `brew install gromgit/fuse/sshfs-mac` — note: this formula needs a
  workaround on some Homebrew installs, since its `MacfuseRequirement`
  references a pkgconfig directory that doesn't exist in every Homebrew
  Library version; see quickstart.md §9a) so the operator can inspect or
  back up live production data as an ordinary local folder, without
  SSHing in or writing any new sync/backup tooling. Mounted **read-only**
  (`-o ro`) — nothing in this feature's own scope needs to write to it
  from the Mac.

  **Corrected 2026-08-03, verified end-to-end against the real box**: the
  data folder cannot be mounted directly from the WSL-side deploy
  directory — confirmed Windows' native OpenSSH SFTP server (which sshfs
  rides) cannot traverse into the WSL2 filesystem at all, not via a
  direct UNC path (`\\wsl.localhost\...`) nor an NTFS symlink pointing at
  one (both tested directly against the real box; both failed with
  "not found" even though the target genuinely existed and was readable
  from WSL bash itself). Resolved by relocating the data volume's actual
  storage to a native Windows-side path (e.g.
  `C:\Users\<name>\denidin-prod-data`) via a machine-specific
  `docker-compose.prod.local.yml` override — see FR6a and the Integration
  Contracts section in plan.md for the mechanism. Confirmed working:
  content written on the Windows side is visible through the Mac's
  mount, and a write attempt through the mount correctly fails
  (read-only enforced).

## Functional Requirements

- **FR1**: A documented, repeatable runbook (`quickstart.md`) covers
  one-time Windows-box setup: installing Tailscale and joining the same
  tailnet as the Mac, enabling Windows' OpenSSH Server optional feature and
  configuring it for **key-based auth only** (generate an SSH key pair on
  the Mac, install the public key into the Windows box's
  `authorized_keys`, disable password authentication in `sshd_config`,
  scope the Windows Firewall rule for `sshd` to the Tailscale network
  interface only so it's unreachable from the LAN), installing Docker
  Desktop (with WSL2 backend) purely as a **runtime** — no source code, no
  build tooling, and critically **no `git clone` of this repository on the
  Windows box at all** (corrected 2026-08-02; see Clarifications) —
  creating an empty deploy directory that the first artifact deployment
  (FR3a) populates, and creating the machine's own gitignored
  `config/config.prod.json` (copied by hand from `creds/DeniDin Prod
  Creds.txt`, same as always) directly in that deploy directory ahead of
  the first deploy, since it's deliberately excluded from the deploy
  artifact itself.
- **FR2**: The runbook covers configuring the Windows box, on AC power (the
  laptop stays permanently plugged in), so "always on" holds without
  operator intervention: disabling sleep/hibernate, setting closed-lid
  behavior to "do nothing" (a laptop's default is to sleep on lid-close
  regardless of other power settings, and the box is expected to run
  lid-closed), disabling network-adapter power management so networking
  (and Tailscale reachability) survives the lid closing, Docker Desktop set
  to start on login, and Tailscale set to auto-connect on boot. Windows
  Update's own forced-reboot behavior is left as an open item for
  `plan.md`/the runbook — see Clarifications (depends on the laptop's
  Windows edition, not yet known).
- **FR2a**: A Windows Scheduled Task, configured to run at system boot (or
  user login, whichever proves reliable for an unattended machine —
  determined during planning), re-invokes the existing, unmodified
  `scripts/run_all.sh prod` so production comes back up automatically after
  any host reboot (planned or Windows-Update-forced) without an operator
  needing to notice and SSH in. This does **not** change any compose
  file's `restart:` policy (still `"no"` on every service, per CLAUDE.md's
  2026-07-21 incident hardening) — see Clarifications for why a Scheduled
  Task re-running the full script, rather than a `restart:` policy change,
  is the chosen mechanism.
- **FR2b**: The runbook configures Windows auto-logon (`netplwiz`) under
  the operator's own existing admin account (no separate dedicated
  account), so a logged-in session exists automatically after every boot
  for Docker Desktop and the FR2a Scheduled Task to run in — see
  Clarifications for why a second account was rejected (day-to-day manual
  management would be harder for a single operator) and the pre-existing,
  unrelated fact that this account already has no password.
- **FR3**: An operator can start and stop production
  (`scripts/run_all.sh prod` / `scripts/stop_all.sh prod`) entirely from
  the Mac, by SSHing into the Windows box over the Tailscale hostname and
  running the existing, unmodified wrapper scripts there — no change to
  `run_all.sh`/`stop_all.sh`/`run_denidin.sh`/`run_morning_mcp.sh` or their
  underlying compose files is required by this feature.
- **FR3a**: An operator can deploy a newly merged code change entirely from
  the Mac, with **no code or build step ever touching the Windows box**
  (corrected 2026-08-02; see Clarifications): on the Mac,
  `scripts/windows_prod/build_and_package.sh` builds both prod images
  (`docker buildx build --platform linux/amd64`) against the Mac's own
  already-current `master` checkout, then packages a single `.tar.gz`
  artifact (images + compose files + wrapper scripts + non-secret config —
  never secrets, never `data`/`logs`) into the gitignored `artifacts/`
  folder; `deploy_and_verify.sh` then `scp`s it to the Windows box over the
  existing Tailscale SSH connection and runs the remote extract +
  `docker load` + `docker compose up -d` sequence, followed by an
  automated log smoke-check. This *is* new deploy tooling (unlike the
  original draft's "just run CLAUDE.md's existing steps remotely") —
  necessary because there's no source on the Windows box for "existing
  steps" to run against anymore; the two new scripts are this feature's
  actual deliverable for FR3a.
- **FR4**: An operator can read live and historical container logs
  (`logs/prod/`, `docker compose logs`) from the Mac without opening a
  remote-desktop session — either over the SSH session from FR3, or via a
  Docker remote context (FR5) for lower-friction one-off checks.
- **FR5**: The runbook documents setting up a Docker remote context on the
  Mac (`docker context create <name> --docker
  "host=ssh://<user>@<tailscale-hostname>"`) as an optional convenience for
  routine `docker ps`/`docker compose logs -f`/`docker compose ps` checks
  that don't require running the wrapper scripts themselves.
- **FR6**: Production credentials on the Windows box follow the existing,
  unmodified pattern: `config/config.prod.json` created once by hand from
  `creds/DeniDin Prod Creds.txt`, gitignored, never committed, and
  deliberately outside the FR3a deploy artifact (see Clarifications). No
  new secrets-management tooling (OS credential store, vault, password
  manager CLI) is introduced by this feature.
- **FR6a**: The persistent production data folder (session/ChromaDB
  long-term-memory state, container-mounted at `/app/data`) is a
  singleton that lives only on the Windows box, is never included in a
  deploy artifact (FR3a), and survives every redeploy untouched. It is
  additionally reachable from the Mac as an ordinary local folder via
  **sshfs + macFUSE** (`~/denidin-winprod-data`, mounted read-only by
  default) for inspection and backup, without SSHing in or writing new
  sync/backup tooling. **Corrected 2026-08-03, verified end-to-end
  against the real box**: the data folder's actual storage lives at a
  native Windows-side path (e.g. `C:\Users\<name>\denidin-prod-data`), NOT
  under the WSL-side deploy directory — confirmed Windows' native
  OpenSSH SFTP server (which sshfs rides) cannot traverse into the WSL2
  filesystem at all, so the volume was relocated via a one-time,
  hand-created `docker-compose.prod.local.yml` override (see
  Clarifications) rather than the generated no-op stub every other file
  in that role gets.
- **FR7**: The runbook includes a migration/cutover checklist: verify
  `scripts/killall_containers.sh` has been run on the *previous* production
  host and `prod` is confirmed stopped there, before `scripts/run_all.sh
  prod` is run for the first time on the Windows box — see Edge Cases for
  why this can't be automatically enforced across machines.
- **FR8**: No feature flag — this is infrastructure/operations tooling and
  documentation, not a change to either app's request-handling code path;
  nothing here is gated by `config.feature_flags`.

## Explicitly Out of Scope

- Any change to `apps/denidin-app` or `apps/morning-mcp-app` request-handling
  code, or to `scripts/run_all.sh`/`stop_all.sh`/`env_lock.sh`/`watchdog.py`
  themselves — this feature is entirely about *where* the existing,
  unmodified system runs and *how it's reached*, not what it does.
- Changing any compose file's `restart:` policy to achieve reboot recovery
  — FR2a's Scheduled Task achieves the same outcome without touching that
  deliberate 2026-07-21 hardening (see Clarifications). Note this is a
  narrower exclusion than the original draft's — auto-resume after reboot
  itself is now in scope via FR2a; only the *mechanism* of changing
  `restart:` policy is excluded.
- Guaranteed prevention of Windows Update forced reboots — left open
  pending knowing the laptop's Windows edition (see Clarifications); the
  runbook will document whatever mitigation is achievable for that edition
  once known, not a guarantee.
- Cross-machine enforcement of the "prod runs in exactly one place" rule —
  `env_lock.sh`'s lock is file-based and scoped to clones sharing one
  `shared_state_dir` on a single machine; making it cross-machine-aware
  would require a new shared coordination mechanism (e.g. a lock service
  reachable from both hosts) that doesn't exist today and is not part of
  this ask.
- Remote hard power-cycling of the Windows box if it becomes fully
  unresponsive (SSH itself down) — would require Wake-on-LAN, a smart plug,
  or similar out-of-band hardware, none of which is in scope here.
- OS-level or third-party secrets management (Windows Credential Manager
  integration, 1Password CLI, Vault) — explicitly declined per the
  Clarifications above in favor of the existing config-file pattern.
- `specs/backlog/028-monitoring-and-alerting`'s shared health-check
  logic/`run_all.sh` sanity-gate work — orthogonal, tracked separately.
- Any general-purpose file-sync/backup tooling for the data folder beyond
  the read-only sshfs mount (FR6a) — no scheduled backup job, no
  versioning, no second copy anywhere; the mount is purely a local *view*
  of the one, single-source-of-truth copy that lives on the Windows box.
- A private Docker registry, or pushing images to any registry (Docker
  Hub, GHCR, etc.) — the FR3a artifact transfer is a direct Mac→Windows
  `scp` of a `docker save` tarball, not a registry push/pull; no new
  registry account or infrastructure is introduced.

## Edge Cases

- **Mac sleeps or disconnects while SSHed into the Windows box or tailing
  logs**: no impact on the Windows box or its containers. Containers run
  detached (`docker compose up -d`) under the Windows Docker daemon,
  independent of any client session; only the Mac's SSH session drops,
  reconnectable once the Mac wakes. (Confirmed during spec drafting —
  captured here since it's a natural first question for anyone reading this
  runbook later.)
- **Windows box loses power or reboots unexpectedly** (e.g. Windows
  Update): per FR2/FR2a, Tailscale and Docker Desktop come back on login,
  and the Scheduled Task re-runs `scripts/run_all.sh prod` automatically —
  production is expected to self-recover without operator action. There is
  still no alerting (see 028) if that self-recovery itself fails (e.g. the
  Windows box comes back up but Docker Desktop or the Scheduled Task
  doesn't fire) — an operator would only discover that by noticing
  WhatsApp isn't responding, or by checking in over SSH.
- **Old production host and the Windows box both have `prod` running
  simultaneously** (e.g. cutover step missed): both would be actively
  polling Green API for the same WhatsApp number — a real correctness risk
  the existing single-machine `env_lock.sh` cannot detect across machines.
  Mitigated only by the FR7 runbook checklist, not by tooling — a genuine
  residual risk, documented rather than eliminated (see Out of Scope).
- **Tailscale mesh itself is down/unreachable** (Tailscale's own control
  plane outage, or the Windows box's Tailscale client crashes): the
  operator loses remote control/monitoring/log access until connectivity is
  restored, but production itself is unaffected — the WhatsApp bot's own
  traffic (Green API polling, OpenAI calls, the morning-mcp-app ngrok
  tunnel) does not route through Tailscale at all; Tailscale is purely the
  operator's out-of-band control channel.
- **Mac's sshfs mount (FR6a) is stale or the Mac sleeps while mounted**:
  no impact on the Windows box or the live `data` folder itself — the
  mount is a read-only *view* from the Mac's side. `-o reconnect` handles
  a Mac wake-from-sleep transparently in the common case; if the mount
  ever wedges (a known sshfs/macFUSE failure mode after a long
  disconnect), the fix is unmounting (`umount ~/denidin-winprod-data`) and
  re-mounting — never a reason to touch anything on the Windows box.
- **A deploy (FR3a) is interrupted mid-transfer or mid-extract** (Mac
  sleeps during `scp`, SSH drops during remote extraction): the previous
  deploy's images and containers are untouched and keep running —
  `docker compose up -d` only recreates a container once the *new* image
  has actually finished loading, and a partially-extracted tarball simply
  fails the next step's checks (missing/incomplete files) rather than
  silently running with mixed old/new artifacts. Re-running
  `deploy_and_verify.sh` from the top is safe; it always ships a complete,
  freshly-built artifact rather than resuming a partial one.

## Success Criteria

- **SC1**: After one-time setup, an operator can start, stop, and check the
  status of production, and read both live and historical logs for both
  apps, entirely from the Mac, without opening a remote-desktop session or
  physically touching the Windows box.
- **SC2**: The Windows box remains reachable over Tailscale and continues
  running previously-started containers across the Mac going to sleep,
  disconnecting from the network, or being closed entirely; and across its
  own lid being closed (it runs on permanent AC power, closed-lid, by
  design).
- **SC3**: No production secret is ever committed to git or stored outside
  the existing `config/config.prod.json` gitignored-file pattern already
  used by every other environment/clone in this repo.
- **SC4**: The runbook is followable end-to-end by an operator with no
  prior Windows/Tailscale experience, using only this repo's docs plus
  standard OS-level setup screens (no undocumented manual steps required).
- **SC5**: After a Windows box reboot (planned or update-forced),
  production resumes running on its own — Tailscale, Docker Desktop, and
  both containers are back up — without an operator needing to SSH in and
  manually restart anything.
- **SC6**: An operator can deploy a merged code change entirely from the
  Mac (FR3a) and confirm the new version is actually live by sending a
  real WhatsApp message to the bot and receiving a DeniDin response — the
  definitive end-to-end proof that "control from the Mac" actually reaches
  all the way to a working, user-visible result, not just "containers
  report Up."
- **SC7**: The persistent production data folder is reachable from the Mac
  as an ordinary local folder (FR6a) without SSHing in, and a deploy
  (FR3a) never modifies, duplicates, or loses any of its contents.

## References

- CLAUDE.md's "ONE ENVIRONMENT SET AT A TIME" / "Multi-clone lock" /
  "dev/prod data is also a singleton across clones" sections — the existing
  single-machine coordination mechanism this feature's cutover must respect
  even though it doesn't extend automatic enforcement across machines.
- `scripts/env_lock.sh`, `scripts/killall_containers.sh` — existing
  lock/teardown mechanism referenced by FR7's cutover checklist.
- `specs/done/019-env-separation/quickstart.md` — precedent for a
  runbook-style quickstart doc in this repo's spec format.
- `specs/backlog/028-monitoring-and-alerting` — related but orthogonal
  ops-facing spec; explicitly not merged into this one (see Clarifications).
- `creds/DeniDin Prod Creds.txt` — existing source of truth this feature's
  Windows-box `config/config.prod.json` is copied from, unchanged.
- Docker's `buildx`/`docker save`/`docker load` documentation — the
  cross-platform build (`--platform linux/amd64`) and image-transfer
  mechanism FR3a's `build_and_package.sh`/`deploy_and_verify.sh` are built
  on; all standard Docker CLI functionality, no new tooling.
- macFUSE (`https://osxfuse.github.io`) + `sshfs` — the FR6a data-folder
  mount mechanism; macFUSE requires a one-time manual macOS security
  approval (System Settings → Privacy & Security → allow the system
  extension) and a reboot, documented in `quickstart.md`.
