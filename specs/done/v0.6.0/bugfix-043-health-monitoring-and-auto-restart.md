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
**Done - Merged to master (PR #284).** Windows Task Scheduler wiring live on real prod, live
restart-loop root cause found and fixed, live-verified in both dev and prod at v0.5.4-b43v5
(2026-09-07).

- **2026-09-07: real prod incident, root-caused, fixed, and verified live — this is the actual
  end-to-end proof this bugfix exists to provide.** Full detail in "2026-09-07: live prod incident
  and fix" below. Summary: the Windows Task Scheduler wiring for `prober.py` (last remaining open
  item from 2026-09-06) was completed and deployed; a real live incident surfaced almost
  immediately (the prober's own restart-loop kept re-triggering before the app finished booting,
  plus HTTP-200-only health checks masking real failures) and was root-caused, fixed
  (`run_all_and_verify_healthy.sh` blocks until real JSON-body health is confirmed or a 5-minute
  grace expires; `verify.py` parses the real `status` field instead of trusting HTTP 200 alone;
  every check attempt is now logged to `logs/health_monitoring/<env>/verify.log`), and verified
  live in both `dev` and `prod`. A **second, independent** incident was found and root-caused
  during this same work: two overlapping/interrupted single-app `deploy_release.sh` calls for the
  same app left prod's containers down AND its health-monitoring schedule disabled for ~41
  minutes, undetected, because the very mechanism that would have caught it had itself been
  disabled by the first call's `stop_env.sh` and never re-enabled by either interrupted call. Fixed
  by splitting `cut_release.sh`/`deploy_release.sh` into single-app (`*_single.sh`, unchanged
  logic) and all-apps (one shared stop/start cycle instead of one per app, eliminating the
  interference window) variants — see "cut/deploy release script split" below. Both apps now
  confirmed live on `v0.5.4-b43v5` in `dev` and `prod`.

- **2026-09-06 (same day, later): admin stop/start + deploy-race redesign.** A design review
  surfaced that the original "prober skips if the env is intentionally down" proposal relied on a
  separately-maintained flag file — exactly the class of bug that caused this bugfix's own
  original incident. Replaced with: the prober's own OS-level schedule registration IS the
  on/off signal, driven directly by two new human-facing entry points, `scripts/stop_env.sh`/
  `scripts/run_env.sh` (see "Shared ops-scripts bundling" section below for what ships them to
  prod). Full detail in the new "Admin-initiated stop/start" and "Deploy race with the prober"
  sections below. All new/changed code re-verified: 61/61 `scripts/` tests passing.

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

## Admin-initiated stop/start (2026-09-06)

**Problem surfaced during design review**: could an admin's deliberate decision to take `dev` or
`prod` down (for any reason, at any time) be confused with a real outage, and get "helpfully"
fought by the prober's own auto-restart? A first proposal — have the prober check a persisted
"intentionally down" flag before escalating — was explicitly rejected: relying on a
separately-maintained flag that has to be kept correct by hand is exactly the class of bug that
caused this bugfix's own original incident (a one-shot check nobody re-verified). The approved
design instead ties the prober's own on/off state directly to the same two actions an admin
already uses to stop/start an environment:

- **`scripts/stop_env.sh <env>`** — the ONE sanctioned way to stop an environment now. Order
  matters: (1) disable the prober's OS-level schedule for `<env>` first, so it can't race with
  what follows; (2) archive the prober's state file (`prober.py --archive-state` — renamed with a
  `_stopped_<timestamp>` suffix, never silently deleted, so the last-known-up history survives);
  (3) `stop_all.sh <env> -force`.
- **`scripts/run_env.sh <env>`** — the ONE sanctioned way to start an environment now. It
  (re-)enables the prober's schedule (idempotent) and triggers one immediate probe — and
  deliberately does **not** call `run_all.sh` itself. The probe sees no state file (archived, or a
  genuinely fresh install) → `decide_action` returns a new `"bootstrap"` action (approved change
  to previously-documented behavior — a missing baseline used to mean "do nothing"; now it means
  "start it now via the proper channel", functionally identical to `"soft"`) → the prober itself
  calls `run_all.sh`. This means run_env.sh's own bring-up code path is exercised on **every**
  kind of start — fresh install, admin-requested, crash recovery, reboot recovery alike — not
  just during a rare real crash, which is exactly the confidence a health-monitoring mechanism
  needs to be trustworthy.
- **"No per-app games"**: both scripts operate on the whole environment (both apps together),
  matching the prober's own existing behavior — stopping/starting either app's deploy briefly
  stops/starts both (see "Deploy race with the prober" below for where this matters again).
- New supporting scripts: `scripts/health_monitoring/prober_paths.sh` (shared argument
  resolution — ports/container names/state+log paths derived from this repo's own config, never
  duplicated as separate literals), `run_prober_for_env.sh` (the actual scheduled runner),
  `register_prober_schedule.sh` (platform dispatch: a real macOS LaunchAgent, load/unload/trigger
  via `launchctl`, fully tested against real launchd with safe throwaway labels; a Windows
  Scheduled Task via `schtasks.exe`/`wsl.exe` interop for prod, no automated coverage — same as
  every other real-prod-only path in this repo, relies on a manual gate).
- **Bug fix found along the way**: `prober_paths.sh`'s container-name resolution was originally
  hardcoded to `"denidin-<env>-..."` — the real repo's own compose project name. Since a
  scratch/test environment deliberately uses a *different* project name (so it can never collide
  with a real dev/prod on the same machine), a hardcoded prefix would have made the prober target
  the wrong (potentially real) container the moment it ran against anything but the real repo.
  Fixed to derive the project name from the compose file's own `name:` field, the same way
  `deploy_release.sh` already does for its `PROJECT_NAME`.
- All 5 new/changed scripts added to the release-scripts bundle manifest so prod actually
  receives them.
- Tests: `scripts/health_monitoring/tests/test_prober.py` (+8: `archive_state_file`, the
  `bootstrap` decision, the `--archive-state` CLI mode), `test_env_scripts.py` (+12: real
  `prober_paths.sh` resolution, `run_prober_for_env.sh` argument construction, real macOS
  LaunchAgent enable/disable/trigger-once against real `launchd`, and `stop_env.sh`/`run_env.sh`
  call ordering via stubbed sibling scripts).

## Deploy race with the prober (2026-09-06)

**Problem surfaced by explicit user question**: `deploy_release.sh` talked to `docker compose`/
`docker load`/`docker tag` directly — a THIRD path (alongside a human and the prober's own
schedule) that could touch containers, with no coordination against the prober's independently
scheduled health checks. A deploy's own container swap landing mid-way through the prober's
escalation window could get fought by an unrelated "restart it" tick, or leave the prober
monitoring a stale state after the deploy finished.

**Fix**: both the local/dev path and the remote/prod path now go through the same two sanctioned
entry points above, never `docker compose up/stop` directly:

1. `stop_env.sh <env>` — disables the prober, archives its state, stops both apps.
2. Load the new artifact, retag it (must happen before step 3, so the freshly-tagged `:latest`
   image is what `run_all.sh` picks up).
3. `run_env.sh <env>` — re-enables the prober and triggers one probe, which itself calls
   `run_all.sh` via the `bootstrap` action.
4. Poll until the container is actually running, then run the existing health/version
   verification unchanged.

Because `stop_env.sh`/`run_env.sh` operate on the whole environment, deploying either app briefly
restarts both — an accepted cost, same "no per-app games" rule as above.

**Remote/prod backward compatibility**: gated behind `HAVE_SCRIPTS_BUNDLE` — a version cut before
this existed (no bundled `stop_env.sh`/`run_env.sh` on the box) falls back unchanged to the
original direct `docker compose up -d` + manual `active_env.json` write. **Side-effect fix**: once
on the new path, the previously-known-and-deferred stale `active_env.json` schema gap (gap #1,
explicitly left out of this bugfix's scope per earlier triage) is fixed for free — `env_lock.sh`,
invoked transitively via `stop_all.sh`/`run_all.sh`, already writes the current `active_envs` dict
schema; the old manual write never did. This was not pursued as its own fix — it simply stopped
applying once the manual write was replaced.

**Test ground**: `dev`, via the real `scratch_deploy_repo` fixture (`scripts/tests/conftest.py`),
serves as the mechanical proof this works before prod ever sees it — the fixture now includes a
genuinely functioning two-app environment (real per-app `run_/stop_` scripts, a real
`/health`-serving container) so `test_deploy_release.py`'s existing 8 tests exercise the actual
`stop_env.sh → load → retag → run_env.sh → prober bootstrap → run_all.sh` chain end-to-end, not
just argument validation. `register_prober_schedule.sh` itself is stubbed only in this fixture
(never the real macOS LaunchAgent) since `deploy_release.sh`'s `<env>` argument is hard-locked to
the literal string `"dev"`, which would otherwise collide with a real dev environment's
LaunchAgent label on the same machine — the LaunchAgent mechanism itself stays fully covered
separately, against real `launchd`, by `test_env_scripts.py`. Full `scripts/` suite: 61/61
passing.

**Still no automated coverage for the remote/SSH leg of this** (same as the rest of that path) —
relies on a manual gate against the real box.

## 2026-09-07: live prod incident and fix

With the design above complete and re-verified, the last open item — actually wiring the Windows
Task Scheduler task for `prober.py` on real prod — was completed and the scripts deployed. Real
production use immediately surfaced two genuine, independent gaps neither of which had been caught
by the (extensive) unit-level testing above, because both are about *live, wall-clock, cross-tick*
behavior that a single-process test can't exercise.

### Gap 1: the restart-loop itself, and HTTP-200-only health checks

Deployed to prod (`v0.5.4-b43v2`), the environment entered a visible restart loop: the prober
would trigger a soft restart, the app would still be mid-boot on the *next* scheduled tick a minute
later, and — because Windows Task Scheduler's `MultipleInstancesPolicy=IgnoreNew` only protects
against a second *task instance* overlapping the first, and the first instance's own
`subprocess.run()` call to `run_all.sh` returned as soon as `docker compose up -d` returned, long
before the app inside had actually finished booting — the next tick's task instance was free to
fire, see the app still not yet healthy, and trigger *another* restart. Root cause: nothing made
the scheduled task instance itself span the real boot window.

Separately, `prober.py`'s health check only ever inspected the HTTP status code (200 vs. not-200)
of each app's `/health` endpoint — never the JSON body's own `status` field. Both apps' `/health`
returns HTTP 200 with `"status": "fail"` for some real failure modes (a specific check failing
while the endpoint itself still answers) — a case the old code would silently treat as healthy.

**Fix** (`scripts/run_all_and_verify_healthy.sh` + `scripts/health_monitoring/verify.py`, both
new):
- `verify.py` is the single source of truth for "is this app's `/health` actually healthy" —
  fetches the real JSON body, checks `status == "ok"`, and logs **every single check attempt**
  (`[timestamp] checking app=<name>` / `[timestamp] got reply: <full detail, including the exact
  error string on failure>`) to a new, dedicated `logs/health_monitoring/<env>/verify.log` (kept
  separate from the strict-JSONL `prober.log` — mixing free-text per-attempt logs into a JSONL
  decision log would break its parseability). `prober.py` now imports `verify.py` directly
  (`from verify import ...`) rather than re-implementing health checking — one implementation, no
  two-way duplication between the prober and the deploy path.
- `run_all_and_verify_healthy.sh` wraps `run_all.sh`: it blocks, polling `verify.py` every 10s, for
  up to a 5-minute grace period, until both apps report genuinely healthy — only then does the
  scheduled task instance (and thus `MultipleInstancesPolicy=IgnoreNew`'s protection) actually
  cover the real boot window. `prober.py`'s `run_soft_restart()` now calls this instead of
  `run_all.sh` directly.
- Verified live in both `dev` and `prod`: a clean bootstrap → healthy → steady `"none"` cycle with
  zero premature restarts, reproduced identically in both environments.

### Gap 2: two interrupted single-app deploys left prod down for ~41 minutes, unmonitored

While working through the fix above, a **second, independent** incident was found and confirmed
via direct evidence (Windows Task Scheduler's own event log, `docker events`, and this session's
own tool-call transcript — not inference):

- **11:54:59 IDT**: `./scripts/deploy_release.sh morning-mcp-app prod 0.5.4-b43v4` (the old,
  single-app-only script) was run. Its remote path's `stop_env.sh` step executed on the box
  (11:55:09 — both containers killed, the scheduled prober task disabled), but the call was
  interrupted (11:55:42) before reaching its own restart step. The scheduled prober's own next
  tick (11:56:01, having just been re-enabled) found both apps down and correctly triggered its own
  bootstrap — containers came back up at 11:56:03–04, with `morning-mcp-app` on the new v4 image.
- **11:56:17 IDT**: the *exact same command* was run again — before the first attempt's own
  verification had settled. Its `stop_env.sh` step (11:57:00–07) killed both containers again and
  disabled the task again. This second call was also interrupted (11:57:06), before reaching its
  own restart step.
- **Net result, confirmed directly via `docker events`: zero containers running on the box from
  11:57:07 to 12:38:03 — a continuous 41-minute outage**, undetected the entire time because the
  one thing that would have caught it (the scheduled health prober) had itself been disabled by the
  first call and never re-enabled by either interrupted attempt. `denidin-app` was never part of
  either call and stayed on `v0.5.4-b43v2` throughout — it was never actually deployed to `v3` or
  `v4` on prod at all (confirmed: no such image was ever loaded on the box).
- Recovered only because this session's later `scripts/deploy_release.sh prod 0.5.4-b43v5` call
  (see below) ran to completion at 12:38.

**Root cause, generalized**: `deploy_release.sh`'s remote/prod path always calls `stop_env.sh`
(which disables the prober's schedule and stops both apps) before `run_env.sh` (which restarts
them and re-enables the schedule) — a script interrupted anywhere in between those two steps
leaves the environment down **and** unmonitored, with nothing else positioned to catch or recover
it. The *contributing* factor that made this specific incident more likely: deploying both apps at
that time meant two separate single-app deploy calls, each doing its own full stop/start cycle —
doubling the exposure window and creating exactly the overlap seen above (the second call's stop
landing on top of the first call's still-settling restart).

**Fix — cut/deploy release script split (`scripts/cut_release.sh`/`scripts/deploy_release.sh` vs.
`scripts/cut_release_single.sh`/`scripts/deploy_release_single.sh`)**: the original single-app
scripts were renamed to `*_single.sh` with their logic otherwise unchanged. New
`scripts/cut_release.sh <version> --summary "<text>"` and `scripts/deploy_release.sh <env>
<version>` cut/deploy **every** app at one shared version (and, for cutting, one shared summary) in
a single pass — `cut_release.sh` loops `cut_release_single.sh` once per app;
`deploy_release.sh` does exactly ONE `stop_env.sh`/`run_env.sh` cycle for the whole environment
(loading/retagging every app's image in between) instead of one full cycle per app — eliminating
the double-exposure window that made this incident more likely. This does **not** fully close the
"interrupted mid-flight" gap by itself (a single all-apps call can still be interrupted between its
own stop and start) — that residual gap is flagged, not yet fixed, in Verification below.
Additionally fixed along the way: `scripts/lib/release_scripts_manifest.sh` was missing
`scripts/run_all_and_verify_healthy.sh` and `scripts/health_monitoring/verify.py` (both introduced
by gap 1's fix above), so any bundle-based deploy of a version cut after that fix would have
shipped a `prober.py` that immediately crashed with `ModuleNotFoundError: No module named
'verify'` — found via the scratch-fixture test suite before it ever hit real infrastructure. Also
fixed: `deploy_release.sh`'s associative-array app-field lookups (`declare -A`) don't work under
macOS's default bash 3.2 — replaced with plain lookup functions, found live on the first real `dev`
deploy attempt with this script.

**Verified live**: `v0.5.4-b43v5` cut for both apps, deployed to `dev` then `prod` via the new
all-apps `deploy_release.sh`, both apps confirmed healthy and running the right version in both
environments (dev via the deploy script's own final verification; prod additionally cross-checked
against `verify.log`/`prober.log` directly on the box).

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
- [x] Windows Task Scheduler wiring for `prober.py` deployed to real prod (2026-09-07).
- [x] Live dev + prod demo of the full probe → soft-restart cycle, including a real restart-loop
      incident found, root-caused, fixed, and re-verified live in both environments (2026-09-07 —
      see "2026-09-07: live prod incident and fix" above).
- [x] Live re-verification against a real production incident (not the original ngrok race
      specifically, but the same *class* of problem this bugfix targets — a restart mechanism that
      re-triggered before the app finished booting, live on real prod, 2026-09-07).
- [x] A second, independent real incident (two interrupted single-app prod deploys leaving the
      environment down and unmonitored for ~41 minutes) found, root-caused with direct evidence,
      and fixed via the cut/deploy release script split (2026-09-07).
- [x] Human review/approval of this design as the path forward — confirmed via live prod use and
      this haleluya finish-up (2026-09-07).
- [ ] The two additional-scope items surfaced 2026-09-01 (gap #1, `active_env.json` schema — now
      fixed *incidentally*, see "Deploy race with the prober" above; gap #2, ops-scripts drift —
      fixed via the scripts bundle) are effectively closed; not re-verified as their own explicit
      checklist items here.
- [ ] Feature 068's hard-restart gap (see above) designed and either folded into this bugfix or
      split out, once 068 actually merges — 068 still unmerged as of this bugfix's closure.
- [ ] Residual gap, explicitly NOT fixed here: an all-apps `deploy_release.sh` call can still be
      interrupted between its own `stop_env.sh` and `run_env.sh` steps, leaving an environment down
      and unmonitored with nothing to catch it (the 2026-09-07 incident's root cause, only
      partially mitigated by the single-cycle redesign — not eliminated). A proposed fix (a `trap`
      that best-effort re-runs `run_env.sh` on early exit) was discussed but not implemented or
      approved as of this bugfix's closure — worth a follow-up bugfix if it recurs.
