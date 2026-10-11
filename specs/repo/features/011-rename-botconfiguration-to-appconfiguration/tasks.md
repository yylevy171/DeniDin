# Implementation Tasks: Rename BotConfiguration to AppConfiguration

**Feature ID**: 011-rename-botconfiguration-to-appconfiguration  
**Created**: January 21, 2026  
**Status**: Ready for Implementation

---

## Task Overview

**Total Tasks**: 10 (5 test/validation + 5 implementation)  
**Estimated Duration**: 1-2 hours  
**Dependency**: Should be done AFTER 010-rename-openai-to-ai

---

## Git Workflow

### Branch Setup
```bash
git checkout master
git pull origin master
git checkout -b 011-rename-botconfiguration-to-appconfiguration
```

### Commit Strategy
- Single atomic commit for all changes
- Descriptive commit message
- Reference spec in commit body

### PR Creation
```bash
git push origin 011-rename-botconfiguration-to-appconfiguration
gh pr create --base master --head 011-rename-botconfiguration-to-appconfiguration \
  --title "Refactor: Rename BotConfiguration to AppConfiguration" \
  --body "See specs/011-rename-botconfiguration-to-appconfiguration/spec.md"
```

### Important Rules
- **NEVER** push directly to master
- All tests MUST pass before creating PR
- Squash merge PR to keep clean history
- Delete branch after merge

---

## Task List

### [IMPL-011-001] Identify All References
**Priority**: P1  
**Estimated Duration**: 15 minutes  
**Blocked By**: None

**Acceptance Criteria**:
- [ ] Complete list of all files referencing `BotConfiguration`
- [ ] Understand each usage context (import, type hint, variable)
- [ ] No references missed

**Implementation Steps**:
```bash
# Search for all BotConfiguration references
cd /Users/yaronl/personal/DeniDin/denidin-bot
grep -r "BotConfiguration" --include="*.py" . > /tmp/botconfig_refs.txt
cat /tmp/botconfig_refs.txt

# Expected files:
# - src/models/config.py (class definition)
# - denidin.py (import, type hint, variable)
# - src/handlers/ai_handler.py (import, type hint)
# - src/handlers/whatsapp_handler.py (import, type hint)
# - src/memory/memory_manager.py (import, type hint)
# - src/memory/session_manager.py (import, type hint)
# - tests/unit/*.py (various test files)
# - tests/integration/*.py (various test files)
```

**Deliverable**: List of all files requiring updates (save in notes or comment)

---

### [IMPL-011-002] Refactor Configuration Class
**User Story**: US-011-01  
**Priority**: P1  
**Estimated Duration**: 30 minutes  
**Blocked By**: IMPL-011-001

#### [IMPL-011-002a] ✍️ Verify Tests Use AppConfiguration
**Type**: Test Validation  
**Blocked By**: IMPL-011-001  
**Blocks**: IMPL-011-002b

**Acceptance Criteria**:
- [ ] Identified tests that validate config loading
- [ ] Tests will validate correct class name after refactor
- [ ] No test changes needed (tests are already correct)

**Implementation Steps**:
1. Check for config-specific tests:
   ```bash
   find tests/ -name "*config*" -type f
   ```
2. Review tests to understand how they load configuration
3. Verify tests use the imported class (will auto-update with imports)

**Note**: Most tests import the class, so renaming class + updating imports is sufficient.

**Human Approval Required**: ✋ Confirm test approach before proceeding

---

#### [IMPL-011-002b] 🔨 Rename Class Definition
**Type**: Implementation  
**Blocked By**: IMPL-011-002a (human approval)  
**Blocks**: IMPL-011-003

**Acceptance Criteria**:
- [ ] Class name changed to `AppConfiguration` in `src/models/config.py`
- [ ] `@dataclass` decorator preserved
- [ ] All fields unchanged
- [ ] Docstring updated

**Files to Modify**:
- `src/models/config.py`

**Implementation Steps**:
```python
# File: src/models/config.py

# BEFORE:
@dataclass
class BotConfiguration:
    """Configuration for the DeniDin bot."""
    # ... fields

# AFTER:
@dataclass
class AppConfiguration:
    """Configuration for the DeniDin application."""
    # ... fields (unchanged)
```

**Validation**:
```bash
# Verify class name changed
grep "class AppConfiguration" src/models/config.py
# Expect: Match found

# Verify no BotConfiguration class remains
grep "class BotConfiguration" src/models/config.py
# Expect: No match
```

---

### [IMPL-011-003] Update All Imports
**User Story**: US-011-01, US-011-03  
**Priority**: P1  
**Estimated Duration**: 20 minutes  
**Blocked By**: IMPL-011-002b

**Acceptance Criteria**:
- [ ] All source files import `AppConfiguration`
- [ ] All test files import `AppConfiguration`
- [ ] No `BotConfiguration` imports remain

**Files to Modify**: (Identified in IMPL-011-001)
- `denidin.py`
- `src/handlers/ai_handler.py`
- `src/handlers/whatsapp_handler.py`
- `src/memory/memory_manager.py`
- `src/memory/session_manager.py`
- `tests/unit/*.py`
- `tests/integration/*.py`

**Implementation Steps**:

**Option 1: IDE Refactor Tool (Recommended)**
1. Open `src/models/config.py` in VS Code
2. Right-click on `AppConfiguration` class name
3. Select "Rename Symbol"
4. Verify preview shows all references
5. Apply changes

**Option 2: Manual Find & Replace**
```bash
# Use multi_replace or manual editing
# For each file:
# FIND: from src.models.config import BotConfiguration
# REPLACE: from src.models.config import AppConfiguration

# FIND: config: BotConfiguration
# REPLACE: config: AppConfiguration

# FIND: BotConfiguration.from_json
# REPLACE: AppConfiguration.from_json
```

**Validation**:
```bash
# Search for remaining BotConfiguration imports
grep -r "from src.models.config import BotConfiguration" . --include="*.py"
# Expect: No results

# Search for BotConfiguration type hints
grep -r ": BotConfiguration" . --include="*.py"
# Expect: No results

# Search for BotConfiguration class usages
grep -r "BotConfiguration\." . --include="*.py"
# Expect: No results (or only comments)
```

---

### [IMPL-011-004] Update Variable Names
**User Story**: US-011-02  
**Priority**: P2  
**Estimated Duration**: 15 minutes  
**Blocked By**: IMPL-011-003

**Acceptance Criteria**:
- [ ] Main entry point uses `app_config` variable
- [ ] Other modules use `config` parameter (acceptable)
- [ ] No `bot_config` variables remain

**Files to Modify**:
- `denidin.py` (main priority)

**Implementation Steps**:
```python
# File: denidin.py

# BEFORE:
bot_config = AppConfiguration.from_json(config_data)
logger.info(f"Loaded configuration: {mask_api_key(bot_config.ai_api_key)}")
ai_client = OpenAI(api_key=bot_config.ai_api_key)
ai_handler = AIHandler(bot_config, ai_client)
whatsapp_handler = WhatsAppHandler(bot_config, ai_handler)

# AFTER:
app_config = AppConfiguration.from_json(config_data)
logger.info(f"Loaded configuration: {mask_api_key(app_config.ai_api_key)}")
ai_client = OpenAI(api_key=app_config.ai_api_key)
ai_handler = AIHandler(app_config, ai_client)
whatsapp_handler = WhatsAppHandler(app_config, ai_handler)
```

**Other Files**: Review if any use `bot_config`, but `config` parameter is acceptable (short form).

**Validation**:
```bash
# Search for bot_config variables
grep -r "bot_config" . --include="*.py"
# Expect: No results (or only comments/external libs)

# Verify app_config in denidin.py
grep "app_config" denidin.py
# Expect: Multiple matches
```

---

### [IMPL-011-005] Run Type Checking
**Priority**: P1  
**Estimated Duration**: 10 minutes  
**Blocked By**: IMPL-011-004

**Acceptance Criteria**:
- [ ] `mypy` type checking passes
- [ ] No type errors related to AppConfiguration
- [ ] IDE shows no type errors

**Validation**:
```bash
cd /Users/yaronl/personal/DeniDin/denidin-bot

# Run mypy type checking
python3 -m mypy src/ --ignore-missing-imports

# Expected output:
# Success: no issues found

# If mypy not installed:
pip3 install mypy
```

**If errors occur**: Review and fix type hints, then re-run.

---

### [IMPL-011-006] Run Full Test Suite
**User Story**: US-011-03  
**Priority**: P1  
**Estimated Duration**: 15 minutes  
**Blocked By**: IMPL-011-005

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

**If tests fail**: 
1. Review failure messages
2. Check for missed `BotConfiguration` references
3. Fix and re-run

---

### [IMPL-011-007] Manual Smoke Test
**Priority**: P2  
**Estimated Duration**: 5 minutes  
**Blocked By**: IMPL-011-006

**Acceptance Criteria**:
- [ ] Application starts without errors
- [ ] Configuration loads successfully
- [ ] No runtime errors related to class name

**Validation**:
```bash
cd /Users/yaronl/personal/DeniDin/denidin-bot
timeout 5 python3 denidin.py 2>&1 | head -20

# Expected:
# - Configuration loaded successfully
# - No errors about BotConfiguration
# - Application starts normally
```

---

### [IMPL-011-008] Update Documentation
**User Story**: US-011-04  
**Priority**: P3  
**Estimated Duration**: 15 minutes  
**Blocked By**: IMPL-011-006

#### [IMPL-011-008a] 🔨 Update Docstrings and Comments
**Type**: Implementation  
**Blocked By**: IMPL-011-006  
**Blocks**: IMPL-011-008b

**Acceptance Criteria**:
- [ ] Class docstring references "application configuration"
- [ ] Function docstrings use `AppConfiguration`
- [ ] Inline comments updated

**Files to Review**:
- `src/models/config.py` - Class docstring
- `denidin.py` - Any comments about configuration
- `src/handlers/*.py` - Docstrings

**Implementation Steps**:
1. Review docstrings mentioning "bot configuration"
2. Update to "application configuration" or "AppConfiguration"
3. Check inline comments

**Validation**:
```bash
# Search for "bot configuration" in docstrings/comments
grep -ri "bot configuration" src/ denidin-bot/denidin.py
# Review each occurrence, update if needed
```

---

#### [IMPL-011-008b] 🔨 Update Spec Documentation
**Type**: Implementation  
**Blocked By**: IMPL-011-008a  
**Blocks**: None

**Acceptance Criteria**:
- [ ] Spec files reference `AppConfiguration` where applicable
- [ ] No misleading `BotConfiguration` references in specs

**Files to Review**:
- `specs/001-whatsapp-chatbot-passthrough/spec.md`
- Any other specs mentioning configuration class

**Implementation Steps**:
1. Search specs for `BotConfiguration` references
2. Update to `AppConfiguration`
3. Verify context makes sense

**Validation**:
```bash
grep -r "BotConfiguration" specs/
# Review and update any references
```

---

### [IMPL-011-009] Final Verification
**Priority**: P1  
**Estimated Duration**: 10 minutes  
**Blocked By**: IMPL-011-008b

**Acceptance Criteria**:
- [ ] No `BotConfiguration` references in source code
- [ ] No `bot_config` variables (except external libs)
- [ ] All tests pass
- [ ] Type checking passes
- [ ] Application runs successfully

**Final Checks**:
```bash
# 1. Search for BotConfiguration (should only be in comments/history)
cd /Users/yaronl/personal/DeniDin/denidin-bot
grep -r "BotConfiguration" --include="*.py" .
# Expect: No results or only comments

# 2. Search for bot_config
grep -r "bot_config" --include="*.py" .
# Expect: No results or only external lib references

# 3. Type checking
python3 -m mypy src/ --ignore-missing-imports
# Expect: Success

# 4. Full test suite
python3 -m pytest tests/ -v
# Expect: 212+ passed, 4 skipped

# 5. Application start
timeout 5 python3 denidin.py 2>&1 | head -20
# Expect: Clean startup
```

---

## Commit and Push

```bash
# Stage all changes
git add .

# Commit with descriptive message
git commit -m "refactor: rename BotConfiguration to AppConfiguration

- Renamed class in src/models/config.py
- Updated all imports across source and test files
- Renamed bot_config variable to app_config in denidin.py
- Updated docstrings and comments
- All tests pass (212 passed, 4 skipped)

Improves code clarity by using accurate terminology.
DeniDin is an application with AI capabilities, not just a bot.

Closes #011-rename-botconfiguration-to-appconfiguration"

# Push to remote
git push origin 011-rename-botconfiguration-to-appconfiguration

# Create PR
gh pr create --base master --head 011-rename-botconfiguration-to-appconfiguration \
  --title "Refactor: Rename BotConfiguration to AppConfiguration" \
  --body "## Summary
Renames \`BotConfiguration\` class to \`AppConfiguration\` for accurate terminology.

## Changes
- Class name: \`BotConfiguration\` → \`AppConfiguration\`
- Variable: \`bot_config\` → \`app_config\` (main entry point)
- All imports and type hints updated
- Documentation and comments updated

## Test Results
✅ 212 passed, 4 skipped
✅ Type checking passes

See \`specs/011-rename-botconfiguration-to-appconfiguration/spec.md\` for details."
```

---

## Post-Merge Cleanup

```bash
# After PR merged
git checkout master
git pull origin master
# Branch auto-deleted by gh pr merge --delete-branch
```

---

## Notes

- **Low-risk refactoring** - pure naming change
- **IDE refactor tools recommended** for accuracy
- **Type checking validates correctness**
- Should be done **after 010-rename-openai-to-ai** to avoid conflicts
- Estimated time: 1-2 hours
