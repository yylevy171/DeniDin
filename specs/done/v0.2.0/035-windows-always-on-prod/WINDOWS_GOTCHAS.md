# Working with the Windows Box: Gotchas & Findings

A dedicated troubleshooting reference for everything non-obvious discovered
while setting up and operating this feature's Windows always-on production
host (2026-08-03, against the real box). Each item here is explained in
full narrative detail in `spec.md`'s Clarifications, `research.md`'s
Decision entries, and `quickstart.md`'s numbered steps — this file exists
to be **scanned quickly** when something breaks, not read end to end. If
you hit a weird Windows/WSL/SSH/Docker error working on this box, check
here first before re-diagnosing from scratch.

---

## 1. SSH shell routing (the big one)

**Symptom**: `ssh host 'some-bash-command'` either lands in `cmd.exe`
(command literally echoed back, e.g. `echo $0` prints `$0`) or, if
`DefaultShell` is pointed at a WSL wrapper, `sshfs`/`scp` mysteriously
hang or fail with `mount_macfuse: the file system is not available` or
`sftp-server.exe` errors.

**Root cause**: Windows OpenSSH Server defaults to `cmd.exe` for every
session. Pointing `DefaultShell` at a custom WSL-bash wrapper (to get
`ssh host 'bash command'` working) **breaks the SFTP subsystem** —
subsystem launches get routed through the custom shell too, and
`sftp-server.exe` either hangs (bare filename, bash finds it via
interop PATH but stdio doesn't wire up right) or exits instantly with
"command not found" (Windows-style path, bash doesn't understand
`C:/...`) depending on how the `Subsystem sftp` line is spelled.

**Fix in place**: `DefaultShell` is left at its **native default**
(nothing set in the registry). Every script wraps its own remote bash
commands **client-side** instead, via `scripts/windows_prod/_wsl_ssh.sh`'s
`wsl_ssh_run` helper — base64-encodes the command and runs
`wsl.exe -e bash -c "echo <b64> | base64 -d | bash"` over a plain
`cmd.exe`-routed SSH session. Base64 has no shell-special characters at
any layer, so this sidesteps nested cmd.exe/bash quoting entirely (we hit
real, reproducible bugs from naive quoting attempts twice before landing
on this).

**If you need a genuinely new remote bash one-liner**: `source
scripts/windows_prod/_wsl_ssh.sh` then `wsl_ssh_run denidin-winprod
'your command'`. Don't write raw `ssh denidin-winprod 'command'` expecting
bash — that lands in `cmd.exe`.

**Native Windows commands** (not bash) still go through plain
`ssh denidin-winprod "windows command"` unwrapped — e.g.
`verify_reboot_recovery.sh`'s `shutdown /r /t 0`.

## 2. Every native Windows CLI tool needs `.exe` inside the WSL bash session

Once inside `wsl_ssh_run`'s bash session, `powercfg`, `schtasks`, `reg`,
`netsh`, `hostname`, `query`, `tasklist`, `taskkill`, `wevtutil` — all need
an explicit `.exe` suffix to resolve via WSL interop. Bash's PATH search
doesn't do Windows' PATHEXT-style extension-less resolution. `curl` and
`docker` are native Linux binaries inside WSL and need no suffix.

## 3. WSL default distro must be Ubuntu, not `docker-desktop`

Docker Desktop registers its own internal `docker-desktop` distro, which
has **no bash at all**. If it ends up marked as the *default* WSL distro
(check with `wsl -l -v` — `*` marks default), every `wsl.exe -e bash`
invocation with no `-d` flag silently targets the wrong distro, giving
`execvpe(bash) failed: No such file or directory`. Fix:
`wsl.exe --set-default Ubuntu`.

## 4. Docker Desktop's WSL integration is not automatic

Docker Desktop → Settings → Resources → WSL Integration must be
**manually toggled on for the Ubuntu distro** — it's on by default only
for Docker Desktop's own internal distro. Without this: `the 'docker'
command could not be found in this WSL 2 distro`.

## 5. Docker Desktop's own `AutoStart` setting, separately

Even with the above two fixed, Docker Desktop won't launch at logon
unless its own `AutoStart` setting is `true` in
`%APPDATA%\Docker\settings-store.json`. A Windows Run-key entry existing
(`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`) does **not** mean
this is enabled — check/fix the JSON file directly, or use Docker
Desktop's Settings → General → "Start Docker Desktop when you log in".

## 6. A process started over SSH lands in the wrong session (Session 0)

If you manually start a GUI app (e.g. `Docker Desktop.exe`) via an SSH
command, Windows launches it into **Session 0** (the isolated services
session) — it runs and can be functionally reachable (e.g. `docker ps`
works), but has **no visible window or tray icon**, because Session-0
processes are structurally forbidden from showing UI on the real desktop.
This is not a sign anything's broken — it's specific to *how* the process
was started. A real interactive logon (auto-logon, or a Run-key/Startup-
folder launch at that logon) puts it in the correct **Console** session
instead, with normal visible UI. Check via
`tasklist.exe /V | grep <processname>` — the session name column should
say `Console`, not `Services`.

## 7. Task Scheduler is not used for reboot recovery — it never reliably fired

Both an `"At startup"` trigger and (after that failed) an `"At logon"`
trigger were tested against **two separate real reboots**. Neither ever
fired — `schtasks /query` showed the "never ran" placeholder
(`Last Run Time: 30-Nov-99 00:00:00`) both times, even with auto-logon
confirmed genuinely working (`explorer.exe` running in the Console
session) and *other* built-in Windows logon-triggered tasks firing
correctly for the same user in the same boot window (confirmed via the
`Microsoft-Windows-TaskScheduler/Operational` event log — **disabled by
default**, enable with
`wevtutil.exe set-log Microsoft-Windows-TaskScheduler/Operational /enabled:true`
if you want to see this yourself). Root cause not pinned down despite
real investigation.

**Fix in place**: Task Scheduler abandoned entirely for this. A plain
script in the Windows **Startup folder**
(`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\DeniDinProdAutostart.cmd`)
does the job instead — a much older, simpler, decades-proven mechanism
with no trigger-timing behavior to get wrong.

**Also worth knowing**: if you ever create a Scheduled Task by hand via
the GUI anyway, the "Add arguments" field has been observed to **silently
drop the trailing closing quote** on this Windows build. Create tasks via
`schtasks.exe /create` command line instead, and verify with
`schtasks.exe /query /tn <name> /xml` (check the `<Arguments>` value is
properly closed).

## 8. `netplwiz`'s auto-logon checkbox is gone on this Windows build

Recent Windows 11 builds removed the "Users must enter a username and
password to use this computer" checkbox from `netplwiz` entirely (only
"Users"/"Advanced" tabs remain). Set auto-logon directly via registry
instead:
```powershell
reg.exe add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v AutoAdminLogon /t REG_SZ /d 1 /f
reg.exe add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v DefaultUserName /t REG_SZ /d "<username>" /f
reg.exe add "HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon" /v DefaultDomainName /t REG_SZ /d "<computer-name>" /f
```
No `DefaultPassword` needed if the account already has no password.

## 9. Two separate power settings, both needed for "always on"

- **System sleep** (`powercfg /change standby-timeout-ac 0`) — the one
  most guides mention.
- **Display/monitor timeout** — a completely **separate** setting
  (`SUB_VIDEO`/`VIDEOIDLE`) that a screen going black was traced back to
  on this box (found set to 1800s/30min, never touched before). Disable
  with `powercfg /change monitor-timeout-ac 0`. If SSH/Tailscale still
  work but the screen looks "dead," check this before assuming a crash.
- **Lid-close action** is a *third*, separate setting, and on this
  Windows build **isn't exposed via `powercfg` at all** — neither the
  classic `SUB_BUTTONS`/`LIDACTION` alias nor a direct GUID query returns
  anything. Only the modern Settings app (System → Power & battery →
  "Closing the lid will make my PC...") has it. Manual-only, can't be
  scripted/verified via CLI on this build.
- **Network-adapter power management** ("allow the computer to turn off
  this device to save power") turned out to be **not controllable at all**
  on this hardware's current drivers — absent from both Device Manager's
  Power Management tab and the `MSPower_DeviceEnable` WMI class for the
  WiFi/Ethernet devices specifically (present for unrelated devices like
  USB controllers, so the mechanism itself works — these two devices just
  don't implement it). Accepted as a residual risk rather than reinstalling
  vendor drivers for uncertain benefit.

## 10. `tailscale ping`/`tailscale ip` need the real Tailscale hostname, not the SSH alias

`~/.ssh/config`'s `Host` alias (e.g. `denidin-winprod`) is not something
Tailscale knows about — `tailscale ping denidin-winprod` fails with "no
such host". Resolve the actual hostname first:
`ssh -G denidin-winprod | awk '/^hostname /{print $2; exit}'`.

## 11. Docker's SSH URL parser rejects a username containing a space

If the Windows account's username has a space (e.g. `"yaron levi"`),
`docker context create ... --docker "host=ssh://yaron levi@host"` fails
with `remote username contains invalid characters` — **even
percent-encoded**. Fix: point the context at the `~/.ssh/config` alias
itself instead of a spelled-out `user@host`:
`docker context create <name> --docker "host=ssh://<ssh-alias>"` — lets
plain `ssh` resolve `User`/`HostName` from the config file.

## 12. `scp`/SFTP's home directory ≠ bash's home directory

`scp file.txt host:~/name` and bash's `~` are **two different
directories** on this setup: SFTP (a native Windows process) resolves
`~` to the **Windows-side home** (`C:\Users\<name>`), while
`wsl_ssh_run`'s bash session resolves `~` to the **WSL-side home**
(`/home/<wsl-user>`). A file `scp`'d to `~/foo` will not be found by a
subsequent `wsl_ssh_run '... ~/foo ...'` command, and vice versa.

**Bridging when needed**: from within a `wsl_ssh_run` bash session, the
Windows home is reachable at
`$(wslpath -u "$(cmd.exe /c echo %USERPROFILE% | tr -d '\r')")` — resolved
dynamically, not hardcoded (a different Windows account would have a
different path). `deploy_and_verify.sh` uses exactly this to locate an
artifact `scp`'d to the Windows home before extracting it into the
WSL-side deploy directory.

## 13. Windows' native SFTP server cannot reach into the WSL2 filesystem at all

This is the reason the FR6a data-folder sshfs mount had to be redesigned.
**Confirmed two ways, both failed**: a direct UNC path
(`sftp> ls //wsl.localhost/Ubuntu/home/...`) and an NTFS symlink created
specifically to bridge the gap (`mklink /D` pointing at that same UNC
path) — both returned "not found", even though the symlink target
genuinely existed and was readable from WSL bash the whole time. This
isn't a path-syntax issue — `sftp-server.exe` structurally can't resolve
into that filesystem, symlink or not.

**Implication**: anything that needs to be reachable via `sshfs`/`scp`/
`sftp` (not just plain `wsl_ssh_run` bash commands) must live on a
**native Windows-side path** (e.g. `C:\Users\<name>\something`, reachable
from WSL bash too via `/mnt/c/Users/<name>/something`), not purely under
the WSL-side deploy directory. This is why the prod data volume was
relocated via a `docker-compose.prod.local.yml` override — see FR6a in
spec.md.

## 14. A Homebrew tap can reference a pkgconfig path that doesn't exist in your Homebrew version

`gromgit/homebrew-fuse`'s `sshfs-mac` formula failed to build with
`Dependency "fuse3" not found (tried pkg-config and framework)`, even
though macFUSE was installed and `pkg-config --exists fuse3` succeeded
in a normal shell. Cause: the formula's `MacfuseRequirement` adds
`$(brew --repository)/Library/Homebrew/os/mac/pkgconfig/fuse` to
`PKG_CONFIG_PATH` inside Homebrew's sandboxed build environment — and
that directory didn't exist at all in this Homebrew Library version
(only macOS-SDK-numbered pkgconfig subdirs existed). Fixed once with:
```bash
mkdir -p "$(brew --repository)/Library/Homebrew/os/mac/pkgconfig/fuse"
cp /usr/local/lib/pkgconfig/{fuse,fuse3}.pc \
  "$(brew --repository)/Library/Homebrew/os/mac/pkgconfig/fuse/"
```
Not specific to this feature — could recur for any macFUSE-dependent
Homebrew formula on a similar Homebrew install.

## 15. `export -f` + nested `bash -c` is not reliable everywhere

A `check() { ... "$@" ...}` pattern combined with
`bash -c "exported_function args"` silently failed with
`exported_function: command not found` in at least one real execution
environment — `export -f` never actually populated the corresponding
`BASH_FUNC_*` environment variable there (confirmed via `env | grep
BASH_FUNC`, completely absent). `scripts/windows_prod/verify_windows_prod.sh`
now avoids this entirely: every check is a plain named function defined
in the same top-level shell, called directly by `check` — no `export -f`,
no nested `bash -c`, anywhere.
