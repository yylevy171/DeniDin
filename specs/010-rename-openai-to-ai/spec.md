# Feature Specification: Rename "openai" References to "ai"

**Feature ID**: 010-rename-openai-to-ai  
**Created**: January 21, 2026  
**Status**: Draft  
**Priority**: Medium

---

## 1. Overview

### 1.1 Purpose
Refactor all "openai" naming references to "ai" throughout the codebase to achieve vendor-agnostic naming and improve long-term maintainability.

### 1.2 Background
Current codebase uses "openai" in variable names, parameters, configuration keys, and test mocks. This creates:
- Vendor lock-in at the naming level
- Reduced flexibility for future AI provider changes
- Violation of abstraction principles
- Harder migration path if switching from OpenAI to alternative providers

### 1.3 Scope
**In Scope:**
- Python variable names (`openai_client` → `ai_client`)
- Function parameters (`openai_api_key` → `ai_api_key`)
- Configuration file keys (`"openai_api_key"` → `"ai_api_key"`)
- Test mock objects (`mock_openai` → `mock_ai`)
- Documentation references to "OpenAI client" → "AI client"

**Out of Scope:**
- OpenAI library import statements (`from openai import OpenAI` remains unchanged)
- OpenAI class instantiation (`OpenAI(...)` remains unchanged)
- External API references (actual OpenAI API endpoints)
- Historical git commit messages

### 1.4 Success Criteria
- ✅ All Python files use `ai_client` instead of `openai_client`
- ✅ All configuration files use `ai_api_key` instead of `openai_api_key`
- ✅ All test files use `mock_ai` or `test_ai_client` naming
- ✅ All 212+ tests pass with zero failures
- ✅ No references to "openai_client", "openai_api_key", or "mock_openai" remain in codebase
- ✅ Documentation updated to reference "AI client" generically

---

## 2. User Stories

### US-010-01: Developer Refactors Configuration (P1)
**As a** developer  
**I want** configuration files to use `ai_api_key` instead of `openai_api_key`  
**So that** the configuration is vendor-agnostic and supports future AI provider changes

**Acceptance Criteria:**
- `config/config.json` uses `"ai_api_key"`
- `config/config.example.json` uses `"ai_api_key"`
- `config/config.test.json` uses `"ai_api_key"`
- Configuration model (`BotConfiguration`) uses `ai_api_key` field name
- All references to the old key name are removed

**Priority**: P1 (Must refactor config model first, as it's used by all other components)

---

### US-010-02: Developer Refactors Source Code (P1)
**As a** developer  
**I want** all source code to use `ai_client` instead of `openai_client`  
**So that** the codebase is vendor-neutral and easier to understand

**Acceptance Criteria:**
- `denidin.py` uses `ai_client` for OpenAI client instances
- `src/handlers/ai_handler.py` uses `self.ai_client`
- `src/memory/memory_manager.py` uses `ai_client` parameter
- `src/models/config.py` uses `ai_api_key` field
- All docstrings reference "AI client" instead of "OpenAI client"
- No occurrences of `openai_client` variable name remain

**Priority**: P1 (Core implementation files)

---

### US-010-03: Developer Refactors Test Files (P2)
**As a** developer  
**I want** all test files to use `mock_ai` and `test_ai_client` naming  
**So that** tests reflect the vendor-agnostic naming convention

**Acceptance Criteria:**
- All test files use `mock_ai_client` or `test_ai_client`
- No references to `mock_openai` remain in test files
- Module-level variables in tests use `test_ai_client`
- All mock patches target correct new variable names
- Test suite passes with 212+ passed, 4 skipped

**Priority**: P2 (Dependent on US-010-02)

---

### US-010-04: Developer Updates Documentation (P3)
**As a** developer  
**I want** documentation to reference "AI client" generically  
**So that** documentation is accurate and vendor-agnostic

**Acceptance Criteria:**
- Spec files reference "AI client" instead of "OpenAI client"
- Code comments use "AI" instead of "OpenAI" where referring to abstractions
- README references "AI-powered" instead of "OpenAI-powered"
- Configuration examples show `ai_api_key`

**Priority**: P3 (Documentation polish)

---

## 3. Functional Requirements

### FR-010-01: Configuration Key Renaming
**Requirement**: All configuration files MUST use `ai_api_key` instead of `openai_api_key`

**Acceptance Criteria:**
- Given the configuration model is loaded
- When parsing `config.json`
- Then the field name is `ai_api_key`
- And backward compatibility is NOT required (breaking change accepted)

---

### FR-010-02: Variable Name Consistency
**Requirement**: All Python source files MUST use `ai_client` for OpenAI client instances

**Acceptance Criteria:**
- Given any Python source file is analyzed
- When searching for variable names containing "openai"
- Then only library imports contain "openai" (e.g., `from openai import OpenAI`)
- And no variable names contain "openai" substring

---

### FR-010-03: Test Mock Naming
**Requirement**: All test mocks MUST use `mock_ai` or `test_ai_client` naming pattern

**Acceptance Criteria:**
- Given any test file is analyzed
- When searching for mock object names
- Then all mocks use `mock_ai_client`, `test_ai_client`, or `self.mock_ai_client`
- And no mocks use `mock_openai` naming

---

### FR-010-04: Functional Equivalence
**Requirement**: Refactoring MUST NOT change application behavior

**Acceptance Criteria:**
- Given the full test suite is executed
- When all tests complete
- Then 212+ tests pass
- And 4 tests skipped
- And zero test failures
- And application runtime behavior is identical to pre-refactor

---

## 4. Non-Functional Requirements

### NFR-010-01: Zero Downtime
**Requirement**: Refactoring is a breaking change requiring configuration update
- Users MUST update their `config.json` to use `ai_api_key`
- Application will fail to start with old configuration (by design)
- Clear error message MUST indicate configuration key mismatch

### NFR-010-02: Maintainability
**Requirement**: Refactored code MUST improve long-term maintainability
- Future AI provider swaps only require changing client instantiation
- No vendor-specific naming in application layer
- Clear separation between library imports and application abstractions

---

## 5. Edge Cases & Error Scenarios

### EC-010-01: Old Configuration Key
**Scenario**: User runs application with old `config.json` containing `openai_api_key`

**Expected Behavior:**
- Application fails to start
- Error message: `"Configuration error: 'ai_api_key' is required"`
- Exit code: 2 (configuration error per CONSTITUTION XVI)
- Log message indicates missing required field

**Mitigation**: Update `config.example.json` and add migration notes to CHANGELOG

---

### EC-010-02: Mixed Naming During Refactor
**Scenario**: Developer leaves some files with old naming during incomplete refactor

**Expected Behavior:**
- Code fails to run (NameError or AttributeError)
- Tests fail immediately
- Developer catches error before commit

**Mitigation**: Refactor all files in single atomic PR

---

## 6. Technical Constraints

### TC-010-01: Library Imports Unchanged
- `from openai import OpenAI` MUST remain unchanged
- `OpenAI(api_key=...)` class instantiation unchanged
- Only application-layer variable names are refactored

### TC-010-02: Breaking Change
- This is an intentional breaking change
- Users MUST update their `config.json`
- No backward compatibility layer provided
- Version bump to indicate breaking change (if using semantic versioning)

---

## 7. Dependencies

### Internal Dependencies
- Configuration model (`src/models/config.py`) MUST be updated first
- Source code refactor depends on config model
- Test refactor depends on source code refactor
- Documentation update is independent

### External Dependencies
- None (OpenAI library usage unchanged)

---

## 8. Open Questions

**Q1**: Should we provide a migration script to update existing config files?  
**A1**: No - manual update is simple and ensures users review their configuration.

**Q2**: Should we support both key names temporarily for backward compatibility?  
**A2**: No - clean break is simpler and this is a development project, not production with users.

---

## 9. Out of Scope

- Adding support for alternative AI providers (Anthropic, Google, etc.) - future enhancement
- Abstracting AI client behind interface/protocol - future enhancement
- Changing OpenAI library to alternative - out of scope
- Renaming "AI" to more generic "LLM" - not necessary

---

## 10. Approval

**Specification Approved By**: [Pending]  
**Date**: [Pending]  
**Approved to Proceed to Planning**: [ ] Yes [ ] No
