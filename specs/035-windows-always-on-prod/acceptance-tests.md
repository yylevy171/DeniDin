# Acceptance Test Plan: Windows Always-On Production Host

**Feature ID**: 035-windows-always-on-prod
**Created**: August 2, 2026
**Updated**: August 2, 2026 (added FR3a deploy tests; dropped 2 manual items per operator review; corrected FR1/FR3a for build-once-on-Mac/deploy-only, added FR6a data-folder mount tests)

Maps every FR/SC/user-story acceptance criterion in `spec.md`/`user-stories.md`
to a concrete, checkable test — tagged **[Automated]** (scripted, run from
the Mac) or **[Manual]** (requires a human, usually because it needs
physical action, a second network vantage point, or touches real
production messaging/billing). Automated checks live in `scripts/windows_prod/`
at the repo root (promoted there from this directory per `plan.md`'s
Project Structure decision); run them from the Mac once the Windows box
exists per `quickstart.md` (they don't exist to run against yet).

Three automated scripts, split by risk:

- **`scripts/windows_prod/build_and_package.sh`** (new, 2026-08-02) —
  Mac-only, builds both prod images (`linux/amd64`, regardless of the
  Mac's own architecture) and packages them plus non-secret runtime files
  into `artifacts/*.tar.gz`. Never touches the Windows box itself — pure
  local build step, safe to run anytime, doesn't change what's running in
  production until `deploy_and_verify.sh` (below) actually ships it.
- **`scripts/windows_prod/verify_windows_prod.sh`** — read-only, non-disruptive. Safe to
  run anytime; checks connectivity, deploy-directory contents, power/reboot-recovery
  configuration, Docker remote context, logs, container uptime, the sshfs
  data mount, and morning-mcp-app's `/health` endpoint.
- **`scripts/windows_prod/deploy_and_verify.sh`** — deploys a new version (FR3a),
  **rewritten 2026-08-02**: calls `build_and_package.sh`, `scp`s the
  resulting artifact to the Windows box, then SSHes in to extract +
  `docker load` + `docker compose up -d`, followed by an automated log
  smoke-check. No `git pull`/`docker compose build` ever runs on the box
  itself anymore. Changes what's running in production, so run it
  deliberately (i.e. when you actually mean to deploy), not as a routine
  check — but this is the feature's whole point, so "deliberately" here
  just means "when you're deploying," not a special approval ceremony.
- **`scripts/windows_prod/verify_reboot_recovery.sh`** — **disruptive**: actually
  reboots the real production Windows box to prove FR2a/FR2b/SC5.
  Requires an explicit confirmation flag and must only be run deliberately
  (e.g. a planned maintenance window) — same discipline this repo already
  applies to `billed`/`expensive` pytest tests. **An AI agent must never
  invoke this script on its own — it restarts real production, which
  CLAUDE.md's "never start an environment without explicit approval" rule
  squarely covers.**

---

## FR1 — one-time setup (Tailscale, SSH, firewall, Docker Desktop, config files)

| ID | Check | Type |
|----|-------|------|
| T1.1 | Tailscale reachable from the Mac (`tailscale ping`) | [Automated] |
| T1.2 | SSH login succeeds with key-based auth, no password prompt | [Automated] |
| T1.3 | `sshd` Windows Firewall rule is scoped to the Tailscale interface | [Automated] (config check only) |
| ~~T1.4~~ | ~~SSH unreachable from a LAN device not on the tailnet~~ | **Dropped** — not required (operator decision, 2026-08-02); T1.3's static config check is considered sufficient |
| T1.5 | Deploy directory exists at the expected path on the box **and is not a git repo** (`.git` absent) | [Automated] — **rewritten 2026-08-02**: originally checked for a git clone; now the box deliberately has no repo at all, so this checks the opposite |
| T1.6 | `config/config.prod.json`, `config/shared_state.local.json`, `docker-compose.prod.local.yml` all present in the deploy directory (the latter two arrive via the FR3a artifact, not manual setup — see T1.7) | [Automated] |
| T1.7 | `config/shared_state.local.json` and `docker-compose.prod.local.yml` match `build_and_package.sh`'s generated templates exactly (proves they came from the artifact, not manual drift) | [Automated] — **rewritten 2026-08-02**: originally checked `git check-ignore`, which no longer applies with no git repo on the box |
| T1.8 | `config/config.prod.json`'s values are real production credentials copied correctly from `creds/DeniDin Prod Creds.txt` (not placeholders, not stale) | [Manual] — verifying secret *values* are correct isn't something a script should do; a human eyeballs this once during setup |

## FR2/FR2a/FR2b — always-on power settings + reboot auto-recovery

| ID | Check | Type |
|----|-------|------|
| T2.1 | AC-power lid-close action = "do nothing" | [Manual] — **rewritten 2026-08-03**: verified against the real box that this setting isn't exposed via `powercfg` at all on this Windows build (neither the classic `SUB_BUTTONS`/`LIDACTION` alias nor a direct GUID query returns it) — only through the modern Settings app (System > Power & battery). Eyeball it there instead. |
| T2.2 | AC-power sleep timeout = never | [Automated] (config check) |
| T2.3 | Network-adapter power management disabled | **Accepted residual risk, not achievable (verified 2026-08-03)** — this Windows box's WiFi/Ethernet adapters don't expose the standard power-management interface at all (absent from Device Manager's Power Management tab *and* from the `MSPower_DeviceEnable` WMI class), on the drivers currently installed. A vendor-driver reinstall might expose it but wasn't pursued (uncertain payoff vs. effort/risk, and Windows Update could just revert it) — operator decision 2026-08-03. Mitigated by AC-power sleep already being disabled (T2.2) and Tailscale/SSH/sshfs's own reconnect logic; not eliminated. |
| T2.4 | Laptop lid physically closed for 10+ minutes: box stays reachable over Tailscale, container uptime unbroken | [Manual] — requires physically closing/reopening the lid, no software equivalent |
| T2.5 | Mac put to sleep for 10+ minutes, then woken: Tailscale reconnects automatically, Windows-side container uptime unaffected | [Manual] — see note below |
| T2.6 | Scheduled Task exists, enabled, configured to run at startup/logon, targets `scripts/run_all.sh prod` | [Automated] (config check) |
| T2.7 | Windows auto-logon configured for the operator's own account | [Automated] (config check) |
| T2.8 | **End-to-end**: reboot the box for real, confirm it comes back logged-in, Docker Desktop starts, the Scheduled Task fires, and both containers are `Up` again — with no operator action | [Automated, disruptive] via `verify_reboot_recovery.sh` — gated, run deliberately only |

> **On T2.5, answering "is production down during this test?"**: **No.**
> Production runs entirely on the Windows box; the Mac is only ever the
> *operator's window into it*. Putting the Mac to sleep doesn't touch the
> Windows box or its containers at all — they keep serving WhatsApp
> traffic the whole time, uninterrupted. What the test actually verifies is
> narrower and purely on the Mac/Tailscale side: that reachability comes
> back cleanly (Tailscale reconnects, SSH/Docker context work again) once
> the Mac wakes — i.e. the *operator* didn't lose anything permanently by
> letting their Mac sleep, not that production survived (it was never at
> risk).

## FR3 — start/stop the existing (already-built) version

| ID | Check | Type |
|----|-------|------|
| T3.1 | `scripts/run_all.sh prod` over SSH starts both containers successfully | [Automated, changes running state — run when you mean to start prod] |
| T3.2 | `scripts/stop_all.sh prod` over SSH stops both containers successfully | [Automated, changes running state — run when you mean to stop prod] |

## FR3a — build & deploy a *new* version, then prove it actually works

**Rewritten 2026-08-02** — the build now happens on the Mac, not the box;
see spec.md/research.md Clarifications for why.

| ID | Check | Type |
|----|-------|------|
| T-D.0 | `build_and_package.sh` produces `linux/amd64` images and a `.tar.gz` under `artifacts/` that contains neither `config.prod.json` nor `data`/`logs`/`shared/` | [Automated] via `build_and_package.sh` |
| T-D.1 | The artifact reaches the box (`scp`) and extracts cleanly into the deploy directory, leaving `data`/`logs`/`shared/active_env.json`/`config.prod.json` byte-for-byte unchanged from before the deploy | [Automated] via `deploy_and_verify.sh` |
| T-D.2 | `docker load` + `docker compose up -d` (with the artifact's own `docker-compose.prod.local.yml`) completes without error and recreates the container(s) with the new image — **never invokes `build:`** | [Automated] via `deploy_and_verify.sh` |
| T-D.3 | Post-deploy logs show a clean startup (no tracebacks/CRITICAL/FATAL in the first ~50 lines) | [Automated] via `deploy_and_verify.sh`, as a smoke-check proxy |
| T-D.4 | **The definitive proof**: send a real WhatsApp message to the bot and receive a DeniDin response reflecting the new code | [Manual] — deliberately not automated: it's the real production number and a real, billed OpenAI call. Scripting it would mean either building a Green-API send-message integration just for this test, or risking an automated process sending unexpected messages through the real bot — disproportionate for something the operator can just as easily do by hand in 30 seconds |

## FR4/FR5 — tailing logs & checking health/uptime from the Mac

| ID | Check | Type |
|----|-------|------|
| T4.1 | Docker remote context created and reachable (`docker context inspect`) | [Automated] |
| T4.2 | `docker compose ps` via the remote context shows both containers, state `running`/`Up`, with nonzero uptime (not `Restarting`/`Exited`) | [Automated] |
| T4.3 | Live logs tail correctly via the remote context (`docker compose logs -f`), historical logs via `--tail` | [Automated] |
| T4.4 | `morning-mcp-app-prod`'s internal `/health` endpoint responds, over SSH (`curl 127.0.0.1:<mapped-port>/health`) | [Automated] — the one real functional health signal that already exists in this codebase (per `watchdog.py`'s own internal check); `denidin-app` has no HTTP endpoint to check, so its "health" is limited to the uptime/state check in T4.2 |
| T4.5 | Switching back to the Mac's local `default` Docker context works cleanly, no leftover confusion between contexts | [Automated] |

## FR6 — credentials pattern

Covered by T1.6–T1.8 and T-D.0 above; no separate test.

## FR6a — persistent data folder, mounted read-only on the Mac (added 2026-08-02)

| ID | Check | Type |
|----|-------|------|
| T-M.1 | macFUSE + `sshfs` installed on the Mac, mount succeeds | [Manual] — macFUSE's security approval + reboot is an unavoidable GUI step, not scriptable |
| T-M.2 | `ls ~/denidin-winprod-data` from the Mac matches `ssh denidin-winprod 'ls ~/denidin-prod/apps/denidin-app/data'` | [Automated] |
| T-M.3 | Writing into the mount fails (read-only) | [Automated] |
| T-M.4 | Mount survives a Mac sleep/wake cycle without manual re-mounting (`-o reconnect`) | [Manual] — same physical-action caveat as T2.5 |
| T-M.5 | `apps/denidin-app/data` is absent from every `build_and_package.sh` artifact (covered by T-D.0) and untouched by every deploy (covered by T-D.1) | Covered by T-D.0/T-D.1 above |

**Status note**: this feature's own sshfs/macFUSE installation was in
progress when an earlier session was interrupted (2026-08-02) — T-M.1–T-M.4
are not yet run against the real box.

## FR7 — migration/cutover checklist

| ID | Check | Type |
|----|-------|------|
| T7.1 | Confirm `scripts/killall_containers.sh` has been run on the *previous* production host and `prod` is stopped there, before first starting `prod` on the Windows box | [Manual] — touches a different machine/clone entirely; per this project's clone-confinement rules, an AI agent working from this clone isn't allowed to inspect or act on that other host anyway |

## Success Criteria

| ID | Check | Type |
|----|-------|------|
| SC1 | Start/stop/status/logs all achievable from the Mac with no remote-desktop session | Covered by T1–T5 above collectively |
| SC2 | Box stays up and reachable through Mac sleep, Mac disconnect, and its own lid closing | T2.4, T2.5 |
| SC3 | No production secret ever committed to git | T-D.0 (artifact excludes secrets) |
| SC4 | Runbook is followable end-to-end by someone with no prior Windows/Tailscale experience | **Dropped** — not required (operator decision, 2026-08-02) |
| SC5 | Production self-recovers after a reboot, no operator action | T2.8 |
| SC6 | Deploy a merged change from the Mac and confirm it's genuinely live via a real WhatsApp round-trip | T-D.0 – T-D.4 |
| SC7 | Persistent data folder reachable from the Mac without SSHing in; never touched by a deploy | T-M.1–T-M.5 |

---

## Manual Test Checklist (for review)

Everything above still tagged **[Manual]**, in one place:

1. **T1.8** — Eyeball that `config/config.prod.json`'s values were copied correctly from `creds/DeniDin Prod Creds.txt` (real values, not leftover placeholders).
2. **T2.4** — Physically close the Windows laptop's lid for 10+ minutes; confirm from the Mac it stays reachable and containers keep running throughout.
3. **T2.5** — Put the Mac to sleep for 10+ minutes, wake it, confirm Tailscale reconnects. (Production itself is never down during this one — see the note above.)
4. **T-D.4** — After deploying, send a real WhatsApp message to the bot and confirm a DeniDin response comes back — the one true end-to-end proof a deploy actually worked.
5. **T7.1** — Confirm the *old* production host has been fully stopped (`scripts/killall_containers.sh`) before cutting over — this is on a different machine/clone this agent cannot and should not touch itself.
6. **T-M.1** — Install macFUSE + `sshfs` on the Mac (one-time security approval + reboot), mount the data folder.
7. **T-M.4** — Sleep/wake the Mac, confirm the sshfs mount survives without manual re-mounting.
8. *(Conditional, once the laptop's Windows edition is known — see spec.md's still-open Windows-edition clarification)*: verify whatever update-reboot mitigation applies for that edition is actually in effect.

Dropped per operator review (2026-08-02): the LAN-unreachability test (T1.4)
and the novice-walkthrough test (SC4) — neither is required.
