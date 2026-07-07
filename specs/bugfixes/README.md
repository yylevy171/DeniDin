# Bug Fixes Directory

**Purpose**: Centralized storage for all bugfix specifications following Bug-Driven Development (BDD) workflow.

---

## Directory Structure

```
specs/bugfixes/
├── README.md                                  # This file
├── bugfix-004-data-root-ignored.md           # Bugfix spec (Not Started)
└── bugfix-###-description.md                 # Future bugfix specs

specs/done/bugfixes/
├── bugfix-001-constitution-not-loaded.md     # ✅ Complete
├── bugfix-002-max-retries-unused.md          # ✅ Complete
└── bugfix-003-poll-interval-unused.md        # ✅ Complete
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
# After merge, move spec to done folder
mv specs/bugfixes/bugfix-005-new-bug-description.md specs/done/bugfixes/bugfix-005-new-bug-description.md
```

---

## Active Bugfixes

| # | Title | Priority | Status | Branch |
|---|-------|----------|--------|--------|
| 004 | data_root Config Value Not Respected | P2 | Not Started | `bugfix/004-data-root-ignored` |
| 005 | Media Flow Integration - File Empty Issue | - | Open | - |
| 008 | Forwarded Text Messages (extendedTextMessage) Not Routed/Extracted | P1 | Fixed | `bugfix/008-extended-text-message-not-routed` |

## Completed Bugfixes

| # | Title | Priority | Completed | PR/Commit |
|---|-------|----------|-----------|-----|
| 001 | Constitution Config Not Loaded | P1 | 2026-01-23 | 6610279 |
| 002 | max_retries Config Value Unused | P2 | 2026-01-23 | #55 |
| 003 | poll_interval_seconds Config Value Unused | P3 | 2026-01-23 | #56 |
| 006 | Media Flow Integration - File Empty Issue (resolved) | - | 2026-01-29 | - |
| 007 | Media Response Missing ChatId / Notification Data Validation | P0 | 2026-01-29 | #75-78 |

---

## Priority Levels

- **P1 (High)**: Critical bugs affecting core functionality or user experience
- **P2 (Medium)**: Important bugs causing inconsistencies or confusion
- **P3 (Low)**: Minor bugs, dead code, or cleanup tasks

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
- Completed bugfixes move to `specs/done/bugfixes/`
