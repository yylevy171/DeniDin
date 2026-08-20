# User Stories: Lift Dev/Prod Concurrency Ban

Feature ID: 042-lift-dev-prod-concurrency-ban

---

## US1: Start dev without tearing down a live prod

**As** an operator (human or AI agent) working in a dev clone while prod is
live,
**I want** to start the dev environment without first stopping prod,
**so that** I can develop/test against dev without disrupting real
WhatsApp/invoicing traffic currently being served by prod.

**Given** prod (both apps) is currently running and healthy,
**When** I run `scripts/run_all.sh dev` (with explicit per-action approval,
per CLAUDE.md's environment-start rule, unchanged by this feature),
**Then** dev starts successfully, `shared/active_env.json`'s `active_envs`
gains a `"dev"` key without removing prod's `"prod"` key, and prod's own
containers, application, and health continue completely unaffected.

## US2: Environment-mismatch safety net still works per-environment

**As** the project's safety mechanism against a container silently serving
the wrong environment's traffic,
**I want** each container's watchdog to keep checking that its own declared
environment is legitimately active,
**so that** a container whose environment was torn down (e.g. via
`killall_containers.sh`) still shuts down its app subprocess rather than
continuing to serve stale traffic - independent of whatever the *other*
environment's state is.

**Given** a container declares itself `config.environment: "dev"`,
**When** `shared/active_env.json`'s `active_envs` does NOT contain a `"dev"`
key (regardless of whether `"prod"` is present or absent),
**Then** that container's watchdog kills its own app subprocess and does not
respawn it, exactly as before this feature - the only thing that changed is
the membership check (dict key presence) replacing scalar equality, not the
mismatch-response behavior itself.

**Given** a container declares itself `config.environment: "dev"` and
`active_envs` DOES contain a `"dev"` key,
**When** `active_envs` also happens to contain a `"prod"` key,
**Then** no mismatch is triggered - a currently-active prod entry is no
longer evidence of a problem for a dev container (this is the actual
behavior change this feature introduces).

## US3: Dev-ownership lock is unaffected

**As** a developer working in one of several sibling clones on the same
machine,
**I want** the existing multi-clone `dev` lock (one owning clone at a time)
to keep working exactly as before,
**so that** two clones still can't collide on the same dev containers/data
volumes - a concern this feature does not touch.

**Given** clone A currently owns the `dev` lock,
**When** clone B attempts `scripts/run_all.sh dev` without `-force`,
**Then** it's rejected with the same "dev is locked by '<A>'" error as
before this feature - unrelated to, and unaffected by, dev/prod now being
allowed to coexist.
