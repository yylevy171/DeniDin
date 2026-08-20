# Implementation Plan: Versioning & Release Management — Feature 034

**Feature**: 034-versioning-release-mgmt
**Branch**: `feature/034-versioning-release-mgmt`
**Spec**: `./spec.md` · **User stories**: `./user-stories.md`
**Status**: Corrected post-analyze (deploy/rollback unified, 2026-08-02) — Ready for Task Generation update
**Updated**: August 2, 2026

**Compliance**: CONSTITUTION.md (§I no env vars — `VERSION`/`CHANGELOG.md`/`RELEASES.md`/manifest
are all plain git-tracked or artifact-folder files, never env vars; §II UTC — all dates in
changelog/release/manifest entries are UTC `YYYY-MM-DD`; §III git workflow — feature branch,
merge commits, no force-push/history rewriting even for rollback; §XVII no monkey-patching —
logging changes are a `logging.Filter` + formatter-string change in the existing shared
`utils/logger.py`, not runtime patching) and METHODOLOGY.md (§I spec-first, §VII integration
contracts — see below, adapted for this feature's non-webhook shape). No feature flag: this is
new observability/tooling with no existing behavior to gate — every change is additive (new
`version` field on `/health`, new log format, new files, new scripts), except the `haleluya`
flow gaining a new mandatory step, which is a process change, not application behavior.

---

## Summary

Give `denidin-app` and `morning-mcp-app` independent semantic versions with zero silent
AI-agent involvement in choosing them. A `VERSION` file per app is the source of truth, surfaced
via `/health` (morning-mcp-app), every log line (both apps, via a shared `logging.Filter` in each
app's existing centralized `utils/logger.py`), and a WhatsApp-answerable question (denidin-app,
via the same per-call `instructions`-injection pattern already used for today's date). The real
operator flow (confirmed 2026-08-02): merge → `haleluya` asks whether to **cut** a release
(`scripts/cut_release.sh`, produces an artifact, deploys nothing) → separately-approved **deploy**
of that artifact to `dev` → UAT → separately-and-later-requested **promotion** of the same
artifact to `prod`. Rolling back turns out to be the *same* operation as deploying/promoting —
loading a pre-built artifact into a container — just with an older version named
(`scripts/deploy_release.sh <app> <env> <version>`, one script for all three cases). Both scripts
require every argument (app, version, and for deploy, environment) supplied explicitly by a
human, enforced procedurally (CLAUDE.md hard-constraint banner, added immediately ahead of this
plan) since a shell script cannot itself verify who typed an argument — and every deploy also
falls under the pre-existing CLAUDE.md "never start an environment without approval" rule, since
it recreates a running container. Releases are immutable once cut and are stored as portable,
`docker save`d tarballs + JSON manifests in a shared, cross-clone artifacts folder — not a
container registry, not the local Docker image cache alone — so no deploy (forward, promotion, or
rollback) ever needs to rebuild from source (sidestepping dependency-resolution drift, since
neither app pins exact dependency versions today), and every deploy automatically verifies its
own success via health/version checks before reporting done.

## Technical Context

- **Language/Version**: Python 3.9 (`denidin-app`) / 3.11 (`morning-mcp-app`), unchanged. New
  scripts are Bash (matching every existing `scripts/*.sh`/`run_*.sh`/`stop_*.sh` in this repo).
- **Primary Dependencies**: none new for either app's Python code (stdlib `logging`, `pathlib`,
  `json` only). Scripts depend on `docker`, `git`, and `curl` (for `deploy_release.sh`'s
  morning-mcp-app health-poll verification) — all already available in this project's tooling.
- **Storage**: `VERSION`/`CHANGELOG.md`/`RELEASES.md` (git-tracked, one set per app); release
  tarballs + manifests in the shared artifacts folder (outside any single clone's exclusive
  ownership — see research.md Decision 7, resolved as user-owned).
- **Testing**: unit tests for the logging filter/formatter change and the `/health`/`AIHandler`
  version-surfacing (both apps' `tests/unit/`); a `billed`-tier real-API E2E test for US4 (WhatsApp
  version query — text-only OpenAI call, same tier as Feature 030's contact-card tests, per
  Feature 029's `billed`/`expensive` split); script-level tests for `cut_release.sh`/
  `deploy_release.sh` that exercise them against a scratch git repo + throwaway Docker
  build/tag (not the real apps' images) so tests don't mutate this repo's real tags/artifacts
  folder, including `deploy_release.sh`'s automatic verification step against a scratch
  stand-in container.
- **Target Platform**: existing containerized runtime for both apps, unchanged; scripts run on
  the host (matching every other `scripts/*.sh` in this repo — they orchestrate Docker, they
  don't run inside a container themselves).
- **Constraints**: no env vars; UTC for all dates; no monkey-patching; friendly errors N/A (this
  is operator/agent-facing tooling, not end-user error messages, except US4's WhatsApp reply which
  reuses existing friendly-reply infrastructure unchanged); tests immutable once approved;
  REQ-REL-002/REQ-DEPLOY-005 (human-only) and REQ-REL-006 (immutability) are hard constraints, not
  ordinary requirements — any task implementing them must be verifiably testable (e.g. a test
  asserting `cut_release.sh` refuses without both positional args, refuses on a duplicate version,
  and never runs interactively-unattended past the confirmation prompt).

## Constitution Check (pre-Phase 0)

- **No env vars** — PASS: every new value (`VERSION`, changelog/release entries, manifest fields,
  artifacts folder path) lives in a git-tracked file, a script constant, or a generated artifact —
  never `os.getenv`.
- **UTC** — PASS, with an explicit gap closed post-`/speckit.analyze` (finding C1): `cut_release.sh`
  MUST use `date -u` (UTC), not the shell's local time, for every `CHANGELOG.md`/`RELEASES.md`/
  manifest date it writes — T010a (tasks.md) MUST assert this under a non-UTC `TZ`, not just trust
  the script's intent.
- **Feature branch** — PASS: `feature/034-versioning-release-mgmt`.
- **Feature flags** — N/A: additive-only application changes (see Summary); the `haleluya`
  process change isn't application code, so feature-flag gating doesn't apply to it.
- **Real-sandbox tests / ZERO-MOCKING** — MUST ADHERE: US4's WhatsApp version-query test is a
  real-API `billed` E2E test (real OpenAI Responses API call), no mocking. Script-level tests for
  `cut_release.sh`/`deploy_release.sh` use a real (scratch, throwaway) git repo and real `docker
  build`/`save`/`load` — no mocking of `git`/`docker` subprocess calls either, consistent with
  this project's "mock only third-party network services" rule (git/Docker are local tools, not
  network services).
- **No monkey-patching** — PASS: logging change is a `Filter` + formatter string in the existing
  shared setup function; `/health`/`AIHandler` changes follow existing closure/injection patterns
  already in those files.
- **Test immutability (§VIII)** — no existing test changes; this feature only adds new tests and
  new (previously-nonexistent) files/scripts/log format.
- **Human-only hard constraints (REQ-REL-002/006, REQ-DEPLOY-005)** — already partially enforced
  *outside* code, via the CLAUDE.md banner added 2026-08-02 (this governs the AI agent's own
  behavior when invoking these scripts in any future session, independent of what the scripts
  themselves can check). The scripts add defense-in-depth (required positional args, no defaults,
  interactive confirmation, immutability refusal) but the ultimate enforcement is procedural, and
  the plan/tasks phases must not attempt to over-engineer a technical "prove a human typed this"
  mechanism that doesn't actually exist for a CLI script.
- **Deploy needs two separate approvals, not one** — every `deploy_release.sh` call both (a)
  needs a human-supplied app/env/version (REQ-DEPLOY-005) *and* (b) falls under the pre-existing
  CLAUDE.md "never start an environment without approval" rule (it recreates a running container).
  Neither approval substitutes for the other; both apply to every call.

## Integration Contracts (METHODOLOGY §VII)

This feature has no webhook/router surface — its "integration contracts" are: two CLI scripts,
one extended HTTP response, one extended prompt-injection point, and one shared artifacts-folder
layout. See `contracts/` for the full CLI/JSON contracts; summarized here:

### `scripts/cut_release.sh` ↔ human/agent caller

See `contracts/cut_release_cli.md`. **MUST** require `<app> <version>` as required positional
args with no defaults; refuse a duplicate version; require interactive confirmation before any
irreversible step. **MUST NOT** deploy anywhere — cutting only produces the artifact.

### `scripts/deploy_release.sh` ↔ human/agent caller

See `contracts/deploy_release_cli.md`. One script for initial `dev` deploy, `dev`→`prod`
promotion, and rollback alike (research.md Decision 9). **MUST** require `<app> <env> <version>`
as required positional args with no defaults; never rebuild from source; fail clearly if the
requested artifact is missing; automatically verify success (REQ-DEPLOY-002) before reporting
done.

### `apps/morning-mcp-app`'s `/health` ↔ callers (extended, existing contract)

See `contracts/health_response.schema.json`. **MUST** remain backward compatible — `status`/
`environment` unchanged, `version` additive only. Also now the automated-verification target
`deploy_release.sh` polls after redeploying morning-mcp-app.

### `VERSION` file ↔ artifacts folder ↔ release manifest (new)

See `data-model.md`. **MUST** keep `VERSION`/git tag/manifest `version` field/artifact filename
all in agreement for any given release — `deploy_release.sh` validates this at load time
(REQ-ART-002's validation rule).

### `ai_handler.py`'s `instructions` assembly ↔ model (extended, existing contract)

**`AIHandler` MUST**: append the current `denidin-app` version to the same per-call dynamic
block where today's date is already appended after the constitution + `---` separator
(`ai_handler.py:363-368`) — preserving the existing prompt-caching-friendly ordering (stable
constitution prefix first, dynamic content after). **Zero changes** to the constitution file
itself or to the caching-relevant ordering CLAUDE.md documents.

## Project Structure

### Documentation (this feature)

```text
specs/in-progress/034-versioning-release-mgmt/
├── spec.md                         # done, clarified, corrected post-analyze (2026-08-02)
├── user-stories.md                 # done, clarified, corrected post-analyze (US1-US4)
├── checklists/requirements.md      # done
├── plan.md                         # this file
├── research.md                     # Phase 0 output
├── data-model.md                   # Phase 1 output
├── contracts/                      # Phase 1 output
│   ├── health_response.schema.json
│   ├── release_manifest.schema.json
│   ├── cut_release_cli.md
│   └── deploy_release_cli.md       # renamed from rollback_release_cli.md, 2026-08-02
└── quickstart.md                   # Phase 1 output
```
(`tasks.md` is Phase 2 output — `/speckit.tasks`, not produced by this command — also needs its
own post-analyze corrections to match, see spec.md's latest Clarifications entry.)

### Source Code

```text
apps/denidin-app/VERSION                    # NEW - plain text, e.g. "1.0.0"
apps/denidin-app/CHANGELOG.md               # NEW - append-only, data-model.md shape
apps/denidin-app/RELEASES.md                # NEW - append-only, data-model.md shape
apps/denidin-app/src/utils/logger.py
  # + VersionFilter (logging.Filter subclass), reads VERSION once at module import
  # + formatter string: add "[v%(version)s]" (research.md Decision 1)
apps/denidin-app/src/handlers/ai_handler.py
  # ai_handler.py:363-368 area: append current version to the per-call dynamic
  # instructions block, same pattern as today's-date injection (research.md Decision 4)

apps/morning-mcp-app/VERSION                # NEW
apps/morning-mcp-app/CHANGELOG.md           # NEW
apps/morning-mcp-app/RELEASES.md            # NEW
apps/morning-mcp-app/src/denidin_mcp_morning/utils/logger.py
  # + VersionFilter, formatter string change - mirrors denidin-app's logger.py exactly
apps/morning-mcp-app/src/denidin_mcp_morning/server.py
  # server.py:71-82 (_build_health_handler/_health): read VERSION once at startup,
  # add "version" to the existing JSONResponse (research.md Decision 3)

scripts/cut_release.sh                      # NEW - contracts/cut_release_cli.md
scripts/deploy_release.sh                   # NEW - contracts/deploy_release_cli.md
  # one script for: initial dev deploy, dev->prod promotion, rollback (all identical
  # mechanically - research.md Decision 9); includes automatic post-deploy verification
  # (REQ-DEPLOY-002) via /health polling (morning-mcp-app) or log-tail (denidin-app)

CLAUDE.md
  # 🚨 human-only version/release/deploy banner - ALREADY ADDED 2026-08-02, ahead of this plan
  # + REQ-DOC-001: document VERSION/tag/changelog/artifacts-folder scheme (still to do)

.github/METHODOLOGY.md
  # "Finish-Feature Trigger Phrase" section: reference the new mandatory release-prompt
  # step (REQ-REL-001/REQ-DOC-002) so haleluya's shorthand covers it

apps/denidin-app/tests/unit/
  # + tests for VersionFilter / formatter output
  # + tests for AIHandler's version-in-instructions injection

apps/morning-mcp-app/tests/unit/
  # + tests for VersionFilter / formatter output
  # + tests for /health's new "version" field

apps/denidin-app/tests/billed/
  # + test_denidin_version_query_e2e.py (US4, @pytest.mark.billed - text-only OpenAI call)

scripts/ (or a new tests/ location for host-level script tests - TBD at /speckit.tasks)
  # + tests exercising cut_release.sh/deploy_release.sh against a scratch git repo +
  #   throwaway Docker image, not this repo's real tags/VERSION files/artifacts folder
  #   (including deploy_release.sh's three shapes: initial deploy, promotion, rollback,
  #   plus its automatic verification step)
```

**Structure Decision**: Single-project-per-app structure (unchanged) plus two new root-level
`scripts/*.sh`, matching the existing `scripts/killall_containers.sh`/`scripts/env_lock.sh`
convention. No new top-level app, no new container, no new port. The artifacts folder
(`/Users/yaron/Projects/DeniDin/artifacts/`) is outside `apps/` entirely, matching how
`shared/` (cross-clone state) is already outside `apps/` too.

## Phased Execution

### Phase 0 — Research (this plan's Phase 0, see research.md)
Resolved: logging/filter mechanism, VERSION path resolution, `/health` extension, AIHandler
injection point, script build/tag/artifact mechanics, changelog/release-notes format, the
deploy/rollback unification (Decision 9), and automated verification mechanism (Decision 10). The
root clone's `.gitignore` coordination point (Decision 7) is resolved as **user-owned, out of this
feature's task list** — the user will add that entry themselves.
**Checkpoint**: no unknown blocks implementation.

### Phase 1 — VERSION + observability (US1), TDD
`VERSION` files, `VersionFilter`/formatter change in both apps' `logger.py`, `/health` extension,
each preceded by a failing unit test per CONSTITUTION §V/METHODOLOGY §VI.

### Phase 2 — Cut script (US2) + artifacts folder
`scripts/cut_release.sh` per its CLI contract, script-level tests against scratch fixtures (not
this repo's real releases). Assumes the user has already added the root clone's `.gitignore`
entry (Decision 7, user-owned) before this phase's tests populate the real shared artifacts
folder — worth a quick check at Phase 2 kickoff, not a task this feature implements itself.

### Phase 3 — Deploy script (US3): initial deploy, promotion, rollback, all one mechanism
`scripts/deploy_release.sh` per its CLI contract — depends on Phase 2 (needs `cut_release.sh`
producing real artifacts to deploy). Covers all three shapes (initial `dev` deploy, `dev`→`prod`
promotion, rollback to an older version) as the same script, plus its automatic post-deploy
health/version verification (REQ-DEPLOY-002).

### Phase 4 — WhatsApp version query (US4)
`AIHandler` instructions-injection change, the `billed`-tier real E2E test. Independent of
Phase 2/3 (only needs Phase 1's `VERSION` file), can run in parallel.

### Phase 5 — Documentation + haleluya integration (REQ-DOC-001/002)
CLAUDE.md's remaining documentation (banner already landed 2026-08-02 — this phase is the
"where VERSION/tags/changelog/artifacts folder live" reference doc, not the hard-constraint
rule itself); `.github/METHODOLOGY.md`'s "Finish-Feature Trigger Phrase" update so `haleluya`
covers the new mandatory release-prompt step, correctly sequenced *before* any deploy step.

### Phase 6 — Cross-cutting verification
Full spec-to-test traceability pass; manually walk `quickstart.md` end-to-end at least once
(including the "confirm no version suggested before the human states one" check called out there
as a P0-severity regression if it ever fails, and the "deploy only reports success after
automatic verification passes" check).

## Complexity Tracking

No Constitution Check violations requiring justification. The one non-standard element — a
shared, cross-clone, hardcoded-path artifacts folder living inside the root clone's working tree
rather than inside `apps/` — mirrors an existing precedent (`shared/` symlink,
`config/shared_state.local.json`) rather than introducing a new architectural pattern; the
`.gitignore` coordination point (Decision 7) is resolved as user-owned, not a task this feature
implements. Unifying deploy and rollback into one script (Decision 9) is a simplification
discovered mid-planning, not added complexity — it removes what would otherwise have been two
near-identical scripts.
