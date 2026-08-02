# Feature Spec: Versioning & Release Management

**Feature ID**: 034-versioning-release-mgmt
**Priority**: P2 (assumed default — not blocking other work; revisit if the user wants this elevated)
**Status**: Tasks Generated (spec + user-stories + plan/research/data-model/contracts/quickstart + tasks.md complete 2026-08-02; ready for `/speckit.analyze`)
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
- **Any AI-computed or AI-suggested version number**, whether via bump-type classification (MAJOR/
  MINOR/PATCH parsed from commit messages/PR titles) or any other heuristic. The exact version
  string is always supplied verbatim by a human, every time — REQ-REL-002 is a hard constraint,
  not a default-with-override.
- **CI/CD pipeline changes.** This project has no automated build/deploy pipeline today (deploys
  are the manual rebuild-and-recreate steps documented under "Environments (dev/prod)" in
  CLAUDE.md); this feature does not introduce one. Release automation here means scripting/
  documenting the manual steps, not standing up CI.
- **Zero-downtime or automated rollback.** Rollback stays a manual, documented procedure (redeploy
  a prior release's pre-built, version-tagged image — see REQ-ROLL-002), not an automated
  blue-green mechanism or a script that triggers itself.
- **Versioning `apps/morning-mcp-app`'s Morning/Green Invoice API integration itself** (that's a
  third-party API DeniDin doesn't control) — only this repo's own two apps are in scope.
- **Automated retention/pruning policy for old release images.** REQ-REL-005 requires retaining
  version-tagged images so rollback (REQ-ROLL-002) can always redeploy without rebuilding, but
  disk-space cleanup of old release images stays a manual, human-judgment decision (consistent
  with this project's existing manual container-lifecycle operations, e.g.
  `scripts/killall_containers.sh`) — no automatic garbage collection is introduced.
- **A container registry.** Release images (REQ-REL-005) are exported as tarballs into the shared
  artifacts folder (REQ-ART-001) instead, matching how this project already builds/runs everything
  locally — no push to a remote registry (Docker Hub, ECR, etc.) is in scope.
- **Any AI-initiated release or rollback.** Both `scripts/cut_release.sh` and
  `scripts/rollback_release.sh` may only ever be run with human-supplied app/version/environment
  arguments in that specific request (REQ-REL-002, REQ-ROLL-004) — an AI agent deciding on its own
  that "this seems like a good time to cut a release" or "this looks like it needs a rollback" is
  explicitly out of scope, permanently, not just for this feature's v1.

## Functional Requirements

### Version tagging

- **REQ-VER-001**: Each app (`denidin-app`, `morning-mcp-app`) MUST have its own current semantic
  version (`MAJOR.MINOR.PATCH`), stored in a single git-tracked source of truth per app (not an
  environment variable, per CONSTITUTION §I) — e.g. a `VERSION` file at each app's root.
- **REQ-VER-002**: `apps/morning-mcp-app`'s existing `/health` endpoint (`server.py:76-82`) MUST
  include the app's current version in its JSON response, alongside the existing `status`/
  `environment` fields.
- **REQ-VER-003**: **Every** log line in **both** apps (not just a startup line) MUST include the
  app's current version — e.g. as a prefix/field on each line, consistent with each app's existing
  log line format. Applies to `apps/denidin-app`'s `logs/denidin.log` and
  `apps/morning-mcp-app`'s equivalent log output alike.
- **REQ-VER-004**: The version is a per-app fact, not per-environment — `dev` and `prod` for the
  same app may run *different* versions at different times (that's normal during a dev→prod
  promotion), but there is exactly one version concept per app, not one per environment.
- **REQ-VER-005**: `apps/denidin-app` MUST be able to answer a user's question about its own
  running version over WhatsApp (e.g. "what version are you running?") in normal conversation —
  implemented the same way current-date is already injected into `AIHandler`'s `instructions` per
  call (`ai_handler.py:363-368`), so the model can answer accurately instead of guessing.
  **Assumption**: not newly RBAC-gated — any role that can otherwise get a reply from the bot at
  all can ask this; existing role-based access (e.g. blocked users get no reply) is unchanged,
  since this is non-sensitive operational information, unlike Morning-tool access.

### Release process automation

- **REQ-REL-001**: The existing `haleluya`/`/haleluya` finish-feature flow (CLAUDE.md, "Spec-Driven
  Workflow") MUST gain a mandatory release prompt as its final step: after merge + deploy, for
  each app touched by that work, **always ask the human** whether to cut a release for that app —
  never silently skip this question, and never decide the answer.
- **REQ-REL-002** 🚨 **HUMAN-ONLY, HARD CONSTRAINT**: If the human says yes to cutting a release
  for an app, the AI agent MUST then ask the human for the **exact target version string**
  (e.g. "1.4.2") — it MUST NOT compute, suggest, default, or recommend a version number itself,
  not even as a "recommended, just say yes to accept" suggestion (unlike ordinary clarifying
  questions elsewhere in this workflow). The agent supplies the human-stated version verbatim to
  `scripts/cut_release.sh` (REQ-SCR-001) and nothing else. This applies with no exceptions, every
  single time — approval for one release never carries over to the next.
- **REQ-REL-003**: Each app's release changelog (`CHANGELOG.md` at that app's root) MUST gain one
  entry per release: version, date, and a short human-readable summary of what changed — sourced
  from the merged PR(s)/spec(s) since the last release, not auto-generated from raw git log.
- **REQ-REL-004**: Release notes (a longer-form, user-facing description of a release) MUST be
  captured in a git-tracked `RELEASES.md` file at each app's root, one section per release
  (version, date, longer-form notes) — separate from the terser `CHANGELOG.md` (REQ-REL-003),
  which stays a short one-line-per-release summary list. No GitHub Releases dependency.
- **REQ-REL-005**: Cutting a release MUST build that app's Docker image, tag it with the release
  version (e.g. `denidin-app:<version>`, `morning-mcp-app:<version>`), export it with `docker save`
  into the shared artifacts folder (REQ-ART-001) as `<app>-v<version>.tar`, and write an
  accompanying manifest (REQ-ART-002) — this tarball, not just the local Docker image cache, is
  the durable artifact future rollbacks load from (REQ-ROLL-002). Ordinary forward deploys during
  normal dev iteration are unaffected and keep using the existing rebuild-and-recreate flow
  (CLAUDE.md, "Environments (dev/prod)") — REQ-REL-005 only adds a durable, exported artifact *in
  addition to* that, at release time specifically.
- **REQ-REL-006** 🚨 **IMMUTABILITY, HARD CONSTRAINT**: Once a version is cut (REQ-SCR-001 has run
  successfully for it), it is permanently frozen — its release image tarball, git tag, `CHANGELOG.md`
  entry, and `RELEASES.md` entry MUST NOT be modified, overwritten, or re-generated afterward, and
  no later commit may retroactively be considered part of that version. `scripts/cut_release.sh`
  MUST refuse to run again for a version that already exists (matching tag/tarball/manifest found).
  A bug found in a cut version is fixed by cutting a **new** version, never by mutating the old one
  — consistent with this project's existing git safety rules (no force-push, no history rewriting).

### Rollback / release history

- **REQ-ROLL-001**: For each environment (`dev`/`prod`) of each app, the currently-deployed
  version MUST be discoverable after the fact — via REQ-VER-002/003 (live `/health` or logs), via
  the git tag history (REQ-REL-001), and via which release tarballs are still present in the
  artifacts folder (REQ-REL-005/REQ-ART-001) — without needing tribal knowledge of "what we last
  deployed."
- **REQ-ROLL-002**: `scripts/rollback_release.sh` (REQ-SCR-002) implements rollback by loading the
  version's tarball (`docker load`) from the shared artifacts folder (REQ-ART-001) and redeploying
  that exact image to the affected environment's container — rollback MUST NOT rebuild from git
  source. This is a deliberate departure from the ordinary forward-deploy flow (which does rebuild,
  per CLAUDE.md's "Environments (dev/prod)") specifically so a rollback is guaranteed to reproduce
  the exact bytes that were previously running, immune to dependency-resolution drift over time.
- **REQ-ROLL-003**: Rollback MUST NOT require reverting or rewriting git history on `master` —
  it operates by redeploying an older tagged image into a running container, leaving `master`'s
  own history untouched (consistent with this project's git safety rules: no force-push, no
  history rewriting).
- **REQ-ROLL-004** 🚨 **HUMAN-ONLY, HARD CONSTRAINT**: `scripts/rollback_release.sh` MUST only be
  invoked with an app, environment, and target version **explicitly supplied by the human in that
  specific request** — the AI agent MUST NOT decide on its own initiative to roll back, and MUST
  NOT infer/guess/default the target version (e.g. "the previous one") even if that seems obvious
  from context. Approval to roll back once does not carry over to a later rollback.

### Scripts

- **REQ-SCR-001**: A `scripts/cut_release.sh <app> <version>` script MUST exist, callable only
  with an app and an explicit version both required as arguments (no defaults, no "latest bump"
  shorthand). It performs, atomically enough that a failure partway through doesn't leave a
  half-cut release masquerading as complete: update that app's `VERSION` file, build the Docker
  image, `docker save` it into the artifacts folder (REQ-REL-005), write the manifest
  (REQ-ART-002), append `CHANGELOG.md`/`RELEASES.md` entries, commit those file changes, and apply
  the `<app>-v<version>` git tag. Refuses to run if that exact version already exists
  (REQ-REL-006). Prompts for an interactive final confirmation before doing anything irreversible
  (the git tag / artifact export), so a typo'd version string can still be caught.
- **REQ-SCR-002**: A `scripts/rollback_release.sh <app> <env> <version>` script MUST exist,
  callable only with an app, environment (`dev`/`prod`), and explicit target version all required
  as arguments. It loads that version's tarball from the artifacts folder (`docker load`) and
  redeploys it to the named environment's running container for that app — no rebuild, no
  guessing the target version. Fails clearly (not silently) if the requested version's tarball
  isn't found in the artifacts folder.

### Artifacts Storage

- **REQ-ART-001**: Release artifacts (image tarballs + manifests) live in one canonical,
  hardcoded-path artifacts folder shared identically across every clone (root `DeniDin`, `coder1`,
  `coder2`, ...) on the machine — e.g. `/Users/yaron/Projects/DeniDin/artifacts/` — laid out as
  `artifacts/<app>/<app>-v<version>.tar` (+ manifest, REQ-ART-002). This mirrors the existing
  cross-clone shared-state precedent (`shared/` symlink + `config/shared_state.local.json` for
  env-lock state; `docker/docker-compose.*.local.yml` for dev/prod data volumes) rather than
  fragmenting release artifacts per clone.
- **REQ-ART-002**: Each release's tarball MUST be accompanied by a small JSON manifest
  (`<app>-v<version>.json` alongside the `.tar`) recording at minimum: `app`, `version`, `date`,
  `git_commit` (the deployed commit the release was cut from), and the Docker image ID/digest —
  enough for a human (or `scripts/rollback_release.sh`) to identify and verify an artifact without
  needing to inspect the tarball's contents.

### Internal documentation

- **REQ-DOC-001**: CLAUDE.md MUST document the versioning scheme (where `VERSION` lives per app,
  tag naming convention, changelog/release-notes/artifacts locations, and the two scripts) so it's
  discoverable the same way every other cross-cutting convention in this repo is.
- **REQ-DOC-002** 🚨: CLAUDE.md MUST carry a dedicated, prominent hard-constraint banner (matching
  the style of its existing "AI AGENTS: NEVER START AN ENVIRONMENT..." section) stating the
  human-only release-authority rule (REQ-REL-002, REQ-ROLL-004) and immutability rule
  (REQ-REL-006) as binding on any AI agent working in this repo — **added immediately, 2026-08-02,
  ahead of the rest of this feature's implementation**, since it governs agent behavior starting
  now, not only once the full feature ships. The `haleluya` finish-feature definition (CLAUDE.md +
  `.github/METHODOLOGY.md` "Finish-Feature Trigger Phrase") MUST also be updated to reference the
  new mandatory release-prompt step (REQ-REL-001), so it's covered by the existing trigger-phrase
  shorthand rather than a second, separate command to remember.

## Assumptions

Reasonable defaults applied where no explicit user direction was given, documented here per
`speckit.specify`'s "document assumptions" guidance:

- **Priority: P2.** Not specified by the user; assumed non-blocking/normal priority since this is
  operational tooling, not a user-facing bug or urgent need. Revisit if the user wants it
  elevated or demoted.
- **Semantic versioning (`MAJOR.MINOR.PATCH`).** Standard scheme, matches the one prior precedent
  in this repo (`v1.0.0`) and industry convention; not explicitly requested but no reasonable
  alternative exists for this kind of feature.
- **Tag naming `<app>-v<version>`** (e.g. `denidin-app-v1.4.2`). Chosen to disambiguate the two
  independently-versioned apps in one shared git history — a bare `v1.4.2` tag would be ambiguous
  as to which app it refers to now that independent per-app versioning is confirmed.
- **Whether to cut a release is a per-`haleluya`-run yes/no the human answers each time**
  (REQ-REL-001) — not every merge (e.g. docs-only changes) needs a release, but the question is
  always asked, never silently skipped and never answered by the AI agent itself.
- **`apps/denidin-app`'s version-query answer (REQ-VER-005) is not RBAC-gated.** Assumed since
  it's non-sensitive operational info, unlike Morning-tool access — flag if this should actually
  be restricted to godfather/admin instead.
- **The artifacts folder's exact path is `/Users/yaron/Projects/DeniDin/artifacts/`** (sibling to
  the `DeniDin`/`coder1`/`coder2` clones, matching the existing shared-state precedent) —
  confirmed by the user 2026-08-02.

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
- **release image**: The Docker image built and tagged with a release's `semantic_version` at
  release time (REQ-REL-005), exported as a `.tar` into the artifacts folder as the exact artifact
  rollback (REQ-ROLL-002) loads and redeploys — distinct from the untagged/`latest`-style images
  produced by ordinary forward rebuild-and-recreate deploys.
- **artifacts folder**: The single, hardcoded-path, cross-clone-shared directory (REQ-ART-001)
  holding every cut release's tarball + manifest, for every app.
- **release manifest**: The small JSON file (REQ-ART-002) accompanying each release tarball,
  recording `app`/`version`/`date`/`git_commit`/image ID — the human-readable index into the
  artifacts folder.

## Success Criteria

- **SC-001**: Given a running `morning-mcp-app` container (dev or prod), a human can determine its
  exact deployed version with a single `curl /health` call, without SSH/docker exec.
- **SC-002**: Given `logs/denidin.log` for a running `denidin-app` container, a human can determine
  its exact deployed version by reading any single log line (not just at startup), without needing
  the source tree.
- **SC-003**: Given a need to roll back either app in either environment, a human can find the
  documented procedure (REQ-ROLL-002) and the specific prior version to roll back to (via git tags
  + changelog) without asking anyone else, and the rollback completes by redeploying a pre-built
  image — no rebuild step, no risk of a dependency-resolution drift changing the result.
- **SC-004**: Every release since this feature ships has a corresponding changelog entry and a
  git tag — verifiable by `git tag -l '<app>-v*'` matching `CHANGELOG.md` entries 1:1 per app.
- **SC-005**: Every past AI-agent transcript that cut a release or rolled back shows the agent
  asking for (never stating first) the app, version, and (for rollback) environment — verifiable
  by inspecting the conversation that preceded any `scripts/cut_release.sh`/
  `scripts/rollback_release.sh` invocation.
- **SC-006**: Attempting to re-cut an already-existing `<app>-v<version>` fails loudly (REQ-REL-006)
  rather than silently overwriting it — verifiable by running `scripts/cut_release.sh` twice with
  the same arguments and confirming the second call refuses.

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
- Q: Does rollback (REQ-ROLL-002) rebuild from the tagged git commit, or redeploy a pre-saved
  artifact? Raised because rebuilding from an old commit risks dependency-resolution drift
  (`requirements.txt` isn't pinned to exact versions in either app today), undermining the
  guarantee that a rollback actually reproduces what was previously running. → A: **Rollback MUST
  deploy a pre-saved version, not build anything.** Added REQ-REL-005: cutting a release now also
  builds and retains a version-tagged Docker image (the "release image") as a durable artifact;
  REQ-ROLL-002 rewritten so rollback redeploys that saved image directly, with no rebuild step at
  rollback time — this sidesteps the dependency-drift risk entirely rather than mitigating it via
  a lockfile. Also added two new Explicitly-Out-of-Scope bullets (no automated image-retention
  policy; no container registry — images stay on the local Docker host, consistent with how this
  project already runs everything locally).

### Session 2026-08-02 (continued — user-initiated, not agent-prompted)

The user proactively raised several requirements the agent's first taxonomy scan missed —
recorded here in the same format even though the agent didn't ask for these directly, since they
resolve real ambiguity the same way a clarify-loop answer would:

- Q (user-raised): Should log lines include the version once at startup, or on every line? → A:
  **Every log line, both apps** (REQ-VER-003, rewritten — previously said startup-only, which was
  an unasked assumption the agent should have flagged instead of defaulting silently).
- Q (user-raised): Once a version is cut, can later commits or fixes still be considered part of
  it? → A: **No — immutable.** A cut version is permanently frozen (REQ-REL-006); any fix requires
  a new version, never mutating an existing one.
- Q (user-raised): Should the AI agent ever pick, suggest, or default a version number, or decide
  on its own to cut a release / roll back? → A: **Absolutely not, no exceptions, enforced as a
  hard constraint** (REQ-REL-001/002, REQ-ROLL-004) — always ask explicitly after `haleluya`
  whether to release each touched app, always ask for the exact version string verbatim, never
  compute or suggest one. This is elevated beyond spec-level documentation: **CLAUDE.md's binding
  AI-agent rules were updated in this same session** (see REQ-DOC-002) so this takes effect
  immediately, not only once this feature is implemented.
- Q (user-raised): Should the WhatsApp bot be able to answer "what version are you"? → A: **Yes**
  (REQ-VER-005), assumed ungated by RBAC (see Assumptions).
- Q (user-raised): Should release/rollback be scripted, or stay purely manual/documented? → A:
  **Scripted** — `scripts/cut_release.sh <app> <version>` and
  `scripts/rollback_release.sh <app> <env> <version>` (REQ-SCR-001/002), both requiring explicit
  human-supplied arguments, never invoked with agent-inferred values.
- Q (user-raised): Where do release artifacts (images) live? → A: **A shared, hardcoded-path
  `artifacts/` folder accessible from every clone** (REQ-ART-001), not per-clone, not a registry —
  storing exported image tarballs + manifests (REQ-ART-002), superseding the earlier "retained in
  the local Docker image cache" language from the prior session's REQ-REL-005/REQ-ROLL-002, which
  is now built on top of this artifacts-folder mechanism instead.

### Session 2026-08-02 (final confirmation)

- Q: Is `/Users/yaron/Projects/DeniDin/artifacts/` the correct artifacts folder path? → A:
  **Confirmed correct as-is.**

No open `[NEEDS CLARIFICATION]` markers remain.

### Clarification Coverage Summary (speckit.clarify taxonomy scan, 2026-08-02)

| Category | Status |
|---|---|
| Functional Scope & Behavior | Clear |
| Domain & Data Model | Clear |
| Interaction & UX Flow | Clear (single-operator release/rollback flow, no concurrency concern at this project's scale) |
| Non-Functional: Reliability & Availability | Resolved (rollback reproducibility — this session) |
| Non-Functional: Observability | Resolved (per-line logging + WhatsApp version query — user-raised, this session; initially mis-marked Clear on a too-shallow first pass) |
| Non-Functional: other (perf/scale/security/compliance) | Clear — not applicable to this feature |
| Integration & External Dependencies | Clear |
| Edge Cases & Failure Handling | Clear (missing-VERSION-file handled in US1; low-impact items deferred to planning) |
| Constraints & Tradeoffs | Clear (no env vars; GitHub Releases vs. `RELEASES.md` — this session; shared vs. per-app version — this session) |
| Terminology & Consistency | Clear (Key Entities section) |
| Completion Signals | Clear (Success Criteria + per-story acceptance criteria) |

3 agent-prompted questions asked and answered (well under the 5-question quota that applies to
agent-initiated clarify questions), plus 6 further requirements the user raised unprompted (not
counted against that quota — user-initiated clarification isn't subject to the same 5-question
cap). No Outstanding or Deferred high-impact categories remain — ready for `/speckit.plan`.

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
- `apps/denidin-app/requirements.txt`, `apps/morning-mcp-app/requirements.txt` — neither pins
  exact dependency versions today; the reason REQ-ROLL-002 requires rollback to redeploy a
  pre-built image (REQ-REL-005) rather than rebuild from an old git tag.
- `apps/denidin-app/src/handlers/ai_handler.py:363-368` — existing current-date injection into
  `instructions`, the precedent REQ-VER-005's version-query capability follows.
- CLAUDE.md's "Multi-clone lock" / "dev/prod data is also a singleton across clones" sections —
  existing precedent (`shared/` symlink, `config/shared_state.local.json`,
  `docker/docker-compose.*.local.yml`) for one canonical cross-clone-shared path, the pattern
  REQ-ART-001's artifacts folder follows.
- CLAUDE.md's "AI AGENTS: NEVER START AN ENVIRONMENT OR EDIT CONFIG WITHOUT EXPLICIT APPROVAL"
  banner — the existing hard-constraint style/precedent REQ-DOC-002's new version/release banner
  matches.
