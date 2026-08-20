# Feature Spec: Chat Session Management

**Feature ID**: 002-chat-session-management  
**Priority**: P0 (Critical)  
**Status**: Planning  
**Created**: January 17, 2026

## Problem Statement

Currently, DeniDin treats each WhatsApp message independently with no memory of previous interactions. Each message starts fresh, making it impossible to have contextual conversations like you would in ChatGPT's web interface.

**Current Behavior:**
- User: "What's the weather?"
- Bot: "I can help with that..."
- User: "What about tomorrow?" ❌ Bot has no context about "weather"

**Desired Behavior:**
- User: "What's the weather?"
- Bot: "I can help with that..."
- User: "What about tomorrow?" ✅ Bot remembers we're talking about weather

## Solution Overview

Implement conversation session management that:
1. Tracks conversation history per user/chat
2. Maintains context across messages
3. Stores message history (user + assistant messages)
4. Sends conversation history to OpenAI API
5. Manages session lifecycle (creation, continuation, expiration)

## Technical Design

### 1. Data Model

```python
# src/models/session.py
class ChatSession:
    session_id: str              # Unique session identifier
    chat_id: str                 # WhatsApp chat ID (user or group)
    messages: List[ChatMessage]  # Conversation history
    created_at: datetime
    last_activity: datetime
    metadata: dict               # User preferences, context, etc.

class ChatMessage:
    role: str                    # "user" or "assistant"
    content: str                 # Message text
    timestamp: datetime
    tokens: int                  # Token count for this message
```

### 2. Storage Options

**Option A: In-Memory (Simple, MVP)**
- Store sessions in dictionary: `{chat_id: ChatSession}`
- Pros: Simple, fast, no dependencies
- Cons: Lost on restart, memory limits
- **Recommended for Phase 1**

**Option B: File-Based (Persistent)**
- Store sessions in JSON files in `state/` directory
- Pros: Persists across restarts, simple
- Cons: Slower, file I/O overhead

**Option C: Database (Production)**
- Redis for fast access + TTL expiration
- PostgreSQL for long-term storage
- Pros: Scalable, reliable, feature-rich
- Cons: Additional infrastructure
- **Recommended for Phase 2**

### 3. Session Management

```python
# src/utils/session_manager.py
class SessionManager:
    def get_or_create_session(chat_id: str) -> ChatSession
    def add_message(session_id: str, role: str, content: str)
    def get_conversation_history(session_id: str, max_messages: int) -> List[dict]
    def clear_session(chat_id: str)
    def expire_old_sessions(max_age_hours: int)
```

### 4. Token Management

**Challenge**: OpenAI has token limits (e.g., 128K for gpt-4o-mini)

**Strategy**:
- Track cumulative tokens in session
- Keep last N messages (e.g., 20 messages)
- OR keep messages within token budget (e.g., 4000 tokens)
- Implement conversation summarization when limit reached
- Allow manual session reset via command

### 5. Integration Points

**Modified Flow**:
1. Receive WhatsApp message
2. **NEW**: Get or create session for chat_id
3. **NEW**: Add user message to session history
4. **NEW**: Get conversation history (last N messages)
5. Call OpenAI API with full conversation history
6. **NEW**: Add assistant response to session history
7. Send response to WhatsApp

**Modified Files**:
- `denidin.py` - Initialize SessionManager
- `src/handlers/ai_handler.py` - Use conversation history in API calls
- `src/models/` - Add session.py
- `src/utils/` - Add session_manager.py

## Configuration

```json
{
  "session": {
    "max_messages": 20,
    "max_tokens": 4000,
    "expiry_hours": 24,
    "storage": "memory"
  }
}
```

## User Commands

- `/new` or `/reset` - Start new conversation (clear history)
- `/history` - Show current session info (message count, tokens)
- `/context on|off` - Enable/disable context for this chat

## Implementation Plan

### Phase 1: In-Memory MVP
- [ ] Create ChatSession and ChatMessage models
- [ ] Implement in-memory SessionManager
- [ ] Modify AIHandler to use conversation history
- [ ] Add session expiration (24 hours)
- [ ] Add `/reset` command
- [ ] Write unit tests for SessionManager
- [ ] Write integration tests for multi-message conversations

### Phase 2: Persistence
- [ ] Add file-based session storage
- [ ] Implement session save/load on startup/shutdown
- [ ] Add session export/import functionality

### Phase 3: Advanced Features
- [ ] Token-based history management
- [ ] Conversation summarization when limit reached
- [ ] Per-user session preferences
- [ ] Session analytics

## Testing Strategy

### Unit Tests
- Session creation and retrieval
- Message addition and history retrieval
- Token counting and limits
- Session expiration logic

### Integration Tests
- Multi-turn conversation flow
- Session persistence across messages
- Context maintained correctly
- Token limit handling

### Manual Testing Scenarios
1. Simple back-and-forth conversation
2. Long conversation exceeding message limit
3. Multiple concurrent conversations (different users)
4. Session expiration after 24 hours
5. Session reset command

## Success Metrics

- ✅ Bot remembers context across messages
- ✅ Users can have natural multi-turn conversations
- ✅ No token limit errors
- ✅ Sessions persist appropriately
- ✅ 90%+ test coverage for session management

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Memory exhaustion with many sessions | High | Implement session expiration and limits |
| Token limit exceeded | Medium | Track tokens, implement truncation |
| Lost sessions on crash | Low | Add file persistence in Phase 2 |
| Slow response with large history | Low | Optimize history retrieval, limit messages |

## Future Enhancements

- Different conversation modes (chat, Q&A, research)
- Conversation branching (alternative responses)
- Session sharing between users
- Conversation export (PDF, text)

---

**Next Steps**: 
1. Review and approve this spec
2. Create feature branch `002-chat-session-management`
3. Implement Phase 1 (In-Memory MVP)
4. Test thoroughly
5. Deploy and monitor
