# bugfix-076: denidin-app health server starts last + deploy scripts' false-positive verification

**Status**: Done - fixed, live-verified in dev (health server bind time dropped from ~3m23s to
~18s, real /health check confirmed `status: "ok"`), merging to master via haleluya
(2026-09-07).

## Root cause (Bug-Driven Development)

Live prod incident, 2026-09-07, immediately after deploying v0.6.0 for both apps via
`scripts/deploy_release.sh prod 0.6.0`:

1. `denidin.py`'s `__main__` block started its localhost-only `/health` server LAST among a
   block of startup work - AFTER the reminder-delivery, accounting-reconciliation, and
   daily-summary-roll startup sweeps. The accounting-reconciliation sweep (Feature 025) makes a
   real, synchronous OpenAI Responses API call (with Morning MCP tools attached) before
   returning. Measured live: from watchdog spawning `denidin.py` (`10:46:28` UTC) to the health
   server actually binding its port (`10:49:51` UTC) was **~3m23s** - `SessionManager`/
   `LedgerEventManager` init (~37s, indexing 775 ledger events) plus the reconciliation sweep's
   OpenAI round-trip (~69s). During that entire window, denidin-app's health port had nothing
   listening on it at all - every connection attempt got `Connection refused`/`Connection reset`.
2. `scripts/deploy_release.sh`'s (and `scripts/deploy_release_single.sh`'s) final verification
   step for denidin-app was `docker logs --tail 20 | grep "[vVERSION]"` - a log line that prints
   in the first second of `denidin.py`'s startup, long before its health server binds. This grep
   passed almost instantly, so both deploy scripts reported "confirmed live" - and denidin-app
   was actually unreachable for the remainder of that ~3m23s window with nothing watching for
   it. (`morning-mcp-app`'s own verification already did a real `/health` poll, unaffected.)

Both were found and confirmed via direct evidence (verify.log entries, live curl to the health
port, `docker compose logs --timestamps`) - not inference - while investigating a v0.6.0 prod
deploy that the user was independently watching in `verify.log`.

## Fix

1. `apps/denidin-app/denidin.py`: moved the `/health` server + heartbeat-thread startup to run
   FIRST among the `__main__` startup block, immediately after `initialize_app()` returns -
   before the reminder/accounting-reconciliation/daily-roll startup sweeps. It only depends on
   `ai_client`/`live_bot.api`/`denidin.config.mcp`/`denidin.memory_manager`, all already
   available at that point, so this costs nothing and closes the gap at its source.
2. New `scripts/lib/deploy_final_health_check.sh`, sourced by both `scripts/deploy_release.sh`
   and `scripts/deploy_release_single.sh`: replaces the log-grep-based "final check" with a real
   `/health` poll via `scripts/health_monitoring/verify.py` (the same single source of truth
   `scripts/run_all_and_verify_healthy.sh`'s own post-start polling already uses - real
   `status=="ok"` body check, not just HTTP 200), with a 300s grace period (matching
   `run_all_and_verify_healthy.sh`'s own `GRACE_SECONDS`). The old log-grep is kept as a
   separate, fast "the right image actually loaded" check, run before the real health poll -
   this file only replaces the health half of the old combined check.
3. Verified `apps/morning-mcp-app/src/denidin_mcp_morning/server.py`'s `main()` already mounts
   `/health` into the ASGI app before `uvicorn.run()` is called, with nothing heavy running
   before that - no change needed there.

## Test-gap analysis / verification

- `scripts/tests/test_deploy_release.py`'s `scratch_deploy_repo` fixture previously had
  denidin-app's scratch container deliberately NOT serve real `/health` (only morning-mcp-app
  did), with an explicit "harmless, denidin-app is always seen unhealthy here" comment - that
  carve-out stopped being true once the real check started exercising denidin-app too. Fixed:
  denidin-app's scratch container now also serves real `/health` via the same helper
  morning-mcp-app already used.
- `DEPLOY_HEALTH_GRACE_SECONDS`/`DEPLOY_HEALTH_POLL_INTERVAL` env-var overrides added (test-only
  seam) so the scratch suite doesn't have to wait out the real 300s default.
- Full `scripts/tests/` suite (23 tests: `test_deploy_release.py`, `test_cut_release.py`,
  `test_release_scripts_bundle.py`) green after the fix.
- No unit test covers `denidin.py`'s `__main__` startup ordering directly (only
  `initialize_app()` is exercised by the test harness, and the moved block lives in `__main__`
  itself) - this fix was verified against the real prod incident instead (see above).

## Not yet deployed

This fix has not been deployed anywhere yet - deploying it (dev, prod, or both) is a separate,
explicit human decision, per CLAUDE.md's environment-start/release rules.
