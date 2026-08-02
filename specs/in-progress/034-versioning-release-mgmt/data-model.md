# Data Model: Feature 034 (Versioning & Release Management)

Phase 1 output. No database/ChromaDB entities are involved — every entity here is a plain
git-tracked file, a Docker artifact, or a filesystem manifest. Field names match spec.md's Key
Entities section; this document adds concrete shapes/formats.

---

## `VERSION` file

**Location**: `apps/denidin-app/VERSION`, `apps/morning-mcp-app/VERSION` (one per app, at that
app's root — REQ-VER-001).

**Shape**: Plain text, a single line, no trailing content beyond one trailing newline:
```
1.4.2
```

**Validation rule**: Must match `^\d+\.\d+\.\d+$` (semantic version, no `v` prefix, no
pre-release/build metadata in v1). If missing or malformed, consuming code treats it as
`"unknown"` (REQ-VER-001's own acceptance criteria in user-stories.md US1) rather than erroring.

**Lifecycle**: Written only by `scripts/cut_release.sh` (REQ-SCR-001), read by: each app's own
logger setup (Decision 1/2), `apps/morning-mcp-app`'s `/health` handler (Decision 3),
`apps/denidin-app`'s `AIHandler` (Decision 4). Never hand-edited outside the script (REQ-REL-006
immutability applies to the *committed* value at any given commit — the file's content at HEAD is
always "whatever the last cut release set it to").

---

## `CHANGELOG.md` entry

**Location**: `apps/denidin-app/CHANGELOG.md`, `apps/morning-mcp-app/CHANGELOG.md` (append-only,
newest entry at top, per REQ-REL-003).

**Shape** (one entry, Markdown):
```markdown
## [1.4.2] - 2026-08-15

Fixed the RBAC token-limit bug for godfather-role users introduced in 1.4.0.
```

**Fields**: `version` (matches `VERSION` file content), `date` (UTC, `YYYY-MM-DD`, per
CONSTITUTION §II), `summary` (one human-written sentence, sourced from the merged PR/spec title —
never auto-generated from raw `git log`, per REQ-REL-003).

---

## `RELEASES.md` section

**Location**: `apps/denidin-app/RELEASES.md`, `apps/morning-mcp-app/RELEASES.md` (append-only,
newest at top, per REQ-REL-004).

**Shape** (one section, Markdown, no fixed sub-structure beyond the heading):
```markdown
## denidin-app v1.4.2 — 2026-08-15

Fixes a bug where godfather-role users could hit client-role token limits after a config
change in 1.4.0 mis-mapped role precedence. No user-facing behavior change for admin/client
roles. See specs/done/041-rbac-token-fix/ for the full spec.
```

**Fields**: same `version`/`date` as `CHANGELOG.md`, plus free-form `notes` (a few sentences to a
short paragraph — longer-form than `CHANGELOG.md`'s one-liner, per REQ-REL-004).

---

## Release image (Docker)

**Identity**: Tagged locally as `<app>:<version>` (e.g. `denidin-app:1.4.2`) at build time
(Decision 5) — this tag is transient/local-Docker-only; the durable artifact is the exported
tarball below.

**Exported artifact**: `<artifacts-root>/<app>/<app>-v<version>.tar` (`docker save` output).

---

## Release manifest (JSON)

**Location**: `<artifacts-root>/<app>/<app>-v<version>.json`, one per release tarball
(REQ-ART-002), sibling to the `.tar` file.

**Shape**:
```json
{
  "app": "denidin-app",
  "version": "1.4.2",
  "date": "2026-08-15",
  "git_commit": "a1b2c3d4e5f6...",
  "image_id": "sha256:9f8e7d6c5b4a..."
}
```

**Fields**:
- `app` — `"denidin-app"` or `"morning-mcp-app"` (matches the `<app>` argument
  `scripts/cut_release.sh`/`scripts/deploy_release.sh` were invoked with).
- `version` — matches the `VERSION` file content at cut time (and the tag/filename).
- `date` — UTC `YYYY-MM-DD`, the date the release was cut (CONSTITUTION §II).
- `git_commit` — full SHA of the commit the image was built from (`git rev-parse HEAD` at cut
  time — cutting always happens **before** any deploy, per REQ-REL-001's corrected ordering
  2026-08-02, so this is the merged commit about to be deployed, not one already running anywhere
  yet).
- `image_id` — the built image's Docker ID/digest (`docker images --no-trunc --format
  '{{.ID}}'` for the just-built `<app>:<version>` tag), so a human can verify a loaded image
  matches what the manifest claims without trusting the tarball's filename alone.

**Validation rule**: `scripts/deploy_release.sh` MUST refuse to proceed if the manifest is
missing or its `app`/`version` fields don't match the requested deploy target — a corrupted or
mismatched manifest should fail loudly, not silently load the wrong image. Applies identically
whether the call is an initial deploy, a promotion, or a rollback.

---

## Artifacts folder layout

```
/Users/yaron/Projects/DeniDin/artifacts/
├── denidin-app/
│   ├── denidin-app-v1.4.0.tar
│   ├── denidin-app-v1.4.0.json
│   ├── denidin-app-v1.4.2.tar
│   └── denidin-app-v1.4.2.json
└── morning-mcp-app/
    ├── morning-mcp-app-v0.2.0.tar
    └── morning-mcp-app-v0.2.0.json
```

One subdirectory per app (REQ-ART-001); flat within each app's subdirectory, one `.tar` +
`.json` pair per cut release, filenames matching `<app>-v<version>`. Confirmed real cross-clone
path (2026-08-02) — see research.md Decision 7 (root-clone `.gitignore` entry is user-owned, not
part of this feature's task list).

---

## Relationships

```
VERSION file  --(read by, once per process)-->  logger version-Filter, /health handler, AIHandler
VERSION file  --(written by)-->  scripts/cut_release.sh

scripts/cut_release.sh --(produces, atomically)--> VERSION update + git tag + release image
                                                     + release tarball + manifest + CHANGELOG entry
                                                     + RELEASES section

release tarball + manifest  --(consumed by)-->  scripts/deploy_release.sh
                                                 (initial dev deploy, dev->prod promotion,
                                                  or rollback - same operation, see research.md
                                                  Decision 9)

scripts/deploy_release.sh --(on success, blocks on)--> automatic /health poll (morning-mcp-app)
                                                         or log-tail (denidin-app) verification
                                                         (research.md Decision 10)

git tag <app>-v<version>  --(1:1 with)-->  CHANGELOG.md entry  --(1:1 with)-->  RELEASES.md section
                                            --(1:1 with)-->  artifacts/<app>/<app>-v<version>.{tar,json}
```
