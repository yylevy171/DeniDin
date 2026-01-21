# DeniDin Project Constitution

**Established**: January 15, 2026  
**Last Updated**: January 21, 2026  
**Purpose**: Development constraints, coding standards, and technical guidelines

> **Note**: This file defines WHAT we enforce (technical constraints, standards).  
> For HOW we work (workflow, process, TDD), see `METHODOLOGY.md`.  
> **When creating/updating specs**: Reference BOTH files.

---

## I. Configuration & Secrets Management

**Principle**: All configuration MUST be in config files. NO environment variables allowed.

**Rules**:
- **NO environment variables**: Configuration exclusively in `config/config.json`
- **NO os.getenv()**: Do not use `os.getenv()` anywhere in the codebase
- **Secrets storage**: API keys and tokens stored in `config/config.json` (excluded from git via `.gitignore`)
- **Feature flags**: Use `config.feature_flags` dictionary for enabling/disabling features
- **Example config**: Always maintain `config/config.example.json` with safe placeholder values
- **Validation**: Validate all configuration at startup with clear error messages
- **Logging**: Log configuration (mask sensitive values like API keys)
- **Testing**: Tests create config objects programmatically or use fixtures, NOT environment variables

**Rationale**:
- Single source of truth for all configuration
- Easier to understand and debug (no hidden environment dependencies)
- Simpler deployment (just copy config file)
- Explicit configuration loading prevents "works on my machine" issues

---

## II. UTC Timestamp Requirement

**All timestamps in the codebase MUST use UTC timezone.**

**Requirements**:
1. **ALWAYS** use `datetime.now(timezone.utc)` - NEVER use `datetime.now()` without timezone
2. **ALWAYS** use `datetime.now(timezone.utc).timestamp()` for Unix timestamps
3. **ALWAYS** store `datetime` objects with UTC timezone information
4. **ISO format logs** must include timezone: `message.received_timestamp.isoformat()` outputs UTC ISO format
5. **Code review** must verify all datetime operations use UTC explicitly

**Examples**:
```python
# ✅ CORRECT
from datetime import datetime, timezone
received_timestamp = datetime.now(timezone.utc)

# ❌ WRONG
received_timestamp = datetime.now()  # FORBIDDEN
```

**Rationale**: Consistent timezone usage prevents time-related bugs, simplifies debugging across distributed systems, and ensures accurate message tracking.

---

## III. Version Control Workflow

**Principle**: All work on feature branches with PRs - NEVER push directly to master.

**Requirements**:
- NEVER push directly to master/main - ALL work on feature branches
- Branch naming: `###-feature-name` or `chore/description`, `docs/description`
- All tests must pass before creating PR
- Use CLI tools (`git`, `gh`) for all version control operations
- Squash merge PRs to keep clean history
- Delete branches after merge

**Git Workflow**:
```bash
git checkout -b feature/my-feature
# ... make changes ...
git add .
git commit -m "descriptive message"
git push origin feature/my-feature
gh pr create --base master --head feature/my-feature
gh pr merge --squash --delete-branch
```

**Rationale**: Feature branches enable proper code review, maintain stable main branch, and provide clear audit trail.

---

## IV. Code Quality Standards

**Requirements**:
- **Type Hints**: All functions must have type annotations
- **Docstrings**: All modules, classes, and functions must have Google-style docstrings
- **PEP 8 Compliance**: Follow Python style guide (120 char line limit)
- **Error Handling**: All external API calls must have proper error handling
- **Logging**: Appropriate logging at INFO and DEBUG levels

**Rationale**: Consistent code quality reduces technical debt and prevents subtle bugs through type safety.

---

## V. Feature Flags for Safe Deployment

**Principle**: New features deployed behind feature flags to enable safe rollouts.

**Requirements**:
- New features MUST be configurable via feature flags (default: disabled)
- Feature flags in `config.json` under `feature_flags` dictionary
- Code MUST check feature flag state before executing new functionality
- Document feature flags and their purpose
- Remove feature flags after feature is stable

**Example**:
```python
if config.feature_flags.get("enable_memory_system", False):
    # New memory system code
    session_manager.add_message(message)
```

**Rationale**: Feature flags reduce deployment risk, enable A/B testing, and provide instant rollback capability.

---

## VI. Error Handling & Resilience

**Principle**: Fail gracefully, log thoroughly, recover automatically when possible.

**Requirements**:
- All API calls must have timeout and retry logic
- **Network Errors**: Retry ONCE on 5xx errors only (1 second wait)
  - 4xx client errors are NOT retried
- User-friendly error messages (not stack traces)
- Full error logging with context (DEBUG level)
- **Bot must never crash**: Catch exceptions at top level
- Application only exits on explicit signals (SIGINT, SIGTERM) or startup failures

**Rationale**: Graceful error handling improves user experience and enables automatic recovery from transient failures.

---

## VII. Command-Line Development Workflow

**Principle**: All code management via command-line tools for reproducibility.

**Requirements**:
- Git operations via CLI: `git add`, `git commit`, `git push`, `git checkout -b`
- Pull request management via `gh` CLI: `gh pr create`, `gh pr merge`
- Testing via CLI: `pytest` commands
- All code-modifying operations must use CLI tools

**Rationale**: CLI operations are scriptable, automatable, reproducible, and work consistently across platforms.

---

## VIII. Test Immutability

**Principle**: Once tests are approved, they are immutable without explicit human approval.

**Requirements**:
- Tests reviewed and approved by human are IMMUTABLE
- New phases ADD new tests, never modify existing ones
- If test change is necessary:
  1. Clear justification why
  2. Explicit human approval before changes
  3. Documentation in commit message with "HUMAN APPROVED:" tag

**Rationale**: Ensures regression protection and maintains confidence in previously validated functionality.

---

## Enforcement

All contributors must:
1. Read and understand this constitution and METHODOLOGY.md
2. Follow all principles for all code
3. Complete version control steps for all phases
4. Never compromise on standards or security

**Violations**:
- PRs not following this constitution will be rejected
- Direct commits to master will be reverted
- Untested code will not be merged

---

**Version**: 2.0.0 | **Effective Date**: January 21, 2026
