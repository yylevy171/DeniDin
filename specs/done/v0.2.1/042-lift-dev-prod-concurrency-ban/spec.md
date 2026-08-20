# Feature Specification: Lift Dev/Prod Concurrency Ban

**Feature Branch**: `chore/lift-dev-prod-concurrency-ban`
**Feature ID**: 042-lift-dev-prod-concurrency-ban
**Priority**: P2
**Created**: August 5, 2026
**Status**: Done - Merged to master
**Input**: Explicit human request: "fix the one env rule - it shouldn't exist any more" (following up on CLAUDE.md's own deferred note that the ban needed an explicit human review before being lifted)

---

**MANDATORY REQUIREMENT MET**: See `user-stories.md` (this directory) for Given-When-Then user stories, per METHODOLOGY.md §I/§II.

**This spec complies with**:
- **CONSTITUTION.md** §I (config/dependency handling, no env vars), §III (feature branch workflow).
- **METHODOLOGY.md** §I (user stories mandatory), §II (template structure).

---

## Origin

CLAUDE.md's "Environments (dev/prod)" section already documented, as of the
2026-08-03 asymmetry update, that the *original* technical reason dev and
prod couldn't safely run concurrently (`GreenAPIBot` polling one shared
Green API instance/WhatsApp number from two containers at once) no longer
applied, since each environment now has its own fully separate WhatsApp/
Green API/Green Invoice infrastructure. That same section explicitly said
the "ONE ENVIRONMENT SET AT A TIME" rule was **not** lifted by that
asymmetry update alone - it required an explicit human review first,
because the rule's *enforcement mechanism* (`env_lock.sh`, `watchdog.py`,
`killall_containers.sh`, `shared/active_env.json`) and its other motivating
incident (2026-07-21, about credential/config isolation, not instance
sharing) hadn't been reviewed against the new topology.

That review happened in this session: the human explicitly reviewed the
reasoning and directed the ban lifted ("fix the one env rule - it shouldn't
exist any more"), then confirmed the exact scope (only the dev+prod
concurrency ban - not the multi-clone dev-ownership lock, not the
watchdog/killall safety net) and confirmed starting dev concurrently with
the then-live prod as a real validation of the change, not just a
documentation edit.

## Problem Statement

`shared/active_env.json`'s pre-existing schema (`{"active_env":
"dev"|"prod"|null, "owner": ...}`) could only ever record ONE environment as
active at a time by construction - a scalar field, not a set. `env_lock.sh`'s
`env_lock_acquire` explicitly refused to start dev while prod was active (and
vice versa). Both `watchdog.py` implementations (denidin-app, morning-mcp-app)
tore down their own app subprocess on any inequality between their own
declared environment and that single scalar value. Simply removing the
documentation prohibition without also changing this mechanism would have
meant starting dev while prod was active would silently flip
`active_env.json` to `"dev"`, causing prod's own watchdog to detect a
"mismatch" and kill prod's live application - the opposite of the intended
effect.

## Scope

### In scope
- Redesign `shared/active_env.json`'s schema from a single `active_env`
  scalar to an `active_envs` dict keyed by environment name - presence of a
  key means that environment is active, independent of the other's state.
- Update `scripts/env_lock.sh` (`env_lock_read`, `env_lock_acquire`,
  `env_lock_release`) for the new schema - `env_lock_acquire dev` and
  `env_lock_acquire prod` no longer block on each other; each only touches
  its own environment's entry, leaving the other's untouched.
- Update `scripts/killall_containers.sh` to reset the new schema
  (`active_envs: {}`) and drop its "run this before switching environments"
  framing (nothing to switch away from anymore).
- Update `watchdog.py` in both `apps/denidin-app` and `apps/morning-mcp-app`
  to check "is my own declared environment currently listed as active"
  (dict membership) instead of "does the single active value equal mine"
  (scalar equality) - with old-schema-vs-new-code and
  new-schema-vs-old-code transitions both degrading safely (skip the check,
  never false-trigger) for any rollout window where the file and a running
  container's baked-in code are briefly out of sync.
- Remove a stale operational warning in `run_denidin.sh` (dev sharing one
  Green API instance with prod) that already contradicted the 2026-08-03
  asymmetry update.
- Update `CLAUDE.md` (this clone's copy): rename the "ONE ENVIRONMENT SET AT
  A TIME" banner to "ENVIRONMENT ISOLATION & LOCKING", record the review's
  conclusion in the "Environments (dev/prod)" section, and update every
  description of the lock schema/enforcement mechanism to match.
- Fix an unrelated, discovered-along-the-way false-positive in
  `scripts/windows_prod/verify_windows_prod.sh`'s
  `shared_state_local_json_valid` check, which required the configured
  `shared_state_dir` target to be literally named `shared` - the real,
  working prod box uses `.shared_canonical` instead (functionally fine,
  just a different name), which the check's regex rejected. Loosened to
  just require an absolute path.

### Out of scope
- Any change to the multi-clone `dev`-ownership lock itself (still fully
  enforced, unchanged in spirit) or to `prod` never being owner-locked.
- Any change to the "two apps within one environment are bundled" rule
  (`denidin-app` + `morning-mcp-app` must still start/stop together).
- A full migration of `mcp` or any other dependency (unrelated; see Feature
  041 for that).

## Verification (real, not simulated)

- Dry-run tested `env_lock.sh`'s new `acquire`/`release`/`read` logic in an
  isolated temp repo before touching anything real: confirmed dev and prod
  can both be active at once, each release only clears its own entry,
  ownership rejection and `-force` override both still work.
- Started `dev` for real, for real, concurrently with the then-live `prod`
  (v0.2.1, both apps) on the separate Windows box (Feature 035) - confirmed
  dev came up healthy (`/health` returns `v0.2.1`, `active_envs.dev.owner:
  "Avi"`) and prod remained fully healthy and unaffected throughout (dev and
  prod turned out to never share the same `active_env.json` file at all,
  since prod's copy lives on the physically separate Windows box - the ban
  had been procedural, not a literal file-collision risk).
- Re-ran `scripts/windows_prod/verify_windows_prod.sh` after the false-positive
  fix: 20/20 checks passed (was 19/20 before).
