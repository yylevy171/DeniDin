# Bug Fixes Directory

**Purpose**: Centralized storage for all bugfix specifications following Bug-Driven Development (BDD) workflow.

---

## Directory Structure

```
specs/bugfixes/
├── README.md                                  # This file
├── bugfix-004-data-root-ignored.md           # Bugfix spec (Not Started)
└── bugfix-###-description.md                 # Future bugfix specs

specs/done/                                    # A completed bugfix lands here FLAT
├── bugfix-001-constitution-not-loaded.md     # ✅ Complete, not yet in a cut release
└── v0.4.0/                                    # Once a release is cut (scripts/cut_release.sh,
    ├── 048-whatsapp-typing-indicator/         # 2026-08-20 reorganization), every flat entry
    └── bugfix-036-mcp-server-has-no-audit-trail.md  # sitting in specs/done/ moves into that
                                                # release's own version folder, features and
                                                # bugfixes together, no separate bugfixes/
                                                # subfolder anymore - see specs/done/v*/ for the
                                                # full, versioned history.
```

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
# Create new bugfix spec (use next sequential number)
touch specs/bugfixes/bugfix-005-new-bug-description.md
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
# After merge, move spec to done folder - flat, no version subfolder yet
# (scripts/cut_release.sh sweeps flat specs/done/ entries into a versioned
# folder, e.g. specs/done/v0.4.4/, the next time a release is cut)
mv specs/bugfixes/bugfix-005-new-bug-description.md specs/done/bugfix-005-new-bug-description.md
```

---

## Active Bugfixes

| # | Title | Priority | Status | Branch |
|---|-------|----------|--------|--------|
| 013 | Client Name Garbling and Unrequested Date Narrowing | - | Open (documentation only) | - |
| 014 | list_invoices Only Returns One of Many | - | Open (documentation only) | - |
| 022 | OpenAI MCP Approval Duplicate Execution | P0 | Open (interim mitigation deployed, true prevention deferred) | feature/033-ledger-event-persistence |
| 051 | `list_reminders` discloses a private 1:1 reminder's text into a group chat | P1 | Open (root cause documented; awaiting approval) | bugfix/051-list-reminders-cross-chat-disclosure |

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

- ALL bugfix specs MUST live in this directory (never in `specs/in-progress/`)
- Each bugfix gets a sequential number (never reuse numbers)
- Branch name MUST match spec file number
- Completed bugfixes move to `specs/done/` flat (no subfolder), same as a finished feature -
  `scripts/cut_release.sh` moves it into that release's own `specs/done/vX.Y.Z/` folder the next
  time a release is cut (2026-08-20 reorganization - see `specs/done/v*/` for the versioned
  history)
