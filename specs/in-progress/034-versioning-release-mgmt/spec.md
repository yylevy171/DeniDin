# Feature Spec: Versioning & Release Management

**Feature ID**: 034-versioning-release-mgmt
**Priority**: P2 (assumed default — not blocking other work; revisit if the user wants this elevated)
**Status**: Draft - Clarified (scope + open questions resolved 2026-08-02; ready for `/speckit.plan`)
**Created**: July 30, 2026
**Updated**: August 2, 2026

---

**CRITICAL - MANDATORY REQUIREMENT**:
🚨 **This feature MUST have a separate `user-stories.md` file** before spec approval:
- Spec approval is BLOCKED if `user-stories.md` does not exist
- See `user-stories.md` in this directory and `.github/METHODOLOGY.md §I`

---

## Problem Statement

Neither `apps/denidin-app` nor `apps/morning-mcp-app` has any versioning today. A single
repo-wide git tag exists from before the two-app split (`v1.0.0`, Jan 17 2026, "DeniDin WhatsApp
AI Chatbot Complete", tagging `10af058`) — nothing since. Consequences observed today:

- **No way to tell which code a running container is actually serving.** `docker compose up -d`/
  `restart` does not rebuild when source changed on disk (CLAUDE.md, "Environments (dev/prod)") —
  this already caused a real incident (2026-07-20, a merged RBAC fix had zero effect on prod for
  hours because the container was never rebuilt). Nothing in the running system currently exposes
  "what version am I" to catch this class of bug faster.
- **No changelog or release notes anywhere.** `apps/morning-mcp-app`'s `/health` endpoint
  (`server.py:76-82`) reports `{"status": "ok", "environment": ...}` but no version.
  `apps/denidin-app` has no HTTP surface at all (it's a polling WhatsApp bot, not a server) and no
  startup log line identifying a version either.
- **No documented rollback procedure.** If a deployed change needs to be reverted, the only
  documented lever is `git checkout`/rebuild by hand — there's no record of "what version was
  running before this deploy" to roll back *to*.
- **The two apps are independently deployable** (own `Dockerfile`, own `requirements.txt`, own
  release cadence per CLAUDE.md's "Repository Layout") but any future versioning scheme must
  decide whether that independence extends to version numbers too — the pre-split `v1.0.0` tag
  predates this and offers no precedent either way.

**Goal**: give each app (`denidin-app`, `morning-mcp-app`) its own semantic version, a way to see
that version at runtime, a documented process for cutting a release (tied into the existing
`haleluya`/`/haleluya` finish-feature flow already used for every merge), a changelog/release-notes
record per release, and a documented rollback procedure — all config-file-driven, no environment
variables (CONSTITUTION §I), consistent with the existing dev/prod container model.

## Explicitly Out of Scope

- **A unified, repo-wide version number.** `denidin-app` and `morning-mcp-app` version and
  release independently, matching how they're already deployed independently (confirmed via
  clarification — see below).
- **Automatic semantic-version-bump classification** (e.g. parsing commit messages/PR titles to
  decide MAJOR vs MINOR vs PATCH). The bump type is a human decision made at release time, same as
  every other judgment call in the existing `haleluya` flow.
- **CI/CD pipeline changes.** This project has no automated build/deploy pipeline today (deploys
  are the manual rebuild-and-recreate steps documented under "Environments (dev/prod)" in
  CLAUDE.md); this feature does not introduce one. Release automation here means scripting/
  documenting the manual steps, not standing up CI.
- **Zero-downtime or automated rollback.** Rollback stays a manual, documented procedure (checkout
  a prior release tag, rebuild, redeploy — mirroring the existing manual deploy steps), not an
  automated blue-green mechanism.
- **Versioning `apps/morning-mcp-app`'s Morning/Green Invoice API integration itself** (that's a
  third-party API DeniDin doesn't control) — only this repo's own two apps are in scope.

## Functional Requirements

### Version tagging

- **REQ-VER-001**: Each app (`denidin-app`, `morning-mcp-app`) MUST have its own current semantic
  version (`MAJOR.MINOR.PATCH`), stored in a single git-tracked source of truth per app (not an
  environment variable, per CONSTITUTION §I) — e.g. a `VERSION` file at each app's root.
- **REQ-VER-002**: `apps/morning-mcp-app`'s existing `/health` endpoint (`server.py:76-82`) MUST
  include the app's current version in its JSON response, alongside the existing `status`/
  `environment` fields.
- **REQ-VER-003**: `apps/denidin-app` (no HTTP surface) MUST log its current version at startup
  (same log file/format as existing startup logging), so the running version is visible in
  `logs/denidin.log` without needing a new endpoint.
- **REQ-VER-004**: The version is a per-app fact, not per-environment — `dev` and `prod` for the
  same app may run *different* versions at different times (that's normal during a dev→prod
  promotion), but there is exactly one version concept per app, not one per environment.

### Release process automation

- **REQ-REL-001**: The existing `haleluya`/`/haleluya` finish-feature flow (CLAUDE.md, "Spec-Driven
  Workflow") MUST gain an explicit release step: after merge + deploy, bump the affected app's
  `VERSION` file (human-chosen MAJOR/MINOR/PATCH per REQ-REL-002), tag the deployed commit
  `<app>-v<version>` (e.g. `denidin-app-v1.4.2`), and append a changelog entry.
  This step is optional per-merge (not every merge needs a version bump — e.g. a docs-only change
  might not) but MUST be an explicit decision point, not silently skipped.
- **REQ-REL-002**: The MAJOR/MINOR/PATCH bump decision is made by a human at release time (no
  automatic classification, see "Explicitly Out of Scope").
- **REQ-REL-003**: Each app's release changelog (`CHANGELOG.md` at that app's root) MUST gain one
  entry per release: version, date, and a short human-readable summary of what changed — sourced
  from the merged PR(s)/spec(s) since the last release, not auto-generated from raw git log.
- **REQ-REL-004**: Release notes (a longer-form, user-facing description of a release) MUST be
  captured in a git-tracked `RELEASES.md` file at each app's root, one section per release
  (version, date, longer-form notes) — separate from the terser `CHANGELOG.md` (REQ-REL-003),
  which stays a short one-line-per-release summary list. No GitHub Releases dependency.

### Rollback / release history

- **REQ-ROLL-001**: For each environment (`dev`/`prod`) of each app, the currently-deployed
  version MUST be discoverable after the fact — via REQ-VER-002/003 (live `/health` or logs) and
  via the git tag history (REQ-REL-001), without needing tribal knowledge of "what we last
  deployed."
- **REQ-ROLL-002**: A documented rollback procedure MUST exist: given a prior `<app>-v<version>`
  tag, check out that commit, rebuild that app's image, and recreate the running container for the
  affected environment — the same manual rebuild/recreate mechanics already documented under
  CLAUDE.md's "Environments (dev/prod)" (`docker compose ... build ... && ... up -d ...`), just
  anchored to a named release tag instead of an arbitrary commit.
- **REQ-ROLL-003**: Rollback MUST NOT require reverting or rewriting git history on `master` —
  it operates by checking out/rebuilding an older tagged commit into a running container, leaving
  `master`'s own history untouched (consistent with this project's git safety rules: no
  force-push, no history rewriting).

### Internal documentation

- **REQ-DOC-001**: CLAUDE.md MUST document the versioning scheme (where `VERSION` lives per app,
  tag naming convention, changelog location) so it's discoverable the same way every other
  cross-cutting convention in this repo is.
- **REQ-DOC-002**: The `haleluya` finish-feature definition (CLAUDE.md + `.github/METHODOLOGY.md`
  "Finish-Feature Trigger Phrase") MUST be updated to reference the new optional release step
  (REQ-REL-001), so it's covered by the existing trigger-phrase shorthand rather than a second,
  separate command to remember.

## Key Entities

- **semantic_version**: A `MAJOR.MINOR.PATCH` string identifying one app's release (e.g.
  `"1.4.2"`). Independent per app.
- **release_tag**: A git tag of the form `<app>-v<semantic_version>` (e.g. `denidin-app-v1.4.2`,
  `morning-mcp-app-v0.3.0`), applied to the commit that was actually built/deployed.
- **CHANGELOG.md**: Per-app, git-tracked, one short entry per release (version, date, one-line
  summary) — the terse index.
- **RELEASES.md**: Per-app, git-tracked, one longer-form section per release (version, date,
  fuller release notes) — the detailed record, no GitHub dependency.
- **deployed_version**: The semantic_version an environment (`dev`/`prod`) of an app is currently
  running, discoverable via REQ-VER-002 (morning-mcp-app `/health`) / REQ-VER-003 (denidin-app
  startup log).

## Success Criteria

- **SC-001**: Given a running `morning-mcp-app` container (dev or prod), a human can determine its
  exact deployed version with a single `curl /health` call, without SSH/docker exec.
- **SC-002**: Given `logs/denidin.log` for a running `denidin-app` container, a human can determine
  its exact deployed version by reading the startup log lines, without needing the source tree.
- **SC-003**: Given a need to roll back either app in either environment, a human can find the
  documented procedure (REQ-ROLL-002) and the specific prior version to roll back to (via git tags
  + changelog) without asking anyone else.
- **SC-004**: Every release since this feature ships has a corresponding changelog entry and a
  git tag — verifiable by `git tag -l '<app>-v*'` matching `CHANGELOG.md` entries 1:1 per app.

## Clarifications

### Session 2026-08-02

- Q: What should this feature cover? → A: App version tagging, release process automation,
  rollback/release history, plus internal documentation and release notes (all five folded into
  one feature per user's explicit answer — not split further).
- Q: Independent per-app versioning, or one shared repo-wide version continuing the pre-split
  `v1.0.0` precedent? → A: **Independent per app** (`denidin-app-v*`, `morning-mcp-app-v*`) —
  confirmed, matches how the two apps are already deployed independently.
- Q: Where should release notes live — GitHub Releases, or a git-tracked file? → A: **A
  `RELEASES.md` file per app** — confirmed, no GitHub Releases dependency (spec.md and
  user-stories.md updated accordingly; REQ-REL-004 now specifies `RELEASES.md` instead of `gh
  release create`).

No open `[NEEDS CLARIFICATION]` markers remain.

## References

- CLAUDE.md, "Environments (dev/prod)" — existing manual rebuild/recreate deploy mechanics this
  feature's rollback procedure (REQ-ROLL-002) reuses rather than replaces; also documents the
  2026-07-20 incident motivating REQ-VER-002/003.
- CLAUDE.md, "Spec-Driven Workflow" / `.github/METHODOLOGY.md` "Finish-Feature Trigger Phrase" —
  the existing `haleluya` flow this feature's release step (REQ-REL-001) extends.
- `apps/morning-mcp-app/src/denidin_mcp_morning/server.py:71-82` — existing `/health` endpoint
  REQ-VER-002 extends with a version field.
- `git tag v1.0.0` (`10af058`, Jan 17 2026) — the one prior versioning precedent in this repo,
  predating the two-app split; establishes that semantic versioning + annotated tags + a
  human-written release message is already the project's implicit style.
- `.github/CONSTITUTION.md` §I — no environment variables; version storage (REQ-VER-001) must be a
  git-tracked file, not config injected via env var.
