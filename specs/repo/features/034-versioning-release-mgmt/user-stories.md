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
**When** a human calls `GET /health` on the morning-mcp-app container, and separately reads
**any** line of `logs/denidin.log` (or `logs/dev/`/`logs/prod/` per that container) for the
denidin-app container — not just a startup line
**Then** the `/health` response includes a `version` field with the app's current semantic
version, and **every** denidin-app log line includes its current semantic version — both sourced
from that app's own `VERSION` file (REQ-VER-001/002/003).

**Independent Test**: Fully testable standalone — read each app's `VERSION` file, start (or use an
already-running) container of each, `curl` morning-mcp-app's `/health`, and grep an arbitrary
sample of denidin-app log lines (not just the first one) — assert all match the `VERSION` file's
contents.

Acceptance criteria:
- `/health`'s existing `status`/`environment` fields are unchanged — `version` is additive, not a
  replacement (no consumer of `/health` should break).
- Every denidin-app log line carries the version, not just a one-time startup line — a log line
  sampled at any point during a long-running process still shows the correct current version.
- If a `VERSION` file is missing or malformed for either app, the app MUST still start normally
  (this is observability, not a startup precondition) — the version surfaces as `"unknown"` rather
  than blocking startup or crashing.

---

## US2 — Cut a release as part of finishing a feature (Priority: P1)

**Given** a feature branch has just been merged via the existing `haleluya`/`/haleluya` flow
(CLAUDE.md's "Finish-Feature Trigger Phrase") — **before any deploy happens** (REQ-REL-001's
corrected ordering, 2026-08-02: cut comes first, deploy is a separate later step, see US3)
**When** the flow reaches its final step, the AI agent MUST ask the human, for each app touched,
whether to cut a release — never silently skip this, never decide the answer itself (REQ-REL-001)
**Then**, if the human says yes for a given app, the agent asks for the **exact target version
string** and waits — it MUST NOT propose, compute, or default one, even as a "recommended, say
yes to accept" suggestion (REQ-REL-002, hard constraint)
**When** the human states the exact version (e.g. "1.4.2")
**Then** the agent runs `scripts/cut_release.sh <app> 1.4.2` (REQ-SCR-001) with that verbatim
value: the `VERSION` file is updated, the Docker image is built and exported as a tarball into the
artifacts folder (REQ-REL-005/REQ-ART-001/002), a `CHANGELOG.md` entry and a `RELEASES.md` section
are appended (REQ-REL-003/004), and the `<app>-v1.4.2` git tag is applied — after one final
interactive confirmation showing exactly what's about to happen, since this action is permanent
(REQ-REL-006). **Cutting itself deploys nothing anywhere** — the artifact just now exists,
ready for US3 to deploy it wherever/whenever separately approved.

**Independent Test**: Fully testable standalone — pick a fixed version/summary, run
`scripts/cut_release.sh` by hand with that exact version, then verify: `git tag` shows the new
`<app>-v<version>` tag on the right commit, `CHANGELOG.md`/`RELEASES.md` have the new entries, and
the artifacts folder has the new tarball + manifest.

Acceptance criteria:
- Skipping the release step for a given app (e.g. a docs-only change touched it) is a valid,
  explicit "no" answer to the mandatory question — not an error state — but the question itself is
  always asked, never silently defaulted either way.
- At no point does the agent state a version number before the human does — not as a suggestion,
  not as a "did you mean," nothing. If the human's answer is ambiguous, the agent asks again rather
  than guessing.
- The git tag is applied to the commit that was actually deployed (per CLAUDE.md's rebuild/
  recreate deploy step), not merely the merge commit on `master` if those differ in timing.
- `CHANGELOG.md`'s new entry is human-written prose summarizing the change (from the merged
  spec/PR), not a raw `git log` dump.
- Running `scripts/cut_release.sh` again for a version that already exists refuses instead of
  overwriting anything (REQ-REL-006).

---

## US3 — Deploy a cut release to an environment (initial deploy, promotion, or rollback) (Priority: P1)

**Corrected 2026-08-02**: this story was originally scoped as "roll back a deployed environment"
only. The user's actual operator flow revealed that deploying a freshly cut version to `dev`,
promoting a validated version from `dev` to `prod`, and rolling back to an older version are **the
same operation** — load a pre-built artifact, redeploy it, verify it — differing only in which
version is named. Re-prioritized to **P1** (it was implicitly always needed just to get a cut
version running at all, not just for the rollback edge case).

**Given** a version has been cut for an app (US2 — a tarball exists in the artifacts folder for
some `<version>`, whether that's the newest one just cut, or an older one being returned to)
**When** a human explicitly asks, in that specific request, to deploy a named app/version to a
named environment — the agent MUST NOT decide on its own that a deploy/promotion/rollback is
warranted, and MUST NOT infer/guess the target version even if "the one just cut" or "the previous
one" seems obvious (REQ-DEPLOY-005, hard constraint) — **and** this is a separate approval from
"start an environment," per the existing CLAUDE.md rule: cutting a version never implies
authorization to deploy it anywhere
**Then** the agent runs `scripts/deploy_release.sh <app> <env> <version>` (REQ-SCR-002), which
loads that version's tarball from the artifacts folder (`docker load`) and redeploys it directly
to the named environment's container — no rebuild from git source, regardless of whether
`<version>` is newer or older than what's currently running there
**Then** the script automatically verifies success (REQ-DEPLOY-002) — polling `/health` until its
`version` matches (morning-mcp-app) or tailing recent logs until the version marker appears
(denidin-app) — and only reports the deploy as done once that check passes, reporting failure
(with the container's actual observed state) if it doesn't
**Then** the environment now serves the deployed version — independently verifiable the same way
as US1 (`/health` field or any log line) — and no `master` git history was reverted/rewritten to
get there (REQ-DEPLOY-004), and the redeployed bytes are guaranteed identical to what was
originally cut (no dependency-resolution drift, since nothing was rebuilt).

**Independent Test**: Fully testable standalone, covering all three shapes of this one story:
1. **Initial deploy**: cut release A (US2), deploy A to `dev`, confirm A is live (US1 check +
   the deploy's own automatic verification).
2. **Promotion**: with A live on `dev`, deploy A to `prod`, confirm A is live on `prod` too, while
   `dev` is untouched (still A, or whatever it's since moved to — dev/prod versions are
   independent, REQ-VER-004).
3. **Rollback**: cut release B, deploy B to `dev` (dev now ahead of prod, the normal case per
   REQ-VER-004), then deploy **A** back to `dev`, confirm A is live again, confirm `master`'s
   commit history is unchanged (`git log master` before/after matches) throughout all three.

Acceptance criteria:
- The deploy/rollback procedure is discoverable in documentation (REQ-DOC-001) without needing to
  ask the person who last deployed.
- No `docker ... build` (or equivalent rebuild step) runs as part of any deploy, promotion, or
  rollback — only `docker load` of the already-exported tarball (REQ-REL-005) plus redeploying it.
- The agent never states or suggests a version, environment, or "should we deploy this" before the
  human has said so explicitly, in that request — applies identically whether it's an initial
  `dev` deploy, a `prod` promotion, or a rollback.
- The deploy is only reported successful once its own automatic health/version check passes
  (REQ-DEPLOY-002) — a container that merely started, without the check passing, is a **failed**
  deploy, reported as such.
- Deploying to one app/environment (e.g. `denidin-app-prod`) does not require touching the other
  app or the other environment — matches the existing per-app, per-environment deploy granularity
  documented under "Environments (dev/prod)" — and `dev`/`prod` are expected to often be on
  different versions at any given time (REQ-VER-004), not treated as a drift/inconsistency to fix.
- The deploy leaves a discoverable record of what happened equivalent to any other deploy (i.e.
  it's not a silent, undocumented change).
- If the needed release tarball is no longer present in the artifacts folder (e.g. manually
  deleted — REQ-REL-005/REQ-ART-001 intentionally leave retention/cleanup as a manual decision),
  `scripts/deploy_release.sh` fails clearly rather than silently falling back to a rebuild; this
  is an accepted tradeoff of "no container registry" (see spec.md's Explicitly Out of Scope), not
  a bug.

---

## US4 — Ask the bot its own version over WhatsApp (Priority: P3)

**Given** `denidin-app` is running with some current version (any role able to get a reply from
the bot at all — see spec.md's Assumptions on REQ-VER-005)
**When** a user asks a natural-language question like "what version are you running?" or "אתה
בגרסה מה?"
**Then** the model answers accurately with the current `denidin-app` version, sourced from the
same per-call injection mechanism already used for today's date (`ai_handler.py:363-368`) — no
guessing, no stale cached value from earlier in a long conversation.

**Independent Test**: Fully testable standalone — set a known `VERSION` file value, send a real
"what version are you" webhook message, assert the reply states that exact version.

Acceptance criteria:
- Works the same regardless of role (client/godfather/admin) — this is not gated behind Morning
  MCP tool attachment or any existing RBAC boundary.
- The answer reflects the version at reply time, not whatever version was current when the
  session/conversation started (relevant if a release happens mid-conversation, however unlikely).
- Does not require a new MCP tool or Morning integration — this is purely a prompt-injection
  addition, the same pattern as current-date, not a callable tool the model invokes.

---

## Out of Scope for This Feature

- **Any AI-computed version number, including bump-type classification** (MAJOR/MINOR/PATCH
  parsed from commit messages/PR titles) — US2's exact version string is always human-stated
  verbatim; the agent never even offers a bump-type shortcut to compute from.
- **A single shared version number across both apps** — resolved via clarification; independent
  per-app versioning is confirmed (`spec.md`'s Clarifications section).
- **Automated/zero-downtime deploy or rollback** — US3's deploy/promotion/rollback is a manual,
  human-triggered redeploy of a pre-built release image (REQ-REL-005/REQ-DEPLOY-001), not an
  automated mechanism that decides for itself when to deploy or roll back.
- **A dedicated RBAC story** — US4 is deliberately ungated rather than restricted; nothing here
  changes who can talk to the bot or what Morning tools they can call.
- **Versioning any change that doesn't ship to a real environment** (e.g. work still on a feature
  branch, not yet merged/deployed) — release/version bumps happen at `haleluya` time, not per
  commit.
- **Any story where the AI agent picks a version/environment or decides to release/deploy/roll
  back on its own** — deliberately not a story, permanently, per REQ-REL-002/REQ-DEPLOY-005. Every
  US2/US3 flow above requires the human to state the app/version/environment first, in that
  specific request.
- **A separate "rollback script"** — merged into US3/`scripts/deploy_release.sh` 2026-08-02 once
  it became clear rollback is mechanically identical to an ordinary forward deploy/promotion.
