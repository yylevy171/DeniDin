# Enhancements Backlog

## Deployment & Operations

### Fix run_denidin.sh and stop_denidin.sh Scripts
**Priority:** High  
**Status:** Pending

**Problem:**
The `run_denidin.sh` and `stop_denidin.sh` scripts currently don't work properly:
- Bot process exits immediately when started via script (background execution fails)
- Script reports "Bot failed to start" even though logs show it started
- Process doesn't stay alive when detached from terminal
- Multiple bot instances can be created despite single-instance checks

**Root Causes:**
1. Background process execution with redirected stdin/stdout causes premature exit
2. `disown` alone not sufficient to keep process alive
3. Verification timing (3-second sleep) may be insufficient
4. Bot may be exiting when stdin is closed

**Proposed Solutions:**

1. **Use screen/tmux for process management:**
   - Start bot in detached screen/tmux session
   - More reliable than nohup/disown
   - Allows attaching to view live output
   - Cons: Requires screen/tmux installed

2. **Create proper daemon with double-fork:**
   - Implement proper daemonization in Python or shell
   - Fully detach from terminal session
   - Handle all signal forwarding properly
   - Cons: More complex implementation

3. **Use systemd/launchd for process management:**
   - Rely on OS service manager instead of custom scripts
   - Better for production deployment anyway
   - Cons: Not portable across dev/prod environments

4. **Fix background execution with proper I/O handling:**
   - Investigate why stdin closure causes exit
   - May need to modify bot code to handle detached mode
   - Add `--daemon` flag to denidin.py for proper background mode
   - Cons: Requires bot code changes

**Recommendation:** Option 4 (fix background execution) or Option 1 (use screen/tmux) for simplicity.

**Files to fix:**
- `run_denidin.sh` - Background process startup
- `stop_denidin.sh` - Graceful shutdown
- Possibly `denidin.py` - Add daemon mode support

## Memory System

### Remove /reset Command
**Priority:** Medium  
**Status:** Pending

**Problem:**
The `/reset` command allows users to manually transfer their conversation to long-term memory, but this creates issues:
- Users can call `/reset` multiple times, storing duplicate messages with different UUIDs
- Duplicate results appear in semantic search
- Increased storage costs and database bloat
- Sessions transfer to long-term memory automatically on 24h expiration anyway

**Proposed Solution:**
Remove the `/reset` command entirely and rely solely on automatic session expiration for long-term memory transfer.

**Trade-off:**
Users cannot manually control when a conversation becomes searchable in ChromaDB - must wait 24h for automatic expiration.

**Implementation:**
1. Remove `/reset` command handler from `denidin.py` (lines ~143-177)
2. Remove corresponding tests for `/reset` behavior
3. Update spec documentation to remove US-MEM-03 references
4. Sessions will naturally transfer once on expiration, preventing duplicates

**Files to modify:**
- `denidin.py` - Remove `/reset` command handler
- `tests/unit/test_memory_unit.py` - Remove `/reset` test cases
- `tests/integration/test_memory_integration.py` - Remove `/reset` test cases
- `specs/002-007-memory-system/spec.md` - Remove US-MEM-03 references

## Code Quality & Naming Conventions

### Rename "openai" References to "ai"
**Priority:** Medium  
**Status:** ✅ Completed (PR #30-32)

**Problem:**
Current codebase uses "openai" in variable names, parameters, and code references, creating vendor lock-in at the naming level. This:
- Makes it harder to switch AI providers in the future
- Violates abstraction principles
- Reduces code flexibility and maintainability

**Proposed Solution:**
Rename all "openai" references to "ai" throughout the codebase:
- `openai_client` → `ai_client`
- `openai_api_key` → `ai_api_key`
- `mock_openai` → `mock_ai`
- `test_openai_client` → `test_ai_client`

**Implementation:**
1. Update all Python files with "openai" variable names
2. Update configuration files (config.json, config.example.json, config.test.json)
3. Update all test files
4. Keep OpenAI class imports unchanged (from openai import OpenAI)
5. Update documentation to reference "AI client" instead of "OpenAI client"

**Files to modify:**
- `denidin.py` - Main entry point
- `src/handlers/ai_handler.py` - AI request handler
- `src/memory/memory_manager.py` - Memory system
- `src/models/config.py` - Configuration model
- `config/*.json` - All config files
- `tests/**/*.py` - All test files
- Documentation files

---

### Rename BotConfiguration to AppConfiguration
**Priority:** Medium  
**Status:** Pending

**Problem:**
The class `BotConfiguration` incorrectly describes the application as a "bot", but DeniDin is an application that happens to have conversational capabilities.

**Proposed Solution:**
Rename `BotConfiguration` to `AppConfiguration` throughout:
- Class name in `src/models/config.py`
- All imports and references
- Documentation and comments

**Implementation:**
1. Rename class in `src/models/config.py`
2. Update all imports: `from src.models.config import AppConfiguration`
3. Update variable names: `bot_config` → `app_config` where appropriate
4. Update docstrings and comments

**Files to modify:**
- `src/models/config.py` - Class definition
- `denidin.py` - Main entry point
- All files importing BotConfiguration
- Test files
- Documentation

---

### Update "Bot" Terminology to "App/Application"
**Priority:** Medium  
**Status:** Pending

**Problem:**
Documentation, specs, and code comments refer to DeniDin as a "bot" or "chatbot", which is inaccurate. DeniDin is an application with AI-powered conversational features, not just a bot.

**Proposed Solution:**
Update all references from "bot" to "app" or "application":
- "DeniDin WhatsApp AI Chatbot" → "DeniDin WhatsApp AI Application"
- "the bot" → "the application" or "DeniDin"
- "bot instance" → "application instance"
- "bot starts" → "application starts"

**Scope:**
- All markdown files (specs, plans, README)
- Code comments and docstrings
- Log messages
- Error messages
- Configuration file comments

**Exceptions (keep "bot"):**
- GreenAPIBot class (external library)
- WhatsApp bot account references (industry term)
- Historical git commit messages (don't rewrite history)

**Files to modify:**
- `README.md`
- `specs/**/*.md` - All specification files
- `denidin.py` - Comments and docstrings
- All source files - Comments and log messages
- `config/config.example.json` - Comments

