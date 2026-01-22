# Implementation Plan: Rename "openai" to "ai"

**Feature ID**: 010-rename-openai-to-ai  
**Created**: January 21, 2026  
**Status**: Draft

---

## 1. Implementation Phases

### Phase 0: Research ✓
**Status**: Complete

**Findings:**
- Identified all files containing "openai" references:
  - `src/models/config.py` - Configuration model (1 field)
  - `denidin.py` - Main entry point (2 variables)
  - `src/handlers/ai_handler.py` - AI handler (1 instance variable)
  - `src/memory/memory_manager.py` - Memory manager (1 parameter)
  - `config/config.json` - Runtime config (1 key)
  - `config/config.example.json` - Example config (1 key)
  - `config/config.test.json` - Test config (1 key)
  - `tests/unit/test_memory_manager.py` - Memory tests (3 variables)
  - `tests/unit/test_ai_handler.py` - AI handler tests (mock names)
  - `tests/integration/*.py` - Integration tests (various mocks)

**Technical Constraints:**
- Must maintain OpenAI library imports unchanged
- Breaking change: requires config file updates
- Must refactor atomically to avoid partial state

**Dependencies:**
- None - pure refactoring with no external dependencies

---

### Phase 1: Design

#### 1.1 Data Model Changes

**Configuration Model** (`src/models/config.py`):
```python
# BEFORE
class BotConfiguration:
    openai_api_key: str

# AFTER
class BotConfiguration:
    ai_api_key: str
```

**Configuration Files**:
```json
// BEFORE
{
  "openai_api_key": "sk-..."
}

// AFTER
{
  "ai_api_key": "sk-..."
}
```

#### 1.2 Affected Components

**Component Dependency Order** (refactor in this sequence):
1. Configuration model (`src/models/config.py`) - Foundation
2. Configuration files (`config/*.json`) - Config instances
3. Main entry point (`denidin.py`) - Application initialization
4. AI Handler (`src/handlers/ai_handler.py`) - AI client wrapper
5. Memory Manager (`src/memory/memory_manager.py`) - Memory system
6. Unit tests (`tests/unit/*.py`) - Test isolation
7. Integration tests (`tests/integration/*.py`) - End-to-end flows

#### 1.3 Naming Convention Mapping

| Old Name | New Name | Context |
|----------|----------|---------|
| `openai_api_key` | `ai_api_key` | Config field |
| `openai_client` | `ai_client` | Main entry point |
| `self.openai_client` | `self.ai_client` | AIHandler instance var |
| `openai_client` (param) | `ai_client` | MemoryManager parameter |
| `mock_openai` | `mock_ai_client` | Test mocks |
| `test_openai_client` | `test_ai_client` | Test fixtures |
| `self.mock_openai_client` | `self.mock_ai_client` | Test instance vars |

**Unchanged:**
- `from openai import OpenAI` - Library import
- `OpenAI(api_key=...)` - Class instantiation

---

### Phase 2: Task Breakdown

**Task Sequence** (dependency-ordered):

```
[IMPL-010-001] Refactor Configuration Model
  ├─ [IMPL-010-001a] Write tests for config with ai_api_key
  └─ [IMPL-010-001b] Update BotConfiguration field name

[IMPL-010-002] Update Configuration Files
  ├─ [IMPL-010-002a] Update config.json
  ├─ [IMPL-010-002b] Update config.example.json
  └─ [IMPL-010-002c] Update config.test.json

[IMPL-010-003] Refactor Main Entry Point
  ├─ [IMPL-010-003a] Write tests for denidin.py with ai_client
  └─ [IMPL-010-003b] Update denidin.py variable names

[IMPL-010-004] Refactor AI Handler
  ├─ [IMPL-010-004a] Write tests for AIHandler with self.ai_client
  └─ [IMPL-010-004b] Update AIHandler instance variable

[IMPL-010-005] Refactor Memory Manager
  ├─ [IMPL-010-005a] Update memory_manager.py parameter name
  └─ [IMPL-010-005b] Verify memory tests with new naming

[IMPL-010-006] Refactor Test Files
  ├─ [IMPL-010-006a] Update test_memory_manager.py mocks
  ├─ [IMPL-010-006b] Update test_ai_handler.py mocks
  └─ [IMPL-010-006c] Update integration test mocks

[IMPL-010-007] Update Documentation
  ├─ [IMPL-010-007a] Update code comments/docstrings
  └─ [IMPL-010-007b] Update spec documentation
```

---

### Phase 3: Implementation Strategy

#### 3.1 Refactoring Approach
**Strategy**: Atomic multi-file refactor in single PR

**Rationale**:
- Prevents partial/broken state
- All tests pass or all fail (no ambiguity)
- Single review/approval cycle
- Clean git history

**Alternative Considered**: Incremental file-by-file refactor
- **Rejected**: Would create broken intermediate states

#### 3.2 Testing Strategy

**Test Validation Points**:
1. After config model refactor: Config loading tests pass
2. After source code refactor: Unit tests pass
3. After test refactor: Full suite passes (212+ passed, 4 skipped)
4. Manual smoke test: Application starts successfully

**Regression Prevention**:
- No new tests required (pure refactoring)
- Existing tests validate functional equivalence
- Test count must remain identical (212 passed, 4 skipped)

#### 3.3 Rollback Plan

**If refactor introduces issues**:
1. `git revert` the PR commit
2. Application immediately returns to working state
3. Config files revert to `openai_api_key`

**Low Risk**: Pure naming refactor with comprehensive test coverage

---

## 2. Risk Analysis

### High Risk Items
None - this is a low-risk refactoring task.

### Medium Risk Items
**Risk**: Developer forgets to update config.json after merge  
**Mitigation**: 
- Clear error message on startup
- Update config.example.json as reference
- Document in PR description

### Low Risk Items
**Risk**: Typo in variable name during refactor  
**Mitigation**: Tests will catch immediately

---

## 3. Technical Decisions

### TD-010-01: No Backward Compatibility
**Decision**: Do NOT support both `openai_api_key` and `ai_api_key` simultaneously

**Rationale**:
- Clean break simplifies code
- No production users to support
- Migration is trivial (one key rename)

**Alternatives Considered**:
- Support both keys with deprecation warning - **Rejected** (unnecessary complexity)

---

### TD-010-02: Atomic Multi-File Refactor
**Decision**: Refactor all files in single PR

**Rationale**:
- Prevents broken intermediate states
- Cleaner git history
- Single approval gate

**Alternatives Considered**:
- Incremental file-by-file - **Rejected** (creates broken states)

---

### TD-010-03: Keep OpenAI Library Imports
**Decision**: Do NOT rename `from openai import OpenAI` or `OpenAI(...)` class usage

**Rationale**:
- These are external library references, not application abstractions
- Renaming would require wrapper classes (out of scope)
- Clear separation: library imports vs. application variables

---

## 4. Success Metrics

### Completion Criteria
- ✅ Zero occurrences of `openai_client` variable name in source code
- ✅ Zero occurrences of `openai_api_key` in config files (except comments)
- ✅ Zero occurrences of `mock_openai` in test files
- ✅ All 212+ tests pass
- ✅ Application starts successfully with updated config
- ✅ `grep -r "openai_client" src/` returns zero results
- ✅ `grep -r "openai_api_key" config/*.json` returns zero results

### Performance Metrics
- No performance impact (pure naming refactor)
- Test execution time unchanged

---

## 5. Timeline Estimate

**Total Estimated Duration**: 2-3 hours

**Breakdown**:
- Configuration model refactor: 30 minutes
- Source code refactor: 45 minutes
- Test file refactor: 45 minutes
- Documentation update: 30 minutes
- Testing & validation: 30 minutes

---

## 6. METHODOLOGY Compliance Checklist

- [x] **Integration Contracts**: N/A - pure refactoring, no API changes
- [x] **Terminology Glossary**: "AI client" = abstraction for LLM provider client
- [x] **Technology Choices**: No new technologies
- [x] **Requirement IDs**: US-010-01 through US-010-04 defined in spec
- [x] **Phase Checkpoints**: Phase 0 complete, Phase 1 documented above
- [x] **Task ID Format**: Tasks use [IMPL-010-###] format
- [x] **Path Conventions**: All paths use absolute references from project root
- [x] **Clarifications Tracking**: No open questions (all resolved in spec)
- [x] **Estimated Duration**: 2-3 hours documented above
- [x] **Templates**: Following plan-template.md structure

---

## 7. CONSTITUTION Compliance Review

**Principle I (Configuration & Testing)**: 
- ✅ Config files updated with new key name
- ✅ Tests validate configuration loading

**Principle II (Logging)**:
- ✅ No logging changes required (variable names don't affect logs)

**Principle III (Version Control)**:
- ✅ All work on feature branch `010-rename-openai-to-ai`
- ✅ PR required before merge to master

**Principle IV (Testing)**:
- ✅ Existing tests validate functional equivalence
- ✅ No new test logic required

**Principle IX (Logging Standards)**:
- ✅ No changes to log messages

**Principle X (Error Response Format)**:
- ✅ Config error message follows standard format

---

## 8. Open Issues

None - all design decisions finalized.

---

## 9. Approval

**Plan Approved By**: [Pending]  
**Date**: [Pending]  
**Approved to Proceed to Task Generation**: [ ] Yes [ ] No
