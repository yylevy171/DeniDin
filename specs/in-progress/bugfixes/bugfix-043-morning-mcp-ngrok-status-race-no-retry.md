# Bugfix Spec: Morning MCP ngrok-status handshake race — no retry, permanent false "not running"

## Bug ID
bugfix-043-morning-mcp-ngrok-status-race-no-retry

## Title
`morning-mcp-app`'s container entrypoint checks ngrok's local API for the tunnel's public URL
**exactly once**, `sleep 2` after launching the tunnel. If the tunnel hasn't finished
establishing at that moment, the single check comes back empty and the shared status file is
left reporting `status: "not running"` **permanently** — nothing ever re-checks it. This is a
**real production incident**: after an unattended Windows Update reboot of the prod host,
`denidin-app-prod` silently ran for hours with no Morning invoicing tools attached, even though
the ngrok tunnel and MCP server were both healthy the entire time.

## Priority
**P0** — real, client-facing production outage (Morning invoicing tools silently unavailable),
and the failure mode recurs on every future restart/reboot of `morning-mcp-app` until fixed.

## Status
**Fix implemented and unit-tested on this branch (bugfix/043-morning-mcp-ngrok-status-race-no-retry).**
Mitigated live in prod via a human-approved restart before this root-cause fix existed — see
"Mitigation Applied" below. Awaiting human review/approval of this spec + fix per Bug-Driven
Development (METHODOLOGY.md §VII).

## Date Opened
2026-08-25

## Reported By
yaronlev171 — surfaced as "seems like no morning connectivity" in production; root-caused live
during the same session, then explicitly directed to be filed as a bugfix and fixed immediately
("we need to solve it NOW").

## Affected Area
- `apps/morning-mcp-app/docker-entrypoint.sh` — the one-shot ngrok public-URL fetch (root cause)
- `apps/morning-mcp-app/src/denidin_mcp_morning/status_writer.py` — the status file this feeds
  (unaffected by this bug itself, but is the mechanism whose correctness depends on the fix)
- `apps/denidin-app/src/handlers/morning_mcp_locator.py` — the consumer that read the stale file
  and correctly, but silently, degraded to "proceed without invoicing tools"

---

## Root Cause

`docker-entrypoint.sh`, prior to this fix:

```bash
# Give ngrok a moment to establish the tunnel, then print the
# assigned public URL for operator convenience (best-effort; if it
# fails, the server still starts normally below).
sleep 2
PUBLIC_URL=$(python3 -c "
import json, urllib.request
try:
    with urllib.request.urlopen('http://127.0.0.1:4040/api/tunnels', timeout=5) as resp:
        data = json.load(resp)
    print(data['tunnels'][0]['public_url'])
except Exception:
    print('')
" 2>/dev/null) || PUBLIC_URL=""
if [[ "$PUBLIC_URL" == https://* ]]; then
    write_status_running "$PUBLIC_URL"
fi
```

`write_status_not_running` is called unconditionally at the top of the script, before any tunnel
attempt (the documented "safe default" for every failure path). `write_status_running` is only
ever reached if that single check, 2 seconds after launch, already returns a URL. If ngrok hasn't
finished establishing the tunnel session yet — which the real incident shows can take several
more seconds — the check fails once, and the status file is left at `"not running"` forever, with
no other code path that ever corrects it.

## Evidence (real, from prod — 2026-08-25)

**Trigger — an unattended, planned Windows Update reboot**, confirmed from the Windows Event Log
on the prod host (`denidin-winprod`, read via `wevtutil.exe qe System`):

```
Event ID 1074, 2026-08-24T23:29:04 Israel time
Source: MoUsoCoreWorker.exe (Windows Update Orchestrator), on behalf of NT AUTHORITY\SYSTEM
Reason: Operating System: Service pack (Planned)
Shutdown Type: restart

Event ID 109, 2026-08-24T23:29:13 Israel time
Source: Microsoft-Windows-Kernel-Power
Action: Power Action Reboot / Reason: Kernel API   (clean, planned — not a crash)
```
System boot time back up: `2026-08-24T23:29:25` Israel time. (The same box took an identical
Windows-Update-triggered reboot on 2026-08-13 at 02:28 — this is not a one-off.)

**Container recovery worked correctly** (Feature 035's own scope — confirmed via
`docker inspect`, both containers `RestartCount=0`, `Status=running`, started cleanly a few
minutes after the reboot, no crash-loop):
```
morning-mcp-app-prod: StartedAt=2026-08-24T20:34:49Z  (23:34:49 Israel time)
denidin-app-prod:     StartedAt=2026-08-24T20:33:31Z  (23:33:31 Israel time)
```

**The one-shot check failed, exactly as the code predicts** —
`morning-mcp-app-prod`'s own container log:
```
Starting ngrok tunnel (free tier, random URL)...
Could not fetch ngrok public URL yet (check /app/logs/ngrok.log)
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

**But the tunnel itself came up fine, just a few seconds later** — `/app/logs/ngrok.log`:
```
t=2026-08-24T20:35:29+0000 lvl=info msg="starting web service" obj=web addr=127.0.0.1:4040
t=2026-08-24T20:35:36+0000 lvl=info msg="client session established" obj=tunnels.session
t=2026-08-24T20:35:37+0000 lvl=info msg="started tunnel" ... url=https://zookeeper-gutter-hatchling.ngrok-free.dev
```

**Result: `denidin-app-prod` read the stale status file on every single turn for hours**,
degrading gracefully but silently — real client-facing impact, no alert, discovered only because
a human happened to ask:
```
2026-08-25 09:22:27+0300 - src.handlers.morning_mcp_locator - WARNING - Morning MCP server
  reports status='not running' (not 'running'): /app/mcp-status/morning_mcp_status.prod.json
2026-08-25 09:22:27+0300 - src.handlers.ai_handler - WARNING - Morning MCP server unavailable -
  proceeding without invoicing tools
```
(Repeated identically at 09:24:20, 09:25:10, 09:26:47, 09:29:52 — every single conversational
turn that reached `AIHandler`, for at least the ~7 minutes of logs sampled, and in reality for
the full ~10 hours between the reboot and the human-approved restart.)

## Mitigation Applied (already done, live in prod, before this fix)

With explicit human approval, both prod containers were restarted via the box's own deploy-dir
scripts over SSH (`./denidin-prod/scripts/stop_all.sh prod` then `./denidin-prod/scripts/run_all.sh prod`),
**not** `scripts/deploy_release.sh` (no version change — this was a plain restart). Verified after:
- Status file: `{"status": "running", "server_url": "https://zookeeper-gutter-hatchling.ngrok-free.dev/mcp", ...}`
- External reachability from the Mac: `HTTP 401` on the public ngrok URL (auth-required response
  — confirms the tunnel is live and routing, not a connection failure)
- `verify_windows_prod.sh denidin-winprod`: 20/20 checks pass

**This mitigation does not close the incident** — the race condition is still live in the code
and will recur on the next reboot/restart until the fix below ships. Per the new
METHODOLOGY.md §XXII (added as part of this same incident response), a restart is mitigation,
never closure.

## Fix

Extracted the one-shot inline-python check into a proper, unit-tested, bounded-retry poller —
`apps/morning-mcp-app/src/denidin_mcp_morning/ngrok_discovery.py`, `fetch_ngrok_public_url()`:
polls ngrok's local API every 1.5s for up to 30s (both configurable), returning as soon as a
tunnel is reported, or `None` if the budget is exhausted — never raises, never hangs container
startup indefinitely. `docker-entrypoint.sh` now calls this instead of `sleep 2` + one inline
`urllib` check.

This directly implements CONSTITUTION.md §XVIII (added in this same incident response):
startup-time external dependency handshakes must poll with bounded retry, never check once and
silently give up.

## Test Coverage (new)

`apps/morning-mcp-app/tests/unit/test_ngrok_discovery.py` — real HTTP calls to a local fixture
server standing in for ngrok's own local agent API (no mocking of internal code, per CONSTITUTION
§V's "local HTTP fixture servers" guidance):
1. `test_fetch_ngrok_public_url_succeeds_immediately_when_tunnel_already_up` — the common/fast
   case still works.
2. `test_fetch_ngrok_public_url_retries_until_tunnel_establishes` — **reproduces the actual
   incident**: the API is reachable but reports zero tunnels for the first 3 checks (tunnel
   session still establishing), then succeeds on the 4th. Was the one scenario the old code could
   never survive; passes now.
3. `test_fetch_ngrok_public_url_gives_up_after_budget_exhausted_returns_none` — confirms the
   retry is bounded, not unbounded (must not hang startup forever either).
4. `test_fetch_ngrok_public_url_returns_none_when_api_unreachable` — the other real failure mode
   (nothing listening on the port yet at all).

All 4 new tests pass; full `apps/morning-mcp-app` unit suite (300 tests) passes unchanged.
`bash -n docker-entrypoint.sh` confirms no syntax error in the edited script.

## Verification

- [x] Root cause identified from real prod evidence (Windows Event Log, container logs, ngrok
      log, status file, denidin-app-prod warnings) — no assumption, all directly observed.
- [x] Fix implemented, isolated to the one-shot check (`ngrok_discovery.py` + entrypoint call
      site) — no other behavior changed.
- [x] New unit tests reproduce the exact failure shape and pass against the fix.
- [x] Full existing unit suite still green (300 passed).
- [ ] Human approval of this spec (Bug-Driven Development gate).
- [ ] Live re-verification on a real reboot/restart of `morning-mcp-app-prod` — not yet performed
      as part of this fix (the live mitigation restart happened *before* this code fix existed
      and does not exercise it); the next real or intentional restart of `morning-mcp-app` in any
      environment will be the first live confirmation of the fix.
