# Research: Feature 034 (Versioning & Release Management)

Phase 0 output. All prior `[NEEDS CLARIFICATION]` markers were already resolved during
`/speckit.clarify` (see spec.md's Clarifications section) — this phase resolves the remaining
*technical* unknowns (how, not what) needed before Phase 1 design.

---

## Decision 1: Where does per-log-line version stamping live?

**Decision**: A single `logging.Filter` subclass added inside each app's own
`utils/logger.py` (`apps/denidin-app/src/utils/logger.py`,
`apps/morning-mcp-app/src/denidin_mcp_morning/utils/logger.py`) — attached in `setup_logger()`,
alongside a formatter-string change from `'%(asctime)s - %(name)s - %(levelname)s - %(message)s'`
to `'%(asctime)s - [v%(version)s] - %(name)s - %(levelname)s - %(message)s'`. The filter reads
that app's `VERSION` file once (module-level constant, read at import time) and stamps
`record.version` on every `LogRecord` that passes through.

**Rationale**: Both apps already funnel every logger through this exact same shared module
(`get_logger(__name__)` → `setup_logger(...)`, confirmed identical in both files down to the
formatter string and handler setup) — this is the one existing choke point that touches every log
line in the app without needing to change any individual `logger.info(...)` call site. Matches
REQ-VER-003's "every log line, both apps" requirement with a minimal, single-file-per-app change.

**Alternatives considered**:
- Passing version as `extra={'version': ...}` on every log call — rejected: would require
  touching every call site across both apps (dozens of files), unlike the filter approach.
  Same architectural mistake the current codebase already ruled out once (both apps deliberately
  centralize logger setup in one module for exactly this kind of cross-cutting change).
- A wrapper `get_logger()` returning a `LoggerAdapter` — rejected: functionally equivalent to a
  `Filter` here but more code for no benefit, since there is no per-call dynamic context needed
  (version is static for the process's lifetime — see Decision 2).

## Decision 2: Read the VERSION file once per process, or on every log line?

**Decision**: Once, at import/setup time (module-level constant), not per log line.

**Rationale**: A version only changes when a **new container is deployed** (REQ-VER-004: version
is a per-app fact tied to what's actually running) — never mid-process. Re-reading the file on
every log call would be pure overhead with no behavioral benefit, since REQ-REL-006 (immutability)
already guarantees a running process's own `VERSION` file never changes underneath it once
started.

**Alternatives considered**: Per-call re-read (rejected — see Rationale; also inconsistent with
how `ai_handler.py`'s per-call date injection works only because *date* genuinely does change
within a long-lived process, unlike version).

## Decision 3: How does `apps/morning-mcp-app`'s `/health` learn the version?

**Decision**: Same closure pattern `_build_health_handler` already uses for `environment`
(`server.py:71-82`) — read the `VERSION` file once at server startup, close over it, add a
`"version"` key to the existing `JSONResponse({"status": "ok", "environment": environment})`.

**Rationale**: Direct precedent already in the file; zero new architectural pattern introduced.

**Alternatives considered**: Re-reading `VERSION` on every `/health` call — rejected for the same
reason as Decision 2 (version is immutable for a running process's lifetime).

## Decision 4: How does `apps/denidin-app` answer "what version are you" over WhatsApp?

**Decision**: Extend `AIHandler`'s existing per-call `instructions` assembly
(`ai_handler.py:363-368`, where today's UTC date is computed and appended after the `---`
separator) to also append the current version on that same line/block. Read `VERSION` once at
`AIHandler`'s construction time (module-level or instance-level constant — matches Decision 2's
"read once" reasoning), not freshly per call, since it cannot change mid-process.

**Rationale**: This is the exact mechanism CLAUDE.md's own architecture notes describe for
"per-call-dynamic content appended after the constitution" (prompt-caching-preserving ordering) —
reusing it for version avoids inventing a second mechanism for what is architecturally the same
kind of fact (a per-call-dynamic value the model needs to answer accurately, appended after the
cached constitution prefix).

**Alternatives considered**:
- A new MCP tool the model calls to fetch version — rejected: overkill for a static string with
  no external state, and REQ-VER-005's acceptance criteria explicitly say this should **not**
  require a new MCP tool (same reasoning that ruled out per-call file re-reads applies here too,
  plus unlike Morning tools this needs no external API round-trip).

## Decision 5: How do the release/deploy scripts build, tag, and store images?

**Decision**: `scripts/cut_release.sh <app> <version>` runs `docker build -t <app>:<version>
apps/<app>/` directly (not via `docker compose`), independent of whatever image name/tag
`docker-compose.dev.yml`/`.prod.yml`'s `build:` context produces at ordinary deploy time. It then
`docker save <app>:<version> -o <artifacts-root>/<app>/<app>-v<version>.tar` and writes the
manifest (REQ-ART-002) alongside it — and stops there, deploying nothing (Decision 9).
`scripts/deploy_release.sh <app> <env> <version>` reverses the save step: `docker load -i
<artifacts-root>/<app>/<app>-v<version>.tar`, then **retags** the loaded `<app>:<version>` image
to `<compose-project-name>-<service-name>:latest` (e.g. `denidin-dev-denidin-app-dev:latest` in
the real repo — verified 2026-08-02 against the real compose files' `name:` field and service
keys) and runs `docker compose -f docker/docker-compose.<env>.yml --project-directory <repo-root>
up -d --no-build <service-name>`, so compose recreates the container using the loaded image while
keeping its existing volume mounts (config/logs/data — both apps declare these as `VOLUME`, not
baked into the image) instead of rebuilding from source. Then verifies (Decision 10).

**Safety-critical detail**: the project name is read from the compose file's own `name:` field
(`grep -m1 '^name:' <compose-file>`), never hardcoded as `denidin-<env>` — hardcoding it would
mean a scratch/test compose file using the same project name could collide with (and potentially
disrupt) a real running `dev`/`prod` environment on the same machine, since Compose's container
namespace is keyed by project name. Deriving it from the file in front of the script keeps
scratch tests trivially collision-proof (they just use a different `name:`), with no special-casing
needed in the script itself.

**Rationale**: Keeps the release/rollback mechanism fully decoupled from `docker compose`'s own
build/naming (which is oriented around ordinary forward dev iteration, not durable named
releases) — a direct `docker build -t` avoids ambiguity about which compose-generated image name
a "version" would even correspond to.

**Alternatives considered**: Tagging whatever image `docker compose build` produces — rejected:
compose-generated image names/tags aren't guaranteed stable across compose config changes, and
conflating "the image compose happens to have built most recently" with "the durable release
artifact for version X" would undermine REQ-REL-006's immutability guarantee.

## Decision 6: Where does `VERSION` get read from, path-wise?

**Decision**: `apps/denidin-app/VERSION` resolved via `Path(__file__).resolve().parent /
"VERSION"` from `denidin.py` (app root, since `denidin.py` already lives at that app's root).
`apps/morning-mcp-app/VERSION` resolved via `Path(__file__).resolve().parents[2] / "VERSION"`
from `server.py` — same depth pattern `DEFAULT_CONFIG_PATH` already uses one line above
(`server.py:37`, `Path(__file__).resolve().parents[2] / "config" / "config.json"`).

**Rationale**: Reuses an existing, already-correct path-resolution precedent in the same file
rather than inventing a new convention.

**Alternatives considered**: Routing `VERSION` through `AppConfiguration`/`MorningMCPConfig` like
other config values — rejected: `VERSION` is git-tracked, non-secret, identical regardless of
which config file (`config.dev.json`/`config.test.json`/`config.prod.json`) is loaded, and not
environment-specific — architecturally it belongs with `runtime_constitution.md` (a plain
git-tracked file resolved by direct path, not through the config-loading pipeline), not with
`AppConfiguration`.

## Decision 7: Is the artifacts folder inside any clone's git working tree?

**Finding (not fully resolved — flagged for `/speckit.tasks`/implementation)**: The confirmed path
`/Users/yaron/Projects/DeniDin/artifacts/` sits directly inside the **root clone's own working
tree** (`/Users/yaron/Projects/DeniDin/` is both "the root clone" and the parent directory
containing `coder1/`/`coder2/` as nested subdirectories — confirmed via `ls`, 2026-08-02: `CLAUDE.md`,
`apps/`, `.git`, `coder1/`, `coder2/` are all direct children of the same directory). That means:
- The root clone's own `.gitignore` almost certainly already excludes `coder1/`/`coder2/` (else
  `git status` there would show two entire nested repos as untracked) — an `/artifacts/` entry
  would need to be added there too, for the same reason `dev_data/`/`logs/` are already
  gitignored elsewhere in this project (large, mutable, non-source content).
- This is a **root-clone file edit**, outside `coder1`'s own confinement boundary — per CLAUDE.md's
  clone-confinement rule, doing this from a `coder1` session requires either explicit per-request
  user authorization for that specific edit, or should be done by the user directly / from a
  session actually running in the root clone.

**Resolved (2026-08-02)**: the user will add the root clone's `.gitignore` entry themselves,
outside this feature's implementation tasks — `/speckit.tasks` should not generate a task for it,
and no `coder1` session should attempt this edit.

## Decision 8: `RELEASES.md`/`CHANGELOG.md` entry format

**Decision**: `CHANGELOG.md` — one line per release: `## [<version>] - <YYYY-MM-DD>` heading
followed by a single-sentence summary (loosely inspired by the widely-used "Keep a Changelog"
heading convention, but simplified to match this project's terser style elsewhere).
`RELEASES.md` — one `## <app> v<version> — <YYYY-MM-DD>` section per release with full prose
notes (a few sentences to a short paragraph), no fixed sub-structure imposed.

**Rationale**: Matches REQ-REL-003/004's "terse index vs. detailed record" split; a lightweight,
human-writable format keeps `cut_release.sh` simple (append text, no complex parsing/templating
engine needed) — consistent with this project's general preference for plain, inspectable files
over generated/templated artifacts.

**Alternatives considered**: A structured YAML/JSON changelog — rejected: over-engineered for a
human-read, human-written file; the release **manifest** (REQ-ART-002) already covers the
machine-readable case.

## Decision 9: Is rollback a separate script from ordinary forward deploy/promotion?

**Decision (2026-08-02, user-clarified)**: No — one script, `scripts/deploy_release.sh <app> <env>
<version>`, covers the initial deploy of a freshly cut version to `dev`, later promotion of the
same version to `prod`, and rollback to any older version in either environment. All three are the
same operation (load a pre-built artifact from the artifacts folder, redeploy it, verify it) —
they differ only in whether `<version>` happens to be newer, equal, or older than what's currently
running. Supersedes the earlier `scripts/rollback_release.sh` design from the prior planning
session.

**Rationale**: The user's own described operator flow makes no mechanical distinction between
these cases — "deploy 1.4.6 to prod" and "roll back prod to 1.4.5" are literally the same command
shape with a different version argument. Building two scripts would mean duplicating the load/
retag/verify logic for no behavioral difference, and would invite drift between them over time.

**Alternatives considered**: Keep `rollback_release.sh` as a thin wrapper around a shared
`deploy_release.sh` for operator-vocabulary clarity ("rollback" is meaningful terminology) —
rejected for v1 as unnecessary indirection; `deploy_release.sh <app> <env> <older-version>` reads
clearly enough as "this is a rollback" from its arguments alone, and `contracts/deploy_release_cli.md`
documents the equivalence explicitly. Can be revisited if the single name proves confusing in
practice.

## Decision 10: How does a deploy automatically verify its own success?

**Decision (2026-08-02, user-clarified)**: `deploy_release.sh` blocks on verification before
reporting done, per app:
- `morning-mcp-app`: poll `GET /health` (already exposes `version` per REQ-VER-002) every ~2s for
  up to a bounded timeout (e.g. 30s), succeeding as soon as the response's `version` field matches
  the target version.
- `denidin-app` (no HTTP surface): `docker logs <container-name> --tail 20` every ~2s for up to
  the same bounded timeout, succeeding as soon as a line carries the target version's marker
  (REQ-VER-003's `[v<version>]` format, Decision 1). This works because both apps' loggers
  attach a `StreamHandler` to stderr (`logger.py`, unchanged by Feature 034) in addition to the
  file handler, and `watchdog.py` (the container's PID 1) spawns the app as a child process
  without redirecting its stdout/stderr — so the child's stderr output flows through to the
  container's own stdout/stderr, which `docker logs` captures. No new logging surface needed;
  this is the same log line REQ-VER-003 already guarantees carries the version, just read via
  `docker logs` instead of the mounted file (host-mounted `logs/dev/denidin.log` would work too,
  but `docker logs` needs no assumption about *which* environment's log path is mounted where).

A timeout without a match is a **failed** deploy — the script reports failure with the container's
actual last-observed state, not a silent/ambiguous "started but who knows."

**Rationale**: The user's own description makes this a blocking part of the deploy operation
("deployment is successful when health and version checks show..."), not an optional follow-up a
human might separately run — REQ-DEPLOY-002 codifies this. Reusing REQ-VER-002/003's existing
surfaces (rather than inventing a third "deploy-specific" health mechanism) keeps this consistent
with US1 and avoids new observability surface area.

**Alternatives considered**: A fixed sleep-then-assume-success — rejected: doesn't actually verify
anything, defeats the purpose of REQ-DEPLOY-002. A dedicated `/deploy-status` endpoint — rejected
as over-engineered; the existing `/health` version field and log lines are already sufficient
verification signals.
