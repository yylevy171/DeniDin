# Handoff — 2026-07-21 (afternoon)

## State: merged, NOT deployed

PR #116 merged to `master` (commit `978b20d`). **Deploy step was explicitly skipped this session** — `denidin-app-dev`/`morning-mcp-app-dev` are still running the OLD pre-merge image. Next session: `docker compose -f docker-compose.dev.yml build && docker compose -f docker-compose.dev.yml up -d denidin-app-dev morning-mcp-app-dev` to actually pick up everything below.

## What merged (PR #116)

Two unrelated pieces of work landed in one PR/commit (should have been split — didn't happen this session):

### 1. bugfix-013 (partial — NOT closed, still open)
- Date-narrowing half: fixed. `runtime_constitution.md` strengthened with an explicit "omit from_date/to_date entirely if no date is mentioned" example. Two new expensive E2E tests added to `test_denidin_morning_mcp_e2e.py` as standing regression tripwires (`test_zehavit_client_name_transcribed_exactly`, `test_no_date_mentioned_omits_date_range`), using the exact real message from the original incident log.
- Name-garbling half: still unresolved, accepted as residual/probabilistic risk. **`specs/bugfixes/bugfix-013-...md` was deliberately NOT moved to `specs/done/bugfixes/`** — bug is not closed.
- Also fixed live in the same test file: the `list_invoices` "one specific day" test's Hebrew wording (מיום → ביום) — was genuinely ambiguous, not a real bug.

### 2. P0: environment isolation (the bigger piece)
Triggered by discovering, mid-session, that `morning-mcp-app-prod` had been left running for ~13 hours under the old "morning-mcp-app has no run-together restriction" policy, and a stale legacy config path (`config.test.json`'s `morning_status_file`, orphaned since the 019-env-separation migration) caused the E2E test suite to silently talk to **real production Green Invoice** instead of the sandbox. Confirmed real invoices were created in prod (#100006–#100011, today's session only — earlier suspected ones from 07-13–07-20 were ruled out by timeline, prod container didn't exist yet). **User needs to verify/cancel those on the Morning site if not already done.**

Fixes landed:
- `CLAUDE.md`: new top-of-file rule — **at most one full environment set (dev OR prod, never both) may run, ever, for either app.** Old "morning-mcp-app has no restriction" language corrected everywhere it appeared (docker-compose comments too).
- `killall_containers.sh` (repo root) — tears down every container in every env, resets `shared/active_env.json` to null. Verified live.
- `shared/active_env.json` (gitignored runtime state) — single shared source of truth for which env is active. `run_denidin.sh`/`run_morning_mcp.sh` write it on start.
- `watchdog.py` (new, one per app) — now each container's actual PID 1 (Dockerfile CMD / docker-entrypoint.sh changed). Spawns the real app as a child process; every 30s checks its own `config.environment` against `shared/active_env.json`. `morning-mcp-app`'s watchdog checks both internally (`localhost/health`, now returns JSON with `environment`) and externally over its live ngrok tunnel. On mismatch: kills the app subprocess, does NOT respawn, container stays `Up` (no zombie restart loop) until a human runs `killall_containers.sh` and restarts explicitly. **Verified live**: forced a real mismatch, watched it kill cleanly.
- `restart: "no"` on every service in both compose files (was `unless-stopped`) — required for the above to actually stick.
- `environment` field added to both apps' config schema/dataclass/every config file (dev/prod/test/example).
- Config cleanup, same session: merged each app's dev+prod example templates into one `config.example.json`; scrubbed all real credentials out of every config file (moved to two new gitignored root files: `DeniDin Dev Creds.txt`, `DeniDin Prod Creds.txt`); deleted the stale unused `config/config.json` in both apps and fixed the ~10 test files that still read it directly (would have crashed or silently started skipping).

## Current runtime state

**Everything is torn down.** `./killall_containers.sh` was run at the very end of this session — no containers running in any environment, `shared/active_env.json` is `null`. Next session starts from a completely clean slate.

## Suggested next steps

1. **Deploy**: build + start whichever environment is needed (`./apps/denidin-app/run_denidin.sh dev` + `./apps/morning-mcp-app/run_morning_mcp.sh dev`, or `prod`) to actually run the merged code (this hasn't been deployed anywhere yet).
2. **Restore `denidin-app`'s real Green API credentials** for whichever env you start, from `DeniDin Dev Creds.txt`/`DeniDin Prod Creds.txt` (currently placeholders from the credential-scrub step) — it will crash-loop (403 from Green API) without them.
3. **Verify/cancel the 6 real production invoices** created today (#100006–#100011) on the Morning site, if not already done.
4. **bugfix-013 is now closed** (2026-07-21) — name-garbling half accepted as residual/non-reproducible model risk (human decision), no follow-up feature spec opened. Spec moved to `specs/not_reproducible/bugfixes/`.
5. Consider splitting future sessions' commits — bugfix-013 and the P0 env-isolation work should probably have been two separate PRs; they got bundled together here under time pressure.
