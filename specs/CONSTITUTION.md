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
- **NO os.getenv()**: Do not use `os.getenv()` or `os.environ` anywhere in the codebase
- **Secrets storage**: API keys and tokens stored in `config/config.json` (excluded from git via `.gitignore`)
- **Feature flags**: Use `config.feature_flags` dictionary for enabling/disabling features
  - New features MUST be gated behind feature flags (default: `false`)
  - When flag is disabled, code flow MUST NOT CHANGE from pre-feature implementation
  - **NEVER modify existing working code** - only ADD new code paths that execute when flag is enabled
  - Implementation pattern: `if config.feature_flags.get('enable_feature'): new_behavior() else: existing_behavior()`
  - This guarantees backward compatibility and safe gradual rollout
  - **FEATURE FLAGS MUST NEVER APPEAR IN TESTS**:
    - DO NOT test feature flags directly (no `if feature_flag:` in tests)
    - DO NOT write tests with different behavior based on flag state
    - **Unit tests**: MAY set feature flags in test configs to test new feature behavior
    - **Integration tests**: MUST NEVER set feature flags - they test default production behavior
    - New feature unit tests should ASSUME the feature flag is enabled
    - Existing tests for pre-feature behavior MUST NOT CHANGE when feature is added
    - If enabling a feature flag causes existing tests to fail, investigate why - this indicates the feature violated backward compatibility
- **Example config**: Always maintain `config/config.example.json` with safe placeholder values
- **Validation**: Validate all configuration at startup with clear error messages
- **Logging**: Log configuration (mask sensitive values like API keys)
- **Testing**: Tests load config from `config/config.test.json` to create clients/objects (NO env vars). External API calls should still be mocked to avoid costs/network dependencies.
- **Dependency injection**: Pass configuration-dependent objects (e.g., OpenAI client) as parameters from main entry point

**Rationale**:
- Single source of truth for all configuration
- Easier to understand and debug (no hidden environment dependencies)
- Simpler deployment (just copy config file)
- Explicit configuration loading prevents "works on my machine" issues
- Config-based testing reflects real initialization patterns while mocking external APIs

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

**🚨 CRITICAL RULE - ALWAYS ON A FEATURE BRANCH**:
- **NEVER work on master branch directly** - ALL changes MUST be on a feature branch
- **BEFORE starting ANY work**: Check current branch with `git branch --show-current`
- **If on master**: IMMEDIATELY create feature branch with `git checkout -b feature/###-description`
- **If unsure what feature you're working on**: STOP and ASK the user for:
  - Feature number (e.g., 003)
  - Feature name (e.g., media-processing)
  - Phase/component (e.g., phase1, phase2)
- **Example branch names**: `feature/003-media-processing-phase2`, `feature/014-user-auth`, `docs/update-readme`

**Branch Naming Convention**:
- **Features**: `feature/###-description` (e.g., `feature/003-media-processing-phase1`)
  - Use feature number from specs directory (e.g., 003 from `specs/in-progress/003-media-document-processing/`)
  - Include phase/component for multi-phase features (e.g., `-phase1`, `-phase2`)
- **Bug fixes**: `bugfix/component-issue-description` (e.g., `bugfix/session-expiry-memory-transfer`)
  - Component: affected module/system (e.g., `session`, `memory`, `auth`)
  - Issue: concise bug description in kebab-case
  - See METHODOLOGY.md §VII for bug-fixing workflow
- **Other**: `docs/`, `chore/` prefixes for non-feature, non-bugfix work

**Requirements**:
- NEVER push directly to master - ALL work on feature branches
- All tests must pass before creating PR
- Use CLI tools (`git`, `gh`) for all version control operations
- Merge commits (not squash) to preserve commit history
- Delete branches after merge

### Standard Git/GitHub Workflow

**For Every Task/Phase**:

```bash
# 1. Create and switch to feature branch
git checkout -b feature/###-description

# 2. Make changes, write tests, implement code
# ... work on files ...

# 3. Stage changes (be selective - only relevant files)
git add path/to/file1.py path/to/file2.py path/to/test_file.py

# 4. Commit with descriptive message following conventional commits
git commit -m "feat: implement XYZ (CHK###)

- Add feature A with validation
- Add tests covering scenarios B, C
- Update configuration for D

CHK Requirements: CHK001-004, CHK012-015
Tasks: TASK-00X complete"

# 5. Push to remote (first time)
git push -u origin feature/###-description

# 6. Create Pull Request with detailed description
gh pr create --title "Feature ###: Description" --body "## Summary

**Tasks Completed**: TASK-00X to TASK-00Y

### Changes
- List key changes
- Include test results
- Reference CHK requirements

### Test Results
- X tests passing
- Y% coverage

### Files Changed
- path/to/file1.py
- path/to/file2.py" --base master

# 7. Merge PR (regular merge, not squash)
# Via GitHub web interface OR:
git checkout master
git merge --no-ff feature/###-description -m "Merge pull request #X from user/feature/###-description

Feature Description"
git push origin master

# 8. Delete local branch after merge
git branch -d feature/###-description

# 9. Delete remote branch (if not auto-deleted)
git push origin --delete feature/###-description
```

### Commit Message Format

Follow **Conventional Commits** specification:

```
<type>: <short summary> (CHK###)

<detailed description>
- Bullet points for key changes
- Test coverage information
- Dependencies or breaking changes

CHK Requirements: CHK###, CHK###
Tasks: TASK-### complete
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `test`: Adding tests
- `refactor`: Code refactoring
- `docs`: Documentation changes
- `chore`: Maintenance tasks

**Examples**:

```bash
# Good commit message
git commit -m "feat: Phase 1 - Document Models & Media Config (CHK001-048)

Implements Feature 003 Phase 1 using TDD:
- Document type enum with 5 types
- MediaAttachment with file size validation
- MediaConfig with centralized constants
- 48 tests, 100% coverage, pylint 10/10

CHK Requirements: CHK001-004, CHK012-018, CHK039-048
Tasks: TASK-001 to TASK-005 complete (Phase 1: 5/5)"

# Bad commit message
git commit -m "updates"  # ❌ Too vague
git commit -m "fixed stuff"  # ❌ Not descriptive
```

### Pull Request Best Practices

**PR Title**: `Feature ###: Clear Description`

**PR Body Template**:
```markdown
## Summary
Brief overview of what this PR accomplishes

## Tasks Completed
- [x] TASK-00X: Description
- [x] TASK-00Y: Description

## Changes
- Bullet point list of key changes
- Include file names and what changed

## Test Results
```
pytest output showing passing tests
Coverage: XX%
```

## CHK Requirements Validated
- CHK###: Description
- CHK###: Description

## Files Changed
- `path/to/file.py` - What changed
- `path/to/test.py` - What tests added

## Next Steps
What comes after this PR
```

**Rationale**: 
- Feature branches enable proper code review and isolated development
- Merge commits preserve full commit history for detailed audit trail
- Conventional commits provide clear, searchable history
- Detailed PR descriptions serve as documentation
- CLI workflow ensures consistency and automation

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

## IX. Logging Standards

**Principle**: Structured, consistent logging with correlation IDs for request tracing.

**Requirements**:
- **Log Format**: `[msg_id={uuid}] [recv_ts={timestamp}] {log_message}`
  - All logs related to message processing MUST include message_id
  - All logs MUST include UTC timestamp in ISO format
- **Log Levels**:
  - **INFO**: Application events, message flow, state transitions
  - **DEBUG**: Detailed parsing, configuration, API request/response details
  - **ERROR**: Exceptions, failures, error recovery attempts
  - **WARNING**: Recoverable issues, deprecation notices, configuration warnings
- **Sensitive Data Masking**:
  - API keys: Log only first/last 4 characters: `sk-...xyz123`
  - Phone numbers: Mask middle digits: `+972-50-***-1234`
  - User content: Never log full message content at INFO level (DEBUG only, if needed)
- **Correlation IDs**: Use message_id or session_id to trace related logs
- **Structured Fields**: Include context fields (user_role, whatsapp_chat, session_id) when available

**Examples**:
```python
# ✅ CORRECT
logger.info(f"[msg_id={message_id}] [recv_ts={timestamp.isoformat()}] Processing message from {whatsapp_chat}")
logger.debug(f"[msg_id={message_id}] API request: POST /v1/chat/completions")
logger.error(f"[msg_id={message_id}] Failed to send message: {error}", exc_info=True)

# ❌ WRONG
logger.info("Processing message")  # No correlation ID
logger.info(f"User said: {full_message_content}")  # Sensitive data at INFO level
```

**Rationale**: Structured logging enables efficient debugging, correlation IDs enable tracing across distributed operations, sensitive data masking protects privacy.

---

## X. Error Response Format Standards

**Principle**: User-facing error messages must be friendly, actionable, and consistent.

**Requirements**:
- **User-Facing Errors**:
  - No technical jargon or stack traces
  - Explain what went wrong in simple terms
  - Tell user what to do next (retry, contact support, check input)
  - Consistent emoji/tone across error types
- **Error Message Format**: `"[Emoji] [What happened]. [What to do next]."`
- **Standard Error Messages**:
  - AI Service Unavailable: `"Sorry, I'm having trouble connecting to my AI service. Please try again later."`
  - Rate Limit: `"I'm receiving too many messages right now. Please wait a moment and try again."`
  - Invalid Input: `"I can only process text messages right now. Please send text instead of [media type]."`
  - Configuration Error: `"I'm not configured correctly. Please contact support."`
  - Unknown Error: `"Something went wrong. Please try again or contact support if this persists."`
- **Internal Errors**: Log full technical details (stack trace, context) at DEBUG/ERROR level
- **Error Codes**: Optional internal error codes for support reference (not shown to user)

**Example**:
```python
# ✅ CORRECT
try:
    response = ai_service.get_response(message)
except TimeoutError:
    logger.error(f"[msg_id={msg_id}] AI service timeout", exc_info=True)
    return "⏱️ Sorry, I'm having trouble connecting to my AI service. Please try again later."

# ❌ WRONG
except Exception as e:
    return f"Error: {str(e)}"  # Technical error exposed to user
```

**Rationale**: Friendly error messages improve user experience, actionable guidance reduces support burden, consistent format builds user trust.

---

## XI. Retry Logic Details

**Principle**: Retry transient failures intelligently; fail fast on permanent errors.

**Requirements**:
- **Retry Policy**:
  - **5xx Server Errors**: Retry ONCE after 1 second delay
  - **Network Timeout**: Retry ONCE after 1 second delay
  - **Connection Errors**: Retry ONCE after 1 second delay
  - **4xx Client Errors**: DO NOT retry (permanent failure)
  - **Authentication Errors (401, 403)**: DO NOT retry (configuration issue)
- **Timeout Values**:
  - API calls: 30 seconds default timeout
  - Network requests: 10 seconds connect timeout, 30 seconds read timeout
  - Database operations: 5 seconds timeout
- **Circuit Breaker** (for critical services):
  - After 3 consecutive failures: Stop retrying for 60 seconds
  - Log circuit breaker state changes
  - Resume attempts after cooldown period
- **Idempotency**: Retried operations MUST be idempotent (no duplicate side effects)
- **Logging**: Log all retry attempts with attempt number and reason

**Example**:
```python
# ✅ CORRECT
@retry(
    stop=stop_after_attempt(2),  # Original + 1 retry
    wait=wait_fixed(1),           # 1 second wait
    retry=retry_if_exception_type((TimeoutError, ConnectionError)),
    retry_error_callback=lambda retry_state: None  # 5xx only
)
def call_api(request):
    response = requests.post(url, json=request, timeout=30)
    if response.status_code >= 500:
        raise requests.exceptions.HTTPError("5xx error")
    response.raise_for_status()  # Raises for 4xx, no retry
    return response.json()
```

**Rationale**: Smart retry logic improves reliability for transient failures, avoids wasting resources on permanent failures, prevents cascading failures with circuit breaker.

---

## XII. API Response Handling

**Principle**: Validate all API responses; handle unexpected formats gracefully.

**Requirements**:
- **Response Validation**:
  - Check HTTP status code before processing body
  - Validate response Content-Type matches expected format
  - Verify required fields present in JSON response
  - Check data types match expected schema
  - Validate ranges/constraints (e.g., token counts, lengths)
- **Unexpected Formats**:
  - Log full response for debugging (DEBUG level)
  - Return graceful error to user
  - Do NOT crash on missing/extra fields
- **Partial Failures**:
  - Process what succeeded
  - Log what failed
  - Return partial results with warning if applicable
- **Timeout Handling**:
  - All API calls MUST have explicit timeout
  - Log timeout occurrences
  - Return user-friendly timeout message

**Example**:
```python
# ✅ CORRECT
response = requests.post(url, json=request, timeout=30)
if response.status_code != 200:
    logger.error(f"API error: {response.status_code} - {response.text}")
    raise APIError(f"Unexpected status: {response.status_code}")

data = response.json()
if "choices" not in data or not data["choices"]:
    logger.error(f"Invalid response format: {data}")
    raise APIError("Missing required field: choices")

return data["choices"][0]["message"]["content"]

# ❌ WRONG
data = response.json()  # No status check
return data["choices"][0]["message"]["content"]  # No validation, will crash
```

**Rationale**: Response validation prevents crashes from API changes, graceful handling improves reliability, detailed logging aids debugging.

---

## XIII. Data Validation Standards

**Principle**: Validate all inputs at entry points; fail fast with clear messages.

**Requirements**:
- **Validation Location**: Validate at handler/controller layer (entry point)
- **Validation Approach**:
  - Type validation: Use type hints + runtime checks for external inputs
  - Required fields: Check for None/empty before processing
  - Format validation: Regex for phone numbers, UUIDs, etc.
  - Range validation: Min/max for numbers, lengths for strings
  - Enum validation: Check against allowed values list
- **Validation Error Messages**:
  - Format: `"[Field] [issue]: [expected format/value]"`
  - Example: `"whatsapp_chat format invalid: expected phone@c.us"`
- **Validation Functions**:
  - Create reusable validation functions for common patterns
  - Return `List[str]` of validation warnings/errors
  - Log validation failures at WARNING level
- **Default Values**: Provide safe defaults for optional fields (document in config)

**Example**:
```python
# ✅ CORRECT
def validate_memory_config(config) -> List[str]:
    warnings = []
    
    if config.godfather_phone and not config.godfather_phone.endswith(("@c.us", "@g.us")):
        warnings.append("godfather_phone format invalid: expected phone@c.us")
    
    if not 0.0 <= config.memory_min_similarity <= 1.0:
        warnings.append("memory_min_similarity must be between 0.0 and 1.0")
    
    if config.session_token_limits.get("client", 0) > config.session_token_limits.get("godfather", 0):
        warnings.append("client token limit exceeds godfather limit")
    
    return warnings

warnings = validate_memory_config(config)
if warnings:
    for warning in warnings:
        logger.warning(f"Config validation: {warning}")
```

**Rationale**: Early validation prevents cascading failures, clear messages aid debugging, reusable validators reduce code duplication.

---

## XIV. File Path Handling

**Principle**: Use consistent, safe path handling across all platforms.

**Requirements**:
- **Path Type**: Use `pathlib.Path` for all file operations (not string concatenation)
- **Relative vs Absolute**:
  - Configuration: Accept relative paths (relative to project root)
  - Internal operations: Convert to absolute paths immediately
  - Logging: Log absolute paths for clarity
- **Path Separators**: Use `/` in documentation/config; `pathlib` handles platform differences
- **Path Validation**:
  - Check paths exist before reading: `path.exists()`
  - Check parent directory exists before writing: `path.parent.mkdir(parents=True, exist_ok=True)`
  - Validate paths are within expected directories (prevent path traversal)
- **Home Directory**: Use `Path.home()` for user-specific paths
- **Platform Compatibility**: Never hardcode `/` or `\\` in code; use `pathlib` methods

**Example**:
```python
# ✅ CORRECT
from pathlib import Path

project_root = Path(__file__).parent.parent  # Relative to current file
config_path = project_root / "config" / "config.json"  # Path composition

if not config_path.exists():
    raise FileNotFoundError(f"Config not found: {config_path.absolute()}")

data_dir = project_root / "data" / "sessions"
data_dir.mkdir(parents=True, exist_ok=True)  # Create if needed

# ❌ WRONG
config_path = "config/config.json"  # String concatenation
if not os.path.exists(config_path):  # os.path instead of pathlib
    raise FileNotFoundError("Config not found")
```

**Rationale**: `pathlib` provides platform-independent path handling, validation prevents security issues, absolute paths aid debugging.

---

## XV. JSON & File Format Standards

**Principle**: Consistent, readable file formats across the project.

**Requirements**:
- **JSON Formatting**:
  - Indentation: 2 spaces (not tabs)
  - Key ordering: Alphabetical (use `sort_keys=True` in production)
  - No trailing commas
  - UTF-8 encoding
  - Pretty-print for human-readable files (config, data)
  - Minified for logs (single line)
- **JSON Schema**:
  - Document expected schema in docstrings or separate schema files
  - Validate JSON against schema on load
  - Provide example JSON files (`.example.json`)
- **File Encoding**: UTF-8 for all text files (code, config, data, logs)
- **Line Endings**: LF (`\n`) only - configure git: `* text=auto eol=lf`
- **File Naming**:
  - Config: `config.json`, `config.example.json`
  - Data: `{entity}_{id}.json` (e.g., `session_abc123.json`)
  - Logs: `{name}.log` (e.g., `denidin.log`)
  - Tests: `test_{module}.py`

**Example**:
```python
# ✅ CORRECT - Writing JSON
import json
from pathlib import Path

data = {"session_id": "abc123", "messages": []}
path = Path("data/sessions/abc123.json")
path.parent.mkdir(parents=True, exist_ok=True)

with path.open("w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)

# ✅ CORRECT - Reading JSON
with path.open("r", encoding="utf-8") as f:
    data = json.load(f)

# ❌ WRONG
with open("data.json", "w") as f:  # No encoding specified
    json.dump(data, f)  # No indent, not readable
```

**Rationale**: Consistent formatting improves readability, UTF-8 supports international characters, schemas enable validation.

---

## XVI. Exit Code Standards

**Principle**: Use standard exit codes for consistent error reporting.

**Requirements**:
- **Exit Codes**:
  - `0`: Success (normal termination)
  - `1`: General error (unhandled exception, unknown failure)
  - `2`: Configuration error (missing/invalid config.json)
  - `3`: Dependency error (missing required library, API unavailable)
  - `130`: Interrupted by user (SIGINT/Ctrl+C)
  - `143`: Terminated by signal (SIGTERM)
- **Exit Behavior**:
  - Application exits ONLY on:
    - Startup failures (config error, dependency error)
    - Explicit signals (SIGINT, SIGTERM)
  - Application NEVER exits during normal operation
  - Catch and log exceptions; continue processing
- **Signal Handling**:
  - Register signal handlers for SIGINT and SIGTERM
  - Perform graceful shutdown (close connections, save state)
  - Exit with appropriate code
- **Logging on Exit**:
  - Log exit reason and code
  - Log cleanup actions performed

**Example**:
```python
# ✅ CORRECT
import signal
import sys

def signal_handler(signum, frame):
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    cleanup()  # Close connections, save state
    sys.exit(130 if signum == signal.SIGINT else 143)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

try:
    config = load_config()
except FileNotFoundError:
    logger.error("Config file not found: config/config.json")
    sys.exit(2)  # Configuration error
except Exception as e:
    logger.error(f"Failed to load config: {e}", exc_info=True)
    sys.exit(2)

try:
    main_loop()  # Never exits except on signal
except Exception as e:
    logger.error(f"Unhandled exception in main loop: {e}", exc_info=True)
    # Log and continue, don't exit
```

**Rationale**: Standard exit codes enable automated monitoring, graceful shutdown prevents data loss, signal handling enables clean restarts.

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

**Version**: 2.1.0 | **Effective Date**: January 21, 2026

**Changelog**:
- v2.1.0 (2026-01-21): Added 8 technical standards from existing practice: Logging Standards (IX), Error Response Format (X), Retry Logic Details (XI), API Response Handling (XII), Data Validation (XIII), File Path Handling (XIV), JSON/File Format Standards (XV), Exit Code Standards (XVI)
- v2.0.0 (2026-01-21): Split from methodology - isolated coding standards and technical constraints
- v1.2.0 (2026-01-17): Previous unified constitution with 16 principles
