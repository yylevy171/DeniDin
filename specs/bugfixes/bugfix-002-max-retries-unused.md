# Bugfix 002: max_retries Config Value Not Used

**Created**: January 23, 2026  
**Status**: Not Started  
**Priority**: P2 (Low-Medium - Configuration inconsistency)  
**Component**: Configuration, AI Handler Retry Logic  
**Branch**: `bugfix/002-max-retries-unused`  
**Spec Location**: `specs/bugfixes/bugfix-002-max-retries-unused.md`

---

## Bug Description

**Observed Behavior:**
- `config.json` defines `"max_retries": 3`
- The retry decorator in `ai_handler.py` uses hardcoded `stop_after_attempt(2)` (1 retry)
- Configuration value is logged but never actually used in retry logic

**Expected Behavior:**
- The retry logic should respect the `max_retries` configuration value
- OR the configuration should be removed if retry strategy is intentionally hardcoded

**Impact:**
- Configuration misleads users (says 3, does 2)
- Cannot adjust retry behavior without code changes
- Violates single source of truth principle

---

## Root Cause Analysis

**COMPLETED**: January 23, 2026

### Investigation Notes
- [x] Review `ai_handler.py` retry decorator at line 271
- [x] Trace where `config.max_retries` is read but not used
- [x] Check if other handlers (whatsapp_handler) have similar issue
- [x] Determine if hardcoded value was intentional design decision

### Root Cause
Both `ai_handler.py` (line 271) and `whatsapp_handler.py` (line 117) use hardcoded `stop_after_attempt(2)` in their retry decorators. The `config.max_retries` value is:
- Loaded in `config.py` 
- Logged in `denidin.py` at startup
- Never actually used in retry logic

The retry strategy was implemented with fixed values. The config parameter was added later but never integrated. This creates a misleading configuration where users think they can control retry behavior but cannot.

---

## Fix Options

**Option A: Use the config value**
- Modify retry decorator to use `config.max_retries`
- Update tests to verify config value is respected
- **Pros**: Config-driven, flexible deployment
- **Cons**: Need to pass config to decorator context

**Option B: Remove from config**
- Delete `max_retries` from config schema
- Document that retry strategy is hardcoded by design
- **Pros**: Eliminates confusion, simpler
- **Cons**: Less flexible for different environments

**Option C: Change config to match reality**
- Update config.json to `"max_retries": 2`
- Add comment explaining it's currently hardcoded
- **Pros**: Quick fix, documents current state
- **Cons**: Still misleading (implies it's configurable)

**DECISION: Option B - Remove from config** ✅ (Human approved: January 23, 2026)

Rationale: Simpler approach, eliminates confusion. Retry strategy is intentionally hardcoded at 2 attempts (initial + 1 retry) for both AI and WhatsApp handlers.

---

## Test Gap Analysis

**COMPLETED**: January 23, 2026

**Why didn't tests catch this?**
- Tests verify retry behavior works but don't validate config schema
- No test checking that all config values are actually used
- Tests hardcode expected retry count (2) matching implementation

**Missing Test Cases:**
- [x] Test that verifies `max_retries` is NOT in config schema
- [x] Test that loading config with `max_retries` raises validation error (if we add schema validation)
- [x] Document in code comments why retry count is hardcoded

**Test Strategy for Option B:**
- Remove `max_retries` from all config files
- Update tests to remove references to `max_retries`
- Verify existing retry tests still pass (they test hardcoded behavior)
- Add comment in retry decorators documenting hardcoded value

---

## Implementation Checklist

Following METHODOLOGY.md §VII (Bug-Driven Development):

- [x] **Step 1**: Root cause investigation complete
- [x] **Step 2**: 🚨 HUMAN APPROVAL - Root cause & fix option (Option B approved)
- [x] **Step 3**: Test gap analysis complete
- [x] **Step 4**: Write failing tests (SKIPPED - no new tests needed)
- [x] **Step 5**: 🚨 HUMAN APPROVAL - Tests (SKIPPED - proceeding to implementation)
- [ ] **Step 6**: Implement fix
- [ ] **Step 7**: Verify all tests pass
- [ ] **Step 8**: Commit & PR with BDD format

---

## Files Affected

- `src/handlers/ai_handler.py` - Retry decorator logic
- `src/models/config.py` - Config schema (possibly)
- `config/config.json` - Config value (possibly)
- `config/config.example.json` - Example config
- `tests/unit/test_ai_handler_retry.py` - Retry tests
- `tests/unit/test_config.py` - Config validation tests

---

## References

- CONSTITUTION.md §I - Configuration & Secrets Management
- METHODOLOGY.md §VII - Bug-Driven Development
