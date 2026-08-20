# CLI Contract: `scripts/cut_release.sh`

Implements REQ-SCR-001. This is a "contract" in the same sense webhook JSON shapes are contracts
for message-routing features (METHODOLOGY §VII) — the interface other things (the human, the
`haleluya` flow, `scripts/deploy_release.sh` downstream) depend on.

## Invocation

```
scripts/cut_release.sh <app> <version>
```

- `<app>`: literal `denidin-app` or `morning-mcp-app`. Any other value → usage error, exit 2, no
  side effects.
- `<version>`: exact semantic version string, e.g. `1.4.2`, optionally with a `-suffix` (e.g.
  `0.0.1-test`, for placeholder/dry-run use — 2026-08-02 decision). Must match
  `^\d+\.\d+\.\d+(-[A-Za-z0-9.]+)?$`. Any other shape (including a leading `v`, or empty) → usage
  error, exit 2, no side effects.
- **Both arguments are required, positional, with no defaults.** 🚨 Per REQ-REL-002/CLAUDE.md's
  hard-constraint banner: whoever/whatever invokes this script (including an AI agent) must have
  obtained the exact `<version>` value directly from a human in that specific request — the script
  itself has no way to enforce this technically, so the obligation is procedural (documented here
  + in CLAUDE.md), not code-enforced. The script's own defense-in-depth is REQ-SCR-001's
  interactive confirmation step below.

## Preconditions checked (fail before any side effect)

1. Git tag `<app>-v<version>` does not already exist (`git rev-parse <tag>` fails) — REQ-REL-006.
2. `<artifacts-root>/<app>/<app>-v<version>.tar` does not already exist — REQ-REL-006.
3. Working tree is clean for `apps/<app>/` (no uncommitted changes that would end up baked into
   the release image ambiguously) — refuses with a clear message if dirty.

Any precondition failure → exit 1, human-readable message naming which check failed, **no side
effects** (no partial file writes, no partial tag).

## Interactive confirmation

After preconditions pass, before doing anything irreversible, prints a summary and requires an
explicit `y`/`yes` response on stdin:

```
About to cut denidin-app v1.4.2:
  - from commit: a1b2c3d (HEAD)
  - VERSION file: 1.4.0 -> 1.4.2
  - git tag: denidin-app-v1.4.2 (new)
  - artifact: /Users/yaron/Projects/DeniDin/artifacts/denidin-app/denidin-app-v1.4.2.tar

This is permanent (REQ-REL-006) - continue? [y/N]
```

Anything other than `y`/`yes` → abort, exit 0 (not an error — a deliberate "no"), no side effects.

## Side effects (in order, once confirmed)

1. Update `apps/<app>/VERSION` to `<version>`.
2. Prepend a `CHANGELOG.md` entry (data-model.md shape) — summary text supplied interactively or
   via a `--summary` flag (exact UX left to task-implementation).
3. Prepend a `RELEASES.md` section (data-model.md shape).
4. `git add`/`git commit` those three file changes (one commit, message
   `"release: <app> v<version>"`).
5. `docker build --platform linux/amd64 -t <app>:<version> apps/<app>/` — pinned to `linux/amd64`
   (2026-08-03, Feature 035 reconciliation) so the single artifact this produces is deployable to
   *either* target: `dev` (local Docker) and `prod` (the Windows/WSL2 box, native `amd64` —
   `specs/035-windows-always-on-prod/`), with no per-environment rebuild.
6. `docker save <app>:<version> -o <artifacts-root>/<app>/<app>-v<version>.tar`.
7. Write `<artifacts-root>/<app>/<app>-v<version>.json` manifest (data-model.md shape).
8. `git tag <app>-v<version>` on the commit from step 4.

## Exit codes

- `0`: success, or a deliberate "no" at the confirmation prompt.
- `1`: a precondition failed (see above) or a side-effect step failed partway (see "atomically
  enough" note in spec.md REQ-SCR-001 — task-implementation must decide exact partial-failure
  recovery, e.g. whether step 5 failing after step 4 already committed needs a documented manual
  cleanup path).
- `2`: usage error (bad/missing arguments) — no side effects, fails before any precondition check.

## Explicitly not this script's job

- Deciding whether to cut a release at all, or what the version number should be (REQ-REL-001/002
  — that's the calling human/agent's job, before this script is ever invoked).
- Deploying the built image anywhere (that's `run_denidin.sh`/`run_morning_mcp.sh`'s job for
  ordinary forward deploys — this script only produces the durable artifact).
