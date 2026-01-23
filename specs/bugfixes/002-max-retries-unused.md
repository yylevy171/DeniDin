# Bugfix 002: max_retries Config Value Not Used

**Created**: January 23, 2026  
**Status**: Not Started  
**Priority**: P2 (Low-Medium - Configuration inconsistency)  
**Component**: Configuration, AI Handler Retry Logic  
**Branch**: `bugfix/002-max-retries-unused`  
**Spec Location**: `specs/bugfixes/002-max-retries-unused.md`

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

**TO BE COMPLETED**: Follow BDD workflow step 1

### Investigation Notes
- [ ] Review `ai_handler.py` retry decorator at line 211-216
- [ ] Trace where `config.max_retries` is read but not used
- [ ] Check if other handlers (whatsapp_handler) have similar issue
- [ ] Determine if hardcoded value was intentional design decision

### Root Cause
*TO BE DOCUMENTED after investigation*

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

**TO BE DECIDED**: Human approval gate required

---

## Test Gap Analysis

**Why didn't tests catch this?**
- Tests may mock the retry logic
- No integration test verifying retry count matches config
- No test asserting config value is actually used

**Missing Test Cases:**
- [ ] Test that verifies actual retry count matches `config.max_retries`
- [ ] Test that changing config value changes retry behavior
- [ ] Integration test with real API failures counting retries

---

## Implementation Checklist

Following METHODOLOGY.md §VII (Bug-Driven Development):

- [ ] **Step 1**: Root cause investigation complete
- [ ] **Step 2**: 🚨 HUMAN APPROVAL - Root cause & fix option
- [ ] **Step 3**: Test gap analysis complete
- [ ] **Step 4**: Write failing tests
- [ ] **Step 5**: 🚨 HUMAN APPROVAL - Tests
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
