# Implementation Tasks: Rename "openai" to "ai"

**Feature ID**: 010-rename-openai-to-ai  
**Created**: January 21, 2026  
**Status**: Ready for Implementation

---

## Task Overview

**Total Tasks**: 14 (7 test tasks + 7 implementation tasks)  
**Estimated Duration**: 2-3 hours  
**Dependency Chain**: Sequential (each implementation depends on its test approval)

---

## Git Workflow

### Branch Setup
```bash
git checkout master
git pull origin master
git checkout -b 010-rename-openai-to-ai
```

### Commit Strategy
- Commit after each major component refactor
- Use descriptive commit messages following pattern: `refactor: update [component] to use ai_client naming`
- Final commit: `refactor: rename all openai references to ai`

### PR Creation
```bash
# After all tasks complete and tests pass
git push origin 010-rename-openai-to-ai
gh pr create --base master --head 010-rename-openai-to-ai \
  --title "Refactor: Rename 'openai' references to 'ai'" \
  --body "See specs/010-rename-openai-to-ai/spec.md for details"
```

### Important Rules
- **NEVER** push directly to master
- All tests MUST pass before creating PR
- Squash merge PR to keep clean history
- Delete branch after merge

---

## Task List

### [IMPL-010-001] Refactor Configuration Model
**User Story**: US-010-01  
**Priority**: P1  
**Estimated Duration**: 30 minutes

#### [IMPL-010-001a] ✍️ Write Tests for Config Model
**Type**: Test Implementation  
**Blocked By**: None  
**Blocks**: IMPL-010-001b

**Acceptance Criteria**:
- [ ] Test validates `BotConfiguration` loads with `ai_api_key` field
- [ ] Test verifies `config.test.json` uses `ai_api_key` key
- [ ] Test fails if `ai_api_key` is missing
- [ ] All config loading tests pass

**Test Files**:
- `tests/unit/test_config.py` (if exists, update; otherwise verify integration tests)

**Implementation Steps**:
1. Check if `test_config.py` exists for unit testing config model
2. If not, verify integration tests cover config loading
3. Update test assertions to expect `ai_api_key` field
4. Run tests - expect failures (field doesn't exist yet)

**Validation**:
```bash
python3 -m pytest tests/ -k config -v
# Expect: Tests fail because config model still has openai_api_key
```

**Human Approval Required**: ✋ Tests must be reviewed before proceeding to IMPL-010-001b

---

#### [IMPL-010-001b] 🔨 Update Configuration Model
**Type**: Implementation  
**Blocked By**: IMPL-010-001a (human approval)  
**Blocks**: IMPL-010-002

**Acceptance Criteria**:
- [ ] `src/models/config.py` uses `ai_api_key` field name
- [ ] All references to `openai_api_key` removed from config model
- [ ] Config loading tests pass
- [ ] No regression in other tests

**Files to Modify**:
- `src/models/config.py`

**Implementation Steps**:
```python
# File: src/models/config.py
# BEFORE:
@dataclass
class BotConfiguration:
    openai_api_key: str
    # ... other fields

# AFTER:
@dataclass
class BotConfiguration:
    ai_api_key: str
    # ... other fields (unchanged)
```

**Validation**:
```bash
python3 -m pytest tests/unit/test_config.py -v
# Expect: Config tests now pass
```

---

### [IMPL-010-002] Update Configuration Files
**User Story**: US-010-01  
**Priority**: P1  
**Estimated Duration**: 15 minutes  
**Blocked By**: IMPL-010-001b

**Note**: These are data files, no separate test task required. Update all three atomically.

**Acceptance Criteria**:
- [ ] `config/config.json` uses `"ai_api_key"`
- [ ] `config/config.example.json` uses `"ai_api_key"`
- [ ] `config/config.test.json` uses `"ai_api_key"`
- [ ] All config files have consistent structure

**Files to Modify**:
- `config/config.json`
- `config/config.example.json`
- `config/config.test.json`

**Implementation Steps**:
1. Open `config/config.json`
2. Replace `"openai_api_key"` key with `"ai_api_key"`
3. Repeat for `config.example.json`
4. Repeat for `config.test.json`
5. Verify JSON syntax is valid

**Validation**:
```bash
# Verify JSON is valid
python3 -c "import json; json.load(open('config/config.json'))"
python3 -c "import json; json.load(open('config/config.example.json'))"
python3 -c "import json; json.load(open('config/config.test.json'))"

# Run config loading tests
python3 -m pytest tests/ -k config -v
```

---

### [IMPL-010-003] Refactor Main Entry Point
**User Story**: US-010-02  
**Priority**: P1  
**Estimated Duration**: 30 minutes  
**Blocked By**: IMPL-010-002

#### [IMPL-010-003a] ✍️ Write/Update Tests for denidin.py
**Type**: Test Update  
**Blocked By**: IMPL-010-002  
**Blocks**: IMPL-010-003b

**Acceptance Criteria**:
- [ ] Tests reference `ai_client` variable name
- [ ] Tests validate client initialization with `config.ai_api_key`
- [ ] Integration tests pass with new naming

**Test Files**:
- `tests/integration/test_main.py` (if exists)
- Or verify through integration tests

**Implementation Steps**:
1. Search for tests that validate main entry point initialization
2. Update test assertions to expect `ai_client` variable
3. Update mocks/fixtures if needed
4. Run tests - expect failures

**Validation**:
```bash
python3 -m pytest tests/integration/ -v
# Expect: Some failures due to openai_client → ai_client rename
```

**Human Approval Required**: ✋ Tests must be reviewed before proceeding to IMPL-010-003b

---

#### [IMPL-010-003b] 🔨 Update denidin.py Variable Names
**Type**: Implementation  
**Blocked By**: IMPL-010-003a (human approval)  
**Blocks**: IMPL-010-004

**Acceptance Criteria**:
- [ ] Variable `openai_client` renamed to `ai_client` in `denidin.py`
- [ ] All usages of the variable updated
- [ ] Client instantiation: `ai_client = OpenAI(api_key=config.ai_api_key)`
- [ ] AIHandler receives: `ai_handler = AIHandler(config, ai_client)`

**Files to Modify**:
- `denidin-bot/denidin.py`

**Implementation Steps**:
1. Open `denidin.py`
2. Find: `openai_client = OpenAI(api_key=config.openai_api_key)`
3. Replace with: `ai_client = OpenAI(api_key=config.ai_api_key)`
4. Find all usages of `openai_client` variable
5. Replace with `ai_client`
6. Update docstrings/comments referencing "OpenAI client" → "AI client"

**Validation**:
```bash
# Verify no occurrences of openai_client remain
grep -n "openai_client" denidin-bot/denidin.py
# Expect: No results

# Run integration tests
python3 -m pytest tests/integration/ -v
```

---

### [IMPL-010-004] Refactor AI Handler
**User Story**: US-010-02  
**Priority**: P1  
**Estimated Duration**: 30 minutes  
**Blocked By**: IMPL-010-003b

#### [IMPL-010-004a] ✍️ Write/Update Tests for AIHandler
**Type**: Test Update  
**Blocked By**: IMPL-010-003b  
**Blocks**: IMPL-010-004b

**Acceptance Criteria**:
- [ ] Test mocks use `mock_ai_client` name
- [ ] Tests validate `AIHandler.__init__` accepts `ai_client` parameter
- [ ] Tests verify `self.ai_client` instance variable exists
- [ ] All AIHandler tests updated

**Test Files**:
- `tests/unit/test_ai_handler.py`

**Implementation Steps**:
1. Open `tests/unit/test_ai_handler.py`
2. Find all `mock_openai` references
3. Plan rename to `mock_ai_client`
4. Update test assertions
5. Run tests - expect failures

**Validation**:
```bash
python3 -m pytest tests/unit/test_ai_handler.py -v
# Expect: Failures due to self.openai_client → self.ai_client rename
```

**Human Approval Required**: ✋ Tests must be reviewed before proceeding to IMPL-010-004b

---

#### [IMPL-010-004b] 🔨 Update AIHandler Instance Variable
**Type**: Implementation  
**Blocked By**: IMPL-010-004a (human approval)  
**Blocks**: IMPL-010-005

**Acceptance Criteria**:
- [ ] `self.openai_client` renamed to `self.ai_client`
- [ ] Constructor parameter: `def __init__(self, config, ai_client)`
- [ ] All references to `self.openai_client` updated
- [ ] Docstrings updated

**Files to Modify**:
- `src/handlers/ai_handler.py`

**Implementation Steps**:
1. Open `src/handlers/ai_handler.py`
2. Update `__init__` signature: `def __init__(self, config: BotConfiguration, ai_client: OpenAI)`
3. Update assignment: `self.ai_client = ai_client`
4. Find all `self.openai_client` usages
5. Replace with `self.ai_client`
6. Update docstrings

**Validation**:
```bash
# Verify no occurrences remain
grep -n "openai_client" src/handlers/ai_handler.py
# Expect: No results

# Run AI handler tests
python3 -m pytest tests/unit/test_ai_handler.py -v
```

---

### [IMPL-010-005] Refactor Memory Manager
**User Story**: US-010-02  
**Priority**: P1  
**Estimated Duration**: 30 minutes  
**Blocked By**: IMPL-010-004b

#### [IMPL-010-005a] 🔨 Update MemoryManager Parameter Name
**Type**: Implementation  
**Blocked By**: IMPL-010-004b  
**Blocks**: IMPL-010-005b

**Note**: MemoryManager tests were already refactored in governance compliance work, so only source code update needed.

**Acceptance Criteria**:
- [ ] Parameter: `def __init__(self, ..., ai_client: OpenAI)`
- [ ] Assignment: `self.ai_client = ai_client`
- [ ] Error message references `ai_client`
- [ ] All usages updated

**Files to Modify**:
- `src/memory/memory_manager.py`

**Implementation Steps**:
1. Open `src/memory/memory_manager.py`
2. Update `__init__` signature: `def __init__(self, config: BotConfiguration, ai_client: OpenAI = None)`
3. Update assignment: `self.ai_client = ai_client`
4. Update error message: `"ai_client parameter is required"`
5. Find all `self.openai_client` usages
6. Replace with `self.ai_client`
7. Update docstrings

**Validation**:
```bash
# Verify no occurrences remain
grep -n "openai_client" src/memory/memory_manager.py
# Expect: No results (except comments if any)

# Run memory manager tests
python3 -m pytest tests/unit/test_memory_manager.py -v
```

---

#### [IMPL-010-005b] ✅ Verify Memory Tests with New Naming
**Type**: Test Validation  
**Blocked By**: IMPL-010-005a  
**Blocks**: IMPL-010-006

**Acceptance Criteria**:
- [ ] All 29 memory manager tests pass
- [ ] No references to `mock_openai` in test file
- [ ] Tests use `test_ai_client` and `mock_ai_client`

**Test Files**:
- `tests/unit/test_memory_manager.py`

**Implementation Steps**:
1. Open `tests/unit/test_memory_manager.py`
2. Find: `test_openai_client` (module-level variable)
3. Replace with: `test_ai_client`
4. Find: `self.mock_openai_client`
5. Replace with: `self.mock_ai_client`
6. Update all references in test methods
7. Run tests

**Validation**:
```bash
python3 -m pytest tests/unit/test_memory_manager.py -v
# Expect: 29 passed
```

---

### [IMPL-010-006] Refactor Test Files
**User Story**: US-010-03  
**Priority**: P2  
**Estimated Duration**: 45 minutes  
**Blocked By**: IMPL-010-005b

**Note**: Most test updates already done in previous tasks. This task handles any remaining test files.

#### [IMPL-010-006a] 🔨 Update Remaining Unit Tests
**Type**: Implementation  
**Blocked By**: IMPL-010-005b  
**Blocks**: IMPL-010-006b

**Acceptance Criteria**:
- [ ] All unit test files use `mock_ai_client` naming
- [ ] No occurrences of `mock_openai` remain
- [ ] All unit tests pass

**Test Files**:
- `tests/unit/test_*.py` (all remaining files)

**Implementation Steps**:
1. Search for remaining `mock_openai` references:
   ```bash
   grep -r "mock_openai" tests/unit/
   ```
2. Update each occurrence to `mock_ai_client`
3. Update test setUp methods
4. Run full unit test suite

**Validation**:
```bash
python3 -m pytest tests/unit/ -v
# Expect: All unit tests pass
```

---

#### [IMPL-010-006b] 🔨 Update Integration Tests
**Type**: Implementation  
**Blocked By**: IMPL-010-006a  
**Blocks**: IMPL-010-006c

**Acceptance Criteria**:
- [ ] Integration test mocks use `mock_ai_client`
- [ ] Test fixtures updated
- [ ] All integration tests pass

**Test Files**:
- `tests/integration/test_*.py`

**Implementation Steps**:
1. Search for `mock_openai` in integration tests:
   ```bash
   grep -r "mock_openai" tests/integration/
   ```
2. Update each occurrence
3. Update test fixtures/conftest.py if needed
4. Run integration tests

**Validation**:
```bash
python3 -m pytest tests/integration/ -v
# Expect: All integration tests pass
```

---

#### [IMPL-010-006c] ✅ Run Full Test Suite
**Type**: Test Validation  
**Blocked By**: IMPL-010-006b  
**Blocks**: IMPL-010-007

**Acceptance Criteria**:
- [ ] 212+ tests passed
- [ ] 4 tests skipped
- [ ] Zero failures
- [ ] Zero errors

**Validation**:
```bash
cd /Users/yaronl/personal/DeniDin/denidin-bot
python3 -m pytest tests/ -v --tb=short

# Expected output:
# ====== 212 passed, 4 skipped in XXX seconds ======
```

---

### [IMPL-010-007] Update Documentation
**User Story**: US-010-04  
**Priority**: P3  
**Estimated Duration**: 30 minutes  
**Blocked By**: IMPL-010-006c

#### [IMPL-010-007a] 🔨 Update Code Comments and Docstrings
**Type**: Implementation  
**Blocked By**: IMPL-010-006c  
**Blocks**: IMPL-010-007b

**Acceptance Criteria**:
- [ ] Docstrings reference "AI client" instead of "OpenAI client"
- [ ] Code comments use vendor-agnostic terminology
- [ ] Function signatures documented with correct parameter names

**Files to Modify**:
- `src/handlers/ai_handler.py`
- `src/memory/memory_manager.py`
- `denidin.py`

**Implementation Steps**:
1. Review docstrings in each file
2. Replace "OpenAI client" → "AI client" where referring to abstraction
3. Keep "OpenAI" when referring to the library itself
4. Update parameter documentation

**Validation**:
```bash
# Search for remaining "OpenAI client" references
grep -r "OpenAI client" src/ denidin-bot/denidin.py
# Review each occurrence - some may be valid library references
```

---

#### [IMPL-010-007b] 🔨 Update Specification Documentation
**Type**: Implementation  
**Blocked By**: IMPL-010-007a  
**Blocks**: None

**Acceptance Criteria**:
- [ ] Specs reference "AI client" generically
- [ ] Config examples show `ai_api_key`
- [ ] Documentation accurate

**Files to Modify**:
- `specs/001-whatsapp-chatbot-passthrough/spec.md`
- Any other specs mentioning OpenAI configuration

**Implementation Steps**:
1. Search specs for "openai_api_key" references
2. Update to "ai_api_key"
3. Review for other OpenAI-specific language
4. Update to vendor-agnostic terminology

**Validation**:
```bash
grep -r "openai_api_key" specs/
# Verify no config key references remain
```

---

## Final Validation Checklist

Before creating PR, verify:

- [ ] **Code Search**: `grep -r "openai_client" src/` → No results
- [ ] **Code Search**: `grep -r "openai_api_key" config/*.json` → No results  
- [ ] **Code Search**: `grep -r "mock_openai" tests/` → No results
- [ ] **Test Suite**: 212+ passed, 4 skipped, 0 failed
- [ ] **Manual Test**: Application starts successfully
- [ ] **Manual Test**: Can send/receive WhatsApp messages
- [ ] **Config Updated**: Personal `config.json` uses `ai_api_key`

---

## Commit and Push

```bash
# Final commit
git add .
git commit -m "refactor: rename all 'openai' references to 'ai'

- Updated configuration model to use ai_api_key field
- Renamed all openai_client variables to ai_client
- Updated test mocks to use mock_ai_client naming
- Updated documentation to use vendor-agnostic terminology

BREAKING CHANGE: Configuration files must use 'ai_api_key' instead of 'openai_api_key'

Closes #010-rename-openai-to-ai"

# Push to remote
git push origin 010-rename-openai-to-ai

# Create PR
gh pr create --base master --head 010-rename-openai-to-ai \
  --title "Refactor: Rename 'openai' references to 'ai'" \
  --body "## Summary
Refactors all 'openai' naming to vendor-agnostic 'ai' naming.

## Changes
- Configuration: \`openai_api_key\` → \`ai_api_key\`
- Variables: \`openai_client\` → \`ai_client\`
- Test mocks: \`mock_openai\` → \`mock_ai_client\`
- Documentation: Updated to vendor-agnostic terminology

## Breaking Change
⚠️ Configuration files must be updated to use \`ai_api_key\`

## Test Results
✅ 212 passed, 4 skipped

See \`specs/010-rename-openai-to-ai/spec.md\` for full details."
```

---

## Post-Merge Cleanup

```bash
# After PR is merged and branch deleted remotely
git checkout master
git pull origin master
# Branch auto-deleted by gh pr merge --delete-branch
```

---

## Notes

- This is a **pure refactoring task** - no functional changes
- All tests must pass before creating PR
- Breaking change requires config file updates
- Estimated total time: 2-3 hours
