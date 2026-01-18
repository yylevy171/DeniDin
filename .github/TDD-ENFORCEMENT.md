# TDD Enforcement Protocol

**CRITICAL**: This project follows **STRICT Test-Driven Development (TDD)**

## The Iron Rule

```
NO CODE IMPLEMENTATION WITHOUT APPROVED TESTS
```

## Workflow - NO EXCEPTIONS

### Phase A: Write Tests (Agent)
1. Agent writes comprehensive tests in `tests/` directory
2. Tests MUST fail initially (no implementation exists)
3. Agent commits ONLY test files: `git add tests/` 
4. Agent STOPS and requests human approval

### Phase B: Human Approval Gate 👤
**MANDATORY CHECKPOINT - AGENT MUST WAIT**

Human reviews:
- Test coverage completeness
- Test quality and assertions
- Edge cases covered
- Feature flag usage verified

Human explicitly approves: "Tests approved, proceed with implementation"

### Phase C: Implementation (Agent - ONLY AFTER APPROVAL)
1. Agent implements code to make tests pass
2. Agent runs tests to verify
3. Agent commits implementation
4. Tests from previous phases are **IMMUTABLE**

## Enforcement Checklist

Before writing ANY implementation code, agent MUST verify:

- [ ] Tests written and committed?
- [ ] Human approval received in chat?
- [ ] Implementation blocked until approval?

## Violations & Consequences

**If agent implements before approval:**
1. IMMEDIATE HALT
2. Revert ALL code changes: `git restore <files>`
3. Keep only test files
4. Re-request approval
5. Document the violation

## File Modification Rules

### ✅ ALLOWED Without Approval:
- Test files (`tests/**/*.py`)
- Documentation (`docs/`, `*.md`)
- Configuration examples (`config.example.json`)

### ❌ FORBIDDEN Without Approval:
- Source code (`src/**/*.py`)
- Main entry point (`denidin.py`)
- Production config (`config/config.json`)
- Any file that changes runtime behavior

## Red Flags - Agent Self-Check

Agent MUST STOP if about to:
- Modify `src/` files without seeing "Tests approved"
- Edit production code during test-writing phase
- Skip the approval gate
- Batch tests + implementation together

## Recovery Protocol

When violation detected:
```bash
# Revert implementation changes
git restore src/
git restore *.py

# Verify only tests remain
git status --short

# Should see only: ?? tests/unit/test_*.py
```

## Success Pattern

```
Agent: "I've written tests in test_X.py. Ready for review."
Human: [reviews tests]
Human: "Tests approved, proceed with implementation"
Agent: [NOW implements code in src/]
Agent: "Implementation complete, tests passing"
```

---

**Last Violation**: January 18, 2026 - Phase 5 AIHandler integration
**Action Taken**: Full revert of src/handlers/ai_handler.py and src/models/config.py
**Prevention**: This document created

---

**Note to AI Agent**: 
You MUST re-read this file at the start of EVERY implementation phase.
If you find yourself editing src/ files, CHECK if you have explicit approval in the conversation.
When in doubt: STOP and ASK.
