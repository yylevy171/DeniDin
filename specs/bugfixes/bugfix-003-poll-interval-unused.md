# Bugfix 003: poll_interval_seconds Config Value Unused

**Created**: January 23, 2026  
**Status**: Not Started  
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

**TO BE COMPLETED**: Follow BDD workflow step 1

### Investigation Notes
- [ ] Search codebase for any WhatsApp message polling loop
- [ ] Check if bot uses webhooks instead of polling
- [ ] Review git history - was polling ever implemented?
- [ ] Determine if this is legacy from initial design

### Root Cause
*TO BE DOCUMENTED after investigation*

---

## Fix Options

**Option A: Remove entirely**
- Delete from config schema, validation, logging
- Remove from all config files
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

**TO BE DECIDED**: Human approval gate required

---

## Test Gap Analysis

**Why didn't tests catch this?**
- No test verifies that polling actually happens
- Tests just check config loads/validates successfully
- No integration test for bot main loop behavior

**Missing Test Cases:**
- [ ] Test that main loop uses poll_interval (if polling implemented)
- [ ] OR test that explicitly documents polling is not implemented
- [ ] Config test that flags unused config values

---

## Implementation Checklist

Following METHODOLOGY.md §VII (Bug-Driven Development):

- [ ] **Step 1**: Root cause investigation complete
- [ ] **Step 2**: 🚨 HUMAN APPROVAL - Root cause & fix option
- [ ] **Step 3**: Test gap analysis complete
- [ ] **Step 4**: Write tests (if needed for chosen option)
- [ ] **Step 5**: 🚨 HUMAN APPROVAL - Tests
- [ ] **Step 6**: Implement fix
- [ ] **Step 7**: Verify all tests pass
- [ ] **Step 8**: Commit & PR with BDD format

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
