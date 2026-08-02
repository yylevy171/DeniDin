# CLI Contract: `scripts/rollback_release.sh`

Implements REQ-SCR-002.

## Invocation

```
scripts/rollback_release.sh <app> <env> <version>
```

- `<app>`: literal `denidin-app` or `morning-mcp-app`. Any other value → usage error, exit 2.
- `<env>`: literal `dev` or `prod`. Any other value → usage error, exit 2.
- `<version>`: exact semantic version string to roll back to, e.g. `1.4.0`. Must match
  `^\d+\.\d+\.\d+$`. Any other shape → usage error, exit 2.
- **All three arguments are required, positional, with no defaults, no "previous version"
  shorthand.** 🚨 Per REQ-ROLL-004/CLAUDE.md's hard-constraint banner: the exact `<version>` must
  come directly from a human in that specific request — an AI agent must never infer it (e.g. "the
  one before this" from conversation context), even when it seems obvious.

## Preconditions checked (fail before any side effect)

1. `<artifacts-root>/<app>/<app>-v<version>.tar` exists.
2. `<artifacts-root>/<app>/<app>-v<version>.json` exists and its `app`/`version` fields match the
   requested `<app>`/`<version>` (data-model.md's manifest validation rule) — a mismatched or
   corrupt manifest fails loudly rather than proceeding.
3. The target environment's container (`<app>-<env>`) is addressable via the existing
   `docker compose` setup for that environment (same precondition `run_<app>.sh <env>` already
   implicitly assumes).

Any precondition failure → exit 1, human-readable message naming which check failed (e.g. "no
release found for morning-mcp-app v0.9.0 — checked
/Users/yaron/Projects/DeniDin/artifacts/morning-mcp-app/morning-mcp-app-v0.9.0.tar"), **no side
effects**. This is the documented "accepted tradeoff of no container registry" case from
spec.md's Explicitly Out of Scope — a pruned/missing artifact means rollback to that exact version
isn't possible until it's rebuilt by hand; the script's job is to fail clearly, not to silently
fall back to rebuilding.

## Side effects (in order)

1. `docker load -i <artifacts-root>/<app>/<app>-v<version>.tar` (no rebuild — REQ-ROLL-002).
2. Recreate the `<app>-<env>` container from the loaded image (exact `docker compose`/`docker run`
   invocation TBD at task-implementation time — must override the running container to use the
   loaded, version-tagged image rather than triggering that environment's normal `build:` step).
3. Print a confirmation naming the app/env/version now running, so the record of what happened is
   visible the same way an ordinary deploy's output is (spec.md SC-003/US3 acceptance criteria).

No git operations of any kind — REQ-ROLL-003: rollback never touches `master`'s history.

## Exit codes

- `0`: success.
- `1`: a precondition failed, or a side-effect step failed partway.
- `2`: usage error (bad/missing arguments) — no side effects, fails before any precondition check.

## Explicitly not this script's job

- Deciding whether/when to roll back, or which version to roll back to (REQ-ROLL-004 — that's the
  calling human/agent's job, before this script is ever invoked).
- Rebuilding anything from git source, under any circumstance (REQ-ROLL-002).
