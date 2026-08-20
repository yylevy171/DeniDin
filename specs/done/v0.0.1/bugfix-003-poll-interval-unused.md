# Bugfix 003: poll_interval_seconds Config Value Unused

**Created**: January 23, 2026  
**Status**: ✅ Complete  
**Priority**: P3 (Low - Dead configuration)  
**Component**: Configuration, Main Bot Loop  
**Branch**: `bugfix/003-poll-interval-unused`  
**Spec Location**: `specs/bugfixes/bugfix-003-poll-interval-unused.md`

---

## Bug Description

**Observed Behavior:**
- `config.json` defines `"poll_interval_seconds": 5`
- Configuration is validated and logged at startup
- **No code uses this value** - no polling loop exists
- No `time.sleep(poll_interval)` found in codebase

**Expected Behavior:**
- Either implement message polling with this interval
- OR remove the configuration if it's legacy/planned feature

**Impact:**
- Dead configuration clutters config file
- Misleads users about bot behavior (no polling happens)
- Wastes validation/logging resources

---

## Root Cause Analysis

**COMPLETED**: January 23, 2026

### Investigation Notes
- [x] Search codebase for any WhatsApp message polling loop
- [x] Check if bot uses webhooks instead of polling
- [x] Review git history - was polling ever implemented?
- [x] Determine if this is legacy from initial design

### Root Cause
The `poll_interval_seconds` configuration value is **completely unused**:

1. **Bot uses Green API library's `bot.run_forever()`** - This is a blocking call that handles polling internally
2. **No custom polling loop exists** - No `time.sleep(poll_interval)` found anywhere in the codebase
3. **Polling interval is NOT configurable** - The Green API library controls the polling mechanism, not our application
4. **Documentation is misleading** - `DEPLOYMENT.md` line 266 claims: "Polls Green API every 5 seconds (configurable via `poll_interval_seconds`)" but this is FALSE
5. **Added during initial implementation** - Config value was included in Phase 3 (commit 9f4d93e) but never actually used

The config value was added with the assumption that we would control polling, but the Green API library handles this internally. The value serves no purpose and misleads users into thinking they can control polling frequency.

---

## Fix Options

**Option A: Remove entirely**
- Delete from config schema, validation, logging
- Remove from all config files
- Update DEPLOYMENT.md to remove false claim
- **Pros**: Clean, no dead code
- **Cons**: If future polling needed, have to re-add

**Option B: Keep as reserved/future**
- Add comment: `// RESERVED: For future polling implementation`
- Keep validation but skip logging
- **Pros**: Preserves intent, easy to activate later
- **Cons**: Still technically dead code

**Option C: Implement polling**
- Build actual WhatsApp message polling loop
- Use the configured interval
- **Pros**: Feature complete
- **Cons**: Major scope, may not be needed (if using webhooks)

**DECISION: Option A - Remove entirely** ✅ (Human approved: January 23, 2026)

Rationale: Clean approach, eliminates confusion. Green API library handles polling internally via `bot.run_forever()` - we have no control over the interval. Removing dead configuration.

---

## Test Gap Analysis

**COMPLETED**: January 23, 2026

**Why didn't tests catch this?**
- No test verifies that polling actually happens
- Tests just check config loads/validates successfully
- No integration test for bot main loop behavior
- No test checking that all config values are actually used

**Missing Test Cases:**
- N/A - removing the config value, no new tests needed

**Test Strategy for Option A:**
- Remove `poll_interval_seconds` from all config files
- Remove validation logic for this field
- Remove from `AppConfiguration` dataclass
- Remove logging of this value
- Update tests to remove references to `poll_interval_seconds`
- Update DEPLOYMENT.md to remove false claim about configurability
- Verify existing tests still pass

---

## Implementation Checklist

Following METHODOLOGY.md §VII (Bug-Driven Development):

- [x] **Step 1**: Root cause investigation complete
- [x] **Step 2**: 🚨 HUMAN APPROVAL - Root cause & fix option (Option A approved)
- [x] **Step 3**: Test gap analysis complete
- [x] **Step 4**: Write tests (SKIPPED - no new tests needed)
- [x] **Step 5**: 🚨 HUMAN APPROVAL - Tests (SKIPPED - proceeding to implementation)
- [x] **Step 6**: Implement fix
- [x] **Step 7**: Verify all tests pass (316 passed, 4 skipped)
- [ ] **Step 8**: Commit & PR with BDD format

## Implementation Summary

**Completed**: January 23, 2026

Removed `poll_interval_seconds` from configuration entirely:
- Removed from `AppConfiguration` dataclass in `src/models/config.py`
- Removed validation logic for this field
- Removed from all config files (config.json, config.example.json, config.test.json)
- Removed logging in `denidin.py`
- Updated documentation (DEPLOYMENT.md, README.md) to remove false claims about configurability
- Updated all tests to remove `poll_interval_seconds` references
- All 316 unit tests pass

Polling behavior unchanged: Green API library handles polling internally via `bot.run_forever()` - application has no control over polling interval.

---

## Files Affected

- `src/models/config.py` - Config schema and validation
- `config/config.json` - Config value
- `config/config.example.json` - Example config
- `denidin.py` - Logging references
- `tests/unit/test_config.py` - Config tests
- `tests/integration/test_bot_startup.py` - Startup tests

---

## References

- CONSTITUTION.md §I - Configuration & Secrets Management
- METHODOLOGY.md §VII - Bug-Driven Development
