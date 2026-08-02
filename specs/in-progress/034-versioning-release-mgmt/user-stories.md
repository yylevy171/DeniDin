# User Stories — Feature 034 (Versioning & Release Management)

Given-When-Then user stories (METHODOLOGY §I). Unlike most DeniDin features, this one has no
single "external entry point" webhook — its surface area is: a git-tracked `VERSION` file per
app, `apps/morning-mcp-app`'s existing `/health` endpoint, `apps/denidin-app`'s startup log, the
existing `haleluya`/`/haleluya` finish-feature flow (CLAUDE.md), and per-app `CHANGELOG.md` files.
Each story below is independently testable/demonstrable on its own.

Roles referenced: none new — this feature has no user-facing RBAC surface (it's operational
tooling for whoever runs `haleluya`/deploys, not a WhatsApp-facing behavior).

---

## US1 — See which version is currently deployed (Priority: P1)

**Given** `morning-mcp-app-dev` (or `-prod`) is running as a container, and `denidin-app-dev` (or
`-prod`) is running as a container
**When** a human calls `GET /health` on the morning-mcp-app container, and separately reads the
startup lines of `logs/denidin.log` (or `logs/dev/`/`logs/prod/` per that container) for the
denidin-app container
**Then** the `/health` response includes a `version` field with the app's current semantic
version, and the denidin-app startup log includes a line stating its current semantic version —
both sourced from that app's own `VERSION` file (REQ-VER-001/002/003).

**Independent Test**: Fully testable standalone — read each app's `VERSION` file, start (or use an
already-running) container of each, `curl` morning-mcp-app's `/health` and grep denidin-app's
startup log, assert both match the `VERSION` file's contents.

Acceptance criteria:
- `/health`'s existing `status`/`environment` fields are unchanged — `version` is additive, not a
  replacement (no consumer of `/health` should break).
- The denidin-app startup log line appears exactly once per process start, in the same log file
  existing startup logging already uses (no new log file/path introduced).
- If a `VERSION` file is missing or malformed for either app, the app MUST still start normally
  (this is observability, not a startup precondition) — the version surfaces as `"unknown"` rather
  than blocking startup or crashing.

---

## US2 — Cut a release as part of finishing a feature (Priority: P1)

**Given** a feature branch has just been merged and deployed via the existing `haleluya`/
`/haleluya` flow (CLAUDE.md's "Finish-Feature Trigger Phrase")
**When** the human doing the release decides this merge warrants a version bump (not every merge
does — REQ-REL-001) and picks MAJOR/MINOR/PATCH (REQ-REL-002)
**Then** the affected app's `VERSION` file is updated, a git tag `<app>-v<new-version>` is created
on the deployed commit, a new entry is appended to that app's `CHANGELOG.md` (version, date,
one-line summary — REQ-REL-003), and a corresponding section is appended to that app's
`RELEASES.md` with fuller release notes (REQ-REL-004).

**Independent Test**: Fully testable standalone — pick a fixed `VERSION`/bump/summary, run the
documented release steps by hand, then verify: `git tag` shows the new `<app>-v<version>` tag on
the right commit, `CHANGELOG.md` has the new one-line entry, and `RELEASES.md` has the new
detailed section.

Acceptance criteria:
- Skipping the release step for a given merge (e.g. a docs-only change) is a valid, explicit
  choice — not an error state — but the decision itself must be visible (e.g. noted in the PR or
  release discussion), not silently defaulted either way.
- The git tag is applied to the commit that was actually deployed (per CLAUDE.md's rebuild/
  recreate deploy step), not merely the merge commit on `master` if those differ in timing.
- `CHANGELOG.md`'s new entry is human-written prose summarizing the change (from the merged
  spec/PR), not a raw `git log` dump.

---

## US3 — Roll back a deployed environment to a prior release (Priority: P2)

**Given** a release (`<app>-v<version>`) has been deployed to `dev` or `prod` and is later found to
need reverting, and at least one older `<app>-v<older-version>` tag exists
**When** a human follows the documented rollback procedure (REQ-ROLL-002): checks out the older
tag, rebuilds that app's image, and recreates the running container for the affected environment
**Then** the environment now serves the older version — verifiable the same way as US1 (`/health`
field or startup log) — and no `master` git history was reverted/rewritten to get there
(REQ-ROLL-003).

**Independent Test**: Fully testable standalone — deploy version A, "release" version B (per US2),
confirm B is live (per US1), run the documented rollback procedure back to A, confirm A is live
again via the same US1 check, and confirm `master`'s commit history is unchanged (`git log
master` before/after matches).

Acceptance criteria:
- The rollback procedure is discoverable in documentation (REQ-DOC-001) without needing to ask
  the person who last deployed.
- Rolling back one app/environment (e.g. `denidin-app-prod`) does not require touching the other
  app or the other environment — matches the existing per-app, per-environment deploy granularity
  documented under "Environments (dev/prod)."
- The rollback leaves a discoverable record of what happened equivalent to the outgoing deploy
  (i.e. it's not a silent, undocumented revert — same expectation as any other deploy).

---

## Out of Scope for This Feature

- **Automatic MAJOR/MINOR/PATCH classification** — the bump type in US2 is always a human
  decision; no commit-message or PR-title parsing is introduced.
- **A single shared version number across both apps** — pending the `[NEEDS CLARIFICATION]` in
  `spec.md`; these stories assume independent per-app versioning is confirmed.
- **Automated/zero-downtime rollback** — US3's rollback is the same manual rebuild/recreate
  mechanics the project already uses for forward deploys, not a new automated mechanism.
- **A dedicated RBAC story** — this feature has no WhatsApp-facing or godfather/admin-facing
  surface; nothing here changes who can talk to the bot or what tools they can call.
- **Versioning any change that doesn't ship to a real environment** (e.g. work still on a feature
  branch, not yet merged/deployed) — release/version bumps happen at `haleluya` time, not per
  commit.
