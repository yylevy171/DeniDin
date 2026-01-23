# Bugfix 004: data_root Config Value Not Respected

**Created**: January 23, 2026  
**Status**: Not Started  
**Priority**: P2 (Medium - Path management inconsistency)  
**Component**: Configuration, File Storage  
**Branch**: `bugfix/004-data-root-ignored`  
**Spec Location**: `specs/bugfixes/004-data-root-ignored.md`

---

## Bug Description

**Observed Behavior:**
```json
"data_root": "data",
"memory": {
  "session": {
    "storage_dir": "data/sessions"  // Hardcoded absolute path
  },
  "longterm": {
    "storage_dir": "data/memory"     // Hardcoded absolute path
  }
}
```

- `data_root` is defined but storage paths **repeat "data" prefix**
- Changing `data_root` to "mydata" would NOT work - paths stay "data/..."
- Storage dirs should be **relative** to data_root: `"sessions"`, `"memory"`

**Expected Behavior:**
```json
"data_root": "data",
"memory": {
  "session": {
    "storage_dir": "sessions"  // Relative to data_root
  },
  "longterm": {
    "storage_dir": "memory"    // Relative to data_root
  }
}
```

Then code constructs: `{data_root}/{storage_dir}` → `"data/sessions"`

**Impact:**
- Cannot change base data directory without editing multiple paths
- Violates DRY principle (data_root repeated in every path)
- Misleading configuration structure

---

## Root Cause Analysis

**TO BE COMPLETED**: Follow BDD workflow step 1

### Investigation Notes
- [ ] Review `config.py` line 97 - default path construction
- [ ] Check if `ai_handler.py` line 84, 98 use data_root when loading paths
- [ ] Verify `session_manager.py` and `memory_manager.py` path handling
- [ ] Test what happens if data_root is changed to different value

### Root Cause
**Initial hypothesis**: 
- Config defaults in `config.py` build full paths: `f'{data_root}/sessions'`
- But config.json ALSO hardcodes full paths
- Code doesn't properly combine data_root + relative storage_dir
- Result: data_root is completely ignored

*TO BE CONFIRMED after investigation*

---

## Fix Options

**Option A: Make storage_dir relative**
- Change config.json to use relative paths: `"sessions"`, `"memory"`
- Update code to construct: `Path(data_root) / storage_dir`
- **Pros**: Proper hierarchy, data_root works as intended
- **Cons**: Breaking change for existing configs

**Option B: Remove data_root**
- Delete data_root from schema
- Use full paths everywhere
- **Pros**: Matches current behavior
- **Cons**: Less flexible, more repetition

**Option C: Make paths optional, default to data_root-relative**
- If storage_dir is absolute (starts with `/` or contains `/`), use as-is
- If relative, prepend data_root
- **Pros**: Backward compatible
- **Cons**: More complex logic

**TO BE DECIDED**: Human approval gate required

---

## Test Gap Analysis

**Why didn't tests catch this?**
- No test verifies data_root is actually used in path construction
- Tests use default config which happens to work
- No test changes data_root and expects paths to follow

**Missing Test Cases:**
- [ ] Test changing data_root changes all storage paths
- [ ] Test relative vs absolute storage_dir handling
- [ ] Integration test with custom data_root directory
- [ ] Test that verifies path construction: `data_root + storage_dir`

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

- `config/config.json` - Storage dir values
- `config/config.example.json` - Example config
- `src/models/config.py` - Default path construction
- `src/handlers/ai_handler.py` - Path loading (lines 84, 98)
- `src/memory/session_manager.py` - Session storage init
- `src/memory/memory_manager.py` - Memory storage init
- `tests/unit/test_config.py` - Config path tests
- `tests/integration/test_memory_integration.py` - Path integration tests

---

## Migration Notes

If Option A chosen (breaking change):

**Migration Guide for Users:**
```json
// OLD (current)
"data_root": "data",
"memory": {
  "session": { "storage_dir": "data/sessions" }
}

// NEW (after fix)
"data_root": "data",
"memory": {
  "session": { "storage_dir": "sessions" }  // Relative!
}
```

**Backward Compatibility:**
- Could auto-migrate on load: strip data_root prefix from storage_dir if present
- Log warning: "storage_dir should be relative to data_root, auto-fixed"

---

## References

- CONSTITUTION.md §I - Configuration & Secrets Management
- METHODOLOGY.md §VII - Bug-Driven Development
