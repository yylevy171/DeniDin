# CLI Contract: `scripts/deploy_release.sh`

Implements REQ-SCR-002/REQ-DEPLOY-001/002. **One script for three cases** (research.md
Decision 9, 2026-08-02 correction): deploying a freshly cut version to `dev` for the first time,
promoting an already-`dev`-validated version to `prod`, and rolling back to an older version in
either environment. All three are the identical operation — load a pre-built artifact, redeploy
it, verify it — differing only in whether `<version>` is newer, equal, or older than what's
currently running in `<env>`. There is no separate "rollback script."

## Invocation

```
scripts/deploy_release.sh <app> <env> <version>
```

- `<app>`: literal `denidin-app` or `morning-mcp-app`. Any other value → usage error, exit 2.
- `<env>`: literal `dev` or `prod`. Any other value → usage error, exit 2.
- `<version>`: exact semantic version string to deploy, e.g. `1.4.0` or `1.4.6`, optionally with a
  `-suffix` (matches `cut_release.sh`'s format, e.g. `0.0.0-preinit`). Must match
  `^\d+\.\d+\.\d+(-[A-Za-z0-9.]+)?$`. Any other shape → usage error, exit 2.
- **All three arguments are required, positional, with no defaults, no "previous version" or
  "latest" shorthand.** 🚨 Per REQ-DEPLOY-005/CLAUDE.md's hard-constraint banner: the exact
  `<version>` must come directly from a human in that specific request — an AI agent must never
  infer it (e.g. "the previous one," "the one just cut"), even when it seems obvious. This applies
  identically whether the call is an initial `dev` deploy, a `prod` promotion, or a rollback.
- **Every call is also, separately, an environment-start action** under the pre-existing CLAUDE.md
  "AI AGENTS: NEVER START AN ENVIRONMENT... WITHOUT EXPLICIT APPROVAL" rule — it recreates a
  running container in `dev` or `prod`. That approval and the human-supplied-version requirement
  above are two distinct gates; neither substitutes for the other.

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
spec.md's Explicitly Out of Scope — a pruned/missing artifact means deploying that exact version
isn't possible until it's rebuilt by hand; the script's job is to fail clearly, not to silently
fall back to rebuilding.

## Side effects (in order)

1. `docker load -i <artifacts-root>/<app>/<app>-v<version>.tar` (no rebuild — REQ-DEPLOY-001, no
   exception for any of the three cases).
2. Recreate the `<app>-<env>` container from the loaded image (exact `docker compose`/`docker run`
   invocation TBD at task-implementation time — must override the running container to use the
   loaded, version-tagged image rather than triggering that environment's normal `build:` step).
3. **Automatically verify** (REQ-DEPLOY-002, research.md Decision 10) — block until confirmed or
   timeout:
   - `morning-mcp-app`: poll `GET /health` every ~2s (bounded timeout, e.g. 30s) until its
     `version` field matches `<version>`.
   - `denidin-app`: tail recent log lines every ~2s (same timeout) until one carries the
     `[v<version>]` marker.
   - Timeout without a match → **deploy reported as FAILED** (exit 1), even though the container
     did start — the container's actual last-observed version/state is included in the failure
     message. A started-but-unverified container is not a success.
4. On verified success, print a confirmation naming the app/env/version now running, so the
   record of what happened is visible the same way an ordinary deploy's output is (spec.md
   SC-003/US3 acceptance criteria).

No git operations of any kind — REQ-DEPLOY-004: no deploy, promotion, or rollback ever touches
`master`'s history.

## Exit codes

- `0`: success — side effects completed *and* automatic verification (step 3) passed.
- `1`: a precondition failed, a side-effect step failed partway, or verification timed out.
- `2`: usage error (bad/missing arguments) — no side effects, fails before any precondition check.

## Explicitly not this script's job

- Deciding whether/when to deploy, promote, or roll back, or which version/environment (REQ-DEPLOY-005
  — that's the calling human/agent's job, before this script is ever invoked, every time, with no
  approval carrying over from a previous call).
- Rebuilding anything from git source, under any circumstance (REQ-DEPLOY-001) — true for all
  three cases (initial deploy, promotion, rollback) equally, not just rollback.
- Deciding retention/cleanup of old artifacts in the artifacts folder (spec.md's Explicitly Out of
  Scope) — if the requested version's artifact is gone, this script fails rather than rebuilding.
