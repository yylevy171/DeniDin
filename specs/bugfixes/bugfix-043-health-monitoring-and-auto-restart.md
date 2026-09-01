# Bugfix Spec: Health monitoring + auto-restart (canonical bugfix-043)

## Bug ID
bugfix-043 — **this file is the canonical, authoritative bugfix-043**, as of 2026-09-01, per
explicit human direction. See "Branch/numbering discrepancy" below for what that resolves.

## Title
Windows-reboot Morning-connectivity incident (2026-08-24/25 — `morning-mcp-app`'s ngrok tunnel
came back up after a reboot, but the one-shot status check missed it and left
`shared/mcp-status-prod/` stuck reporting `"not running"` for hours, silently). This branch is
the **broad, durable fix** — built per explicit user direction to produce something that "stands
forever and holds up for any quirks real life throws," replacing the original narrow one-shot
patch to just the ngrok check (reverted — see "Branch/numbering discrepancy" below).

## Priority
**P0** — same underlying incident as the narrower spec: real, client-facing production outage,
recurs on every future restart/reboot until a fix lands.

## Status
**Open — code and tests exist on this branch (`bugfix/043-health-monitoring-and-auto-restart`),
merged current with master and re-verified passing 2026-09-01. Never had a PR, never merged to
master. No prod wiring (Windows Task Scheduler) or live demo performed yet.**

- Code written and committed 2026-08-26 (`ee252ca`), pushed to origin.
- **2026-09-01**: this session merged current `master` into the branch — **clean, zero
  conflicts** (130 files, +9819/-323, all upstream unrelated work: ledger/reconciliation/player
  changes, spec reorganizations, releases). Re-ran every test this branch added against the
  merged result:
  - `apps/denidin-app/tests/unit/test_health_server.py` — 23 passed
  - `apps/morning-mcp-app/tests/unit/test_health_checks.py` + `test_health_endpoint.py` — 16 passed
  - `scripts/health_monitoring/tests/test_prober.py` — 18 passed
  - Full `apps/denidin-app/tests/unit/` — **1254 passed, 0 failed** (the commit message's own
    "1 pre-existing unrelated failure" note no longer applies — whatever that was has since been
    fixed or aged out)
  - Full `apps/morning-mcp-app/tests/unit/` — **360 passed, 0 failed**
  - This is a real, fresh, independently-run confirmation as of 2026-09-01, not a repeat of the
    commit message's original claim.
- **This spec file itself did not exist until this session** — the branch shipped code+tests but
  no spec, exactly as its own commit message flagged under "Not yet done."
- Still not done: Windows Task Scheduler wiring for `prober.py` on the real prod box (a real
  environment-affecting change, needs its own explicit approval per CLAUDE.md's "never start an
  environment... without explicit approval" rule — this is system-level scheduling, not just a
  container action, so it likely needs the same care even though it's not literally
  `docker compose up`), and the live dev demo the commit message describes as not yet performed.
  No PR has ever been opened for this branch.

## Branch/numbering discrepancy (flagging explicitly, 2026-09-01)

**Two separate branches both claim bugfix number "043", covering the same real incident with two
different design approaches:**

1. **`bugfix/043-morning-mcp-ngrok-status-race-no-retry`** — the original, narrower attempt:
   extract the ngrok tunnel-URL check into a bounded-retry poller
   (`denidin_mcp_morning.ngrok_discovery.fetch_ngrok_public_url()`). Merged as PR #251, **reverted
   the same day** (PR #254) at explicit human direction — "not the right approach" (the specific
   reasoning was never recorded anywhere retrievable). Its spec had been deleted by the revert;
   restored earlier this session at `specs/bugfixes/bugfix-043-morning-mcp-ngrok-status-race-no-retry.md`
   on that branch, with a note that its scope now overlaps this one.
2. **`bugfix/043-health-monitoring-and-auto-restart`** (this branch/file) — the broader
   replacement, built the very next day (2026-08-26) explicitly *because* the narrow fix was
   rejected. Per its own commit message: "Broad durable fix for the Windows-reboot
   Morning-connectivity incident, replacing the original narrow one-shot-ngrok-check patch
   (reverted, see PR #254) per explicit user direction to build something that 'stands forever
   and holds up for any quirks real life throws.'"

**Resolution (2026-09-01, explicit human direction): this branch/file is the canonical
bugfix-043 going forward.** The other spec is not deleted (it holds real, valuable incident
evidence — Windows Event Log timestamps, container/ngrok/status-file log excerpts, the exact
timeline — that shouldn't be lost) but should be treated as **historical background and a
rejected first attempt**, not the active plan. Anyone continuing this work should start from
*this* file, not that one.

(There is also a third, unrelated stale artifact worth noting so it isn't confused for a fourth
"043": `docs/043-specs-only` and `feature/043-production-data-setup-tooling` are a completely
different, much older Feature 043 — the WhatsApp-export player — sharing the number by
coincidence, already shipped and in `specs/done/v0.5.0/043-production-data-setup-tooling`. Not
part of this incident at all.)

## Affected Area / What's In This Branch

- **`apps/denidin-app/src/services/health_server.py`** (new) — localhost-only
  `ThreadingHTTPServer` on `/health`, checking: OpenAI reachability, WhatsApp
  (`Account.getStateInstance()`), Morning-via-tunnel (a real HTTP call to `morning-mcp-app`'s new
  `/is_alive`), ChromaDB (`.heartbeat()`), and log freshness (a 10-min heartbeat write + mtime
  check). Gated by `config.health_check_port` (`0` = disabled, same convention as
  `accounting_ledger_update_freq`). Started in `__main__` only (never `initialize_app()`, so
  tests never spin up a real server).
- **`apps/morning-mcp-app`**: `src/denidin_mcp_morning/health_checks.py` (new) —
  `check_morning_connectivity`, `check_log_freshness`, heartbeat-thread helpers. `server.py`
  extended: a new unauthenticated, always-200 `/is_alive` (so `denidin-app`'s tunnel check doesn't
  double-hit Morning's own API on every probe) plus a real `/health` wired to a live
  `MorningClient`.
- **`scripts/health_monitoring/prober.py`** (new) — one-shot, externally-scheduled probe-and-
  escalate script. File-based `last_up_time` state only (no daemon, no in-memory state — explicit
  "I DONT WANT A NEW APP FOR THIS" direction at the time). Escalation ladder: <3min stale = no
  action; ≥3min = soft restart (`stop_all.sh` + `run_all.sh` — the well-behaved,
  env-lock-respecting path); ≥10min = hard restart (`docker restart` — blunt, bypasses
  everything, last resort). A first-ever run with no state file yet never escalates on its own.
- Config wiring: `health_check_port` explicit in all 4 `denidin-app` config files (8100 dev/prod,
  0/disabled in test/example).

## Additional scope surfaced this session (2026-09-01) — not yet designed or implemented

Found while restarting real prod for an unrelated reason (stale ledger index — see
`specs/done/065-august-ledger-audit-apply/`) and while restoring the sibling spec above. Both
are the same *class* of problem this bugfix already exists to solve — a piece of external/startup
state that's checked or written once, trusted, and never re-verified — just surfacing in
different places than the ngrok check itself. Recording as scope for whoever designs the next
increment of this branch, not implementing here:

1. **`scripts/deploy_release.sh` writes a stale JSON schema into `shared/active_env.json` on
   every real prod deploy.** Step R6 still writes `{"active_env": "prod", "owner": null, ...}`
   (the pre-2026-08-05 single-scalar shape) instead of the `active_envs` dict shape
   `env_lock.sh`/`watchdog.py` moved to on 2026-08-05. Confirmed live on the box, 2026-08-31.
   `watchdog.py` degrades this safely today (`_read_active_environments()` returns `None` for a
   file with no `active_envs` key, treated as "skip the check," never a false shutdown — so no
   visible outage) — but it means the exact safety net this whole bugfix is about (verifying the
   real external dependency chain, not just "container is up") has been silently non-functional
   for prod deploys since 2026-08-05. Whether `health_server.py`'s `/health` should include a
   check that `shared/active_env.json` is well-formed/current-schema, or whether this is simply a
   `deploy_release.sh` bug to fix directly, is an open design question.
2. **The operational scripts that actually drive restart/recovery on the real prod box
   (`scripts/run_all.sh`, `stop_all.sh`, `env_lock.sh`, `killall_containers.sh`, the per-app
   `run_denidin.sh`/`run_morning_mcp.sh`) are never part of any release and can silently drift
   stale on the box.** `~/denidin-prod` on the Windows box is not even a git checkout — a plain
   directory populated once at Feature 035 setup. `cut_release.sh`/`deploy_release.sh` only ever
   build/ship each app's own Docker image, never these scripts. Confirmed concretely: as of
   2026-08-31, six of these files had drifted stale on the box — `env_lock.sh` was the entire
   pre-2026-08-05 model (old schema, still blocked dev+prod concurrency — a rule lifted weeks
   earlier), `killall_containers.sh` wrote the same old schema, `run_all.sh` started
   `denidin-app-prod` **before** `morning-mcp-app-prod` (the inverse of the 2026-08-07
   dependency-order fix). All manually synced and verified byte-for-byte against master this
   session — but nothing prevents this from happening again. `prober.py`'s soft-restart path
   literally calls these same scripts on the box, so this bugfix's own auto-restart mechanism is
   exactly the thing that would silently execute stale, possibly-wrong recovery logic on the next
   incident. Worth considering whether the prober (or a startup check in the health server) should
   verify these scripts' provenance/version before or as part of using them.

Neither of the above is designed or implemented yet — flagging as scope, per instruction, not
building it out.

## How this branch would land (2026-09-01 merge trial)

`git merge --no-commit --no-ff origin/master` from the pre-merge tip (`ee252ca` + the branch's
prior catch-up merge) applied **cleanly with zero conflicts** — 130 files changed
(+9819/-323), entirely unrelated upstream work (ledger/reconciliation changes, spec
reorganizations, player features, releases up through v0.5.3). No file this branch touches
(`health_server.py`, `health_checks.py`, `server.py`, `prober.py`, the 4 config files,
`denidin.py`, `requirements.txt`, `models/config.py`) was touched by anything upstream in the
intervening 40 commits, so there was nothing to reconcile. The merge was committed to this branch
(`af889df`). Every test this branch added still passes against the merged result (see Status
above) — this branch is mergeable to current master today with no further reconciliation work,
purely on the "does it apply cleanly and still pass" axis. Whether it's *ready* to merge (spec
approval, prod wiring, live demo, the two open-scope items above) is a separate, human decision.

## Verification

- [x] Root cause (same incident as the sibling spec) identified from real prod evidence.
- [x] Code + tests exist on this branch, all passing at commit time (2026-08-26, self-reported).
- [x] Re-verified independently, 2026-09-01, against current master after a clean merge: 23 + 16
      + 18 = 57 branch-specific tests pass; full suites 1254 (denidin-app) + 360 (morning-mcp-app)
      pass, zero failures.
- [x] Branch merges cleanly with current master, no conflicts.
- [x] Branch/numbering discrepancy flagged and resolved (this file is canonical).
- [ ] Human review/approval of this design as the path forward (never formally requested — no PR
      was ever opened for this branch).
- [ ] The two additional-scope items above designed and either folded into this bugfix or split
      out, per human decision.
- [ ] Windows Task Scheduler wiring for `prober.py` on real prod (needs its own explicit
      approval).
- [ ] Live dev demo of the full probe → soft-restart → hard-restart ladder.
- [ ] Live re-verification against a real reboot/restart of `morning-mcp-app-prod` that actually
      loses the original ngrok race (not yet observed since the incident itself).
