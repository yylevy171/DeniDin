# Implementation Plan: Memory System (002+007)

**Feature**: Conversation History + Long-term Memory  
**Branch**: `002-007-memory-system`  
**Status**: Ready for Implementation  
**Estimated Duration**: 10-12 days

## Overview

Implement unified memory system combining:
- **Short-term**: Session-based conversation history (JSON storage in `data/sessions/`)
- **Long-term**: Semantic memory with ChromaDB and embeddings (in `data/memory/`)
- **Commands**: `/remember`, `/reset`
- **AI Integration**: Automatic memory recall in responses
- **Feature Flags**: Deployed behind `enable_memory_system` flag for safe incremental rollout
- **Role-based Token Limits**: 4,000 tokens for clients, 100,000 for godfather
- **Image Support**: JSON stores image file references, actual images in `data/sessions/images/`

## Phase 1: Foundation & Dependencies (Day 1)

### Tasks
- [x] Create feature branch `002-007-memory-system`
- [x] Update `requirements.txt` with `chromadb>=0.4.22`
- [ ] Install ChromaDB: `pip3 install chromadb`
- [ ] Create directory structure:
  - `denidin-bot/data/sessions/`
  - `denidin-bot/data/sessions/images/` (for future image storage)
  - `denidin-bot/data/memory/`
- [ ] Add to `.gitignore`: `data/` (keep data local)
- [ ] Update `config/config.json` with memory settings and feature flags

### Files Modified
- `denidin-bot/requirements.txt` ✅
- `denidin-bot/.gitignore`
- `denidin-bot/config/config.json`

### Validation
- `pip3 list | grep chromadb` shows installation
- Directories exist and are git-ignored

---

## Phase 2: SessionManager Implementation (Days 2-3)

### 2.1 Write Tests First (TDD)

**File**: `tests/unit/test_session_manager.py`

```python
# Test cases to implement:
- test_create_new_session()
- test_add_message_to_session()
- test_get_conversation_history()
- test_session_token_pruning()
- test_session_persistence_to_disk()
- test_load_session_from_disk()
- test_session_expiration()
- test_clear_session()
```

### 2.2 Implement SessionManager

**File**: `src/utils/session_manager.py`

**Classes**:
- `Message` dataclass (role, content, timestamp, tokens, image_path: Optional[str])
- `Session` dataclass (chat_id, messages, timestamps, token count)
- `SessionManager` class

**Methods**:
- `__init__(storage_dir, max_tokens_by_role: Dict[str, int], timeout)`
- `get_session(chat_id) -> Session`
- `add_message(chat_id, role, content, user_role='client', image_path=None)`
- `get_conversation_history(chat_id, user_role='client') -> List[Dict]`
- `get_token_limit(user_role: str) -> int` (returns 4000 for 'client', 100000 for 'godfather')
- `clear_session(chat_id)`
- `_prune_session(session, token_limit)`
- `_save_session(session)`
- `_load_sessions()`

### Files Created
- `src/utils/session_manager.py`
- `tests/unit/test_session_manager.py`

### Validation
- All tests pass: `pytest tests/unit/test_session_manager.py -v`
- Code coverage >90%

---

## Phase 3: MemoryManager Implementation (Days 4-5)

### 3.1 Write Tests First (TDD)

**File**: `tests/unit/test_memory_manager.py`

```python
# Test cases to implement:
- test_initialize_chromadb()
- test_remember_fact()
- test_recall_memories()
- test_semantic_search_accuracy()
- test_forget_memory()
- test_list_memories()
- test_embedding_generation()
```

### 3.2 Implement MemoryManager

**File**: `src/utils/memory_manager.py`

**Classes**:
- `Memory` dataclass (id, content, metadata, created_at)
- `MemoryManager` class

**Methods**:
- `__init__(storage_dir, collection_name, embedding_model)`
- `remember(content, metadata) -> str`
- `recall(query, top_k, min_similarity) -> List[Dict]`
- `forget(memory_id)`
- `list_memories(limit, memory_type) -> List[Dict]`
- `_create_embedding(text) -> List[float]`

### Files Created
- `src/utils/memory_manager.py`
- `tests/unit/test_memory_manager.py`

### Validation
- All tests pass: `pytest tests/unit/test_memory_manager.py -v`
- ChromaDB collection created successfully
- Embeddings generated correctly
- Semantic search returns relevant results

---

## Phase 4: Configuration Updates (Day 6)

### 4.1 Update Config Model

**File**: `src/models/config.py`

Add to `BotConfiguration`:
```python
# Feature flags
feature_flags: Dict[str, bool] = field(default_factory=lambda: {
    "enable_memory_system": False
})

# Memory settings
session_storage_dir: str = "data/sessions"
session_token_limits: Dict[str, int] = field(default_factory=lambda: {
    "client": 4000,
    "godfather": 100000
})
session_timeout_hours: int = 24

memory_storage_dir: str = "data/memory"
memory_collection_name: str = "godfather_memory"
memory_embedding_model: str = "text-embedding-3-small"
memory_top_k: int = 5
memory_min_similarity: float = 0.7
```

### 4.2 Update Config File

**File**: `config/config.json`

Add sections:
```json
{
  "feature_flags": {
    "enable_memory_system": false
  },
  "memory": {
    "session": {
      "storage_dir": "data/sessions",
      "token_limits": {
        "client": 4000,
        "godfather": 100000
      },
      "timeout_hours": 24
    },
    "longterm": {
      "storage_dir": "data/memory",
      "collection_name": "godfather_memory",
      "embedding_model": "text-embedding-3-small",
      "top_k_results": 5,
      "min_similarity": 0.7
    }
  }
}
```

### Files Modified
- `src/models/config.py`
- `config/config.json`
- `config/config.example.json`

### Validation
- Config loads successfully
- New fields accessible in code

---

## Phase 5: AIHandler Integration (Days 7-8)

### 5.1 Update AIHandler

**File**: `src/handlers/ai_handler.py`

**Changes**:
1. Add to `__init__`:
   ```python
   self.session_manager = SessionManager(
       storage_dir=config.session_storage_dir,
       max_tokens_by_role=config.session_token_limits,
       timeout_hours=config.session_timeout_hours
   )
   self.memory_manager = MemoryManager(
       storage_dir=config.memory_storage_dir,
       collection_name=config.memory_collection_name,
       embedding_model=config.memory_embedding_model
   )
   self.feature_flags = config.feature_flags
   ```

2. Modify `create_request()`:
   - Accept `chat_id` and `user_role` parameters (default: 'client')
   - **Check feature flag**: Only use memory if `feature_flags.get('enable_memory_system', False)`
   - Retrieve conversation history from SessionManager with role-based token limit
   - Query relevant memories from MemoryManager
   - Build enhanced system prompt with memory context
   - Include conversation history in messages array

3. Modify `get_response()`:
   - Accept `chat_id` and `user_role` parameters
   - **Check feature flag** before storing in session
   - Store user message in session after getting AI response
   - Store AI response in session

4. Add new method `handle_remember_command(content, chat_id, user_role='client') -> str`

### Files Modified
- `src/handlers/ai_handler.py`

### Validation
- Unit tests updated and passing
- Integration test: memory recall in responses

---

## Phase 6: Command Handling (Day 9)

### 6.1 Update Main Handler

**File**: `denidin.py`

**Changes** in `handle_text_message()`:

```python
# Before creating AI request, check for commands
text = message.text_content.strip()

# Determine user role (TODO: implement proper RBAC in feature 006)
user_role = 'godfather' if message.sender_id == config.godfather_id else 'client'

# Check feature flag
memory_enabled = config.feature_flags.get('enable_memory_system', False)

if memory_enabled and text.startswith('/remember '):
    content = text[10:].strip()
    response = ai_handler.handle_remember_command(content, message.chat_id, user_role)
    notification.answer(response)
    logger.info(f"{tracking} Stored memory via /remember command")
    return

if memory_enabled and text == '/reset':
    ai_handler.session_manager.clear_session(message.chat_id)
    notification.answer("🔄 Conversation history cleared. Starting fresh!")
    logger.info(f"{tracking} Session cleared via /reset command")
    return

# Normal message flow continues...
# Pass chat_id and user_role to get_response()
response = ai_handler.get_response(message, chat_id=message.chat_id, user_role=user_role)
```

### Files Modified
- `denidin.py`

### Validation
- `/remember` command stores facts
- `/reset` command clears session
- Normal messages include memory context

---

## Phase 7: Integration Testing (Day 10)

### 7.1 Create Integration Tests

**File**: `tests/integration/test_memory_integration.py`

**Test scenarios**:
```python
- test_end_to_end_memory_recall()
  # 1. Store fact via /remember
  # 2. Ask question requiring that fact
  # 3. Verify AI response includes fact

- test_conversation_history_persists()
  # 1. Send message
  # 2. Send follow-up referencing first message
  # 3. Verify AI understands context

- test_session_clears_but_memory_persists()
  # 1. Store fact via /remember
  # 2. Have conversation
  # 3. /reset
  # 4. Verify conversation cleared but memory remains

- test_memory_semantic_search()
  # 1. Store multiple related facts
  # 2. Ask question matching those facts
  # 3. Verify relevant facts recalled

- test_token_limit_pruning()
  # 1. Send many messages
  # 2. Verify old messages pruned
  # 3. Verify recent messages retained
```

### Files Created
- `tests/integration/test_memory_integration.py`

### Validation
- All integration tests pass
- Manual testing with real WhatsApp messages
- Memory recall works as expected

---

## Phase 8: Documentation & Polish (Day 11)

### 8.1 Update Documentation

**Files to update**:
- `README.md` - Add memory features section
- `CONTRIBUTING.md` - Note memory system testing
- `specs/002-007-memory-system/spec.md` - Mark MVP as complete

### 8.2 Add Usage Examples

Create examples showing:
- How to use `/remember` command
- How memory recall works
- How to reset conversation

### Files Modified
- `README.md`
- `CONTRIBUTING.md`

---

## Phase 9: Testing & Validation (Day 12)

### 9.1 Full Test Suite

Run complete test suite:
```bash
# Unit tests
pytest tests/unit/ -v --cov=src --cov-report=term-missing

# Integration tests
pytest tests/integration/ -v

# Specific memory tests
pytest tests/unit/test_session_manager.py -v
pytest tests/unit/test_memory_manager.py -v
pytest tests/integration/test_memory_integration.py -v
```

### 9.2 Manual Testing

**Test scenarios**:
1. **Store and recall fact**:
   - Send: `/remember TestCorp owes me ₪5000`
   - Later ask: "What's the status with TestCorp?"
   - Verify: Response includes the ₪5000 fact

2. **Multi-turn conversation**:
   - Message 1: "I need to create an invoice"
   - Message 2: "For ₪10,000"
   - Message 3: "What was the amount?" 
   - Verify: Bot remembers ₪10,000

3. **Session reset**:
   - Have conversation
   - Send: `/reset`
   - Ask about previous conversation
   - Verify: Bot doesn't remember conversation but retains long-term memories

4. **Semantic search**:
   - Store: "TestCorp is in Tel Aviv"
   - Store: "TestCorp CEO is John Smith"
   - Ask: "Who runs TestCorp?"
   - Verify: Bot recalls CEO fact

### 9.3 Performance Testing

- Check memory query latency (<100ms)
- Verify token counting accuracy
- Test with large conversations (50+ messages)

### Success Criteria
- ✅ All tests pass (142+ tests)
- ✅ Code coverage >89%
- ✅ Manual tests successful
- ✅ No errors in logs
- ✅ Memory queries fast (<100ms)

---

## Phase 10: Deployment (Day 12-13)

### 10.1 Pre-deployment Checklist

- [ ] All tests passing
- [ ] Code coverage target met
- [ ] No pylint warnings
- [ ] No mypy errors
- [ ] Documentation complete
- [ ] Manual testing successful

### 10.2 Commit and Push

```bash
cd /Users/yaronl/personal/DeniDin
git add .
git commit -m "feat: Memory System (002+007) - Session history + ChromaDB long-term memory

- Implemented SessionManager for conversation history with role-based token limits
- Implemented MemoryManager with ChromaDB and semantic search
- Added /remember and /reset commands
- Integrated memory recall into AI responses
- Added feature flag 'enable_memory_system' (default: false)
- Added comprehensive tests (unit + integration)
- Updated configuration with memory settings
- Storage paths: data/sessions/ and data/memory/
- Support for future image storage references

Features:
- Session management with role-based token limits (4K client, 100K godfather)
- Long-term semantic memory with embeddings
- Automatic memory recall in AI responses (when flag enabled)
- Explicit memory storage via /remember
- Session reset via /reset
- Incremental deployment via feature flags

Tests: 142+ passing, 89%+ coverage"

git push origin 002-007-memory-system
```

### 10.3 Create Pull Request

```bash
gh pr create \
  --title "Feature 002+007: Memory System - Session History + Long-term Memory" \
  --body "## Overview

Implements unified memory system combining session-based conversation history with ChromaDB-powered long-term semantic memory.

**🚀 Deployment Strategy**: Feature flag controlled (`enable_memory_system: false` by default)

## Features Implemented

✅ **SessionManager** - Conversation history with role-based token limits
✅ **MemoryManager** - ChromaDB semantic memory with embeddings  
✅ **Commands** - /remember and /reset (when feature enabled)
✅ **AI Integration** - Automatic memory recall
✅ **Feature Flags** - Safe incremental deployment
✅ **Storage** - data/sessions/ and data/memory/ (gitignored)

## Role-based Token Limits

- **Client**: 4,000 tokens (~15-20 exchanges)
- **Godfather**: 100,000 tokens (includes history + recalled memories)

## Testing

- 142+ tests passing
- 89%+ code coverage
- Integration tests for end-to-end flows
- Manual testing validated

## Changes

- New: \`src/utils/session_manager.py\`
- New: \`src/utils/memory_manager.py\`
- Modified: \`src/handlers/ai_handler.py\`
- Modified: \`denidin.py\`
- Modified: \`src/models/config.py\`
- Added: ChromaDB dependency
- Added: Feature flag configuration

## Deployment Plan

1. **v1.1.0**: Merge with feature flag OFF (default)
2. **Testing**: Enable flag in test environment
3. **Gradual rollout**: Enable for godfather first
4. **Full release**: Enable for all users after validation

## Documentation

- Updated README with memory features
- Updated CONSTITUTION with feature flag guidelines
- Complete spec in \`specs/002-007-memory-system/\`

Ready for review and merge to master."
```

### 10.4 Merge and Tag

After approval:
```bash
gh pr merge --squash
git checkout master
git pull
git tag -a v1.1.0 -m "Release v1.1.0 - Memory System

Features:
- Conversation history (session management)
- Long-term semantic memory (ChromaDB)
- /remember and /reset commands
- Automatic memory recall in AI responses
- Feature flag controlled deployment
- Role-based token limits (4K/100K)

Note: Feature disabled by default (enable_memory_system: false)
Enable in config.json when ready for production use."

git push origin v1.1.0
```

---

## Rollback Plan

If issues arise:

```bash
# Revert to v1.0.0
git checkout master
git revert <commit-hash>
git push origin master

# Or reset branch
git checkout 002-007-memory-system
git reset --hard origin/master
git push origin 002-007-memory-system --force
```

---

## Success Metrics

- ✅ Session history persists across bot restarts
- ✅ Memories recalled with >80% relevance
- ✅ AI responses include contextual memory
- ✅ `/remember` command works reliably
- ✅ Token management prevents API cost overruns
- ✅ ChromaDB queries <100ms
- ✅ 90%+ test coverage maintained

---

## Dependencies

**New**:
- `chromadb>=0.4.22`

**Existing** (no changes):
- `openai>=1.12.0`
- `tenacity>=8.0.0`
- `pytest>=7.0.0`

---

## Next Features (Post-MVP)

After v1.1.0 release:
- Feature 006: RBAC User Roles (P0)
- Feature 004: MCP WhatsApp Server (P1)
- Feature 003: Media Processing (P1)
- Phase 2 enhancements: PDF/DOCX ingestion

---

**Last Updated**: January 17, 2026  
**Status**: Ready to implement  
**Estimated Completion**: January 29, 2026
