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
**In Progress — code and tests exist on this branch (`bugfix/043-health-monitoring-and-auto-restart`),
merged current with master and re-verified passing 2026-09-06. Never had a PR, never merged to
master. No prod wiring (Windows Task Scheduler) or live demo performed yet.**

- Code written and committed 2026-08-26 (`ee252ca`), pushed to origin.
- **2026-09-01**: merged current `master` into the branch — clean, zero conflicts (130 files,
  +9819/-323, all upstream unrelated work). Re-ran every test this branch added against the
  merged result:
  - `apps/denidin-app/tests/unit/test_health_server.py` — 23 passed
  - `apps/morning-mcp-app/tests/unit/test_health_checks.py` + `test_health_endpoint.py` — 16 passed
  - `scripts/health_monitoring/tests/test_prober.py` — 18 passed
  - Full `apps/denidin-app/tests/unit/` — **1254 passed, 0 failed**
  - Full `apps/morning-mcp-app/tests/unit/` — **360 passed, 0 failed**
- **2026-09-06**: merged current `master` into the branch again — this time **NOT** clean. Master
  had moved substantially in the interim (64 commits: all of Feature 070 — the rolling 14-day
  memory window replacing session expiry/cleanup entirely — plus Feature 044 ledger-event
  querying, a v0.5.4-70 release cut). Real 3-way conflicts in `apps/denidin-app/denidin.py`,
  `apps/denidin-app/src/models/config.py`, and `apps/denidin-app/config/config.example.json` —
  all resolved as pure additive merges (this branch's `health_check_port` field/health-server
  startup block kept alongside master's new `logging` field/daily-summary-roll-scheduler block;
  one stale leftover comment referencing Feature 070's now-deleted orphaned-session-recovery code
  was dropped rather than reintroduced). No logic on either side was altered to resolve these —
  confirmed by re-running every test after resolution:
  - Full `apps/denidin-app/tests/unit/` — **1335 passed, 0 failed** (the previous
    session's "1254 passed" count grew with upstream's own new tests; no new failures)
  - Full `apps/morning-mcp-app/tests/unit/` — **371 passed, 0 failed**
  - `scripts/health_monitoring/tests/test_prober.py` — 18 passed
  - Merge commit: `53be8e8`.
- **This spec file itself did not exist until 2026-09-01** — the branch shipped code+tests but
  no spec initially, exactly as its own commit message flagged under "Not yet done."
- Still not done: Windows Task Scheduler wiring for `prober.py` on the real prod box (a real
  environment-affecting change, needs its own explicit approval per CLAUDE.md's "never start an
  environment... without explicit approval" rule — this is system-level scheduling, not just a
  container action, so it likely needs the same care even though it's not literally
  `docker compose up`), and the live dev demo. No PR has ever been opened for this branch's code
  (only for this spec file, tracked separately — see "How this lands" below).

## Familiarization with Feature 068 (webapp) — not merged, reviewed for future-merge impact (2026-09-06)

Per explicit instruction, this session reviewed (but did **not** merge) `origin/feature/068-ledger-ui-and-reports`
— an unmerged branch adding a third app, `apps/webapp/` (a read-only ledger UI, frontend + backend,
containerized, deployed via Cloudflare Tunnel), so that whenever that branch eventually merges to
master, reconciling it against this one is less work. Findings:

- **`scripts/run_all.sh`/`stop_all.sh` on that branch just append a third call** (`apps/webapp/run_webapp.sh`/
  `stop_webapp.sh`) around the existing two — `prober.py`'s **soft-restart** path (which calls
  these two scripts generically, by name, with no knowledge of what they start) will automatically
  restart the webapp too, with zero code changes needed here.
- **Gap**: `prober.py`'s **hard-restart** path (`run_hard_restart`) hardcodes exactly two container
  names (`--denidin-container`/`--morning-container`) and calls `docker restart` on them directly,
  bypassing `run_all.sh`/`stop_all.sh` entirely. Once Feature 068 merges, a hard restart would
  leave the webapp containers untouched. Not fixed here (068 isn't merged yet) — flagged as a
  concrete follow-up task for whoever lands 068 (or a subsequent bugfix-043 increment): either add
  `--webapp-container` args, or have hard-restart delegate to a small script that knows the full
  container set instead of hardcoding two.
- **Coincidental, currently-harmless port-number collision**: Feature 068's `webapp-backend-<env>`
  container listens on port `8100` internally (`BACKEND_UPSTREAM: "webapp-backend-dev:8100"` in its
  `docker-compose.dev.yml`) — the exact same port this bugfix picked for `denidin-app`'s
  `health_check_port`. No actual conflict today (separate containers, separate network
  namespaces, nothing binds both to the same host port), but worth a deliberate check at merge
  time that neither compose file ever host-maps both to `8100` simultaneously.

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

## Additional scope surfaced this session (2026-09-01) — triaged 2026-09-06

Found while restarting real prod for an unrelated reason (stale ledger index — see
`specs/done/065-august-ledger-audit-apply/`) and while restoring the sibling spec above. Both
are the same *class* of problem this bugfix already exists to solve — a piece of external/startup
state that's checked or written once, trusted, and never re-verified — just surfacing in
different places than the ngrok check itself.

**Triage (2026-09-06, explicit human decision)**: item 1 left out of this bugfix entirely (not
understood/wanted as in-scope here); item 2 pulled into this bugfix and implemented same day (see
"Shared ops-scripts bundling" below); item 3 (Feature 068's webapp) deferred — when that branch
lands, its own release/deploy tooling should follow the identical bundling pattern established
here, per explicit user confirmation ("when deploy webapp arrives with 68 - it also does the
same").

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

Item 1 (`deploy_release.sh`'s stale `active_env.json` schema) is explicitly left out of this
bugfix — see triage above.

## Shared ops-scripts bundling (2026-09-06, implements gap #2 above)

Both apps' release artifacts now carry a second tarball, `<app>-v<version>-scripts.tar.gz`,
alongside the existing Docker image tarball — the same host-side ops scripts that drive
restart/recovery on the real prod box (`scripts/run_all.sh`, `stop_all.sh`, `env_lock.sh`,
`killall_containers.sh`, each app's `run_*.sh`/`stop_*.sh`, and `scripts/health_monitoring/
prober.py`), which previously could only ever be manually synced onto `~/denidin-prod` (not a git
checkout — Feature 035) and had already been caught silently stale once (2026-08-31, see gap #2's
original writeup above).

- **Canonical manifest**: `scripts/lib/release_scripts_manifest.sh` — one `RELEASE_SCRIPTS_BUNDLE_FILES`
  array, sourced by both `cut_release.sh` (bundling) and `scripts/lib/unpack_scripts_bundle.sh`
  (verification after extraction), so the two lists can never drift apart.
- **`cut_release.sh`**: refuses to cut (before any side effect) if any manifest file is missing
  from the checkout; builds `<app>-v<version>-scripts.tar.gz` right after the existing `docker
  save` step; records it in the JSON manifest as `"scripts_bundle"`; reverts cleanly (no commit)
  if bundling fails. Symmetric for both apps (`denidin-app` and `morning-mcp-app`) — the manifest
  itself already spans both apps' own `run_*.sh`/`stop_*.sh`, so no app-specific branching was
  needed in `cut_release.sh` itself.
- **`scripts/lib/unpack_scripts_bundle.sh`**: extracts the bundle into a target directory and
  verifies every manifest file actually landed, failing loudly and naming exactly what's missing
  otherwise. Runs identically whether invoked directly (this is how
  `scripts/tests/test_release_scripts_bundle.py` proves the mechanism with no SSH and no real
  infrastructure) or shipped to the box and run there over SSH.
- **`deploy_release.sh`**: the **remote/prod path only** ships the bundle tar + the unpack helper
  + the manifest script to the box (new step R2, pushing the old R2-R8 down to R3-R10) and runs
  the helper there via `remote_run`, then cleans up the shipped files off the box. **The
  local/dev path (and `--local`-forced prod) never unpacks the bundle** — a local deploy already
  runs against this very git checkout, so its ops scripts are current by construction; unpacking
  on top would dirty tracked files for no benefit. **Backward compatible**: a version cut before
  this feature existed simply has no bundle file (`HAVE_SCRIPTS_BUNDLE=0`) — deploying it logs a
  note and skips the unpack rather than failing.
- **Tests**: `scripts/tests/test_release_scripts_bundle.py` (7 tests, all real subprocess calls,
  no mocking) — bundle creation + manifest field, the checkout-missing-a-file refusal, the unpack
  helper's success and two distinct failure modes (incomplete bundle, missing bundle file
  entirely), local deploy never touching tracked files, and the pre-bundle-version backward-compat
  path. `scripts/tests/conftest.py`'s `scratch_repo`/`scratch_deploy_repo` fixtures now stub every
  manifest file (including a full `apps/morning-mcp-app/` stub, previously absent from both
  fixtures) plus a no-op `scripts/env_lock.sh`/local-override compose file, so the new
  `cut_release.sh` precondition is satisfiable without dragging real cross-clone locking into
  these tests. All pre-existing `scripts/tests/`/`scripts/health_monitoring/tests/` tests
  (41 total) re-verified green after this change.
- **Still no automated coverage for the actual remote/SSH ship+unpack steps in
  `deploy_release.sh`** (same gap as the rest of that path, per `test_deploy_release.py`'s own
  docstring) — relies on a manual gate against real infrastructure, same as everything else on
  that path.

## How this branch would land

**2026-09-01 merge trial**: `git merge --no-commit --no-ff origin/master` from the pre-merge tip
(`ee252ca` + the branch's prior catch-up merge) applied **cleanly with zero conflicts** — 130
files changed (+9819/-323), entirely unrelated upstream work. The merge was committed to this
branch (`af889df`).

**2026-09-06 re-merge**: master had moved 64 commits further (Feature 070's full session-model
rearchitecture, Feature 044, a release cut) — this time **3 real conflicts**, all in files this
branch itself touches (`denidin.py`, `models/config.py`, `config.example.json`), all resolved as
pure additive merges with no logic changes on either side (see "Status" above for detail).
Committed as `53be8e8`. This confirms the pattern going forward: this branch **will** need active
reconciliation on every future master merge (it touches `denidin.py`'s `__main__` and
`AppConfiguration`, both high-churn files), not a one-time "applies cleanly forever" guarantee —
whoever lands this next should expect to redo this same 3-conflict resolution if master has moved
again by then. Every test this branch added still passes against the merged result (see Status
above). Whether it's *ready* to merge (spec approval, prod wiring, live demo, the two open-scope
items above, and now the Feature 068 hard-restart gap) is a separate, human decision.

## Verification

- [x] Root cause (same incident as the sibling spec) identified from real prod evidence.
- [x] Code + tests exist on this branch, all passing at commit time (2026-08-26, self-reported).
- [x] Re-verified independently, 2026-09-01, against current master after a clean merge: 23 + 16
      + 18 = 57 branch-specific tests pass; full suites 1254 (denidin-app) + 360 (morning-mcp-app)
      pass, zero failures.
- [x] Branch merged cleanly with master on 2026-09-01; re-merged 2026-09-06 with 3 conflicts,
      resolved additively (no logic changes either side), all tests re-confirmed passing.
- [x] Branch/numbering discrepancy flagged and resolved (this file is canonical).
- [x] Familiarized with unmerged Feature 068 (webapp) for future-merge impact; one real gap
      flagged (hard-restart doesn't yet know about a third app), no functional collision found.
- [ ] Human review/approval of this design as the path forward (never formally requested — no PR
      was ever opened for this branch's code, only for this spec file — see "How this lands").
- [ ] The two additional-scope items above designed and either folded into this bugfix or split
      out, per human decision.
- [ ] Feature 068's hard-restart gap (see above) designed and either folded into this bugfix or
      split out, once 068 actually merges.
- [ ] Windows Task Scheduler wiring for `prober.py` on real prod (needs its own explicit
      approval).
- [ ] Live dev demo of the full probe → soft-restart → hard-restart ladder.
- [ ] Live re-verification against a real reboot/restart of `morning-mcp-app-prod` that actually
      loses the original ngrok race (not yet observed since the incident itself).
