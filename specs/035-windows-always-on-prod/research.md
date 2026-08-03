# Research: Windows Always-On Production Host

**Feature ID**: 035-windows-always-on-prod
**Created**: August 2, 2026

All substantive research and decision-making for this feature happened
interactively during `/speckit.specify` and `/speckit.clarify` (see
`spec.md`'s Clarifications section for the full record, including the
reasoning behind each choice) rather than as a separate desk-research pass
— this document consolidates those decisions into the
Decision/Rationale/Alternatives format Phase 0 expects, for anyone
reading the plan without wanting to re-read the full clarification
transcript.

---

### Decision: Remote connectivity — Tailscale

**Rationale**: Free "Personal" plan (6 users, unlimited user-owned
devices) comfortably covers a 2-device setup at no cost; gives the Windows
box a stable private hostname reachable regardless of NAT/dynamic IP, with
no port-forwarding or public exposure.

**Alternatives considered**: Plain SSH over an existing VPN/LAN (rejected —
still needs *some* mesh/VPN underneath, so doesn't remove a step);
cloud relay / ngrok-style tunnel (rejected — exposes the control surface
publicly through a relay, unlike a private mesh); full RDP (rejected —
heavier, slower for routine ops, and doesn't compose with the Docker
remote-context workflow FR4/FR5 depend on).

### Decision: Control mechanism — SSH (key-based, Tailscale-interface-only) + Docker remote context

**Rationale**: SSH lets the existing, unmodified wrapper scripts
(`run_all.sh`, `stop_all.sh`, etc.) run exactly as they would locally — no
new tooling. Docker remote context adds a lower-friction path for routine
`docker ps`/`logs`/`ps` checks without a full interactive session. Key-based
auth + firewall scoping to the Tailscale interface closes off the two
obvious attack surfaces (weak/reused password; LAN-reachable sshd) an
always-on 24/7 box otherwise carries.

**Alternatives considered**: Password auth (rejected — meaningfully weaker
for a box that's reachable continuously); leaving sshd on all interfaces
(rejected — unnecessary LAN exposure with no offsetting benefit).

**Verified against the real box (2026-08-03)**: Windows' OpenSSH Server
defaults to `cmd.exe` for remote sessions, not bash — required installing
WSL2, explicitly setting Ubuntu (not Docker Desktop's bash-less internal
`docker-desktop` distro) as the default WSL distro, and pointing
`DefaultShell` at a small `.cmd` wrapper that forwards into `wsl.exe -e
bash` correctly (a naive `DefaultShell=wsl.exe` doesn't work — see
quickstart.md §2 for the exact fix and the two dead ends that preceded
it). Also discovered: native Windows CLI tools need an explicit `.exe`
suffix to resolve via WSL interop from this shell, and Docker Desktop's
WSL integration must be manually enabled for the Ubuntu distro
specifically (not automatic). None of this changes the decision above —
SSH + WSL bash is still correct — it just took more setup than
originally scoped.

### Decision: Credentials — unchanged existing pattern

**Rationale**: `config/config.prod.json` created once by hand from
`creds/DeniDin Prod Creds.txt`, gitignored — already satisfies
CONSTITUTION.md §I with zero new tooling.

**Alternatives considered**: Windows Credential Manager integration, a
third-party secrets manager (1Password CLI/Vault) — both rejected as new
external dependencies this project doesn't have today, for a problem the
existing pattern already solves.

### Decision: Reboot recovery — Scheduled Task re-invoking `run_all.sh`, not a `restart:` policy change

**Rationale**: Every compose service is deliberately pinned to `restart:
"no"` (CLAUDE.md, 2026-07-21 incident hardening) so a container
`watchdog.py` kills for a real mismatch stays dead instead of Docker
silently reviving it. A Scheduled Task that reruns the full wrapper script
gets the same practical outcome (production self-recovers after a reboot)
through the exact code path a human would use over SSH, without touching
that safety property.

**Alternatives considered**: Changing `restart:` to `unless-stopped`
(rejected — directly undoes the 2026-07-21 hardening, not just for the
reboot case).

### Decision: Windows auto-logon under the operator's own existing account

**Rationale**: Docker Desktop (and therefore the Scheduled Task's ability
to do anything useful) needs an active, logged-in session — a boot-time
task alone doesn't create one. The operator's own account already has no
password, so enabling `netplwiz`'s "users must enter a username and
password" toggle off requires no `DefaultPassword` registry value at all.
A separate dedicated account was explicitly rejected by the operator as
making day-to-day manual management harder for one person.

**Alternatives considered**: Dedicated service account (rejected per
operator preference); no auto-logon (rejected — breaks FR2a/SC5's "no
operator action needed after reboot" goal entirely, since nothing would
create the session Docker Desktop needs).

### Decision: Lid-close / power settings — explicit "do nothing" + network-adapter power management disabled

**Rationale**: A laptop's default closed-lid behavior is to sleep
regardless of other power settings; since the box is expected to run
lid-closed on permanent AC power, this must be set explicitly, along with
disabling network-adapter power-saving so Tailscale reachability survives
the lid closing.

**Alternatives considered**: None seriously — this is a factual Windows
default that has to be overridden for "always on, lid closed" to hold at
all, not a judgment call with competing options.

**Verified against the real box (2026-08-03)**: sleep timeout (T2.2) sets
and queries cleanly via `powercfg`. Lid-close action does not — this
Windows build doesn't expose it under the classic `SUB_BUTTONS`/`LIDACTION`
power-scheme alias at all (confirmed via both the general scheme dump and
a direct GUID query), only through the modern Settings app (System > Power
& battery), where it was set by hand; downgraded to a manual-only
acceptance check (T2.1). Network-adapter power management (T2.3) turned
out to be **not achievable at all** on this hardware's current drivers —
absent from both Device Manager's Power Management tab and the
`MSPower_DeviceEnable` WMI class for the WiFi/Ethernet devices specifically
(present for unrelated devices like USB controllers, so the WMI class
itself works, these two devices just don't implement it). Operator decision
2026-08-03: accept as a residual risk rather than reinstall vendor drivers
for uncertain benefit — see acceptance-tests.md T2.3.

### Deferred (not a blocking unknown): Windows Update forced-reboot mitigation

**Status**: Intentionally left open per the operator's explicit direction
during `/speckit.clarify` ("not sure, leave it open for now until we
actually start working on the windows machine").

**Why this doesn't block Phase 1/2**: FR2's reboot-recovery mechanism
(FR2a/FR2b) already handles *any* reboot, planned or Windows-Update-forced,
by design — so the rest of the plan doesn't depend on knowing whether
forced reboots can be fully prevented or merely deferred/mitigated. This is
purely about *frequency of an already-handled event*, not a design input
for anything else in this plan.

**What determines the answer, once known**: Windows Pro/Enterprise has a
Group Policy for fully-manual, notify-only updates (no automatic install or
reboot at all). Windows Home has no equivalent — only deferral of feature
updates, widened "active hours", and a registry tweak
(`NoAutoRebootWithLoggedOnUsers`) to avoid rebooting out from under a
logged-in session, none of which *guarantees* prevention for an unattended
machine. `tasks.md`/`quickstart.md` should include a step to check
`winver`/Settings → System → About for the edition once the laptop is in
hand, and apply whichever mitigation that edition actually supports.

---

### Decision (2026-08-02, re-established after a conversation loss — corrects the original FR1/FR3a research below): Build once on the Mac, deploy-only on the Windows box

**Rationale**: Every other clone in this repo builds its own images locally
from its own git checkout — that's the default pattern FR1/FR3a originally
just inherited without questioning it for this feature. But the Windows
box has no reason to carry a full dev toolchain (git, a source checkout,
Docker's build path) just to run two already-known-good images; it only
ever needs to *run* containers. Building once, on the Mac (where this
repo's normal git clone and CI-equivalent build already happen), and
shipping a pre-built artifact removes an entire class of box-side failure
modes (a bad `git pull` merge state, a build that succeeds on the Mac but
fails differently on Windows due to some Windows/WSL2-Docker
peculiarity, disk space consumed by build layers on a box nobody's
routinely maintaining) and keeps the Windows box's own footprint as small
as "Docker Desktop + one deploy directory + two loaded images."

**Mechanism**: `scripts/windows_prod/build_and_package.sh` (Mac-side) runs
`docker compose -f docker/docker-compose.prod.yml -f docker/docker-compose.prod.local.yml
--project-directory . build` via `docker buildx build --platform
linux/amd64` (forced regardless of the Mac's own CPU architecture — see
below), `docker save`s both resulting images plus the non-secret
runtime files (compose files, wrapper scripts, `runtime_constitution.md`,
generated `docker-compose.prod.local.yml`/`shared_state.local.json`
stubs for the box) into one `.tar.gz` under a new gitignored `artifacts/`
folder. `scripts/windows_prod/deploy_and_verify.sh` then `scp`s it to the
box and runs the remote `tar xzf` + `docker load` + `docker compose up
-d` sequence over the same SSH transport FR1/FR3 already established —
no new connectivity mechanism, just a different payload than `git pull`.

**Why this doesn't threaten `docker-compose.prod.yml`'s `build:` section**:
Docker Compose only invokes a service's `build:` context automatically
when the referenced image doesn't already exist locally (or `--build` is
passed explicitly). Since `docker load` guarantees an image with the
exact name/tag Compose expects (from this file's `name: denidin-prod` +
service name) is already present before `docker compose up -d` ever
runs on the Windows box, the `build:` section is simply never reached
there — it stays exactly as-is, still used (for real) by the Mac's own
`build_and_package.sh` run.

**Cross-platform correctness**: A Mac's own architecture (Apple
Silicon/ARM64 vs. Intel/x86_64) has no bearing on what the Windows
laptop needs (assumed x86_64 — the overwhelmingly common case, not yet
verified against the real hardware). `docker buildx build --platform
linux/amd64` forces the correct target architecture regardless of which
Mac chip is actually building, at the cost of running under emulation
(slower, not incorrect) if the Mac itself is Apple Silicon.

**Alternatives considered**: Windows box keeps building locally, as
originally drafted (rejected — reintroduces exactly the box-side
toolchain/failure-mode surface described above, for no benefit once the
"no code on Windows" requirement was restated); a private Docker registry
push/pull instead of direct `scp` transfer (rejected — real infrastructure
this 2-machine setup doesn't need; `scp` over the already-established
Tailscale SSH connection is simpler and has no new account/service to
maintain).

### Decision (2026-08-02, re-established after a conversation loss): Persistent prod data folder — singleton on the Windows box, mounted read-only on the Mac via sshfs + macFUSE

**Rationale**: `apps/denidin-app/data` (session state, ChromaDB long-term
memory) must live in exactly one place — duplicating or syncing it would
risk exactly the kind of split-brain state CLAUDE.md's "dev/prod data is
also a singleton across clones" section already warns about for the
multi-clone case, just one machine over instead of one clone over. Since
the Windows box is now the *only* place `prod` ever runs, its `data`
folder simply **is** the canonical copy — no new coordination mechanism
needed, unlike the existing cross-clone singleton (which needed
`docker-compose.<env>.local.yml` overrides specifically because multiple
clones could equally claim to be canonical). What was missing was a way
for the operator to actually look at or back up that data without SSHing
in every time — solved by mounting it locally on the Mac via `sshfs`
(riding the same key-based SSH connection already established for FR3),
using macFUSE as the macOS kernel-extension layer `sshfs` needs to
present a remote filesystem as a local mount point.

**Mechanism**: `brew install --cask macfuse` (one-time manual macOS
security approval + reboot for the kernel extension — a GUI step, not
scriptable), `brew install gromgit/fuse/sshfs-mac`, then `sshfs
<user>@<tailscale-hostname>:<deploy-dir>/apps/denidin-app/data
~/denidin-winprod-data -o reconnect,ro,volname=denidin-winprod-data`.
Mounted **read-only** by default — nothing in this feature's own scope
needs to write to that folder from the Mac side, and read-only removes
any risk of an accidental Mac-side edit corrupting live session/memory
state.

**Status**: this decision's actual *installation* (macFUSE + `sshfs`) was
in progress when the session that originally made this decision was
interrupted (2026-08-02) — treat it as designed but not yet installed;
`tasks.md` tracks it as a resume-from-here item, not a completed step.

**Alternatives considered**: A scheduled rsync/backup job (rejected — new
tooling and a second copy, exactly what FR6a/Out-of-Scope explicitly
declines); Tailscale's own Taildrive file-sharing feature (considered,
not chosen — sshfs reuses the SSH/key-auth trust relationship FR1 already
established rather than introducing a second, separately-configured
Tailscale feature for the same underlying need); read-write mount
(rejected as the default — no current requirement needs write access from
the Mac, and read-only is strictly safer for a singleton holding live
production state).
