# DeniDin Project Constitution

**Established**: January 15, 2026  
**Purpose**: Core principles and guidelines for all development work

---

## I. UTC Timestamp Requirement

**All timestamps in the codebase MUST use UTC timezone.**

**Rationale**: Consistent timezone usage prevents time-related bugs, simplifies debugging across distributed systems, and ensures accurate message tracking and log correlation.

**Requirements**:
1. **ALWAYS** use `datetime.now(timezone.utc)` - NEVER use `datetime.now()` without timezone
2. **ALWAYS** use `datetime.now(timezone.utc).timestamp()` for Unix timestamps
3. **ALWAYS** store `datetime` objects with UTC timezone information
4. **ISO format logs** must include timezone: `message.received_timestamp.isoformat()` outputs UTC ISO format
5. **Code review** must verify all datetime operations use UTC explicitly

**Enforcement**:
- Search codebase for `datetime.now()` without `timezone.utc` before commits
- All new timestamp fields must include UTC in comments/docstrings
- Test fixtures must use `datetime.now(timezone.utc)` for consistency

**Examples**:
```python
# ✅ CORRECT - Always use UTC
from datetime import datetime, timezone
received_timestamp = datetime.now(timezone.utc)
unix_timestamp = int(datetime.now(timezone.utc).timestamp())

# ❌ WRONG - Missing timezone
received_timestamp = datetime.now()  # System timezone - FORBIDDEN
unix_timestamp = int(datetime.now().timestamp())  # Ambiguous - FORBIDDEN
```

---

## II. Test-Driven Development (TDD)

**Principle**: All code must be tested before implementation.

### Workflow for Every Feature:
1. **Write Tests First** - Create comprehensive test suite covering all acceptance criteria
2. **Human Approval Gate** - Tests must be reviewed and approved before implementation
3. **Implement Code** - Write code to pass the approved tests (tests are now immutable)
4. **Validate** - Run tests to verify implementation
5. **Iterate** - Repeat for next feature

### 🔒 Test Immutability Principle:

**Once tests for a phase are working and approved, they are IMMUTABLE.**

- **NO modifications** to existing passing tests without **EXPLICIT HUMAN APPROVAL**
- When working on subsequent phases (e.g., Phase 6, 7), existing tests from completed phases (e.g., Phase 1-5) must NOT be changed
- New phases should ADD new tests, not modify existing ones
- If a test change is absolutely necessary, it requires:
  1. Clear justification explaining why
  2. Explicit human approval before making any changes
  3. Documentation of what changed and why in commit message
- This ensures regression protection and maintains confidence in previously validated functionality

### Enforcement Mechanisms:

To ensure the Test Immutability Principle is followed:

1. **Pre-Commit Check**: Before any commit that modifies test files from completed phases:
   - AI agent MUST explicitly ask: "This modifies tests from Phase X. Do you approve this change?"
   - Must provide clear justification for why the change is needed
   - Must wait for explicit "approve" or "approved" response

2. **Commit Message Requirements**: When test modifications are approved:
   - Include "HUMAN APPROVED:" in commit message
   - State which test file/fixture was modified
   - Provide justification for the change

3. **Git Diff Review**: AI agent should:
   - Use `git diff` to identify if test files are being modified
   - Cross-reference with completed phases (check tasks.md for phase completion)
   - Flag any test file modifications for human review

4. **When In Doubt - ASK**: If unsure whether a change requires modifying existing tests:
   - **ALWAYS ask for human guidance first**
   - Present the options (e.g., optional fields vs test modification)
   - Wait for explicit direction before proceeding
   - Never assume it's okay to modify existing tests

5. **Documentation**: Track all approved test modifications in:
   - Commit messages (with "HUMAN APPROVED" tag)
   - Phase completion notes
   - PR descriptions

### Test Requirements:
- Unit tests for all models, handlers, and utilities
- Integration tests for cross-component interactions
- Mock external dependencies for fast unit/integration tests
- **Real API connectivity tests** for E2E validation (see below)
- Achieve meaningful code coverage (aim for 80%+)
- Tests must pass before any PR is created

### Testing Strategy - Two-Tier Approach:

#### Tier 1: Mocked Tests (Fast, Frequent)
- **Purpose**: Test logic, structure, error handling
- **Speed**: Fast execution, no network delays
- **Usage**: Development, CI/CD pipelines, pre-commit hooks
- **Scope**: Unit tests, integration tests with mocked APIs
- **When**: Run on every code change

#### Tier 2: Real API Tests (Slow, Critical)
- **Purpose**: Verify actual connectivity, credentials, network behavior
- **Speed**: Slower, depends on network and external services
- **Usage**: Pre-deployment validation, periodic checks
- **Scope**: End-to-end tests with REAL API calls (NO MOCKING)
- **When**: Run before deployment, after configuration changes, periodically

#### Real API Test Requirements:
For any service that communicates with external APIs:
1. **Connectivity Tests** - Verify API endpoints are reachable
2. **Authentication Tests** - Confirm API keys/credentials are valid
3. **Send Tests** - Verify the app can send data to external APIs
4. **Receive Tests** - Verify the app can receive and parse responses
5. **Complete Flow Tests** - Full E2E with real API calls

**Example**: For a WhatsApp + OpenAI bot:
- ✅ Mock tests: Fast tests for message parsing, response formatting
- ✅ Real API tests: 
  - Test real Green API connection and authorization
  - Send actual WhatsApp message
  - Make real OpenAI API call (consume quota)
  - Verify complete flow: WhatsApp → OpenAI → WhatsApp

**Note**: Real API tests may consume quotas/credits - this is acceptable and necessary for deployment confidence.

---

## II. Version Control Workflow

**Principle**: Every implementation phase must be version controlled with proper review.

### ⚠️ CRITICAL RULE: NEVER PUSH DIRECTLY TO MASTER/MAIN

**ALL work must be done on feature branches. NO EXCEPTIONS.**

### Required Steps After Each Phase:

1. **Create Feature Branch**
   - ALWAYS create a new branch before starting work
   - Branch naming convention: `###-phase#-description` (e.g., `001-phase2-foundational`)
   - Command: `git checkout -b <feature-branch-name>`

2. **Test Validation**
   - Run all relevant tests: `pytest tests/ -v`
   - Ensure 100% of tests pass
   - For final phases, include coverage: `pytest tests/ -v --cov=src --cov-report=html`

3. **Commit Changes**
   - Stage all changes: `git add .`
   - Descriptive commit message: `git commit -m "Phase X: [Description] - [What was accomplished]"`
   - Follow conventional commits format when applicable

4. **Push to Feature Branch**
   - Push to dedicated feature branch: `git push origin <feature-branch-name>`
   - **NEVER**: `git push origin master` or `git push origin main`

5. **Create Pull Request**
   - Title format: "Phase X: [Short Description] Complete"
   - Include: summary of changes, test results, manual testing notes (if applicable)
   - Link to relevant specifications or issues

6. **Review and Merge**
   - Require at least one approval (human or automated checks)
   - Verify all CI/CD checks pass
   - Merge to main branch using squash or merge commit
   - Delete feature branch after merge

7. **Release Tagging** (for major milestones)
   - Tag releases with semantic versioning: `git tag v1.0.0`
   - Push tags: `git push origin v1.0.0`

### Branch Strategy:
- `master/main` - Production-ready code, always stable, **PROTECTED - NO DIRECT COMMITS**
- `<feature-branch>` - Individual feature/phase development
- One feature branch per phase or user story
- Keep feature branches short-lived (merge within days, not weeks)

### Branch Protection:
- Master/main branch should be protected on GitHub
- Require pull request reviews before merging
- Require status checks to pass before merging
- No force pushes allowed on master/main

---

## III. Code Quality Standards

**Principle**: Maintain high code quality and consistency.

### Requirements:
- **Linting**: Code must pass linting checks (`pylint`, minimum score 9.0/10)
- **Type Hints**: All functions must have type annotations
- **Docstrings**: All modules, classes, and functions must have Google-style docstrings
- **PEP 8 Compliance**: Follow Python style guide (120 char line limit)
- **Error Handling**: All external API calls must have proper error handling
- **Logging**: Appropriate logging at INFO and DEBUG levels

---

## IV. Documentation Requirements

**Principle**: Code without documentation is incomplete.

### Required Documentation:
- **README.md** - Setup, installation, and basic usage
- **DEPLOYMENT.md** - Production deployment guide
- **CONTRIBUTING.md** - How to contribute, coding standards
- **API Documentation** - For all public interfaces
- **Inline Comments** - For complex logic or non-obvious code
- **Changelog** - Track all notable changes between versions

---

## V. Dependency Management

**Principle**: Keep dependencies minimal, secure, and up-to-date.

### Guidelines:
- Lock dependency versions in `requirements.txt`
- Review dependencies for security vulnerabilities
- Minimize external dependencies
- Document why each dependency is needed
- Regular dependency updates (monthly security patches)

---

## VI. Configuration & Secrets

**Principle**: Never commit secrets, always externalize configuration.

### Rules:
- All secrets in environment variables or external config files
- `config.json` and similar files must be in `.gitignore`
- Provide `config.example.json` with placeholder values
- Validate all configuration at startup
- Log configuration (mask sensitive values)

---

## VII. Error Handling & Resilience

**Principle**: Fail gracefully, log thoroughly, recover automatically when possible.

### Requirements:
- All API calls must have timeout and retry logic
- **Network (REST) Errors**: Retry ONCE (maximum 1 retry), only on 5xx server errors, 1 second wait interval
  - 4xx client errors are NOT retried (indicates bad request, auth failure, etc.)
  - 5xx server errors get 1 retry after 1 second (transient server issues)
- **OpenAI API Errors**: Same policy - retry once on transient failures (RateLimitError, APITimeoutError, 5xx errors)
- User-friendly error messages (not stack traces)
- Full error logging with context (DEBUG level)
- **Bot must never crash**: Overarching try-catch blocks prevent application crashes from any exception
- Application only exits on explicit signals (SIGINT, SIGTERM) or startup validation failures

---

## VIII. Development Workflow

**Principle**: Incremental progress with continuous validation.

### Process for Any Feature:
1. Review/create specification document
2. Break down into small, testable tasks
3. For each task:
   - Write tests (get approval)
   - Implement code (make tests pass)
   - Commit and push
4. After logical phase completion:
   - Run full test suite
   - Create PR and get review
   - Merge to main
5. Tag releases at milestones

### Checkpoints:
- Each phase ends with a checkpoint
- Checkpoint includes: test validation + version control steps
- No phase begins until previous phase checkpoint is complete

---

## IX. Manual Testing Requirements

**Principle**: Automated tests are necessary but not sufficient.

### Manual Approval Gates:
- At the end of each user story phase
- Test with real APIs and services
- Verify user-facing behavior
- Document test scenarios and results
- Sign-off required before next phase

### Real API Testing Checklist:
Before approving any phase that involves external services, verify:
- [ ] Real API connectivity tests pass
- [ ] API credentials are valid in production environment
- [ ] All send/receive operations work with real services
- [ ] Error handling works with real API errors (rate limits, timeouts, etc.)
- [ ] Complete E2E flow tested with actual network calls
- [ ] API quota usage is acceptable and documented

---

## X. Command-Line Development Workflow

**Principle**: All code management should be done locally via command-line tools.

### Required Practices:
- **Git Operations**: Use command-line `git` for all version control operations
  - Commits: `git add`, `git commit`
  - Branching: `git checkout -b`, `git branch`
  - Pushing: `git push origin <branch-name>`
  - Status checks: `git status`, `git log`, `git diff`
- **Pull Request Management**: Use `gh` CLI for all PR operations
  - Create PRs: `gh pr create --title "..." --body "..."`
  - Review PRs: `gh pr review`, `gh pr checks`
  - Merge PRs: `gh pr merge`
  - List PRs: `gh pr list`, `gh pr view`
- **Testing**: Run tests via command-line
  - `pytest tests/ -v`
  - `pytest tests/unit/ -v`
  - `pytest --cov=src --cov-report=html`
- **Environment Management**: Use command-line tools for dependencies
  - `python -m venv venv`
  - `pip install -r requirements.txt`
  - `pip list`, `pip freeze`

### Rationale:
- **Reproducibility**: Command-line operations can be scripted and automated
- **Transparency**: All actions are explicit and trackable
- **Portability**: Works across all platforms and CI/CD environments
- **Version Control**: Commands can be documented in scripts and shared with team
- **Efficiency**: Faster than GUI interactions for experienced developers

### GUI Exceptions:
GUI tools may be used for:
- Code editing (VS Code, IDEs)
- Viewing diffs and merge conflicts (optional, CLI alternatives exist)
- Monitoring CI/CD pipelines (optional)
- Reading documentation in browsers

**All code-modifying operations must use CLI tools.**

---

## XI. Amendment Process

**Principle**: This constitution can evolve with the project.

### How to Amend:
1. Propose change in a dedicated PR
2. Include rationale and impact analysis
3. Get team consensus
4. Update this document
5. Communicate changes to all contributors

---

## Application to All Features

**This constitution applies to:**
- ✅ All new features and user stories
- ✅ Bug fixes that involve new code
- ✅ Refactoring efforts
- ✅ Documentation updates
- ✅ Configuration changes
- ✅ Infrastructure modifications

**Exceptions:**
- 🔧 Emergency hotfixes (follow up with proper PR)
- 📝 Typo fixes in documentation (can be direct commits to main)
- 🔄 Automated dependency updates (if tests pass)

---

## Enforcement

All contributors must:
1. Read and understand this constitution
2. Follow TDD workflow for all code
3. Complete version control steps for all phases
4. Maintain code quality standards
5. Never compromise on testing or security

**Violations:**
- PRs not following this constitution will be rejected
- Direct commits to main (except emergencies) will be reverted
- Untested code will not be merged

---

**Signed**: DeniDin Development Team  
**Effective Date**: January 15, 2026  
**Version**: 1.0
