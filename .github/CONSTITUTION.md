# DeniDin Project Constitution

**Established**: January 15, 2026  
**Last Updated**: January 21, 2026  
**Purpose**: Development constraints, coding standards, and technical guidelines

---

## ZERO MOCKING POLICY (ABSOLUTE)

**NO MOCKING WHATSOEVER UNTIL THE END OF ETERNITY, WITH NO EXCEPTION.**

This rule is absolute and applies to all tests, documentation samples, and code in the repository. It takes precedence over any other guidance in this Constitution or in project methodology documents. Any code, test, or PR that introduces or re-introduces mocking (including `unittest.mock`, `patch`, `MagicMock`, or in-process stubs used to simulate external services) will be rejected by CI and reviewers.

Guidelines under this rule:
- Use real sandbox endpoints, recorded immutable fixtures stored under `specs/.../artifacts/`, or controlled test environments—do NOT use in-process mocks.
- Local developer-only hack mocks used during debugging must be removed before committing.
- Additions of mocking libraries or helper utilities for mocking are forbidden in new commits.

Rationale: The project mandates realistic integration and test behavior; this absolute rule enforces that principle repository-wide.

> **Note**: This file defines WHAT we enforce (technical constraints, standards).  
> For HOW we work (workflow, process, TDD), see `METHODOLOGY.md`.  
> **When creating/updating specs**: Reference BOTH files.

---

## NO UNVERIFIED THIRD-PARTY ASSUMPTIONS (ABSOLUTE)

**No assumption about how ANY third-party system behaves — Green API, Morning (Green Invoice), OpenAI, or any other external service — may be treated as confirmed, and no spec/design decision may be built on it, without ACTUAL CONFIRMATION FROM A REAL MESSAGE/CALL AND REVIEWING THE REAL RESULT.**

Reading a vendor's published API documentation, a schema definition, an SDK's type hints, or a client library's source is **not** confirmation. Those describe what a system is *documented* to do — not what it actually does in a real, observed interaction. Only sending or receiving a real message/call through the real system and inspecting the real, raw result counts as confirmed.

**Incident that established this rule (2026-08-05, Feature 039)**: the spec for Feature 039's `"@Name"` mention-recognition design (`specs/done/v0.2.0/039-group-conversation-support/spec.md`) stated as a settled Decision that "a real WhatsApp @-mention still inserts visible `"@DisplayName"` text into the message body" — based on reviewing Green API's documented webhook schema fields and confirming no structured mention metadata existed there. That schema review was real and correct as far as it went, but the conclusion drawn from it (what the mention text itself looks like) was never independently verified against an actual live WhatsApp message. It was wrong: a real native `@`-mention (picked via WhatsApp's own mention UI, the primary way users actually mention someone) inserts the mentioned contact's raw phone number/JID into the text, not a display name. The entire `"@Name"` text-pattern recognition mechanism — spec, constitution wording, and the billed tests' hand-typed `"@רותי"`/`"@DeniDin"` fixtures alike — was built on this single unverified assumption, and none of it could ever have caught the gap, because the test fixtures inherited the same wrong assumption instead of being derived from a real captured message. This was found live, by a human, in manual post-deploy testing — not by any part of the spec, implementation, or test process that was supposed to catch exactly this.

Guidelines under this rule:
- Before a spec/plan/research document states any claim about a third-party system's actual runtime behavior (message format, field contents, response shape, timing, error behavior, etc.) as confirmed, that claim must be backed by an actual real interaction with that system, with the real raw result captured and referenced (not just "per the docs" or "per the SDK").
- If real verification isn't practical yet at spec-writing time, the claim must be marked explicitly as an **unverified assumption**, not stated as a confirmed fact — and the plan must include verifying it for real before the dependent feature is considered done, not after.
- Test fixtures exercising third-party-sourced data (webhook payloads, API responses, message text shapes, etc.) must be derived from a real captured interaction, not hand-typed based on what the author expects the shape to be — a hand-typed fixture can only ever prove "the code behaves correctly given this assumed shape," never "the assumed shape is correct."
- This applies to every third-party system this project integrates with, not just Green API — Morning/Green Invoice, OpenAI, and any future integration.

Rationale: documentation, schemas, and SDKs describe intent, not always actual behavior, and can be incomplete, outdated, or simply wrong about what a real message/response actually contains. A design decision (or a test built to validate it) resting on an unverified reading of documentation is not evidence — it's a guess wearing the clothes of a fact, and this project has now shipped a real feature to production readiness that was undermined by exactly that.

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

## II. Israel Local Time Requirement

**All timestamps in the codebase MUST use Israel local time (`Asia/Jerusalem`), as
timezone-aware datetimes.**

**Amended 2026-08-10 (bugfix-037), by explicit user decision** — this section previously
required UTC everywhere. It no longer does: **there is no UTC anywhere in this codebase.**
The change was made because three representations had accumulated with nothing labelling
which was which (unlabelled UTC log lines, `+00:00` ISO timestamps, and unlabelled local
ledger `event_date`/`event_time`), so the same instant read as `03:00:27` in one store and
`06:00` in another. Everything the system actually handles is Israeli local time — Morning
documents, bank-transfer screenshots, and Events.csv's date/time columns all state local
times — so the representation now matches the domain rather than being converted at the
edges.

**Requirements**:
1. **ALWAYS** use `now_local()` (`utils.time_utils`) - NEVER `datetime.now()` without a
   timezone, and never `datetime.now(timezone.utc)`
2. **ALWAYS** use `now_local().timestamp()` for Unix timestamps (an epoch is an instant and
   is unaffected by representation, but the call site should still read consistently)
3. **ALWAYS** store timezone-**aware** `datetime` objects. A naive local datetime is still
   forbidden: it breaks comparisons against stored values and silently gets DST wrong twice
   a year
4. **ISO format logs/records** therefore always carry the real offset (`+03:00` in IDT,
   `+02:00` in IST), so every record is self-describing
5. **Log lines** are formatted by `LocalTimeFormatter` and print the offset - never
   `logging.Formatter`'s default, which renders whatever zone the process happens to run in
6. **Code review** must verify all datetime operations resolve to `Asia/Jerusalem` explicitly

**Examples**:
```python
# ✅ CORRECT
from src.utils.time_utils import now_local
received_timestamp = now_local()

# ❌ WRONG
received_timestamp = datetime.now()                 # FORBIDDEN (naive)
received_timestamp = datetime.now(timezone.utc)     # FORBIDDEN since 2026-08-10
```

**Pre-2026-08-10 data**: values already persisted with `+00:00` remain valid and compare
correctly against new ones, precisely because both sides are timezone-aware. This is a
fix-forward change; nothing is migrated.

**Rationale**: One representation, matching the domain, stated explicitly on every record and
every log line - so no reader (human or code) has to know which store they are looking at to
know what time it says.

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
- **Bug fixes**: `bugfix/###-issue-description` (e.g., `bugfix/001-constitution-not-loaded`)
  - Use bug number from `specs/bugfixes/` directory (e.g., 001 from `specs/bugfixes/bugfix-001-constitution-not-loaded.md`)
  - Issue: concise bug description in kebab-case
  - See METHODOLOGY.md §VII for bug-fixing workflow
  - All bugfix specs MUST be stored in `specs/bugfixes/bugfix-###-description.md`
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

### Merge Workflow

**Standard Workflow Using GitHub CLI**:

```bash
# After creating PR with 'gh pr create', merge it:
gh pr merge --merge --delete-branch

# Or specify PR number:
gh pr merge 123 --merge --delete-branch
```

**Manual Git Workflow** (if preferred):

```bash
# Step 1: Ensure you're on master branch
git checkout master

# Step 2: Fetch the remote feature branch
git fetch origin

# Step 3: Merge feature branch with no-fast-forward (preserves commit history)
git merge origin/BRANCH-NAME --no-ff -m "Merge DESCRIPTION: SUMMARY"

# Step 4: Push merged changes to remote master
git push origin master

# Step 5: Delete local feature branch
git branch -d BRANCH-NAME

# Step 6: Delete remote feature branch
git push origin --delete BRANCH-NAME
```

**Key Parameters**:
- `--merge`: Create merge commit (preserves feature branch history)
- `--delete-branch`: Automatically delete branch after merge
- `--no-ff`: Forces merge commit even if fast-forward possible

**VALIDATION STEPS**:
After merge, verify success:
```bash
# Check that master has advanced
git log --oneline -5

# Verify branch is deleted locally
git branch -a | grep BRANCH-NAME  # Should return nothing for local

# Verify branch is deleted remotely
git ls-remote --heads origin BRANCH-NAME  # Should return nothing
```

**ERROR RECOVERY**:
If merge creates conflicts:
```bash
# Abort the merge
git merge --abort

# Investigate conflicts locally
git checkout BRANCH-NAME
git pull origin master
# Resolve conflicts, commit, push
# Then retry merge workflow
```

**WHEN TO USE**:
- ✅ Use this workflow for ALL merges (bug fixes, features, config changes)
- ✅ Use this even for simple one-line changes
- ✅ Use this when user says "merge" without additional context
- ❌ NEVER use `gh pr merge` unless explicitly requested by user

**SUMMARY**: 
The direct git merge workflow is the PRIMARY and PREFERRED merge method because it bypasses authentication issues and works reliably every time. It should be your FIRST ATTEMPT, not a fallback.

---

## IV. Code Quality Standards

**Requirements**:
- **Python 3 Only**: This project uses **Python 3.8+** (Python 3.11 recommended)
  - ALWAYS use `python3` command, NEVER `python` (which may point to Python 2)
  - All code must be Python 3 compatible
  - Use Python 3 features (type hints, f-strings, dataclasses, etc.)
- **Type Hints**: All functions must have type annotations
- **Docstrings**: All modules, classes, and functions must have Google-style docstrings
- **PEP 8 Compliance**: Follow Python style guide (120 char line limit)
- **Error Handling**: All external API calls must have proper error handling
- **Logging**: Appropriate logging at INFO and DEBUG levels

**Rationale**: Consistent code quality reduces technical debt and prevents subtle bugs through type safety.

---

## V. Integration Tests: End-to-End from User Perspective

**Principle**: Integration tests trace complete request flow from external entry point through all system layers to user response. They are NOT component linking tests.

**Definition**:
- **Integration Test** (End-to-End): Simulates real external entry point (Green API webhook, user input, API request) and traces complete flow through all system layers to response
  - Example: "Green API sends imageMessage webhook → router dispatches → handler processes → response sent to user"
  - Tests actual system integration from user perspective, not internal component linking
  - Entry point is OUTSIDE the application (webhook, HTTP request, etc.)
  
- **Component Integration Test** (Subsystem): Tests how internal components work together, using direct method calls or internal APIs
  - Example: "Create MediaHandler → call process_media_message() → verify extractors work"
  - Entry point is INSIDE the application (direct Python method call)
  - Tests internal component orchestration
  - **MUST be clearly labeled** to distinguish from true integration tests

**Requirements**:
- **Integration tests MUST simulate real external entry points**:
  - For Green API webhooks: Mock Green API but send real webhook JSON through bot.router dispatcher
  - For HTTP APIs: Send real HTTP requests to the application
  - For user interactions: Simulate real user action (send message, upload file, etc.)
  - Entry point is NEVER a direct Python method call to internal components
  
- **Integration tests MUST trace complete request path**:
  - External entry → Router/Dispatcher → Handler → Business Logic → Response
  - Verify EACH layer correctly passes request to next layer
  - Example: Webhook → @bot.router.message(type) → WhatsAppHandler → MediaHandler → Response
  
- **Integration tests MUST verify dispatcher/routing behavior**:
  - For each new message type: Verify @bot.router.message decorator catches the message
  - For each new endpoint: Verify correct handler is dispatched
  - For each new webhook: Verify router knows about it (no silent drops)
  - This is the CRITICAL gap that prevented detection of missing imageMessage router
  
- **Component linking tests MAY use direct method calls**:
  - Clearly label as "Component Integration" or "Subsystem Integration", NOT "Integration Test"
  - These test internal component orchestration, valid for verifying component interfaces
  - But MUST NOT be the ONLY integration layer - must have E2E integration tests above them
  
- **Real external APIs vs mocking**:
  - MUST use real application layers (routers, handlers, managers)
  - MUST mock external services (OpenAI, Green API download URLs, databases) for cost/speed
  - Example: Mock Green API webhook response but test through real bot.router dispatcher
  
- **Integration test file naming**:
  - True integration tests (E2E from external entry point): `tests/e2e/` or `tests/integration/test_*_e2e.py`
  - Component linking tests (internal method calls): `tests/component/` or `tests/subsystem/test_*_component.py`
  - Clearly distinguish so tests match their actual scope

**Why This Matters**:
The Feature 003 bug (no response when sending real image) existed because:
- ✅ Component tests verified MediaHandler + extractors work perfectly (tested internal linking)
- ❌ Integration tests never simulated Green API webhook → router dispatch (missed external entry point)
- ❌ Routers added to denidin.py were never tested (routing layer completely untested)

Integration tests must explicitly verify "when external entry arrives, does system route it correctly?"

**Rationale**: Integration tests from external perspective catch routing, dispatcher, and system-level bugs that component tests cannot. They verify the complete request path works end-to-end.

### 🚨 CRITICAL: NO MOCKING IN INTEGRATION TESTS

**ABSOLUTE RULE**: Integration tests MUST NEVER import or use `unittest.mock`.

**Forbidden**:
```python
# ❌ FORBIDDEN IN INTEGRATION TESTS
from unittest.mock import Mock, patch, MagicMock
import unittest.mock

# ❌ FORBIDDEN - even inside methods
def test_something():
    from unittest.mock import Mock  # ❌ NOT ALLOWED
    mock = Mock()
```

**What to do instead**:
- **Real system**: Use actual application code (routers, handlers, managers, models)
- **External dependencies**: Find a real service or skip the test if unavailable
  - Can't connect to OpenAI API? Use `@pytest.mark.expensive` to skip in CI/CD but run locally when needed
  - Can't download from Green API? Serve test files from local HTTP server (see test_whatsapp_e2e.py for example)
  - Can't write to production database? Use test database with real code, not mocks
- **Setup/teardown**: Create real objects, not fake ones
  - Create REAL Notification objects: `notification = Notification.__new__(Notification)` with event dict
  - Create REAL config: `config = AppConfiguration.from_file("config/config.test.json")`
  - Create REAL managers: `session_mgr = SessionManager(config)` (not `Mock(spec=SessionManager)`)

**Why No Mocking**:
1. **Mocks hide bugs**: They let tests pass while real code fails
2. **Mocks couple tests to implementation**: Refactoring breaks tests even when functionality is fine
3. **Integration tests verify REAL behavior**: They MUST use real system to catch real problems
4. **External APIs are the issue**: Mock those with actual test services/servers, not Mock objects
5. **Your tests should break if you break the code**: If tests pass with mocks but code fails, mocks lied to you

**Code Review**: Every PR with integration tests MUST verify:
- ✅ NO `import Mock` anywhere in test files
- ✅ NO `@patch` decorators
- ✅ NO `MagicMock()` calls
- ✅ NO mocking internal application components (routers, handlers, models, managers)
- ✅ OK to mock external services IF you provide real test alternatives (local HTTP server, test database, fixture files)

---

## VI. Feature Flags for Safe Deployment

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
- **Test logs location**: All test execution logs are stored in `apps/denidin-app/logs/test_logs/` (each app under `apps/` has its own `logs/test_logs/`)
  - When reviewing test results, check this directory for detailed logs
  - Logs persist across test runs for debugging and analysis
  - Never redirect test output to `/tmp` or other ad-hoc log files — use only the app's own `logs/test_logs/` location
- 🚨 **Run every billed/expensive test through `scripts/run_single_test.sh <node_id>` (2026-08-18, `apps/denidin-app` for now)** — never a raw `pytest ... | tail`/`| grep`/`| head`. A pipe truncates pytest's report *before* it's ever seen; the script instead writes pytest's complete, untruncated output to `logs/test_logs/pytest_results/<test>_<timestamp>.txt` and leaves the app's own per-test-file log untouched. For a sequence of `billed` tests with stop-on-first-failure behavior, use `scripts/run_multiple_billed_tests.sh <node_id> ...` (billed only, never expensive). Neither script grants run approval by itself — every invocation still needs its own fresh, explicit human go-ahead per the tier rules below.
- 🚨 **When driving `scripts/run_multiple_billed_tests.sh`, sound off on each test's PASSED/FAILED result AS IT COMPLETES, not only in one summary after the whole sequence finishes** — unless the human has explicitly said otherwise for that run. The script itself already announces each result individually (see the script's own header) specifically so a human watching along gets live progress; an agent driving it must not defeat that by capturing the run's entire output in one shot (backgrounding it behind a pipe/redirect/command-substitution that only resolves at EOF, e.g. `| tail -N`, `$(...)`) and reporting only once everything is done. Real incident (2026-08-26): an agent ran the script via a backgrounded call piped through `| tail -150`, which buffers ALL output until the process exits — nothing streamed for several minutes while a 23-test sweep ran, and the human had to explicitly demand a status before getting anything. Poll the running script's output (or its individual per-test result files under `logs/test_logs/pytest_results/`) at a short interval — or use a `Monitor`-equivalent — and relay each newly-completed `[N/TOTAL] PASSED/FAILED:` line to the human as soon as it appears.
- **Billed tests** (`@pytest.mark.billed`, real but text-only/cheap paid API calls, `tests/billed/` in every app in this monorepo, split out of the marker formerly named `expensive` by Feature 029, 2026-07-30): can run freely. **These are NOT gated by the approval rule below — do not stop to ask before running a billed test, ever.** No per-run approval, no one-at-a-time restriction, no log-reading requirement. The approval gate below applies ONLY to `expensive`.
- **Expensive tests** (`@pytest.mark.expensive`, real vision/image/PDF/DOCX paid API calls, costlier per run): require explicit human approval before every single run, run one at a time (never a bare `-m expensive` sweep, never `scripts/run_multiple_billed_tests.sh`), read existing logs before re-running, and only re-run a previously-failed one once confident a fix addresses it
- **"Stop on failure" means stop on failure, every single time, regardless of tier.** When a human gives an explicit sequential-run instruction ("run all N tests one by one, on pass continue, on fail stop"), EVERY failure is its own stop point requiring a full report and fresh explicit human input before investigating, fixing, re-running, or moving to the next test. Approval to fix-and-continue past one failure does NOT carry over to a later failure in the same sweep, even a structurally identical one. Real incident (2026-08-02, an AI agent): one approved fix got silently generalized into "fix-and-continue is now standing behavior for this sweep," and a later similar failure was fixed and re-run with no pause to report or ask. An accurate test-tracking log does not substitute for actually stopping at the gate.
- All code-modifying operations must use CLI tools
- **Deploying a cut release is done ONLY by running `scripts/deploy_release.sh` directly** (see CLAUDE.md's "Versioning & Release Management") — never preceded by a manual, ad-hoc pre-flight check (e.g. `tailscale status`, a manual `ssh` probe) as a substitute for the script's own built-in connectivity/health verification. The script already fails loudly and clearly if something's wrong; a manual check first is redundant, not caution.

**Test Execution Efficiency**:
- **DO NOT run tests repeatedly without code changes**
- **Workflow**:
  1. Run the test ONCE via `scripts/run_single_test.sh <node_id>` — it redirects pytest's ENTIRE output to a results file on disk for you (see above); never hand-roll a `pytest ... > file 2>&1` or, worse, a `pytest ... | tail`/`| grep` that can silently drop the part that matters
  2. Analyze that results file (`logs/test_logs/pytest_results/*.txt`) to understand failures — read it, don't re-run to "see more"
  3. Make code changes based on analysis
  4. ONLY THEN run the test again, and only with a fresh explicit approval for that specific run
- **Rationale**: 
  - Billed/expensive tests make real, paid API calls
  - Running tests wastes time and money without providing new information
  - The results file already contains complete diagnostic information - use it
  - Tests should only be re-run after code changes that might affect results, never just to capture output a previous run's own pipe happened to discard

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
  - All logs MUST include an Israel-local timestamp carrying its offset (bugfix-037; was UTC until 2026-08-10)
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

---

## XVII. NO Monkey-Patching

**Principle**: NEVER modify objects or classes at runtime. Use proper design patterns instead.

**ABSOLUTE PROHIBITION**:
- **NO runtime method replacement**: Do NOT replace methods on instances or classes after creation
- **NO dynamic attribute injection**: Do NOT add/modify attributes on objects after instantiation
- **NO function reassignment**: Do NOT reassign functions/methods at module or class level after import/definition

**Why Monkey-Patching is Forbidden**:
- **Breaks encapsulation**: Violates object-oriented design principles
- **Untestable**: Creates timing-dependent bugs that are impossible to catch in tests
- **Race conditions**: Thread-unsafe, leads to concurrency bugs
- **Maintenance nightmare**: Hidden dependencies, impossible to trace execution flow
- **Debugging hell**: Stack traces lie, breakpoints miss the actual code
- **Violates expectations**: Code doesn't do what it says it does

**Correct Alternatives**:

1. **Dependency Injection** (pass callbacks/handlers as constructor parameters):
```python
# ✅ CORRECT
class SessionManager:
    def __init__(self, on_expire_callback=None):
        self.on_expire_callback = on_expire_callback
    
    def _cleanup_expired_sessions(self):
        for session in self.find_expired():
            if self.on_expire_callback:
                self.on_expire_callback(session)
            self._archive(session)

# Usage
def transfer_to_memory(session):
    ai_handler.transfer_session_to_long_term_memory(session.whatsapp_chat, session.session_id)

session_manager = SessionManager(on_expire_callback=transfer_to_memory)
```

2. **Strategy Pattern** (pass strategy object):
```python
# ✅ CORRECT
class SessionManager:
    def __init__(self, cleanup_strategy):
        self.cleanup_strategy = cleanup_strategy
    
    def _cleanup_expired_sessions(self):
        self.cleanup_strategy.cleanup(self.find_expired())
```

3. **Template Method Pattern** (subclass and override):
```python
# ✅ CORRECT
class SessionManagerWithTransfer(SessionManager):
    def __init__(self, ai_handler, **kwargs):
        super().__init__(**kwargs)
        self.ai_handler = ai_handler
    
    def _cleanup_expired_sessions(self):
        for session in self.find_expired():
            self.ai_handler.transfer_session_to_long_term_memory(...)
        super()._cleanup_expired_sessions()
```

4. **Observer Pattern** (event-based callbacks):
```python
# ✅ CORRECT
class SessionManager:
    def __init__(self):
        self.on_expire_listeners = []
    
    def register_expire_listener(self, callback):
        self.on_expire_listeners.append(callback)
    
    def _cleanup_expired_sessions(self):
        for session in self.find_expired():
            for listener in self.on_expire_listeners:
                listener(session)
            self._archive(session)
```

**Examples of FORBIDDEN Practices**:
```python
# ❌ WRONG - Runtime method replacement
session_manager._cleanup_expired_sessions = new_cleanup_function

# ❌ WRONG - Dynamic attribute injection
session_manager.ai_handler = ai_handler

# ❌ WRONG - Module-level monkey-patching
import some_module
some_module.original_function = my_replacement_function

# ❌ WRONG - Class-level patching
SomeClass.method = new_method
```

**Rationale**: Monkey-patching creates timing-dependent bugs (like the session transfer race condition), violates software engineering principles, and makes code unmaintainable. Proper design patterns provide type-safe, testable, and maintainable solutions.

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

## XVIII. Startup-Time External Dependency Handshakes Must Retry — No One-Shot Give-Up

**Principle**: Any check performed at process/container startup against a dependency that can plausibly still be initializing at that exact moment — a local tunnel-agent API, a not-yet-ready sidecar, a discovery/handshake read of any kind — MUST poll with bounded retry before concluding failure. A single check, performed once, with no retry, is not error handling; it's a race condition waiting to happen.

**Real incident (2026-08-25)**: after an unattended Windows Update reboot of the prod host (Feature 035's reboot-recovery worked correctly — both containers came back up on their own), `morning-mcp-app-prod`'s startup code queried ngrok's local API for the tunnel's public URL exactly once, a few seconds too early, got nothing back, logged `Could not fetch ngrok public URL yet` — and never checked again. The tunnel itself came up cleanly moments later, but the shared status file it should have written stayed at `status: "not running"` for hours, with `denidin-app-prod` reading that same stale file on every turn and silently running with Morning invoicing unavailable. A real, client-facing capability outage, caused entirely by a missing retry loop around one local API call. See CLAUDE.md's "PRODUCTION INCIDENTS ARE NOT ACCEPTABLE" banner and METHODOLOGY.md §XXII for the full incident and process follow-through.

**Requirements**:
- **Bounded poll, not a single check**: retry the handshake/discovery check on a short interval (e.g. every 1–2s) for a generous but finite window (e.g. up to ~30s) appropriate to how long the dependency normally takes to become ready. Only after the window is exhausted may the code conclude and record "unavailable."
- **This is distinct from §XI's request-retry policy** (which governs a single already-established connection's transient 5xx/timeout failures, retried once). A startup handshake is instead waiting for a dependency to *finish becoming ready in the first place* — a fundamentally different shape of problem, needing a poll loop keyed to typical startup latency, not a one-shot retry keyed to network transience.
- **A status file (or equivalent shared "is this dependency up" record) must never be left in a failure state past the point where the dependency actually became ready.** If nothing re-checks and corrects it after an initial failed attempt, that's the bug — either the poll loop above prevents the false-negative from ever being written, or a background re-check corrects it afterward. Never both-absent.
- Applies to every process in this codebase with a startup-time external/local dependency check — the ngrok/MCP status-file handshake is the incident that produced this rule, but the requirement is general.

**Rationale**: a dependency that is "not ready yet" and a dependency that is "actually down" are different states with different correct responses, and conflating them by checking only once at the wrong moment turns an ordinary, expected startup race into a silent, hours-long production outage.

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

**Version**: 2.8.0 | **Effective Date**: August 25, 2026

**Changelog**:
- v2.8.0 (2026-08-25): Added **XVIII. Startup-Time External Dependency Handshakes Must Retry — No One-Shot Give-Up** after a real prod incident: `morning-mcp-app`'s ngrok-tunnel-to-status-file handshake checked once, too early, on a post-reboot restart, and never retried — leaving Morning invoicing silently unavailable in prod for hours. See METHODOLOGY.md §XXII for the mandatory incident-response follow-through this also produced.
- v2.7.0 (2026-08-18): Mandated `scripts/run_single_test.sh`/`scripts/run_multiple_billed_tests.sh` (§VII) as the required way to run any single billed/expensive test or a stop-on-first-failure billed sequence, after a real incident where an AI agent's ad-hoc `pytest ... | tail -15` silently discarded the actual assertion/traceback, leading to a wrong report and an unapproved rerun just to see the missing part
- v2.6.0 (2026-08-02): Added explicit "stop on failure means stop on failure" rule to §VII after a real incident where an AI agent generalized one approved test-fix into standing permission to skip the stop-on-fail gate for later, similarly-shaped failures in the same sequential test sweep
- v2.5.0 (2026-07-30): Feature 029 scope correction - the billed/expensive split applies to BOTH `apps/denidin-app` and `apps/morning-mcp-app` (each app's own independent marker registration), not denidin-app alone; also made explicit that billed tests are never subject to the expensive-only approval gate (§VII)
- v2.4.0 (2026-07-30): Feature 029 split the single `@pytest.mark.expensive` marker into `billed` (real, text-only, cheap OpenAI calls - can run freely) and `expensive` (real vision/image/PDF/DOCX calls - keeps the full approval/one-at-a-time discipline) (§VII)
- v2.3.0 (2026-07-07): Repo split into `apps/denidin-app/` and `apps/morning-mcp-app/` (each independently runnable/testable/dockerized) - updated test logs location path accordingly; added expensive-test approval rules (§VII)
- v2.2.0 (2026-01-22): Added **XVII. NO Monkey-Patching** - absolute prohibition with correct design pattern alternatives (dependency injection, strategy, template method, observer)
- v2.1.0 (2026-01-21): Added 8 technical standards from existing practice: Logging Standards (IX), Error Response Format (X), Retry Logic Details (XI), API Response Handling (XII), Data Validation (XIII), File Path Handling (XIV), JSON/File Format Standards (XV), Exit Code Standards (XVI)
- v2.0.0 (2026-01-21): Split from methodology - isolated coding standards and technical constraints
- v1.2.0 (2026-01-17): Previous unified constitution with 16 principles
