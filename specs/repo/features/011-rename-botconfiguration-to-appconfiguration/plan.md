# Implementation Plan: Rename BotConfiguration to AppConfiguration

**Feature ID**: 011-rename-botconfiguration-to-appconfiguration  
**Created**: January 21, 2026  
**Status**: Draft

---

## 1. Implementation Phases

### Phase 0: Research ✓
**Status**: Complete

**Findings:**
- Identified all files referencing `BotConfiguration`:
  - `src/models/config.py` - Class definition
  - `denidin.py` - Import and usage
  - `src/handlers/ai_handler.py` - Type hint
  - `src/handlers/whatsapp_handler.py` - Type hint
  - `src/memory/memory_manager.py` - Type hint
  - `src/memory/session_manager.py` - Type hint
  - `tests/unit/test_config.py` - Test imports (if exists)
  - `tests/integration/*.py` - Integration test imports
  - Various other test files

**Search Results:**
```bash
grep -r "BotConfiguration" --include="*.py" .
# Expected: ~10-20 files with imports and type hints
```

**Technical Constraints:**
- Pure refactoring (no behavior changes)
- Must update all imports atomically
- Type hints must remain valid

**Dependencies:**
- Ideally done after 010-rename-openai-to-ai to avoid merge conflicts

---

### Phase 1: Design

#### 1.1 Class Definition Change

**Before:**
```python
# src/models/config.py
@dataclass
class BotConfiguration:
    ai_api_key: str
    # ... other fields
```

**After:**
```python
# src/models/config.py
@dataclass
class AppConfiguration:
    ai_api_key: str
    # ... other fields (unchanged)
```

#### 1.2 Import Statement Changes

**Before:**
```python
from src.models.config import BotConfiguration

def some_function(config: BotConfiguration):
    pass
```

**After:**
```python
from src.models.config import AppConfiguration

def some_function(config: AppConfiguration):
    pass
```

#### 1.3 Variable Naming Convention

**Recommendations:**
- Main entry point (`denidin.py`): Use `app_config` variable
- Other modules: Use `config` parameter (short form acceptable)
- Avoid `bot_config` except when referencing external libraries

**Example in denidin.py:**
```python
# BEFORE
bot_config = BotConfiguration.from_json(config_data)

# AFTER
app_config = AppConfiguration.from_json(config_data)
```

---

### Phase 2: Task Breakdown

**Task Sequence** (dependency-ordered):

```
[IMPL-011-001] Refactor Configuration Class Definition
  ├─ [IMPL-011-001a] Write/update tests for AppConfiguration
  └─ [IMPL-011-001b] Rename class in config.py

[IMPL-011-002] Update Main Entry Point
  ├─ [IMPL-011-002a] Update denidin.py imports and variables
  └─ [IMPL-011-002b] Verify main entry point tests pass

[IMPL-011-003] Update Source Files
  ├─ [IMPL-011-003a] Update handler imports and type hints
  ├─ [IMPL-011-003b] Update memory module imports and type hints
  └─ [IMPL-011-003c] Update any other source files

[IMPL-011-004] Update Test Files
  ├─ [IMPL-011-004a] Update unit test imports
  ├─ [IMPL-011-004b] Update integration test imports
  └─ [IMPL-011-004c] Run full test suite

[IMPL-011-005] Update Documentation
  ├─ [IMPL-011-005a] Update docstrings and comments
  └─ [IMPL-011-005b] Update spec documentation
```

---

### Phase 3: Implementation Strategy

#### 3.1 Refactoring Approach
**Strategy**: Atomic multi-file refactor in single PR

**Rationale**:
- Prevents broken intermediate states
- All tests pass or all fail
- Single review/approval cycle
- Clean git history

**Alternative Considered**: File-by-file refactor
- **Rejected**: Creates broken states between commits

#### 3.2 Automation Options

**Option 1: Manual Search & Replace**
- Use IDE find/replace with case sensitivity
- Review each change manually
- Safest for precision

**Option 2: IDE Refactor Tool**
- Use VS Code or PyCharm rename refactor
- Automatically updates all references
- Faster but verify all changes

**Recommendation**: Use IDE refactor tool, then verify with grep

#### 3.3 Testing Strategy

**Validation Points**:
1. After class rename: Config loading tests pass
2. After import updates: No import errors
3. After type hint updates: `mypy` passes
4. After all changes: Full test suite passes (212+ passed, 4 skipped)

**Regression Prevention**:
- No new tests needed (pure refactoring)
- Existing tests validate functional equivalence
- Type checking validates correctness

---

## 2. Risk Analysis

### High Risk Items
None - low-risk refactoring task.

### Medium Risk Items
**Risk**: Incomplete refactor leaves some `BotConfiguration` references  
**Mitigation**:
- Use comprehensive search after refactor
- Run `mypy` to catch type errors
- Run full test suite

### Low Risk Items
**Risk**: Merge conflicts if done alongside other refactors  
**Mitigation**: Coordinate sequencing with other enhancement tasks

---

## 3. Technical Decisions

### TD-011-01: Use IDE Refactor Tool
**Decision**: Use IDE's built-in "Rename Symbol" refactor tool

**Rationale**:
- Automatically finds all references
- Updates imports, type hints, and usages
- Reduces human error
- Can be verified with grep afterward

**Alternatives Considered**:
- Manual find/replace - **Accepted as backup** if IDE tool misses anything

---

### TD-011-02: Rename Variables to app_config
**Decision**: Update `bot_config` to `app_config` in main entry point

**Rationale**:
- Consistency with class name
- Improves code clarity
- Matches terminology standards

**Scope**:
- Main entry point: `app_config`
- Other modules: `config` (short form acceptable)

---

### TD-011-03: Single Atomic PR
**Decision**: All changes in one PR

**Rationale**:
- No broken intermediate states
- Clean git history
- Single approval gate

---

## 4. Success Metrics

### Completion Criteria
- ✅ Zero occurrences of `class BotConfiguration` in codebase
- ✅ Zero imports of `BotConfiguration` (except in comments)
- ✅ All type hints use `AppConfiguration`
- ✅ `mypy src/` passes with no errors
- ✅ All 212+ tests pass, 4 skipped
- ✅ Application starts successfully

**Verification Commands**:
```bash
# Search for remaining BotConfiguration references
grep -r "BotConfiguration" --include="*.py" src/ denidin-bot/denidin.py tests/
# Expect: No results (or only in comments)

# Type checking
cd denidin-bot
python3 -m mypy src/ --ignore-missing-imports
# Expect: Success

# Test suite
python3 -m pytest tests/ -v
# Expect: 212+ passed, 4 skipped
```

### Performance Metrics
- No performance impact (pure naming refactor)
- Test execution time unchanged

---

## 5. Timeline Estimate

**Total Estimated Duration**: 1-2 hours

**Breakdown**:
- Class rename: 15 minutes
- Import updates: 30 minutes
- Variable name updates: 15 minutes
- Test verification: 30 minutes
- Documentation: 15 minutes

---

## 6. METHODOLOGY Compliance Checklist

- [x] **Integration Contracts**: N/A - internal refactor
- [x] **Terminology Glossary**: "AppConfiguration" = application configuration model
- [x] **Technology Choices**: No new technologies
- [x] **Requirement IDs**: US-011-01 through US-011-04 defined
- [x] **Phase Checkpoints**: Phase 0 complete, Phase 1 documented
- [x] **Task ID Format**: Tasks use [IMPL-011-###] format
- [x] **Path Conventions**: Absolute paths from project root
- [x] **Clarifications Tracking**: All questions resolved
- [x] **Estimated Duration**: 1-2 hours documented
- [x] **Templates**: Following plan-template.md structure

---

## 7. CONSTITUTION Compliance Review

**Principle I (Configuration & Testing)**:
- ✅ No configuration file changes
- ✅ Tests validate refactoring correctness

**Principle III (Version Control)**:
- ✅ Feature branch: `011-rename-botconfiguration-to-appconfiguration`
- ✅ PR required before merge

**Principle IV (Testing)**:
- ✅ Existing tests validate functional equivalence
- ✅ Type checking validates correctness

---

## 8. Open Issues

None - all design decisions finalized.

---

## 9. Approval

**Plan Approved By**: [Pending]  
**Date**: [Pending]  
**Approved to Proceed to Task Generation**: [ ] Yes [ ] No
