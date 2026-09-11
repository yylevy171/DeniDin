# DeniDin AI Assistant Instructions

**Purpose**: Core constraints and standards for all AI-assisted development on DeniDin  
**Auto-loaded**: This file is attached to every prompt context  
**Reference**: See `.github/CONSTITUTION.md` for full details

---

## 🚨 CRITICAL RULES (ALWAYS FOLLOW)

### 1. NEVER Work on Master Branch
- Check branch: `git branch --show-current`
- If on master: `git checkout -b feature/###-description`
- STOP if unsure about feature number/name

### 2. NO Environment Variables
- **FORBIDDEN**: `os.getenv()`, `os.environ`
- **REQUIRED**: All config in `config/config.json` only
- Pass config objects as parameters (dependency injection)

### 3. Israel Local Timestamps ALWAYS (amended 2026-08-10, bugfix-037)
- ✅ `now_local()` (`utils.time_utils`) — aware, `Asia/Jerusalem`, offset on every record
- ❌ `datetime.now()` (naive)
- ❌ `datetime.now(timezone.utc)` — no UTC anywhere in this codebase any more

### 4. NO Monkey-Patching
- **FORBIDDEN**: Runtime method replacement, dynamic attribute injection
- **USE INSTEAD**: Dependency injection, strategy pattern, observer pattern, template method
- Creates untestable race conditions and violates OOP

### 5. Type Hints & Docstrings Required
- All functions: type annotations
- All modules/classes: Google-style docstrings
- PEP 8: 120 char line limit

### 6. Use pathlib.Path NOT strings
- ✅ `from pathlib import Path; path / "subdir" / "file.json"`
- ❌ `"path/to/file.json"` or `os.path.join()`

---

## Error Handling

### Retry Policy
- **5xx errors**: Retry ONCE after 1 second
- **4xx errors**: DO NOT retry (permanent)
- **Timeouts**: 30 seconds for API calls

### User-Facing Errors (Friendly!)
- Never expose stack traces
- Format: `"[Emoji] [What happened]. [What to do next]."`
- Examples:
  - "Sorry, I'm having trouble connecting to my AI service. Please try again later."
  - "I'm receiving too many messages right now. Please wait a moment and try again."

### Internal Errors (Technical)
- Log full stack trace at DEBUG/ERROR level
- Include context: message_id, session_id, user_id

---

## Testing

### Integration Tests: E2E from User Perspective
- **Integration Test** = External entry point (webhook, HTTP request, user action) → complete system flow → response
  - Example: "Green API webhook → @bot.router dispatcher → handler → response to user"
  - Entry point is OUTSIDE the application, not a direct Python method call
- **Component Test** = Direct Python method calls linking internal components
  - Valid for testing component interfaces, but NOT the complete integration
- **Critical for routing**: Integration tests MUST verify dispatchers/routers work
  - For each new message type: Test that @bot.router.message catches it (Feature 003 bug: imageMessage router missing)
- See `.github/CONSTITUTION.md §V` for full integration test requirements

### Pytest Commands
Run from inside the app you're working on: `cd apps/denidin-app` or `cd apps/morning-mcp-app`.
```bash
# All tests (billed + expensive tests skipped by default)
pytest tests/ -v

# Unit tests only
pytest tests/unit/ -v

# Single test
pytest tests/unit/test_module.py::test_function -xvs
```

### 🚨 Per-test sound-off — the permanent default for EVERY test run
- Every test's result (pass/fail/error/skip) is relayed to the human as its **own line, the moment it lands** — serial, parallel, sanity, bare `pytest`, every tier. Never a single end-of-run summary. Never something the human should have to ask for.
- Enforced in code: both apps' `conftest.py` print `>>> TEST [k/N] STATUS: <nodeid>` per test by default (opt out only `DENIDIN_TEST_SOUNDOFF=0` — never done). Driver must surface each line live (`Monitor`/`tail -f`, or poll `logs/test_logs/pytest_results/`) — never background a run behind `| tail`/`| grep`/`$(...)` and report at the end. CONSTITUTION §VII, METHODOLOGY §VI.

### Billed Tests (both apps, real text-only OpenAI calls - `tests/billed/`, `@pytest.mark.billed`)
- Cheap per run - **can run freely**, no per-run approval or one-at-a-time restriction
- **Never stop to ask before running one** - the approval gate below is `expensive`-only

### Expensive Tests (real, paid API calls - `tests/expensive/`, `@pytest.mark.expensive`)
- **Human approval required before every single run** - no exceptions, even one test, even mid-task
- **Never run them all together** - one test at a time, never a bare `-m expensive` sweep
- Read `logs/test_logs/` before re-running - don't burn money re-deriving known info
- Only re-run a previously-failed one once confident a fix addresses it

### Sanity Suite (`@pytest.mark.sanity`, Feature 059)
- Curated cross-app subset; every sanity test is ALSO `billed` or `expensive` and keeps that tier's rules
- `./scripts/run_sanity.sh` (repo root): gate (`morning-mcp-app`) then `denidin-app` billed subset, one test at a time **only through `run_single_test.sh`** (never a bare `-m` batch). Stop-on-fail, live sound-off, resumable state in `sanity_state.tsv` (`--status`/`--fresh`/`--mark`). `expensive` members are a printed checklist, never auto-run.
- `./scripts/verify_sanity_lists.sh` - guards the decorators vs `run_sanity.sh`'s arrays against drift. Failures log: `specs/done/059-.../sanity-failures.md`
- Fast "anything obviously broken end-to-end" pass. Not a substitute for the full tiers. Not CI.

### Test Standards
- Once approved, tests are IMMUTABLE (never modify without human approval)
- New phases ADD new tests, never modify existing ones
- Unit tests MAY set feature flags to test new features
- Integration tests MUST NEVER set feature flags (test production behavior)
- Integration tests MUST simulate real entry points (not bypass routers)

### Common Test Issues
- **SWIG warnings**: Already suppressed in `pytest.ini`
- **ChromaDB readonly**: Use `shutil.rmtree(path, onerror=remove_readonly_handler)`
- **Mocks not working**: Ensure code uses `ai_handler.send_message()` not `client.chat.completions.create()`

---

## Logging

### Format
```python
logger.info(f"[msg_id={msg_id}] [recv_ts={timestamp.isoformat()}] Message received")
logger.debug(f"[msg_id={msg_id}] API request details")
logger.error(f"[msg_id={msg_id}] Error occurred", exc_info=True)
```

### Rules
- **INFO**: Events, state transitions
- **DEBUG**: Parsing details, config, API details
- **ERROR**: Exceptions, failures
- **WARNING**: Recoverable issues
- Mask sensitive data: API keys (first/last 4 chars), phone numbers (middle digits)

---

## Git Workflow

### Create Feature Branch
```bash
git checkout -b feature/###-description
```

### Commit (Conventional Commits)
```bash
git commit -m "feat: description (CHK###)

- Change A
- Change B

CHK Requirements: CHK###
Tasks: TASK-### complete"
```

### Push & Create PR
```bash
git push -u origin feature/###-description
gh pr create --title "Feature ###: Description"
```

### Merge (Direct git merge preferred)
```bash
git checkout master
git fetch origin
git merge origin/BRANCH-NAME --no-ff -m "Merge description"
git push origin master
git branch -d BRANCH-NAME
git push origin --delete BRANCH-NAME
```

---

## Code Patterns

### Dependency Injection (Preferred for flexibility)
```python
class SessionManager:
    def __init__(self, on_expire_callback=None):
        self.on_expire_callback = on_expire_callback
    
    def _cleanup(self):
        if self.on_expire_callback:
            self.on_expire_callback(session)
```

### Observer Pattern (For multiple listeners)
```python
class SessionManager:
    def __init__(self):
        self.listeners = []
    
    def register(self, callback):
        self.listeners.append(callback)
    
    def _notify(self):
        for listener in self.listeners:
            listener(event)
```

---

## Data Validation

**Location**: Validate at entry points (handlers/controllers)

```python
def validate_config(config) -> List[str]:
    warnings = []
    if not valid_format(config.field):
        warnings.append("field format invalid: expected X")
    return warnings
```

---

## Feature Flags

### Pattern
```python
if config.feature_flags.get("enable_feature", False):
    new_behavior()
else:
    existing_behavior()
```

### Rules
- New features MUST be behind flags (default: False)
- When disabled, behavior MUST be identical to pre-feature code
- Unit tests MAY set flags to test new features
- Integration tests MUST NEVER set flags

---

## File Formats

### JSON
- 2 space indentation
- Alphabetical keys
- UTF-8 encoding
- Pretty-print for config/data, minified for logs

### Line Endings
- LF (`\n`) only - use `git config core.safecrlf true`

---

## Exit Codes

- `0`: Success
- `1`: General error
- `2`: Config error
- `3`: Dependency error
- `130`: Interrupted (Ctrl+C)
- `143`: Terminated (SIGTERM)

**Rule**: Never exit during normal operation - catch and log all exceptions.

---

## Common Patterns to AVOID

❌ `os.getenv()` - Use config.json  
❌ `datetime.now()` / `datetime.now(timezone.utc)` - Use `now_local()`  
❌ Monkey-patching - Use design patterns  
❌ String paths - Use `pathlib.Path`  
❌ Stack traces to users - Use friendly errors  
❌ Retrying 4xx errors - Only retry 5xx  
❌ Direct client calls in testable code - Use abstraction layers  

---

## Quick Checklist

- [ ] On feature branch (not master)
- [ ] Israel-local, timezone-aware timestamps throughout
- [ ] No environment variables
- [ ] Type hints & docstrings
- [ ] Validation at entry points
- [ ] Graceful error handling (5xx only)
- [ ] User-friendly error messages
- [ ] Tests pass locally
- [ ] Feature flags for new code
- [ ] No monkey-patching
- [ ] Using pathlib.Path for files

---

**Last Updated**: July 7, 2026  
**Version**: 1.1.0 (Instruction File)

See `.github/CONSTITUTION.md` for complete reference documentation.
