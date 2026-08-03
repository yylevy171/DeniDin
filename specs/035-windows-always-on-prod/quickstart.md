# Quickstart: Windows Always-On Production Host

One-time setup runbook for moving production onto a dedicated Windows
laptop, reachable and fully operable from the Mac afterward. Do these
steps in order — later steps assume earlier ones are done. See `spec.md`
for the reasoning behind each decision, `acceptance-tests.md` for how to
verify each step actually worked.

## Prerequisites

- The Windows laptop, permanently on AC power, in its intended physical
  location.
- A Tailscale account (free "Personal" plan is enough — see `spec.md`
  Clarifications).
- This repo cloned on the Mac already, with `scripts/windows_prod/*.sh`
  present (promoted from `specs/035-windows-always-on-prod/scripts/` per
  `plan.md`'s Project Structure decision) and `docker buildx` available
  (bundled with Docker Desktop for Mac by default — nothing extra to
  install for step 9's build).
- `creds/DeniDin Prod Creds.txt` (existing source of truth) available to
  copy from.
- Confirm the Windows laptop's edition (Settings → System → About, or
  `winver`) — determines which Windows-Update mitigation applies in step 6
  (see `research.md`'s deferred decision).
- (For step 9a only, not blocking earlier steps) Homebrew on the Mac, for
  installing macFUSE + `sshfs`.

## 1. Windows box: install Tailscale, join the tailnet

On the Windows laptop: install Tailscale, sign in with the same account
you'll use on the Mac, confirm it shows as connected. Note the machine's
assigned Tailscale hostname (Settings in the Tailscale app, or `tailscale
status` — format is typically `<machine-name>.<tailnet-name>.ts.net`).

On the Mac: install Tailscale if not already present, sign into the same
account, confirm `tailscale status` lists the Windows box.

**Verify**: `tailscale ping <windows-hostname>` from the Mac succeeds.

## 2. Windows box: OpenSSH Server, WSL2, route SSH into WSL bash, key-based auth, firewall scoped to Tailscale

**Rewritten 2026-08-03, verified against the real box.** The original draft
of this section assumed enabling OpenSSH Server was sufficient, and left
WSL2 installation until step 3 (for Docker Desktop). In practice, our
wrapper scripts are bash, and Windows' OpenSSH Server defaults to
`cmd.exe` for remote sessions — **WSL2 has to be installed and OpenSSH
explicitly reconfigured to route into it *before* SSH is usable for
anything this repo needs.** This section now reflects the order that
actually worked, including two real dead ends hit along the way (kept
brief, so you don't have to rediscover them).

1. Settings → Apps → Optional Features → add "OpenSSH Server". Start the
   `sshd` service and set it to start automatically.
2. Install WSL2 (Administrator PowerShell): `wsl --install` — installs
   WSL2 plus Ubuntu by default, and prompts you to create a Linux
   username/password on first launch (this is a separate account from
   your Windows login — pick something without spaces, since `~/.ssh/config`
   and scripts quote your Windows username but nothing downstream expects
   *this* one to need quoting). Requires a reboot.
3. **Confirm Ubuntu is the *default* WSL distro** — this bit us for real:
   Docker Desktop registers its own internal `docker-desktop` distro,
   which has no `bash` at all, and it's easy for that to end up marked
   default instead of Ubuntu. Check with `wsl -l -v` (Administrator
   PowerShell) — the default has a `*` next to it. If it's not Ubuntu:
   ```powershell
   wsl.exe --set-default Ubuntu
   ```
4. **Route OpenSSH sessions into WSL bash.** Pointing `DefaultShell`
   straight at `wsl.exe` does *not* work — OpenSSH invokes
   `<DefaultShell> -c "<command>"`, but `wsl.exe`'s own CLI doesn't accept
   a bare `-c` flag (`Invalid command line argument: -c`), and even with
   that worked around, a naive wrapper that re-wraps the command in an
   extra pair of quotes corrupts the argument boundaries
   (`bash: - : invalid option`). The working fix is a tiny `.cmd` wrapper
   that forwards everything through untouched — in an **Administrator
   PowerShell**:
   ```powershell
   @'
   @echo off
   wsl.exe -e bash %*
   '@ | Set-Content -Path "C:\wsl-ssh-shell.cmd" -Encoding ASCII

   New-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShell -Value "C:\wsl-ssh-shell.cmd" -PropertyType String -Force
   Remove-ItemProperty -Path "HKLM:\SOFTWARE\OpenSSH" -Name DefaultShellCommandOption -ErrorAction SilentlyContinue
   Restart-Service sshd
   ```
   **Side effect worth knowing**: every native Windows CLI tool
   (`powercfg`, `schtasks`, `reg`, `netsh`, ...) needs an explicit `.exe`
   suffix to resolve from inside this WSL bash session via interop — bash's
   PATH search doesn't do Windows' extension-less `PATHEXT` resolution.
   `verify_windows_prod.sh` already accounts for this; keep it in mind for
   any ad-hoc commands you type yourself.
5. On the Mac, generate a key pair if you don't already have one for this
   purpose (`ssh-keygen -t ed25519`), then copy the public key into the
   Windows account's `~/.ssh/authorized_keys` (e.g. via a temporary
   password-based SSH session, or by pasting manually).
6. Edit `C:\ProgramData\ssh\sshd_config` (from a Windows-side editor, or
   `/mnt/c/ProgramData/ssh/sshd_config` from within WSL): set
   `PasswordAuthentication no`, confirm `PubkeyAuthentication yes`. Restart
   the `sshd` service.
7. Windows Firewall: edit the auto-created inbound rule (named
   **"OpenSSH SSH Server (sshd)"** on current Windows builds — note the
   extra "SSH", different from some older docs) to apply only to the
   Tailscale network interface — Windows Defender Firewall with Advanced
   Security → Inbound Rules → find that rule → Properties → Advanced →
   uncheck all profiles except the one Tailscale's virtual adapter uses,
   or scope its `LocalIP` to the box's own Tailscale IP directly (what
   `verify_windows_prod.sh` actually checks for).
8. On the Mac, add a `Host` entry to `~/.ssh/config`:
   ```
   Host denidin-winprod
     HostName <windows-hostname>
     User <your-windows-username>
     IdentityFile ~/.ssh/<your-key>
   ```

**Verify**: `ssh -o BatchMode=yes denidin-winprod 'echo $0; whoami; echo $HOME'`
succeeds with no password prompt, prints `bash`, your WSL username, and
`/home/<wsl-username>` (**not** `/mnt/c/Users/...` — confirms you're in
WSL's native filesystem, not a Windows-drive path). Attempting the same
from a device on the LAN but not on the tailnet should fail to even
connect (optional — dropped as a required test per operator review, see
`acceptance-tests.md`).

## 3. Windows box: install Docker Desktop, enable WSL integration, prepare an empty deploy directory

**Corrected 2026-08-02**: the Windows box does **not** get a `git clone`
of this repository at all — no source code, no build tooling, ever. It's
a pure runtime target; the actual code/config/compose files arrive later
(step 9) as a pre-built artifact from the Mac. See `spec.md`/`research.md`
for why.

1. Install Docker Desktop with the WSL2 backend. (It ships build tooling
   too, but nothing in this runbook ever exercises it on this machine —
   only `docker load`/`docker compose up -d`, never `docker compose
   build`.)
2. **Enable WSL integration for Ubuntu specifically** — not automatic.
   Docker Desktop → Settings → Resources → WSL Integration → toggle on
   for "Ubuntu" (it's on by default only for Docker Desktop's own internal
   `docker-desktop` distro) → Apply & Restart. Without this, `docker`/
   `docker compose` inside your actual WSL session can't reach the daemon
   at all (`the 'docker' command could not be found in this WSL 2 distro`).
3. Create an empty directory under your **WSL home** (`~`, i.e.
   `/home/<wsl-username>` — not a Windows path) to receive deploys — e.g.
   `mkdir ~/denidin-prod` (any name; pass it as `deploy_and_verify.sh`'s
   optional third argument if not `denidin-prod`, matching its existing
   default).
4. Directly inside that directory, create the machine's own secret file by
   hand — this is the **one and only** file the runbook has you create
   manually on the box itself, since it's deliberately excluded from every
   deploy artifact (see step 9):
   - `config/config.prod.json` — copy values from `creds/DeniDin Prod
     Creds.txt`. (`apps/denidin-app/config/config.prod.json` and
     `apps/morning-mcp-app/config/config.prod.json`, to be precise — both
     apps' config files, same source.)

   Everything else (`docker/docker-compose.prod.local.yml`,
   `config/shared_state.local.json`, the wrapper scripts, compose files)
   is generated fresh into every deploy artifact by
   `build_and_package.sh` on the Mac — nothing else to create by hand
   here.

**Verify**: `scripts/windows_prod/verify_windows_prod.sh denidin-winprod`
run from the **repo root** on the Mac — the T1.1–T1.3 connectivity checks
should pass now; T1.5+ (deploy-directory contents) won't pass until after
the first deploy
in step 9.

## 4. Windows box: always-on power settings

On the Windows laptop, in Power Options (for the "Plugged in"/AC profile):
1. Sleep: never.
2. Closed-lid action: do nothing.
3. Device Manager → network adapter(s) (Wi-Fi and/or Ethernet) →
   Properties → Power Management → uncheck "Allow the computer to turn off
   this device to save power".

**Verify**: the T2.1–T2.3 checks in `verify_windows_prod.sh`.

## 5. Windows box: auto-logon under your own account

**Corrected 2026-08-03**: recent Windows 11 builds have **removed**
`netplwiz`'s "Users must enter a username and password to use this
computer" checkbox entirely (confirmed on the real box — only "Users" and
"Advanced" tabs, no such checkbox on either). Set the registry values
directly instead (Administrator PowerShell, or `reg.exe` over SSH — either
works identically):
```powershell
reg.exe add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v AutoAdminLogon /t REG_SZ /d 1 /f
reg.exe add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v DefaultUserName /t REG_SZ /d "<your-windows-username>" /f
reg.exe add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v DefaultDomainName /t REG_SZ /d "<computer-name, from `hostname`>" /f
```
Since this account already has no password, no `DefaultPassword` value is
needed.

**Verify**: `reg.exe query "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v AutoAdminLogon`
shows `1`; the full proof is rebooting the box once and confirming it
boots straight to your desktop with no login prompt (deferred to step 7's
combined reboot test, below).

## 6. Windows box: mitigate forced Windows Update reboots (edition-dependent)

- **If Pro/Enterprise**: `gpedit.msc` → Computer Configuration →
  Administrative Templates → Windows Components → Windows Update →
  configure for notify-before-download-and-install (fully manual).
- **If Home**: Settings → Windows Update → Advanced options: defer feature
  updates as long as offered, widen "active hours" as much as allowed. This
  is a mitigation, not a guarantee — see `research.md`'s deferred decision.

## 7. Windows box: Scheduled Task for reboot recovery

**Corrected 2026-08-03**: the action must invoke `wsl.exe` directly (there's
no "Start in" concept that reaches into WSL — Task Scheduler's own "Start
in" field is a Windows path, and the whole point is running a WSL bash
command; the `cd` happens *inside* the bash invocation instead). Easiest
done via command line, since the Task Scheduler GUI's "Add arguments"
field **silently dropped the trailing closing quote** when typed by hand
(confirmed against the real box — `schtasks /query /xml` showed the
`Arguments` value missing its final `"`; relying on it "probably still
working" via an OS quoting quirk wasn't worth the risk). Create it directly
instead:
```powershell
schtasks.exe /create /tn DeniDinProdAutostart /tr "wsl.exe -e bash -c \"cd ~/denidin-prod && ./scripts/run_all.sh prod\"" /sc onstart /f
```
(Adjust `denidin-prod` if you used a different deploy-directory name in
step 3. This only works once at least one deploy from step 9 has
populated that directory — running it before that just fails with "script
not found," which is expected and harmless at this stage.)

This creates the task to run as whichever Windows account runs the
`schtasks` command (interactive logon, not "whether user is logged on or
not" — matches the requirement that it needs the same session auto-logon
creates, since it ultimately needs Docker Desktop's user-session-bound
daemon already reachable).

**Verify**: `schtasks.exe /query /tn DeniDinProdAutostart /xml` shows the
`Arguments` value with a properly closed trailing quote, `LogonType`
`InteractiveToken`, and a `BootTrigger`. The T2.6 check in
`verify_windows_prod.sh` covers the same thing (T2.7 auto-logon is
[Manual]-only — see step 5's verify note). The full end-to-end proof is
`scripts/windows_prod/verify_reboot_recovery.sh` — **run this
deliberately, with fresh explicit intent each time, never routinely**
(see that script's own header), and only once a real deploy exists for it
to actually bring back up.

## 8. Mac: set up the Docker remote context

**Corrected 2026-08-03**: point this at the `~/.ssh/config` alias itself,
**not** a spelled-out `user@host` — Docker's SSH URL parser rejects a
username containing a space (e.g. `"yaron levi"`) outright, even
percent-encoded (`remote username contains invalid characters`, confirmed
against the real box). Letting plain `ssh <alias>` resolve
`User`/`HostName`/`IdentityFile` from `~/.ssh/config` itself works fine:
```bash
docker context create denidin-winprod --docker "host=ssh://denidin-winprod"
```
(`tail_logs.sh` already does this correctly and creates the context
automatically on first use if it's missing.)

**Verify**: `docker --context denidin-winprod ps` from the Mac (empty list
is fine before any deploy exists); once a deploy exists,
`docker --context denidin-winprod compose -f docker/docker-compose.prod.yml ps`.

## 9. Mac: build, package, and ship the first deploy — then first start

**Corrected 2026-08-02**: this replaces the original "clone + build on the
box" flow entirely. Everything below runs **on the Mac**, against its own
already-up-to-date `master` checkout:

```bash
# From the repo root, on the Mac:
./scripts/windows_prod/deploy_and_verify.sh denidin-winprod
```

This one command does the whole thing: builds both prod images locally
(`docker buildx build --platform linux/amd64`, so the result runs on the
Windows box's x86_64 regardless of the Mac's own chip), packages them plus
the compose files/wrapper scripts/`runtime_constitution.md` into a
`.tar.gz` under the repo's gitignored `artifacts/` folder, `scp`s it to
the Windows box's deploy directory (step 3), extracts it there, `docker
load`s both images, and runs `docker compose up -d`. It does **not**
overwrite `apps/*/config/config.prod.json` (deliberately excluded from
the artifact) or any of `data`/`logs`/`shared/` (never included, so a
plain `tar xzf` simply never touches those paths).

**Verify**: `scripts/windows_prod/verify_windows_prod.sh denidin-winprod`
from the Mac — all checks should now pass, including the deploy-directory
content checks (T1.5+) that couldn't pass in step 3.

## 9a. Mac: mount the Windows box's data folder via sshfs + macFUSE (FR6a)

**Status**: this step's own installation was in progress when an earlier
session working on this feature was interrupted (2026-08-02) — pick up
from wherever that install actually got to, rather than assuming a clean
start.

1. `brew install --cask macfuse` — macOS will refuse to load the kernel
   extension until you explicitly approve it: System Settings → Privacy &
   Security → look for a message about a blocked system extension from
   "Benjamin Fleischer" (macFUSE's signer) → Allow, then **reboot the
   Mac** (required for the extension to actually load, not optional).
2. `brew install gromgit/fuse/sshfs-mac` (the maintained Homebrew tap for
   `sshfs` on macOS — the upstream `osxfuse/sshfs` tap is no longer
   maintained).
3. Mount, read-only, over the same Tailscale SSH connection already set
   up (step 2): `scripts/windows_prod/mount_data.sh denidin-winprod`
   (idempotent — a no-op if already mounted; pass a different
   deploy-directory name as a second argument if you didn't use
   `denidin-prod` in step 3). Equivalent to running by hand:
   ```bash
   mkdir -p ~/denidin-winprod-data
   sshfs denidin-winprod:denidin-prod/apps/denidin-app/data \
     ~/denidin-winprod-data \
     -o reconnect,ro,volname=denidin-winprod-data
   ```
4. To unmount: `scripts/windows_prod/unmount_data.sh` (or plain macOS
   `umount ~/denidin-winprod-data` — no special sshfs command needed).

**Verify**: `ls ~/denidin-winprod-data` from the Mac shows the same
contents as `ssh denidin-winprod 'ls ~/denidin-prod/apps/denidin-app/data'`;
attempting to write a file into the mount fails (read-only, by design).

## 10. Cutover checklist (one-time, migration only)

Before step 9 above, on whichever host currently runs production (**not**
this Windows box, and not something this agent/session can check on your
behalf — see `spec.md`'s clone-confinement note in FR7): confirm
`scripts/killall_containers.sh` has been run there and `prod` is stopped.
The two hosts must never both run `prod` at once (spec.md Edge Cases).

## Day-to-day operation, once set up

```bash
# Start / stop (existing wrapper scripts, unmodified, in the deploy directory)
ssh denidin-winprod './denidin-prod/scripts/run_all.sh prod'
ssh denidin-winprod './denidin-prod/scripts/stop_all.sh prod'

# Deploy a new version — builds on the Mac, ships, loads, and starts on the box.
# `git pull` on the Mac first, same as any other clone's normal workflow.
scripts/windows_prod/deploy_and_verify.sh denidin-winprod
# ...then send a real WhatsApp message and confirm a DeniDin response (T-D.4, manual by design)

# Tail logs (creates the Docker remote context automatically on first use)
scripts/windows_prod/tail_logs.sh denidin-winprod                     # denidin-app-prod, default
scripts/windows_prod/tail_logs.sh denidin-winprod morning-mcp-app-prod

# Check status/health
scripts/windows_prod/verify_windows_prod.sh denidin-winprod

# Browse/back up live production data, read-only (mount once per Mac session/reboot; see step 9a)
scripts/windows_prod/mount_data.sh denidin-winprod    # idempotent - no-op if already mounted
ls ~/denidin-winprod-data
scripts/windows_prod/unmount_data.sh                  # when done, optional
```

No remote-desktop session, no physically touching the Windows box, for any
of the above.
