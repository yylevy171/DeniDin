# Quickstart: Windows Always-On Production Host

One-time setup runbook for moving production onto a dedicated Windows
laptop, reachable and fully operable from the Mac afterward. Do these
steps in order — later steps assume earlier ones are done. See `spec.md`
for the reasoning behind each decision, `acceptance-tests.md` for how to
verify each step actually worked, and **`WINDOWS_GOTCHAS.md` for a
quick-scan reference of every non-obvious Windows/WSL/SSH/Docker quirk
found while building this — check there first if something breaks.**

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
   `mkdir ~/denidin-prod` (any name; pass it as `deploy_release.sh`'s
   optional `--remote-deploy-dir` flag if not `denidin-prod`, matching its
   existing default).
4. Directly inside that directory, create two machine-specific files by
   hand — these are excluded from every deploy artifact (see step 9), so
   redeploys never clobber them:
   - `config/config.prod.json` — copy values from `creds/DeniDin Prod
     Creds.txt`. (`apps/denidin-app/config/config.prod.json` and
     `apps/morning-mcp-app/config/config.prod.json`, to be precise — both
     apps' config files, same source.)
   - `docker/docker-compose.prod.local.yml` — **corrected 2026-08-03**:
     this used to be a generated no-op stub, but the data volume needs to
     be redirected to a native Windows-side path (see step 9a — Windows'
     SFTP server can't reach the WSL-side filesystem at all, which is
     what the sshfs mount needs). Create the Windows-side folder first
     (`mkdir "%USERPROFILE%\denidin-prod-data"` in PowerShell, or
     `mkdir "/mnt/c/Users/<name>/denidin-prod-data"` from WSL bash — same
     folder either way), then write:
     ```yaml
     services:
       denidin-app-prod:
         volumes:
           - /mnt/c/Users/<name>/denidin-prod-data:/app/data
     ```
     (Replace `<name>` with your actual Windows username — check via
     `whoami` or the folder that already exists under `/mnt/c/Users/`.)

   `config/shared_state.local.json` is generated once, by hand, the same
   way — it only depends on this deploy directory's own path, which
   doesn't change between deploys, so (2026-08-03 correction) it no
   longer needs regenerating on every deploy the way it used to under the
   retired `build_and_package.sh`/`deploy_and_verify.sh` flow:
   `printf '{"shared_state_dir": "%s/shared"}' "$(pwd)/shared" >
   config/shared_state.local.json` run from inside this deploy directory.
   The wrapper scripts and compose files (`docker/docker-compose.prod.yml`)
   need to exist here too — a one-time `scp` from the Mac (see the
   bootstrap note in step 9), not something any deploy script generates.

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
- **If Home** (this box is confirmed Windows 11 Home, SKU 101 — verified
  2026-08-03 via `(Get-CimInstance Win32_OperatingSystem).Caption`):
  apply via registry over SSH, no GUI/interactive session required —
  ```powershell
  Set-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings' -Name 'ActiveHoursStart' -Value 6 -Type DWord
  Set-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings' -Name 'ActiveHoursEnd' -Value 23 -Type DWord
  Set-ItemProperty -Path 'HKLM:\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings' -Name 'IsActiveHoursEnabled' -Value 1 -Type DWord
  Set-ItemProperty -Path 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate' -Name 'DeferFeatureUpdatesPeriodInDays' -Value 365 -Type DWord
  Set-ItemProperty -Path 'HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate' -Name 'DeferQualityUpdatesPeriodInDays' -Value 4 -Type DWord
  ```
  (create the two key paths with `New-Item -Force` first if they don't
  already exist). Widens the no-forced-reboot active-hours window to 17
  hours, defers feature updates a year, defers quality/security updates
  only 4 days (so security patches still land promptly). This is a
  mitigation, not a guarantee — see `research.md`'s resolved decision.

## 7. Windows box: Startup-folder script for reboot recovery

**Corrected 2026-08-03, superseding an earlier Task Scheduler-based
attempt.** The original design used a `DeniDinProdAutostart` Scheduled
Task (trigger: at startup, then at logon after the first attempt).
**Verified against the real box across two separate real reboots: neither
trigger type ever fired** — `schtasks /query` showed `Last Run Time:
30-Nov-99 00:00:00` (Task Scheduler's "never ran" placeholder) both times,
even once auto-logon was confirmed working (`explorer.exe` running,
Console session) and *other* logon-triggered system tasks fired correctly
for the same user in the same window (confirmed via the
`Microsoft-Windows-TaskScheduler/Operational` event log, which is
disabled by default — enable it with
`wevtutil.exe set-log Microsoft-Windows-TaskScheduler/Operational
/enabled:true` if you want to see this for yourself). The root cause
wasn't pinned down despite real investigation, and continuing to guess at
Task Scheduler internals wasn't a good use of time given it had already
failed twice. **Task Scheduler is not used for this at all anymore.**

Instead: a plain script in the Windows Startup folder
(`shell:startup`, i.e. `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`) —
a much older, simpler, decades-proven mechanism that Windows runs
automatically on every interactive logon, with none of Task Scheduler's
trigger-timing complexity:
```powershell
@'
@echo off
wsl.exe -e bash -c "cd ~/denidin-prod && ./scripts/run_all.sh prod"
'@ | Set-Content -Path "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\DeniDinProdAutostart.cmd" -Encoding ASCII
```
(Adjust `denidin-prod` if you used a different deploy-directory name in
step 3. This only works once at least one deploy from step 9 has
populated that directory — running it before that just fails with "script
not found," which is expected and harmless at this stage.)

**Verify**: the file exists at that path with the exact command above
(including the closing quote — this approach doesn't have the GUI
quote-dropping issue the old Scheduled Task had, since it's created by
direct file write, not through a dialog). `verify_windows_prod.sh`'s T2.6
check now looks for this file instead of a Scheduled Task. The full
end-to-end proof is `scripts/windows_prod/verify_reboot_recovery.sh` —
**run this deliberately, with fresh explicit intent each time, never
routinely** (see that script's own header), and only once a real deploy
exists for it to actually bring back up.

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

## 9. Mac: cut a release and deploy it — then first start

**Retired 2026-08-03**: `scripts/windows_prod/build_and_package.sh` and
`deploy_and_verify.sh` are gone — they rebuilt from source on every
single deploy, which conflicts with the "build once, deploy anywhere"
principle Feature 034's release tooling now implements. Deploying to this
box (or to `dev`, locally) is now always the same two-script flow:

```bash
# From the repo root, on the Mac — cut once (human supplies the exact version, every time):
./scripts/cut_release.sh denidin-app <version> --summary "<text>"
./scripts/cut_release.sh morning-mcp-app <version> --summary "<text>"

# Deploy that same artifact to prod on the Windows box (no rebuild):
./scripts/deploy_release.sh denidin-app prod <version>
./scripts/deploy_release.sh morning-mcp-app prod <version>
```

`cut_release.sh` builds `--platform linux/amd64` (so the result runs
natively on the Windows box's x86_64 regardless of the Mac's own chip)
and saves the image as a durable artifact under
`/Users/yaron/Projects/DeniDin/artifacts/<app>/`. `deploy_release.sh`'s
`prod` path ships that exact artifact to the box over SSH, `docker
load`s it, retags it, and runs `docker compose up -d --no-build` there —
never a rebuild. It does **not** touch `apps/*/config/config.prod.json`
(never part of the artifact) or any of `data`/`logs`/`shared/` on the box.

**One-time bootstrap note**: this flow assumes the box already has
`docker/docker-compose.prod.yml` and the deploy-directory structure from
step 3/4 above (already true for this box as of 2026-08-03). If setting
up a brand-new box from scratch, `scp` `docker/docker-compose.prod.yml`
into the deploy directory by hand once before the first `deploy_release.sh`
call — there's no dedicated bootstrap script for this now; it's a rare,
one-time provisioning action, not part of the ordinary deploy path.

**Verify**: `scripts/windows_prod/verify_windows_prod.sh denidin-winprod`
from the Mac — all checks should now pass, including the deploy-directory
content checks (T1.5+) that couldn't pass in step 3.

## 9a. Mac: mount the Windows box's data folder via sshfs + macFUSE (FR6a)

**Status: done, verified end-to-end against the real box (2026-08-03)**
— content written on the Windows side is visible through the mount, and
a write attempt through the mount correctly fails.

1. `brew install --cask macfuse` — macOS will refuse to load the kernel
   extension until you explicitly approve it: System Settings → Privacy &
   Security → look for a message about a blocked system extension from
   "Benjamin Fleischer" (macFUSE's signer) → Allow, then **reboot the
   Mac** (required for the extension to actually load, not optional).
2. `brew install gromgit/fuse/sshfs-mac` (the maintained Homebrew tap for
   `sshfs` on macOS — the upstream `osxfuse/sshfs` tap is no longer
   maintained). **If this fails to build** with `Dependency "fuse3" not
   found`, this tap's `MacfuseRequirement` references a pkgconfig
   directory that doesn't exist in every Homebrew Library version — fix
   once with:
   ```bash
   mkdir -p "$(brew --repository)/Library/Homebrew/os/mac/pkgconfig/fuse"
   cp /usr/local/lib/pkgconfig/{fuse,fuse3}.pc \
     "$(brew --repository)/Library/Homebrew/os/mac/pkgconfig/fuse/"
   ```
   then retry the `brew install`.
3. **Corrected 2026-08-03**: the data folder is mounted from a native
   Windows-side path (`denidin-prod-data`, directly under the Windows
   account's home — see step 4), **not** the WSL-side deploy directory —
   confirmed Windows' native SFTP server (which sshfs rides) cannot
   traverse into the WSL2 filesystem at all (neither a direct UNC path
   nor an NTFS symlink pointing at one worked, both tested directly).
   Mount, read-only: `scripts/windows_prod/mount_data.sh denidin-winprod`
   (idempotent — a no-op if already mounted; pass a different remote
   folder name as a second argument if you didn't use
   `denidin-prod-data` in step 4). Equivalent to running by hand:
   ```bash
   mkdir -p ~/denidin-winprod-data
   sshfs denidin-winprod:denidin-prod-data \
     ~/denidin-winprod-data \
     -o reconnect,ro,volname=denidin-winprod-data
   ```
4. To unmount: `scripts/windows_prod/unmount_data.sh` (or plain macOS
   `umount ~/denidin-winprod-data` — no special sshfs command needed).

**Verify**: `ls ~/denidin-winprod-data` from the Mac shows the same
contents as `ssh denidin-winprod 'ls "denidin-prod-data"'` (over a plain
SFTP-style listing, not `wsl.exe` — see the note in step 4 about why);
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

# Deploy a new version — cut once, ship the exact same artifact, load, and start on the box.
./scripts/cut_release.sh <app> <version> --summary "<text>"
./scripts/deploy_release.sh <app> prod <version>
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
