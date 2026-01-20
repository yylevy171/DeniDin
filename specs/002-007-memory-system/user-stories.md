# User Stories: Memory System Phase 6 Integration

**Feature**: 002+007 Memory System - Main Bot Integration  
**Phase**: 6 (Main Bot Integration)  
**Status**: Ready for Implementation  
**Created**: January 19, 2026

## Purpose

This document defines the user-facing behaviors that Phase 6 integration tests must verify. These stories describe what users (Godfather and Clients) can do with the memory system when integrated into the main bot.

---

## US-MEM-01: Multi-turn Conversation with Session History

**As a** WhatsApp user  
**I want** the bot to remember what I said earlier in our conversation  
**So that** I don't have to repeat myself and can have natural, contextual conversations

### Acceptance Criteria

**Given** I am chatting with DeniDin via WhatsApp  
**And** the memory system is enabled (`enable_memory_system: true`)  
**When** I send multiple messages in sequence:
1. "I need to create an invoice"
2. "For ₪10,000"
3. "What was the amount?"

**Then** the bot should:
- Remember message 2 contains the amount ₪10,000
- Respond to message 3 with "The amount is ₪10,000" (or similar)
- NOT ask "What amount?" or show no memory of previous messages

### Test Scenarios

1. **Simple 2-message context**
   - Message 1: "My name is John"
   - Message 2: "What's my name?"
   - Expected: Bot responds with "John" or "Your name is John"

2. **Multi-step task tracking**
   - Message 1: "I need to contact TestCorp"
   - Message 2: "They're in Tel Aviv"
   - Message 3: "What city is TestCorp in?"
   - Expected: Bot responds with "Tel Aviv"

3. **Context spanning multiple exchanges**
   - Send 5-10 messages building context
   - Ask question requiring context from message 2-3
   - Expected: Bot recalls correctly

### Related Requirements
- REQ-SESSION-001: Session creation
- REQ-SESSION-002: Message storage
- AC-SESSION-007: Conversation history format

---

## US-MEM-02: Long-term Memory Recall Across Sessions

**As a** Godfather user  
**I want** the bot to remember important facts I've told it, even after I reset the conversation  
**So that** I don't lose important business context

### Acceptance Criteria

**Given** I am the Godfather (my WhatsApp matches `godfather_phone` in config)  
**And** the memory system is enabled  
**When** I have the following conversation flow:
1. Session 1: "TestCorp owes me ₪5000" → Bot stores in long-term memory
2. Send `/reset` command → Session cleared
3. Session 2: "What's the status with TestCorp?" → New session, no conversation history

**Then** the bot should:
- Recall the long-term memory about TestCorp debt
- Include "₪5000" in the response
- NOT say "I don't have any information about TestCorp"

### Test Scenarios

1. **Fact storage and retrieval**
   - Store: "TestCorp CEO is John Smith"
   - Reset session
   - Query: "Who runs TestCorp?"
   - Expected: Bot mentions "John Smith"

2. **Multiple facts about same entity**
   - Store: "TestCorp is in Tel Aviv"
   - Store: "TestCorp CEO is John Smith"
   - Reset session
   - Query: "Tell me about TestCorp"
   - Expected: Bot mentions both Tel Aviv AND John Smith

3. **Semantic search (not exact match)**
   - Store: "The client from Jerusalem prefers afternoon meetings"
   - Reset session
   - Query: "When should I schedule meetings with the Jerusalem client?"
   - Expected: Bot mentions "afternoon" or "afternoon meetings"

### Related Requirements
- REQ-MEMORY-002: Semantic search
- REQ-MEMORY-003: Multi-collection search
- AC-MEMORY-001: Memory recall accuracy

---

## US-MEM-03: Reset Command Clears Session Only

**As a** user  
**I want** to clear the current conversation  
**So that** I can start fresh on a new topic without the bot being confused by old context

### Acceptance Criteria

**Given** I am chatting with DeniDin  
**And** I have sent several messages building context  
**And** the memory system is enabled  
**When** I send the `/reset` command

**Then** the bot should:
- Send confirmation message: "🔄 Conversation history cleared. Starting fresh!"
- Clear the session's conversation history
- Preserve long-term memories (if any)
- Treat next message as start of new conversation

### Test Scenarios

1. **Session cleared but long-term memory intact**
   - Build conversation context (5 messages)
   - Store long-term memory: "My favorite color is blue"
   - Send `/reset`
   - Ask about conversation context → Bot has no memory
   - Ask about favorite color → Bot recalls "blue"

2. **Confirmation message sent**
   - Send `/reset`
   - Expected: Bot responds with confirmation containing "cleared" or "fresh"

3. **No memory of pre-reset conversation**
   - Message 1: "I'm working on Project Alpha"
   - Message 2: "It's due next week"
   - Send `/reset`
   - Message 3: "What project am I working on?"
   - Expected: Bot says it doesn't know (no session history)

### Related Requirements
- REQ-COMMAND-001: /reset command
- AC-RESET-001: Session cleared
- AC-RESET-002: Confirmation message

---

## US-MEM-04: Hybrid Memory (Session + Long-term)

**As a** Godfather user  
**I want** the bot to use BOTH my current conversation AND long-term facts  
**So that** responses are informed by complete context

### Acceptance Criteria

**Given** I am the Godfather  
**And** the memory system is enabled  
**And** there are existing long-term memories about "ClientX"  
**When** I have a new conversation:
1. Message 1: "I just met with ClientX today"
2. Message 2: "How should I follow up?"

**Then** the bot should:
- Use conversation history (current session): "I just met with ClientX today"
- Use long-term memory: Facts about ClientX from past sessions
- Combine both sources in its response
- Provide contextual advice based on complete knowledge

### Test Scenarios

1. **Session + Long-term combination**
   - Long-term memory: "ClientX prefers email communication"
   - Current session: "ClientX seemed interested in our new service"
   - Query: "How should I follow up with ClientX?"
   - Expected: Bot suggests email (long-term) about the new service (session)

2. **Recent context overrides old context**
   - Long-term memory: "ClientX budget is ₪50,000"
   - Current session: "ClientX increased budget to ₪75,000"
   - Query: "What's ClientX's budget?"
   - Expected: Bot prioritizes recent info (₪75,000) from session

### Related Requirements
- REQ-INTEGRATION-001: Hybrid memory recall
- AC-INTEGRATION-001: Both memory types used
- AC-INTEGRATION-002: Semantic + temporal relevance

---

## US-MEM-05: Role-based Memory Access (DEFERRED to Feature 006 - RBAC)

**Status**: DEFERRED to Feature 006 (RBAC - Role-Based Access Control)

**Rationale**: Role detection, token limits, and role-based permissions are part of the RBAC feature. Phase 6 focuses on basic memory integration without role complexity.

**Phase 6 Approach**: All users treated equally for memory access in Phase 6. Role-based differentiation (token limits, permission scopes) will be implemented in Feature 006.

---

## US-MEM-06: Feature Flag Controls (TESTED in Phase 4-5)

**Status**: ALREADY TESTED in Phase 4 (Config) and Phase 5 (AIHandler)

**Coverage**:
- Config model tests: 15 passing tests verify feature flag loading
- AIHandler tests: 10 passing tests verify conditional initialization
- Feature flag respected in AIHandler.__init__()

**No additional Phase 6 tests needed**: Feature flag functionality is fully covered by existing unit tests.

---

## US-MEM-07: Automatic Session Expiration and Transfer

**As a** system  
**I want** to automatically transfer expired sessions to long-term memory  
**So that** conversations are preserved without manual intervention

### Acceptance Criteria

**CRITICAL**: Session expiration and transfer happens in TWO ways:
1. **Startup Recovery**: On bot startup (recover from crashes)
2. **Periodic Cleanup**: Every 1 minute while bot is running (background thread)

**When** a session expires (last_active > 24 hours):
- Transfer session to long-term memory (AI summarization → ChromaDB)
- Move session files to `expired/YYYY-MM-DD/` folder
- Remove from active session index
- Log transfer action

**CRITICAL**: Expired sessions are NEVER used for conversation context (conversation history), ONLY for recall context (long-term memory).

### Test Scenarios

#### 7.1 Startup Recovery (Orphaned Sessions)

1. **Recover expired sessions at startup**
   - Create sessions with `last_active` > 24 hours ago
   - Start bot
   - Verify: Sessions transferred to ChromaDB (recall context)
   - Verify: Files moved to `expired/` folder
   - Verify: Expired sessions NOT in conversation history

2. **No orphans - clean startup**
   - No expired sessions exist
   - Start bot
   - Verify: Recovery runs but finds nothing
   - Verify: Log message "No orphaned sessions found"

3. **Recovery continues despite errors**
   - Multiple expired sessions, one corrupted
   - Start bot
   - Verify: Other sessions recovered successfully
   - Verify: Error logged for corrupted session
   - Verify: Bot starts normally

#### 7.2 Periodic Cleanup (Background Thread)

4. **Periodic cleanup transfers expired sessions**
   - Session created > 24 hours ago
   - Bot running (not restarted)
   - Wait for cleanup interval (1 minute)
   - Verify: Session transferred to ChromaDB
   - Verify: Session moved to `expired/` folder
   - Verify: Session removed from active index

5. **Cleanup runs every 1 minute**
   - Mock time.sleep() in cleanup thread
   - Verify: `_cleanup_expired_sessions()` called every 60 seconds
   - Verify: Cleanup interval configurable

6. **Cleanup thread calls AIHandler for transfer**
   - Session expires during bot runtime
   - Cleanup thread detects expiration
   - Verify: `ai_handler.transfer_session_to_long_term_memory()` called
   - Verify: Transfer happens BEFORE moving to expired folder

### Related Requirements
- REQ-RECOVERY-001: Startup recovery
- REQ-CLEANUP-001: Periodic cleanup (NEW)
- REQ-CLEANUP-002: Cleanup interval = 60 seconds (NEW)
- AC-RECOVERY-001: Expired sessions processed
- AC-RECOVERY-002: Graceful error handling
- AC-CLEANUP-001: Background thread active (NEW)
- AC-CLEANUP-002: Transfer before archival (NEW)

---

## US-MEM-08: Normal Message Flow with Memory

**As a** user  
**I want** every message I send to be processed with full memory context  
**So that** the bot always has the information it needs to help me

### Acceptance Criteria

**Given** the memory system is enabled  
**And** I am chatting with DeniDin  
**When** I send a normal text message (not a command)  
**Then** the system should:
1. Determine my user role (godfather or client)
2. Pass `chat_id`, `user_role`, `sender`, `recipient` to AIHandler
3. AIHandler retrieves conversation history from SessionManager
4. AIHandler queries relevant long-term memories from MemoryManager
5. AIHandler generates response using all context
6. AIHandler stores both user message and assistant response in session
7. Bot sends response via WhatsApp

**And** all steps should be logged with message tracking ID

### Test Scenarios

1. **Complete flow with logging**
   - Send message: "Hello, can you help me?"
   - Verify: All logs include `[msg_id=...]` tracking
   - Verify: User role determined and logged
   - Verify: Response generated and sent
   - Verify: Both messages stored in session

2. **Memory included in response**
   - Long-term memory: "User's company is TechCorp"
   - Session history: "I'm planning a meeting"
   - Send: "What should I prepare?"
   - Verify: Response considers both memory sources

### Related Requirements
- REQ-INTEGRATION-002: Message flow
- AC-INTEGRATION-003: Complete pipeline
- AC-INTEGRATION-004: Tracking logs

---

## US-MEM-09: Message Storage (User and AI Messages)

**As a** system  
**I want** to store BOTH user messages and AI responses in session memory  
**So that** complete conversation history is maintained

### Acceptance Criteria

**Given** the memory system is enabled  
**When** a user sends a message and receives an AI response  
**Then** the system should:
- Store user message in session with role="user"
- Store AI response in session with role="assistant"
- Both messages retrievable via get_conversation_history()
- Messages persisted to disk in session directory

### Test Scenarios

1. **User message stored**
   - Send message: "Hello"
   - Verify: Message in session with role="user"
   - Verify: Message content = "Hello"
   - Verify: Message saved to disk

2. **AI response stored**
   - AI responds: "Hi, how can I help?"
   - Verify: Response in session with role="assistant"
   - Verify: Response content matches AI output
   - Verify: Response saved to disk

3. **Both messages in conversation history**
   - Send message, get response
   - Call get_conversation_history()
   - Verify: Returns [{role: "user", content: ...}, {role: "assistant", content: ...}]

### Related Requirements
- REQ-SESSION-002: Message storage
- AC-SESSION-003: User message stored
- AC-SESSION-004: Assistant message stored

---

## US-MEM-10: Comprehensive Error Handling

**As a** system  
**I want** to handle all errors gracefully  
**So that** the bot never crashes and users always get a response

### Acceptance Criteria

**CRITICAL RULES**:
1. System NEVER crashes (exceptions caught and handled)
2. All errors logged with exc_info=True (full traceback)
3. max_retries = 1 (original attempt + 1 retry, NEVER more)
4. Users receive fallback message on all errors

### Test Scenarios

#### 10.1 WhatsApp API Errors

1. **WhatsApp send failure**
   - Mock notification.answer() to raise exception
   - Verify: Error logged with traceback
   - Verify: Bot continues (no crash)
   - Verify: Retry attempted (max 1 retry)

2. **WhatsApp timeout**
   - Mock notification.answer() to timeout
   - Verify: Timeout logged
   - Verify: User receives fallback message
   - Verify: No more than 2 total attempts (original + 1 retry)

#### 10.2 OpenAI API Errors

3. **OpenAI API failure (500 error)**
   - Mock OpenAI to raise APIError
   - Verify: Error logged with exc_info=True
   - Verify: Fallback message sent to user
   - Verify: Bot continues (no crash)
   - Verify: Retry attempted (max 1 retry)

4. **OpenAI timeout**
   - Mock OpenAI to timeout (>30s)
   - Verify: Timeout logged
   - Verify: User notified of delay
   - Verify: No more than 2 attempts total

5. **OpenAI rate limit (429)**
   - Mock OpenAI to return 429
   - Verify: Rate limit logged
   - Verify: Retry with backoff
   - Verify: User receives fallback after max retries

#### 10.3 ChromaDB Errors

6. **ChromaDB unavailable**
   - Mock ChromaDB to raise connection error
   - Verify: Error logged
   - Verify: Bot continues with session history only (graceful degradation)
   - Verify: No crash

7. **ChromaDB embedding failure**
   - Mock embedding creation to fail
   - Verify: Error logged
   - Verify: Recall returns empty list []
   - Verify: Bot responds using session history only

8. **ChromaDB disk full**
   - Mock ChromaDB to raise disk full error
   - Verify: Error logged
   - Verify: Memory recall disabled
   - Verify: Session history still works

#### 10.4 Session Storage Errors

9. **Session save failure (disk full)**
   - Mock file write to fail
   - Verify: Error logged
   - Verify: User receives error message
   - Verify: In-memory session preserved

10. **Session load failure (corrupted file)**
   - Create corrupted session JSON
   - Verify: Error logged
   - Verify: New session created
   - Verify: Bot continues normally

#### 10.5 Max Retries Enforcement

11. **Retry limit respected (OpenAI)**
   - Mock OpenAI to fail 5 times
   - Verify: Only 2 attempts made (original + 1 retry)
   - Verify: Fallback message sent after retry

12. **Retry limit respected (WhatsApp)**
   - Mock WhatsApp to fail 5 times
   - Verify: Only 2 send attempts
   - Verify: Error logged after final failure

### Related Requirements
- NFR-REL-003: Graceful degradation
- REQ-ERROR-001: No crashes
- REQ-ERROR-002: Max retries = 1
- AC-ERROR-001: All errors logged
- AC-ERROR-002: Fallback messages

---

## Test Coverage Summary

| User Story | Unit Tests | Integration Tests | Manual Tests |
|------------|------------|-------------------|--------------|
| US-MEM-01  | SessionManager (15) | Phase 6 Integration | E2E testing |
| US-MEM-02  | MemoryManager (29) | Phase 6 Integration | E2E testing |
| US-MEM-03  | SessionManager clear | Phase 6 Integration | Manual /reset |
| US-MEM-04  | AIHandler (10) | Phase 6 Integration | E2E testing |
| ~~US-MEM-05~~ | ~~DEFERRED to RBAC~~ | ~~Feature 006~~ | ~~N/A~~ |
| ~~US-MEM-06~~ | ~~Phase 4-5 (done)~~ | ~~N/A~~ | ~~N/A~~ |
| US-MEM-07  | AIHandler recovery + SessionManager | Phase 6 Integration (3 tests) | Crash simulation |
| US-MEM-08  | AIHandler + Session | Phase 6 Integration | E2E testing |
| US-MEM-09  | SessionManager | Phase 6 Integration (3 tests) | Message verification |
| US-MEM-10  | Error handlers | Phase 6 Integration (8 tests) | Error injection |

**Total Existing Tests**: 69 (Phase 1-5)  
**Phase 6 Integration Tests**: ~23 new tests (3 startup + 3 periodic + 3 storage + 8 errors + 6 other)  
**Manual Tests**: 4 scenarios

**NEW in Phase 6**: Periodic session expiration cleanup (background thread, 60s interval)

---

## Notes

1. **Phase 1-5 Coverage**: Most functionality already tested in unit tests
2. **Phase 6 Focus**: Integration between denidin.py ↔ AIHandler ↔ Memory components
3. **Deferred to Future**: Manual `/remember` and `/forget` commands
4. **RBAC Deferred**: Token limits and pruning (Feature 006)

---

**Last Updated**: January 19, 2026  
**Status**: Ready for test implementation (T016a)  
**Next Step**: Write integration tests based on these stories
