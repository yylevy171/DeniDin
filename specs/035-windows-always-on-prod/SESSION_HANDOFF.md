# Session Handoff — 035-windows-always-on-prod

**Written**: 2026-08-03, right before a Mac restart (needed to finish loading
the macFUSE kernel extension). This is a scratch recovery doc, not a formal
SpecKit artifact — read this first in a fresh session to pick up exactly
where things left off, then delete it once Phase 8b (below) is confirmed
working and this doc's content has been folded into `tasks.md`/`quickstart.md`
properly (it already mostly has been — this is a safety net, not the primary
record).

## Repo/branch state

- Branch: `035-windows-always-on-prod` (uncommitted — nothing has been
  committed/pushed for this feature yet).
- Uncommitted changes: `.gitignore` (added `/artifacts/`),
  `apps/denidin-app/config/config.example.json` (operator tweaked
  `max_retries` 3→1, harmless, matches real dev/prod values), new
  `scripts/windows_prod/*.sh` (7 scripts), new
  `specs/035-windows-always-on-prod/` (full spec set, already substantially
  rewritten this session for two corrections — see below).
- All of `spec.md`/`plan.md`/`research.md`/`user-stories.md`/`quickstart.md`/
  `acceptance-tests.md`/`tasks.md` are up to date with everything below —
  this handoff doc summarizes, it doesn't introduce anything not already
  written there.

## The two big corrections already fully worked into the spec (before this session)

1. **Build once on the Mac, deploy-only on Windows** — no source code, no
   build tooling, ever touches the Windows box. `build_and_package.sh`
   builds+packages on the Mac into `artifacts/*.tar.gz`; `deploy_and_verify.sh`
   ships it and does remote `docker load` + `docker compose up -d` only.
2. **Persistent data folder accessible from the Mac** via sshfs+macFUSE,
   read-only, at `~/denidin-winprod-data`.

## What's actually been verified against the real Windows box (this session)

**Windows box**: Tailscale-only hostname `yaronlaptop.tail274e9b.ts.net`.
Windows account: `Yaron Levi` (display name has a space — causes several of
the gotchas below). WSL username: `yaron_levi` (no space, deliberately).
Deploy directory: `~/denidin-prod` (i.e. `/home/yaron_levi/denidin-prod` on
the box — **not** `/mnt/c/...`).

**Mac**: SSH alias `denidin-winprod` in `~/.ssh/config`, key
`~/.ssh/denidin_winprod_ed25519`. Docker context `denidin-winprod` created.
⚠️ **This Mac's actual local Docker context is `colima`, not `default`** —
`quickstart.md`'s "switch back to default" line is wrong for this specific
machine; use `docker context use colima` here instead. Not yet fixed in the
docs — fix if you touch that section next.

### Real gotchas discovered and already fixed (all documented in quickstart.md/research.md/tasks.md with full detail — this is just the index)

1. **SSH lands in `cmd.exe` by default, not bash.** Fixed via: install
   WSL2 (`wsl --install`), confirm/set **Ubuntu** as the *default* WSL
   distro (`wsl --set-default Ubuntu` — Docker Desktop's own internal
   `docker-desktop` distro has no bash and can end up default instead),
   then point OpenSSH's `DefaultShell` at a wrapper script:
   ```
   C:\wsl-ssh-shell.cmd containing:
     @echo off
     wsl.exe -e bash %*
   ```
   (two earlier attempts failed: pointing `DefaultShell` straight at
   `wsl.exe` — fails, `-c` not a valid `wsl.exe` flag; and a wrapper that
   re-wrapped `%*` in its own quotes — corrupts argument boundaries. The
   version above, forwarding `%*` untouched, is the one that works.)
2. **Every native Windows CLI tool needs `.exe`** to resolve via WSL
   interop from this shell (`powercfg.exe`, `schtasks.exe`, `reg.exe`,
   `netsh.exe` — `curl`/`docker` are native Linux binaries, no suffix
   needed).
3. **Docker Desktop's WSL integration must be manually enabled** for
   Ubuntu specifically (Settings → Resources → WSL Integration) — not
   automatic.
4. **`netplwiz`'s auto-logon checkbox is gone** on this Windows build. Set
   directly via registry instead (`AutoAdminLogon`/`DefaultUserName`/
   `DefaultDomainName` under `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon`).
   Already done and verified on the real box.
5. **Task Scheduler GUI silently drops the closing quote** in the "Add
   arguments" field. Created via `schtasks.exe /create` command line
   instead — already done, verified via `/xml` export that the quote is
   correctly closed this time. Task name `DeniDinProdAutostart`, trigger
   "At startup", action `wsl.exe -e bash -c "cd ~/denidin-prod && ./scripts/run_all.sh prod"`.
6. **Docker's SSH URL parser rejects a username containing a space**
   (`"yaron levi"`) even percent-encoded. Fixed by pointing the Docker
   context at the `~/.ssh/config` alias itself (`host=ssh://denidin-winprod`)
   instead of a spelled-out `user@host` — lets plain `ssh` resolve
   User/HostName. `tail_logs.sh` already does this correctly.
7. **Lid-close action isn't exposed via `powercfg` at all** on this
   Windows build (confirmed via both the general scheme dump and a direct
   GUID query) — only through the modern Settings app (System > Power &
   battery). Set there by hand, downgraded to manual-only verification
   (T2.1) — `powercfg` check removed from `verify_windows_prod.sh`.
8. **Network-adapter power management isn't controllable on this
   hardware** — absent from both Device Manager's Power Management tab
   *and* the `MSPower_DeviceEnable` WMI class for the WiFi/Ethernet
   devices specifically (present for unrelated devices like USB
   controllers — so the mechanism works, these two devices just don't
   implement it). **Accepted as a residual risk per operator decision**
   (2026-08-03) rather than reinstalling vendor drivers for uncertain
   benefit. AC-power sleep is already disabled (the primary defense), and
   Tailscale/SSH/sshfs all have their own reconnect logic.
9. **Intermittent Tailscale connectivity blips observed** even with the
   screen on / no full sleep (once genuinely from screensaver-adjacent
   idle, recovered on its own after the operator checked the physical
   machine; a couple of shorter blips mid-session too, also
   self-recovered). Not fully root-caused — kept in mind, not blocking.
10. **`gromgit/homebrew-fuse`'s `sshfs-mac` formula fails to build** on
    this Homebrew installation: its `MacfuseRequirement` tries to add
    `$(brew --repository)/Library/Homebrew/os/mac/pkgconfig/fuse` to
    `PKG_CONFIG_PATH`, but that directory doesn't exist in this Homebrew
    core version at all (only macOS-SDK-numbered subdirs exist under
    `os/mac/pkgconfig/`). Worked around by manually creating that
    directory and copying the real `/usr/local/lib/pkgconfig/{fuse,fuse3}.pc`
    files into it:
    ```bash
    mkdir -p /usr/local/Homebrew/Library/Homebrew/os/mac/pkgconfig/fuse
    cp /usr/local/lib/pkgconfig/fuse3.pc /usr/local/Homebrew/Library/Homebrew/os/mac/pkgconfig/fuse/
    cp /usr/local/lib/pkgconfig/fuse.pc /usr/local/Homebrew/Library/Homebrew/os/mac/pkgconfig/fuse/
    ```
    `sshfs-mac` then built and installed cleanly. **This workaround
    persists on disk** (it's outside the repo, in Homebrew's own
    directory) — no need to redo it after the Mac restart, but worth
    knowing about if Homebrew itself ever gets reinstalled/reset.

## Exactly where things stood the moment this doc was written

- ✅ Tailscale, SSH+WSL+key-auth+firewall, Docker Desktop+WSL integration,
  deploy directory, both `config.prod.json` files created (secrets **not
  yet fully filled in** — operator doing this at their own pace).
- ✅ Power settings: sleep=never, lid-close=do nothing (manual-verify
  only), network-adapter power mgmt = accepted residual risk.
- ✅ Auto-logon (registry), Scheduled Task (recreated with fixed quoting).
- ✅ Docker remote context `denidin-winprod` created and reachable.
- ✅ `sshfs`/macFUSE installed (with the Homebrew workaround above) —
  **macFUSE's system extension was just approved in Privacy & Security,
  Mac restart pending to finish loading it.**
- ❌ **Not yet done**: the actual sshfs mount (blocked on the pending Mac
  restart — retry immediately after reboot, see below). First real deploy
  (blocked on the operator finishing `config.prod.json` secrets). The
  combined reboot test (auto-logon + Scheduled Task actually firing —
  deferred until a real deploy exists for the task to bring up). Full
  Docker-context log/health verification (nothing running yet to check).

## Immediate next steps after the Mac restart

1. Retry the sshfs mount: `bash scripts/windows_prod/mount_data.sh denidin-winprod`
   — should now succeed (macFUSE extension will be loaded post-restart).
   If it still fails with `mount_macfuse: the file system is not
   available`, check `systemextensionsctl list | grep -i fuse` to confirm
   the extension is actually active.
2. Verify: `ls ~/denidin-winprod-data` should match
   `ssh denidin-winprod 'ls ~/denidin-prod/apps/denidin-app/data'` (both
   likely empty right now — no deploy/data yet — that's fine, just
   confirms the mount itself works).
3. Confirm a write fails (read-only): `touch ~/denidin-winprod-data/test`
   should error.
4. Update `tasks.md` T042–T045 (Phase 8b) to `[x]` once confirmed.
5. Then: continue waiting on the operator's `config.prod.json` secrets: once
   ready, run `scripts/windows_prod/deploy_and_verify.sh denidin-winprod`
   for the first real deploy, then do the combined reboot test
   (`verify_reboot_recovery.sh` — requires fresh explicit approval each
   time, never run it unprompted).
6. Minor cleanup whenever convenient: fix `quickstart.md`'s
   `docker context use default` reference — should be `colima` for this
   specific Mac (see above).
