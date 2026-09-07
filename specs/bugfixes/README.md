# Bug Fixes Directory

**Purpose**: Centralized storage for all bugfix specifications following Bug-Driven Development (BDD) workflow.

---

## Directory Structure

**Since the 2026-09-07 reorganization, every real bugfix spec file lives at exactly one
permanent path — `specs/repo/bugfixes/bugfix-###-description.md` — and never moves.** Its
*status* is shown by which folder holds a **relative symlink** to it:

```
specs/repo/bugfixes/
├── bugfix-001-constitution-not-loaded.md      # THE REAL FILE (permanent path, never moves)
└── bugfix-###-description.md                   # ...one per bugfix, forever

specs/bugfixes/          → symlink here while OPEN        (this dir; README.md stays a real file)
specs/done/              → symlink moves here on RESOLVE  (flat, then done/vX.Y.Z/ after a cut)
specs/obsolete/bugfixes/ → symlink here if found STALE / rejected
specs/not_reproducible/bugfixes/ → symlink here if investigated + closed with NO fix
```

`scripts/cut_release.sh` re-points every flat `specs/done/` symlink into that release's own
`specs/done/vX.Y.Z/` (deepening its `../repo/…` target to `../../repo/…`) the next time a
release is cut — features and bugfixes side by side, no separate `bugfixes/` subfolder.
⚠️ `rg`/`grep -r`/`find` don't follow symlinked dirs — search `specs/repo/bugfixes/` for content.

---

## Naming Convention

**Format**: `bugfix-###-description.md`

- **Prefix**: Always starts with `bugfix-` (to distinguish from features)
- **Number**: Sequential (001, 002, 003, ...)
- **Description**: Kebab-case summary of the bug (e.g., `constitution-not-loaded`)
- **Extension**: Always `.md` (Markdown)

**Examples**:
- ✅ `bugfix-001-constitution-not-loaded.md`
- ✅ `bugfix-005-retry-logic-timeout.md`
- ❌ `001-constitution-not-loaded.md` (missing bugfix- prefix)
- ❌ `bugfix-001.md` (missing description)
- ❌ `session-memory-bug.md` (missing bugfix- prefix and number)

---

## Bugfix Workflow

Following **METHODOLOGY.md §VII: Bug-Driven Development**

### 1. Create Bugfix Spec
```bash
# Create the REAL file under specs/repo/, then symlink it from specs/bugfixes/ (same commit)
touch specs/repo/bugfixes/bugfix-005-new-bug-description.md
ln -s ../repo/bugfixes/bugfix-005-new-bug-description.md \
      specs/bugfixes/bugfix-005-new-bug-description.md
```

### 2. Create Branch
```bash
# Branch name MUST match spec number
git checkout -b bugfix/005-new-bug-description
```

### 3. Follow BDD Steps
- [ ] **Step 1**: Root cause investigation
- [ ] **Step 2**: 🚨 HUMAN APPROVAL - Root cause & fix approach
- [ ] **Step 3**: Test gap analysis
- [ ] **Step 4**: Write failing tests
- [ ] **Step 5**: 🚨 HUMAN APPROVAL - Tests
- [ ] **Step 6**: Implement fix
- [ ] **Step 7**: Verify all tests pass
- [ ] **Step 8**: Commit & PR

### 4. Move to Done
```bash
# After merge, move the SYMLINK (not the real file) to specs/done/ - flat, no version
# subfolder yet. scripts/cut_release.sh re-points it into specs/done/vX.Y.Z/ at the next cut.
git mv specs/bugfixes/bugfix-005-new-bug-description.md \
       specs/done/bugfix-005-new-bug-description.md
```

---

## Active Bugfixes

| # | Title | Priority | Status | Branch |
|---|-------|----------|--------|--------|
| 013 | Client Name Garbling and Unrequested Date Narrowing | - | Open (documentation only) | - |
| 014 | list_invoices Only Returns One of Many | - | Open (documentation only) | - |
| 022 | OpenAI MCP Approval Duplicate Execution | P0 | Open (interim mitigation deployed, true prevention deferred) | feature/033-ledger-event-persistence |

## Obsolete Bugfixes (`specs/obsolete/bugfixes/`)

| # | Title | Marked Obsolete | Reason |
|---|-------|-----------|--------|
| 004 | data_root Config Value Not Respected | 2026-07-21 | Already fixed by current `config.py`/example-config behavior — see spec for details |
| 005 | Media Flow Integration - File Empty Issue | 2026-07-21 | Possible duplicate of resolved bugfix-006 — not independently re-verified, see spec for caveat |

## Completed Bugfixes

| # | Title | Priority | Completed | PR/Commit |
|---|-------|----------|-----------|-----|
| 001 | Constitution Config Not Loaded | P1 | 2026-01-23 | 6610279 |
| 002 | max_retries Config Value Unused | P2 | 2026-01-23 | #55 |
| 003 | poll_interval_seconds Config Value Unused | P3 | 2026-01-23 | #56 |
| 006 | Media Flow Integration - File Empty Issue (resolved) | - | 2026-01-29 | - |
| 007 | Media Response Missing ChatId / Notification Data Validation | P0 | 2026-01-29 | #75-78 |
| 008 | Forwarded Text Messages (extendedTextMessage) Not Routed/Extracted | P1 | 2026-07-07 | #90 |
| 010 | Active Session Context Lost on Restart | - | 2026-07-08 (NOT REPRODUCIBLE) | - |
| 010 | RBAC Phone/JID Mismatch | - | 2026-07-20 | #107 |
| 011 | AI Declines Analytical Invoice Query | - | 2026-07-20 | #109 |
| 026 | Morning Documents Created Unsigned (blocks email sharing) | P0 | 2026-08-07 | #195 |
| 012 | Financial Summary Drops Non-Allowlisted Invoice Types | - | 2026-07-21 | #111 |
| 020 | GreenAPIBot Crashes on Empty Notification Response | P0 | 2026-08-03 | #163 |

---

## Priority Levels

**Required as of 2026-07-24**: every bugfix spec MUST declare a `Priority` field, using the same P0/P1/P2 scheme as feature specs (METHODOLOGY.md §VII/§XI) — no more untracked/`-` priority bugfixes going forward.

- **P0 (Critical)**: Bugs causing data loss, security exposure, or breaking core functionality for all/most users
- **P1 (High)**: Critical bugs affecting core functionality or user experience
- **P2 (Medium)**: Important bugs causing inconsistencies, confusion, or cleanup-level issues

---

## References

- **METHODOLOGY.md §VII**: Bug-Driven Development workflow
- **CONSTITUTION.md §III**: Version control and branch naming
- **Template**: `.specify/templates/bugfix-template.md` (if exists)

---

## Notes

- The real file for EVERY bugfix spec MUST live under `specs/repo/bugfixes/` (never a real file
  in `specs/bugfixes/`, `specs/in-progress/`, `specs/done/`, or anywhere else)
- An OPEN bugfix is symlinked from `specs/bugfixes/`; never from `specs/in-progress/`
- Each bugfix gets a sequential number (never reuse numbers)
- Branch name MUST match spec file number
- On resolution the SYMLINK moves to `specs/done/` flat (same as a finished feature);
  `scripts/cut_release.sh` re-points it into `specs/done/vX.Y.Z/` at the next cut
