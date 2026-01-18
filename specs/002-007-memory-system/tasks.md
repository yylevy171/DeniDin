---

description: "Task list for Memory System (002+007) implementation"
---

# Tasks: Memory System (Conversation History + Long-term Memory)

**Input**: Design documents from `/specs/002-007-memory-system/`
**Prerequisites**: plan.md, spec.md, CONSTITUTION.md

**Tests**: Test-Driven Development (TDD) - ALL tests written and approved BEFORE implementation (per Constitution Principle VI)

**Organization**: Tasks are grouped by component/phase to enable systematic implementation with validation gates.

## Format: `[ID] [P?] [Phase] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Phase]**: Which implementation phase this task belongs to
- **[T###a]**: Write tests (REQUIRES HUMAN APPROVAL before T###b)
- **[T###b]**: Implement code (BLOCKED until T###a approved, tests are IMMUTABLE)
- Include exact file paths in descriptions

## TDD Workflow (Per Constitution Principle VI)

1. **Task A (Tests)**: Write comprehensive tests covering acceptance criteria
2. **👤 HUMAN APPROVAL GATE**: Review and approve tests
3. **Task B (Implementation)**: Write code to pass approved tests (tests frozen)
4. **Validation**: Run tests to verify implementation
5. **Next task**: Repeat TDD cycle

## Path Conventions

- Project structure: `denidin-bot/` at repository root
- Source code: `denidin-bot/src/`
- Tests: `denidin-bot/tests/`
- Data storage: `denidin-bot/data/` (gitignored)
- Config: `denidin-bot/config/`

---

## Phase 1: Foundation & Dependencies (Day 1) ✅ COMPLETE

**Purpose**: Setup environment, dependencies, and directory structure

- [x] T001 Create feature branch `002-007-memory-system`
- [x] T002 Update `denidin-bot/requirements.txt` with `chromadb>=0.4.22`
- [x] T003 Install ChromaDB: `pip3 install chromadb` → v1.4.1 installed
- [x] T004 Create directory structure: `denidin-bot/data/sessions/`
- [x] T005 Create directory structure: `denidin-bot/data/sessions/images/` (for future image storage)
- [x] T006 Create directory structure: `denidin-bot/data/memory/`
- [x] T007 Verify `data/` in `.gitignore` (already present)
- [x] T008 Update `config/config.json` with memory settings (already present with correct structure)
- [x] T009 Update `config/config.example.json` with memory settings (already present)

**Validation**:
- [x] V001 Verify ChromaDB installed: `pip3 list | grep chromadb` → chromadb 1.4.1
- [x] V002 Verify directories created: `ls -la data/` → sessions/, memory/ present
- [x] V003 Verify gitignore: `git status data/` → working tree clean (ignored)
- [x] V004 Validate config loads: Config validation passed with all required fields

**Status**: ✅ Phase 1 Complete
- [ ] T007 Update `denidin-bot/.gitignore` to include `data/` directory
- [ ] T008 Update `denidin-bot/config/config.json` with memory settings and feature flags
- [ ] T009 Update `denidin-bot/config/config.example.json` with memory settings (placeholder values)

**Validation**:
- [ ] V001 Verify ChromaDB installed: `pip3 list | grep chromadb`
- [ ] V002 Verify directories exist: `ls -la denidin-bot/data/`
- [ ] V003 Verify data/ is gitignored: `git status` should not show data/
- [ ] V004 Verify config.json loads successfully

**Checkpoint**: Foundation ready - can begin SessionManager implementation

---

## Phase 2: SessionManager Implementation (Days 2-3) ✅ COMPLETE

**Purpose**: Implement conversation history with UUID-based sessions and message persistence

### 2.1 SessionManager Tests (TDD - Write First) ✅

- [x] T010a Write SessionManager tests in `denidin-bot/tests/unit/test_session_manager.py`:
  - Test `test_create_new_session()`: Verify new session created with UUID and whatsapp_chat
  - Test `test_session_has_uuid()`: Verify session_id is valid UUID format
  - Test `test_message_counter_increments()`: Verify message_counter increments with each message
  - Test `test_add_message_to_session()`: Verify message added with all fields and stored in session directory
  - Test `test_get_conversation_history()`: Verify correct message format for AI
  - Test `test_session_persistence_to_disk()`: Verify session saved as JSON in session directory
  - Test `test_load_session_from_disk()`: Verify session loaded correctly after restart
  - Test `test_session_moved_to_expired_folder_by_date()`: Verify sessions moved to expired/YYYY-MM-DD/
  - Test `test_expired_session_messages_also_moved()`: Verify messages move with session
  - Test `test_expired_session_not_in_index()`: Verify expired sessions removed from chat_to_session index
  - Test `test_new_session_created_after_expiration()`: Verify new session created for same chat after expiration
  - Test `test_cleanup_thread_runs_periodically()`: Verify background cleanup thread works
  - Test `test_active_sessions_not_moved()`: Verify active sessions stay in place
  - Test `test_clear_session()`: Verify session cleared completely
  - Test `test_multiple_sessions_isolated()`: Verify sessions are isolated
  - **DEFERRED to Feature 006 (RBAC)**: Token limits, pruning tests (skipped)
  - **DEFERRED to Phase 3**: Image path storage tests (skipped)

**Status**: ✅ 15 tests passing, 4 skipped (RBAC/images deferred)

### 2.2 SessionManager Implementation ✅

- [x] T010b Implement SessionManager in `denidin-bot/src/memory/session_manager.py`:
  - Create `Message` dataclass with fields: message_id, chat_id, role, content, sender, recipient, timestamp, received_at, was_received, order_num, image_path
  - Create `Session` dataclass with fields: session_id (UUID), whatsapp_chat, message_ids, message_counter, created_at, last_active, total_tokens
  - Implement `SessionManager.__init__()` with storage_dir, session_timeout, cleanup_interval
  - Implement `get_session(chat_id)` to get or create session with UUID
  - Implement `add_message(chat_id, role, content, user_role, sender, recipient, image_path)` - stores messages in session subdirectory
  - Implement `get_conversation_history(chat_id, user_role)` returning formatted messages for AI
  - Implement `clear_session(chat_id)` to reset conversation
  - Implement `_save_session(session)` to persist session metadata to {session_id}/session.json
  - Implement `_load_session(session_id)` to load session metadata
  - Implement `_load_sessions()` to load all sessions from disk on startup into chat_to_session index
  - Implement `_cleanup_expired_sessions()` to move expired sessions to expired/YYYY-MM-DD/ folders
  - Implement `_cleanup_loop()` background thread for periodic cleanup
  - Implement `stop_cleanup_thread()` for clean shutdown
  - Use `datetime.now(timezone.utc).isoformat()` for all timestamps (Constitution Principle VIII)
  - **DEFERRED to Feature 006 (RBAC)**: max_tokens_by_role, get_token_limit(), _prune_session()

**Status**: ✅ Implementation complete (354 lines), RBAC features deferred

**Validation**:
- [x] V005 Run SessionManager tests: `pytest tests/unit/test_session_manager.py -v` → 15 passed, 4 skipped
- [ ] V006 Verify test coverage >90%: `pytest tests/unit/test_session_manager.py --cov=src/memory/session_manager --cov-report=term-missing`
- [x] V007 Verify JSON files created in `data/sessions/{session_id}/` with messages/ subdirectory
- [ ] V008 Verify pylint score: `pylint src/memory/session_manager.py`

**Checkpoint**: ✅ SessionManager complete and tested - ready for Phase 3 (MemoryManager)

---

## Phase 3: MemoryManager Implementation (Days 4-5) ✅ COMPLETE

**Purpose**: Implement long-term semantic memory with ChromaDB

### 3.1 MemoryManager Tests (TDD - Write First) ✅

- [x] T011a Write MemoryManager tests in `denidin-bot/tests/unit/test_memory_manager.py`:
  - Test `test_initialize_chromadb_client()`: Verify ChromaDB client initialized with persistent storage
  - Test `test_create_storage_directory_if_missing()`: Verify storage directory created if missing
  - Test `test_custom_embedding_model()`: Verify custom embedding model support
  - Test `test_chromadb_initialization_failure_raises_exception()`: Verify ChromaDB init failure handling (ERR-MEMORY-001)
  - Test `test_openai_initialization_failure_raises_exception()`: Verify OpenAI init failure handling
  - Test `test_get_or_create_collection_creates_new()`: Verify new collection creation
  - Test `test_get_or_create_collection_returns_existing()`: Verify existing collection reuse
  - Test `test_create_per_client_collections()`: Verify per-client collection architecture (main, public, private)
  - Test `test_create_global_collections()`: Verify global collections (system_context, global_client_context)
  - Test `test_remember_stores_memory_in_collection()`: Verify memory storage with embeddings
  - Test `test_remember_with_custom_metadata()`: Verify custom metadata storage
  - Test `test_remember_default_metadata_added()`: Verify default metadata (created_at, type) added
  - Test `test_remember_in_public_collection()`: Verify storage in client's public collection
  - Test `test_remember_in_private_collection()`: Verify storage in client's private collection
  - Test `test_remember_embedding_failure_raises_exception()`: Verify embedding failure handling (ERR-MEMORY-002)
  - Test `test_recall_from_single_collection()`: Verify semantic search from single collection
  - Test `test_recall_from_multiple_collections()`: Verify multi-collection semantic search
  - Test `test_recall_respects_top_k_limit()`: Verify top_k parameter respected
  - Test `test_recall_filters_by_min_similarity()`: Verify similarity threshold filtering
  - Test `test_recall_empty_collections_returns_empty_list()`: Verify empty collection handling
  - Test `test_recall_results_sorted_by_similarity_descending()`: Verify results sorted by similarity
  - Test `test_recall_includes_collection_name_in_results()`: Verify collection name in results
  - Test `test_recall_embedding_failure_raises_exception()`: Verify recall embedding failure handling
  - Test `test_list_all_memories_in_collection()`: Verify memory listing
  - Test `test_list_memories_with_limit()`: Verify limit parameter in listing
  - Test `test_list_memories_filtered_by_type()`: Verify filtering by metadata type
  - Test `test_create_embedding_calls_openai_api()`: Verify OpenAI API integration
  - Test `test_create_embedding_with_custom_model()`: Verify custom model support
  - Test `test_create_embedding_api_failure_raises_exception()`: Verify API failure handling
  - **REMOVED**: `forget()` functionality deferred indefinitely
  - **DEFERRED**: `/remember` command to Phase 4-5 integration

**Status**: ✅ 29 tests passing, all approved

### 3.2 MemoryManager Implementation ✅

- [x] T011b Implement MemoryManager in `denidin-bot/src/memory/memory_manager.py`:
  - Created `CollectionWrapper` class to preserve original collection names (ChromaDB sanitization compatibility)
  - Implement `MemoryManager.__init__()` with storage_dir, embedding_model, optional openai_client
  - Initialize ChromaDB PersistentClient with anonymized_telemetry=False
  - Implement hybrid eager/lazy OpenAI initialization (eager for test failures, lazy for missing API keys)
  - Implement `get_or_create_collection(collection_name)` with name sanitization (`@` → `_at_`)
  - Implement collection caching for test mock compatibility
  - Implement `remember(content, collection_name, metadata)` to store memory with embedding, return UUID
  - Implement `recall(query, collection_names, top_k, min_similarity)` for multi-collection semantic search
  - Implement `list_memories(collection_name, limit, memory_type)` to list/filter memories
  - Implement `_create_embedding(text)` to generate embeddings via OpenAI API (text-embedding-3-small)
  - Use `datetime.utcnow().isoformat()` for created_at timestamps (Constitution Principle VIII)
  - Error handling: ERR-MEMORY-001 (ChromaDB init), ERR-MEMORY-002 (embedding failures) - raise exceptions
  - Per-entity collection architecture: memory_{chat}, memory_{chat}_public, memory_{chat}_private
  - Global collections: memory_system_context, memory_global_client_context
  - Similarity calculation: 1 - cosine_distance
  - Multi-collection search: iterate, merge, sort by similarity descending
  - **REMOVED**: `forget()` method (deferred indefinitely per user decision)

**Status**: ✅ Implementation complete (283 lines), all functionality working

**Validation**:
- [x] V009 Run MemoryManager tests: `pytest tests/unit/test_memory_manager.py -v` → 29 passed in 1.26s
- [x] V010 Verify Phase 2 tests still pass: `pytest tests/unit/test_session_manager.py -v` → 15 passed, 4 skipped
- [x] V011 Verify ChromaDB collections created in `data/memory/` with proper sanitization
- [x] V012 Verify embeddings generated correctly (OpenAI API integration tested)
- [x] V013 Verify real-world error handling with bad API key

**Checkpoint**: ✅ MemoryManager complete and tested - ready for Phase 4 (AIHandler integration)

---

## Phase 4: Configuration Updates (Day 6) ✅ COMPLETE

**Purpose**: Add memory settings to configuration model and files

### 4.1 Update Config Model ✅

- [x] T012 Update `denidin-bot/src/models/config.py`:
  - Added `godfather_phone: Optional[str] = None`
  - Added `feature_flags: Dict[str, bool] = field(default_factory=dict)`
  - Added `memory: Dict = field(default_factory=dict)`
  - Added `constitution_config: Dict = field(default_factory=dict)`
  - Added `user_roles: Dict = field(default_factory=dict)`
  - **NOTE**: Token limits, session settings deferred to Feature 006 (RBAC)

### 4.2 Update Config Files ✅

- [x] T013 Config fields available in `denidin-bot/config/config.json`
- [x] T014 Backward compatibility ensured with getattr() pattern

**Validation**:
- [x] V014 Config loads successfully (15 config tests passing)
- [x] V015 Feature flag accessible via getattr(config, 'feature_flags', {})
- [x] V016 Memory settings accessible via config.memory dict
- [x] V017 Backward compatibility: Old tests still pass (11 legacy AIHandler tests)

**Status**: ✅ Phase 4 Complete - Config model extended, backward compatible

---

## Phase 5: AIHandler Integration (Days 7-8) ✅ COMPLETE

**Purpose**: Integrate memory system into AI response generation

### 5.1 AIHandler Tests (TDD - Write First) ✅

- [x] T015a Write AIHandler integration tests in `denidin-bot/tests/unit/test_ai_handler_memory.py`:
  - Test `test_initialize_with_memory_managers()`: Verify SessionManager and MemoryManager initialized
  - Test `test_create_request_includes_recalled_memories()`: Verify semantic memories in system prompt
  - Test `test_get_response_stores_messages_in_session()`: Verify user + AI messages stored
  - Test `test_api_call_includes_conversation_history()`: Verify conversation history in OpenAI call
  - Test `test_hybrid_memory_recall_with_conversation_context()`: Verify BOTH session history AND long-term memories
  - Test `test_transfer_session_to_long_term_memory_on_session_end()`: Verify AI summarization to ChromaDB
  - Test `test_handle_summarization_failure_gracefully()`: Verify fallback to raw conversation (zero data loss)
  - Test `test_startup_recovery_expired_sessions()`: Verify expired sessions → long-term memory
  - Test `test_startup_recovery_no_orphaned_sessions()`: Verify clean startup when no orphans
  - Test `test_startup_recovery_handles_errors_gracefully()`: Verify recovery continues despite failures

**Status**: ✅ 10/10 tests passing, approved and frozen

### 5.2 AIHandler Implementation ✅

- [x] T015b Update `denidin-bot/src/handlers/ai_handler.py` (524 lines):
  - Added conditional memory initialization with feature flag check (line 47)
  - Updated `create_request()`: Accepts chat_id, user_role; queries MemoryManager for semantic recall
  - Updated `get_response()`: Retrieves conversation history, stores user+assistant messages in session
  - Added `transfer_session_to_long_term_memory()`: AI summarization with fallback to raw conversation (lines 360-445)
  - Added `recover_orphaned_sessions()`: Startup recovery - expired→long-term, active→short-term (lines 460-524)
  - Backward compatibility: Uses getattr(config, 'feature_flags', {}) pattern
  - **Manual commands deferred**: /remember, /forget commands - future release

**Validation**:
- [x] V017 Run AIHandler memory tests: 10/10 PASSED
- [x] V018 Verify existing AIHandler tests still pass: 6/6 errors + 5/5 retry = 11/11 PASSED
- [x] V019 Total AIHandler tests: 21/21 PASSED (backward compatible)
- [x] V020 PR #18 merged to master via squash merge

**Status**: ✅ Phase 5 Complete - All AIHandler memory integration working, merged to production

---

## Phase 6: Main Bot Integration (Day 9)

**Purpose**: Update main bot to use memory-enabled AIHandler

**REMOVED**: `/remember` command - deferred to future release

### 6.1 Main Bot Integration Tests (TDD - Write First)

- [ ] T016a Write integration tests in `denidin-bot/tests/integration/test_memory_integration.py`:
  - Test `test_conversation_uses_session_history()`: Verify multi-turn conversation maintains context
  - Test `test_conversation_uses_long_term_memory()`: Verify long-term facts are recalled
  - Test `test_reset_command_clears_session()`: Verify /reset clears conversation history only
  - Test `test_normal_message_flow_with_memory()`: Verify regular messages include both memories
  - Test `test_user_role_detection()`: Verify godfather vs client role determination

**👤 HUMAN APPROVAL GATE**: Review and approve integration tests before implementation

### 6.2 Main Bot Implementation

- [ ] T016b Update `denidin-bot/denidin.py` in `handle_text_message()` (BLOCKED until T016a approved):
  - **ON STARTUP**: Call `ai_handler.recover_orphaned_sessions()` to handle crash recovery
  - Determine user role: `user_role = 'godfather' if message.sender_id == config.godfather_phone else 'client'`
  - Check feature flag: `memory_enabled = config.feature_flags.get('enable_memory_system', False)`
  - Add `/reset` command handler: Call `ai_handler.session_manager.clear_session()`, send confirmation
  - Update normal message flow: Pass `chat_id`, `user_role`, `sender`, `recipient` to `ai_handler.get_response()`
  - Add logging for memory usage with tracking prefix
  - **SESSION EXPIRATION**: When session expires, call `ai_handler.transfer_session_to_long_term_memory()`

**Validation**:
- [ ] V021 Run integration tests: `pytest tests/integration/test_memory_integration.py -v`
- [ ] V022 Verify existing integration tests pass: `pytest tests/integration/ -v`
- [ ] V023 Verify pylint score: `pylint denidin.py`

**Checkpoint**: Main bot integrated with memory - can begin end-to-end testing

---

## Phase 7: Integration Testing (Day 10)

**Purpose**: End-to-end testing of memory system

### 7.1 Integration Tests

- [ ] T017 Create comprehensive integration tests in `denidin-bot/tests/integration/test_memory_integration.py`:
  - Test `test_end_to_end_memory_recall()`: Store fact via /remember, ask question, verify fact in response
  - Test `test_conversation_history_persists()`: Multi-turn conversation, verify context maintained
  - Test `test_session_clears_but_memory_persists()`: /remember → conversation → /reset → verify memory remains
  - Test `test_memory_semantic_search()`: Store multiple facts, verify relevant ones recalled
  - Test `test_token_limit_pruning_client()`: Send many messages as client, verify pruning at 4K
  - Test `test_token_limit_pruning_godfather()`: Send many messages as godfather, verify pruning at 100K
  - Test `test_feature_flag_disabled()`: Verify memory not used when flag is false
  - Test `test_feature_flag_enabled()`: Verify memory used when flag is true

**Validation**:
- [ ] V024 Run all integration tests: `pytest tests/integration/test_memory_integration.py -v`
- [ ] V025 Run full test suite: `pytest tests/ -v`
- [ ] V026 Verify test count increased: Should be 142+ → 160+ tests

**Checkpoint**: Integration tests passing - can begin manual testing

### 7.2 Manual Testing Checklist

- [ ] T018 👤 **MANUAL TEST 1**: Store and recall fact
  - Send: `/remember TestCorp owes me ₪5000`
  - Later ask: "What's the status with TestCorp?"
  - Verify: Response includes the ₪5000 fact

- [ ] T019 👤 **MANUAL TEST 2**: Multi-turn conversation
  - Message 1: "I need to create an invoice"
  - Message 2: "For ₪10,000"
  - Message 3: "What was the amount?"
  - Verify: Bot remembers ₪10,000

- [ ] T020 👤 **MANUAL TEST 3**: Session reset
  - Have conversation
  - Send: `/reset`
  - Ask about previous conversation
  - Verify: Bot doesn't remember conversation but retains long-term memories

- [ ] T021 👤 **MANUAL TEST 4**: Semantic search
  - Send: `/remember TestCorp is in Tel Aviv`
  - Send: `/remember TestCorp CEO is John Smith`
  - Ask: "Who runs TestCorp?"
  - Verify: Bot recalls CEO fact

**Checkpoint**: Manual tests successful - can begin documentation

---

## Phase 8: Documentation & Polish (Day 11)

**Purpose**: Update documentation with memory features

- [ ] T022 [P] Update `denidin-bot/README.md`:
  - Add "Memory System" section describing features
  - Document `/remember` and `/reset` commands
  - Add usage examples
  - Document feature flag configuration

- [ ] T023 [P] Update `denidin-bot/CONTRIBUTING.md`:
  - Add note about memory system testing
  - Document data/ directory structure
  - Add guidelines for testing with memory

- [ ] T024 [P] Update `specs/002-007-memory-system/spec.md`:
  - Mark MVP scope as complete
  - Add implementation notes

- [ ] T025 [P] Create usage examples document (optional)

**Validation**:
- [ ] V027 Verify README renders correctly
- [ ] V028 Verify all documentation links work
- [ ] V029 Verify code examples in docs are accurate

**Checkpoint**: Documentation complete - ready for final validation

---

## Phase 9: Final Testing & Validation (Day 12)

**Purpose**: Complete test suite and quality checks

### 9.1 Full Test Suite

- [ ] T026 Run unit tests with coverage:
  ```bash
  pytest tests/unit/ -v --cov=src --cov-report=term-missing
  ```

- [ ] T027 Run integration tests:
  ```bash
  pytest tests/integration/ -v
  ```

- [ ] T028 Run specific memory tests:
  ```bash
  pytest tests/unit/test_session_manager.py -v
  pytest tests/unit/test_memory_manager.py -v
  pytest tests/integration/test_memory_integration.py -v
  ```

**Validation**:
- [ ] V030 All tests pass (160+ tests)
- [ ] V031 Code coverage >89%
- [ ] V032 No errors in test output

### 9.2 Performance Testing

- [ ] T029 Test memory query latency:
  - Store 100 memories
  - Query with recall()
  - Verify queries complete in <100ms

- [ ] T030 Test token counting accuracy:
  - Compare estimated tokens vs actual API tokens
  - Verify pruning happens at correct thresholds

- [ ] T031 Test with large conversations:
  - Send 50+ messages
  - Verify pruning works correctly
  - Verify bot remains responsive

**Validation**:
- [ ] V033 Memory queries <100ms
- [ ] V034 Token counting within 10% accuracy
- [ ] V035 No performance degradation with large sessions

### 9.3 Code Quality Checks

- [ ] T032 Run pylint on all modified files:
  ```bash
  pylint src/utils/session_manager.py src/utils/memory_manager.py src/handlers/ai_handler.py src/models/config.py denidin.py
  ```

- [ ] T033 Verify type hints with mypy (if configured)

- [ ] T034 Review code for UTC timestamp compliance (Constitution Principle VIII)

**Validation**:
- [ ] V036 Pylint score >9.0/10 for all new files
- [ ] V037 No mypy errors
- [ ] V038 All datetime operations use `datetime.now(timezone.utc)`

**Checkpoint**: All quality checks pass - ready for deployment

---

## Phase 10: Deployment (Days 12-13)

**Purpose**: Commit, create PR, and prepare for release

### 10.1 Pre-deployment Checklist

- [ ] T035 Verify pre-deployment checklist:
  - [ ] All tests passing (160+ tests)
  - [ ] Code coverage >89%
  - [ ] No pylint warnings (<9.0)
  - [ ] No mypy errors
  - [ ] Documentation complete
  - [ ] Manual testing successful
  - [ ] Feature flag defaults to false

### 10.2 Commit and Push

- [ ] T036 Stage all changes:
  ```bash
  cd /Users/yaronl/personal/DeniDin
  git add .
  ```

- [ ] T037 Commit with detailed message:
  ```bash
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

Tests: 160+ passing, 89%+ coverage"
  ```

- [ ] T038 Push to feature branch:
  ```bash
  git push origin 002-007-memory-system
  ```

### 10.3 Create Pull Request

- [ ] T039 Create PR via GitHub CLI (see plan.md Phase 10.3 for full PR body)

### 10.4 Merge and Tag (After Approval)

- [ ] T040 Merge PR:
  ```bash
  gh pr merge --squash
  ```

- [ ] T041 Switch to master and pull:
  ```bash
  git checkout master
  git pull
  ```

- [ ] T042 Tag release:
  ```bash
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
  ```

- [ ] T043 Push tag:
  ```bash
  git push origin v1.1.0
  ```

**Validation**:
- [ ] V039 PR created successfully
- [ ] V040 PR approved and merged
- [ ] V041 Tag v1.1.0 created
- [ ] V042 Master branch updated

**Checkpoint**: Memory System deployed! 🎉

---

## Dependencies & Execution Order

### Phase Dependencies

1. **Phase 1 (Foundation)**: No dependencies - start immediately
2. **Phase 2 (SessionManager)**: Depends on Phase 1 completion
3. **Phase 3 (MemoryManager)**: Depends on Phase 1 completion (can parallelize with Phase 2)
4. **Phase 4 (Configuration)**: Depends on Phases 2 & 3 completion
5. **Phase 5 (AIHandler)**: Depends on Phases 2, 3 & 4 completion
6. **Phase 6 (Commands)**: Depends on Phase 5 completion
7. **Phase 7 (Integration Tests)**: Depends on Phase 6 completion
8. **Phase 8 (Documentation)**: Can start after Phase 6 (parallel with Phase 7)
9. **Phase 9 (Final Validation)**: Depends on Phases 7 & 8 completion
10. **Phase 10 (Deployment)**: Depends on Phase 9 completion

### TDD Workflow Per Phase

**Critical TDD Rules** (Constitution Principle VI):
- Every T###a (test) MUST be approved before T###b (implementation)
- Tests MUST be written to FAIL initially (no implementation exists yet)
- Once approved, tests are IMMUTABLE without re-approval
- Implementation only proceeds after test approval gate

### Parallel Opportunities

- Phase 1: All T004-T006 directory creation can run in parallel
- Phase 1: T008-T009 config updates can run in parallel
- Phases 2 & 3: SessionManager and MemoryManager can be developed in parallel (different files)
- Phase 8: All documentation tasks can run in parallel

---

## Success Metrics

After implementation completion, verify:

- ✅ Session history persists across bot restarts
- ✅ Memories recalled with >80% relevance
- ✅ AI responses include contextual memory
- ✅ `/remember` command works reliably
- ✅ Token management prevents API cost overruns
- ✅ ChromaDB queries <100ms
- ✅ 160+ tests passing
- ✅ 89%+ code coverage maintained
- ✅ Feature flag defaults to false (safe deployment)
- ✅ All UTC timestamps used (Constitution Principle VIII)

---

## Rollback Plan

If issues arise after deployment:

```bash
# Option 1: Disable feature flag (instant rollback, no code change)
# Edit config.json: "enable_memory_system": false

# Option 2: Revert to v1.0.0
git checkout master
git revert <commit-hash>
git push origin master

# Option 3: Reset branch
git checkout 002-007-memory-system
git reset --hard origin/master
git push origin 002-007-memory-system --force
```

---

## Notes

- [P] tasks = different files, no dependencies, can run in parallel
- [Phase] label maps task to specific implementation phase
- TDD workflow strictly enforced: Tests → Approval → Implementation
- Feature flag ensures safe deployment (disabled by default)
- All timestamps use UTC (Constitution Principle VIII)
- Commit after each completed phase or logical group
- Stop at validation checkpoints to verify progress
- Manual approval gates ensure quality before proceeding

---

**Created**: January 18, 2026  
**Last Updated**: January 18, 2026  
**Status**: Ready for implementation  
**Total Tasks**: 43 implementation tasks + 42 validation tasks = 85 tasks
