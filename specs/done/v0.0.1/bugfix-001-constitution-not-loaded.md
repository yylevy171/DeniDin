# Bugfix 001: Constitution Config Enabled But Files Not Loaded

**Created**: January 23, 2026  
**Status**: ✅ Complete  
**Priority**: P1 (High - Missing core AI behavior guidelines)  
**Component**: Configuration, AI Handler, System Prompt  
**Branch**: `bugfix/001-constitution-not-loaded`  
**Spec Location**: `specs/bugfixes/bugfix-001-constitution-not-loaded.md`

---

## Bug Description

**Observed Behavior:**
- `config.json` has `"constitution_config": { "enabled": true, "files": ["runtime_constitution.md"] }`
- File exists at `data/constitution/runtime_constitution.md` with 45 lines of AI behavioral guidelines
- **No code loads or uses these files** - they're completely ignored
- AI only gets basic `system_message`: "You are a helpful AI assistant named DeniDin."

**Expected Behavior:**
- When `constitution_config.enabled = true`, load constitution file(s)
- Prepend/append constitution content to `system_message` in AI requests
- AI receives rich behavioral context (45 lines) instead of one-line instruction

**Impact:**
- AI lacks detailed behavioral guidelines (communication style, privacy rules, role-based behavior)
- Constitution file is dead documentation
- Misleading config suggests feature works when it doesn't

---

## Root Cause Analysis

**TO BE COMPLETED**: Follow BDD workflow step 1

### Investigation Notes
- [ ] Grep codebase for any constitution file loading logic
- [ ] Check `ai_handler.py` `create_request()` - should load here
- [ ] Review git history - was this feature planned but never implemented?
- [ ] Compare to `system_message` usage to understand integration point

### Root Cause
**Initial hypothesis**: 
- Constitution config structure exists in schema
- File exists in data directory
- But no code bridge between config and AI request construction
- Feature was planned/designed but implementation never completed

*TO BE CONFIRMED after investigation*

---

## Fix Options

### Option A: Implement constitution loading (RECOMMENDED)
Load and prepend constitution to system_message:

```python
# In ai_handler.py create_request():
system_message = self.config.system_message

# Load constitution if enabled
if self.config.constitution_config.get('enabled'):
    constitution_files = self.config.constitution_config.get('files', [])
    constitution_dir = Path(self.config.data_root) / 'constitution'
    
    constitution_text = ""
    for filename in constitution_files:
        file_path = constitution_dir / filename
        if file_path.exists():
            constitution_text += file_path.read_text() + "\n\n"
    
    if constitution_text:
        system_message = constitution_text + system_message
```

**Pros**: 
- Features works as configured
- AI gets rich behavioral context
- Constitution file becomes active documentation

**Cons**: 
- Increases token usage (~500 tokens for constitution)
- Need to handle file loading errors
- May need token limit check vs `max_tokens` config

### Option B: Merge constitution into system_message
Copy constitution content directly into `system_message` string in config:

```json
"system_message": "# DeniDin AI Assistant\n\nYou are DeniDin...[full constitution text]"
```

**Pros**: 
- Simpler, no file I/O
- Single source in config
- No runtime loading overhead

**Cons**: 
- Config.json becomes huge (~50 lines)
- Less maintainable (markdown formatting in JSON)
- Loses separation of concerns

### Option C: Remove constitution config
Delete constitution_config from schema and config files:

**Pros**: 
- Removes dead configuration
- Simpler system

**Cons**: 
- Loses valuable behavioral guidelines
- Wastes existing constitution.md content

**TO BE DECIDED**: Human approval gate required (likely Option A)

---

## Test Gap Analysis

**Why didn't tests catch this?**
- No test verifies constitution content appears in AI requests
- Tests may use simple configs without constitution_config
- No integration test checking full system_message construction
- Feature never had acceptance criteria or tests

**Missing Test Cases:**
- [ ] Test that when `enabled=true`, constitution file is loaded
- [ ] Test that constitution content appears in system_message
- [ ] Test with multiple constitution files (if supported)
- [ ] Test error handling: missing file, empty file, invalid format
- [ ] Test that when `enabled=false`, constitution is NOT loaded
- [ ] Integration test with real AI call including constitution
- [ ] Test token usage increase with constitution loaded

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

### If Option A chosen (Implement loading):
- `src/handlers/ai_handler.py` - Add constitution loading in `create_request()`
- `tests/unit/test_ai_handler_memory.py` - Add constitution loading tests
- `tests/integration/test_end_to_end.py` - Verify constitution in real AI calls
- `config/config.example.json` - Document constitution feature usage

### If Option B chosen (Merge to system_message):
- `config/config.json` - Update system_message with constitution content
- `config/config.example.json` - Same
- `src/models/config.py` - Remove constitution_config from schema

### If Option C chosen (Remove):
- `src/models/config.py` - Remove constitution_config
- `config/config.json` - Remove constitution_config section
- `config/config.example.json` - Same
- `denidin.py` - Remove logging references

---

## Constitution Content Preview

Current file has valuable content that would enhance AI behavior:
- Core identity and purpose
- Communication style guidelines (concise, conversational)
- Memory usage rules (when to recall, acknowledge context)
- Limitations (honesty about unknowns)
- Role-based behavior (Godfather vs Client capabilities)
- Privacy & security guidelines

**Merging this into system_message would significantly improve AI behavior quality.**

---

## Token Usage Analysis

**Current system_message**: ~15 tokens  
**Constitution file**: ~500 tokens  
**Total increase**: ~485 tokens per request

**Impact on max_tokens=1000**:
- Effective remaining: ~515 tokens for conversation + response
- May need to increase default `max_tokens` to 1500-2000
- Should document in config.example.json

---

## References

- CONSTITUTION.md §I - Configuration & Secrets Management
- METHODOLOGY.md §VII - Bug-Driven Development
- `data/constitution/runtime_constitution.md` - Content to be loaded
