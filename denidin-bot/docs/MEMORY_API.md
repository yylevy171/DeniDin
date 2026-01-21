# Memory System API Documentation

## Overview

The DeniDin memory system provides two-tier memory management for AI conversations:
- **SessionManager**: Short-term conversation history with token management
- **MemoryManager**: Long-term semantic memory with ChromaDB vector search

---

## SessionManager API

**Location**: `src/memory/session_manager.py`

### Class: `SessionManager`

Manages conversation sessions with automatic token pruning and persistence.

#### Constructor

```python
SessionManager(
    storage_dir: str,
    max_tokens_by_role: Dict[str, int],
    session_timeout_hours: int = 24,
    openai_api_key: Optional[str] = None
)
```

**Parameters:**
- `storage_dir`: Directory path for session JSON files
- `max_tokens_by_role`: Token limits per role (e.g., `{"client": 4000, "godfather": 100000}`)
- `session_timeout_hours`: Hours before session expires (default: 24)
- `openai_api_key`: OpenAI API key for token counting

**Example:**
```python
from src.memory.session_manager import SessionManager

session_mgr = SessionManager(
    storage_dir="data/sessions",
    max_tokens_by_role={"client": 4000, "godfather": 100000},
    session_timeout_hours=24,
    openai_api_key="sk-..."
)
```

#### Methods

##### `add_message()`

Add a message to the session history.

```python
def add_message(
    whatsapp_chat: str,
    role: str,
    content: str,
    user_role: str = "client",
    sender: str = "",
    recipient: str = ""
) -> str
```

**Parameters:**
- `whatsapp_chat`: WhatsApp chat ID (e.g., "1234567890@c.us")
- `role`: Message role - "user" or "assistant"
- `content`: Message text content
- `user_role`: User's role for token limits - "client" or "godfather"
- `sender`: WhatsApp sender ID or "assistant"
- `recipient`: WhatsApp recipient ID

**Returns:** Message ID (UUID string)

**Raises:** `ValueError` if role is invalid

**Example:**
```python
# User message
msg_id = session_mgr.add_message(
    whatsapp_chat="1234567890@c.us",
    role="user",
    content="What's the weather?",
    user_role="client",
    sender="1234567890@c.us",
    recipient="bot@c.us"
)

# Assistant response
session_mgr.add_message(
    whatsapp_chat="1234567890@c.us",
    role="assistant",
    content="It's sunny today!",
    user_role="client",
    sender="assistant",
    recipient="1234567890@c.us"
)
```

##### `get_conversation_history()`

Retrieve conversation history formatted for OpenAI API.

```python
def get_conversation_history(
    whatsapp_chat: str,
    user_role: str = "client"
) -> List[Dict[str, str]]
```

**Parameters:**
- `whatsapp_chat`: WhatsApp chat ID
- `user_role`: User's role for token limit enforcement

**Returns:** List of message dicts with keys: `role`, `content`
- Format: `[{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]`
- Ordered chronologically
- Pruned to fit within role's token limit

**Example:**
```python
history = session_mgr.get_conversation_history(
    whatsapp_chat="1234567890@c.us",
    user_role="client"
)
# Returns: [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello!"}]
```

##### `clear_session()`

Clear all messages from a session.

```python
def clear_session(whatsapp_chat: str) -> None
```

**Parameters:**
- `whatsapp_chat`: WhatsApp chat ID

**Example:**
```python
session_mgr.clear_session("1234567890@c.us")
```

##### `is_session_expired()`

Check if a session has expired based on timeout.

```python
def is_session_expired(whatsapp_chat: str) -> bool
```

**Parameters:**
- `whatsapp_chat`: WhatsApp chat ID

**Returns:** `True` if session expired, `False` otherwise

**Example:**
```python
if session_mgr.is_session_expired("1234567890@c.us"):
    print("Session expired, transferring to long-term memory")
```

##### `get_all_sessions()`

Retrieve all active session IDs.

```python
def get_all_sessions() -> List[str]
```

**Returns:** List of session IDs (UUIDs)

**Example:**
```python
sessions = session_mgr.get_all_sessions()
# Returns: ["a162e1eb-d585-4812-8811-28cfddc5806e", ...]
```

##### `cleanup_expired_sessions()`

Move expired sessions to expired directory.

```python
def cleanup_expired_sessions() -> int
```

**Returns:** Number of sessions cleaned up

**Example:**
```python
count = session_mgr.cleanup_expired_sessions()
print(f"Cleaned up {count} expired sessions")
```

---

## MemoryManager API

**Location**: `src/memory/memory_manager.py`

### Class: `MemoryManager`

Manages long-term semantic memory with ChromaDB vector search.

#### Constructor

```python
MemoryManager(
    storage_dir: str,
    collection_name: str,
    embedding_model: str,
    openai_api_key: str,
    top_k_results: int = 5,
    min_similarity: float = 0.7
)
```

**Parameters:**
- `storage_dir`: Directory for ChromaDB storage
- `collection_name`: ChromaDB collection name
- `embedding_model`: OpenAI embedding model (e.g., "text-embedding-3-small")
- `openai_api_key`: OpenAI API key
- `top_k_results`: Maximum memories to return (default: 5)
- `min_similarity`: Minimum similarity score (default: 0.7)

**Example:**
```python
from src.memory.memory_manager import MemoryManager

memory_mgr = MemoryManager(
    storage_dir="data/memory",
    collection_name="godfather_memory",
    embedding_model="text-embedding-3-small",
    openai_api_key="sk-...",
    top_k_results=5,
    min_similarity=0.7
)
```

#### Methods

##### `store()`

Store a memory with embeddings.

```python
def store(
    content: str,
    metadata: Optional[Dict[str, Any]] = None
) -> str
```

**Parameters:**
- `content`: Text content to store
- `metadata`: Optional metadata dict (e.g., `{"source": "conversation", "timestamp": "..."}`)

**Returns:** Memory ID (UUID string)

**Example:**
```python
memory_id = memory_mgr.store(
    content="User prefers Python over JavaScript",
    metadata={
        "source": "conversation",
        "timestamp": "2026-01-21T10:30:00Z",
        "topic": "preferences"
    }
)
```

##### `recall()`

Search for relevant memories using semantic similarity.

```python
def recall(query: str) -> List[Dict[str, Any]]
```

**Parameters:**
- `query`: Search query text

**Returns:** List of memory dicts with keys:
- `id`: Memory ID (string)
- `content`: Memory text (string)
- `metadata`: Metadata dict
- `similarity`: Similarity score (float 0-1)

**Sorted by:** Similarity score (descending)

**Example:**
```python
memories = memory_mgr.recall("What programming language does the user like?")
# Returns:
# [
#   {
#     "id": "abc123...",
#     "content": "User prefers Python over JavaScript",
#     "metadata": {"source": "conversation", "topic": "preferences"},
#     "similarity": 0.89
#   }
# ]
```

##### `delete()`

Delete a specific memory.

```python
def delete(memory_id: str) -> bool
```

**Parameters:**
- `memory_id`: ID of memory to delete

**Returns:** `True` if deleted, `False` if not found

**Example:**
```python
success = memory_mgr.delete("abc123...")
```

##### `clear_all()`

Delete all memories (use with caution).

```python
def clear_all() -> int
```

**Returns:** Number of memories deleted

**Example:**
```python
count = memory_mgr.clear_all()
print(f"Deleted {count} memories")
```

---

## Integration Example

### Complete Workflow

```python
from src.memory.session_manager import SessionManager
from src.memory.memory_manager import MemoryManager

# Initialize managers
session_mgr = SessionManager(
    storage_dir="data/sessions",
    max_tokens_by_role={"client": 4000, "godfather": 100000},
    openai_api_key="sk-..."
)

memory_mgr = MemoryManager(
    storage_dir="data/memory",
    collection_name="godfather_memory",
    embedding_model="text-embedding-3-small",
    openai_api_key="sk-..."
)

# 1. Receive user message
whatsapp_chat = "1234567890@c.us"
user_message = "What did we discuss about Python last week?"

# 2. Add user message to session
session_mgr.add_message(
    whatsapp_chat=whatsapp_chat,
    role="user",
    content=user_message,
    user_role="client",
    sender=whatsapp_chat,
    recipient="bot@c.us"
)

# 3. Get conversation history
history = session_mgr.get_conversation_history(
    whatsapp_chat=whatsapp_chat,
    user_role="client"
)

# 4. Recall relevant memories
memories = memory_mgr.recall(user_message)

# 5. Build AI request
messages = []

# Add recalled memories to system message
if memories:
    memory_text = "\n".join([f"- {m['content']}" for m in memories])
    messages.append({
        "role": "system",
        "content": f"Relevant memories:\n{memory_text}"
    })

# Add conversation history
messages.extend(history)

# 6. Call OpenAI API (not shown)
# ai_response = openai.chat.completions.create(...)

# 7. Add AI response to session
ai_response_text = "We discussed Python's advantages for data science..."
session_mgr.add_message(
    whatsapp_chat=whatsapp_chat,
    role="assistant",
    content=ai_response_text,
    user_role="client",
    sender="assistant",
    recipient=whatsapp_chat
)

# 8. Check for session expiration
if session_mgr.is_session_expired(whatsapp_chat):
    # Summarize and transfer to long-term memory
    history = session_mgr.get_conversation_history(whatsapp_chat, "client")
    summary = "... generate summary ..."
    memory_mgr.store(
        content=summary,
        metadata={"source": "session_transfer", "session_id": "..."}
    )
    session_mgr.clear_session(whatsapp_chat)
```

---

## Error Handling

### SessionManager Errors

**ValueError**: Invalid role parameter
```python
try:
    session_mgr.add_message(
        whatsapp_chat="...",
        role="invalid",  # Must be "user" or "assistant"
        content="..."
    )
except ValueError as e:
    print(f"Invalid role: {e}")
```

**FileNotFoundError**: Storage directory doesn't exist
- Solution: Create directory or let SessionManager create it automatically

### MemoryManager Errors

**ConnectionError**: ChromaDB unavailable
- Solution: Check storage directory permissions
- Fallback: Returns empty list from `recall()`

**OpenAI API Errors**: Embedding generation fails
- Solution: Check API key and quota
- Fallback: Logs error, returns empty list

---

## Performance Considerations

### Token Counting
- Uses tiktoken library for accurate token counting
- Cached per model for performance
- ~1ms per message

### ChromaDB Queries
- Typical query: 50-100ms
- Scales well up to millions of documents
- HNSW index for fast approximate nearest neighbor search

### Memory Usage
- Session data: ~1KB per 10 messages
- ChromaDB: ~500 bytes per embedded document
- Embeddings cached in memory

### Best Practices

1. **Session Management**
   - Clean up expired sessions regularly
   - Use appropriate token limits per role
   - Monitor session count (use `get_all_sessions()`)

2. **Memory Storage**
   - Store summaries, not raw conversations
   - Use meaningful metadata for filtering
   - Regularly review and prune irrelevant memories

3. **Performance**
   - Enable ChromaDB persistence
   - Use batch operations when possible
   - Monitor OpenAI API quota

---

## Testing

Run memory system tests:

```bash
# Unit tests
python3 -m pytest tests/unit/test_memory_unit.py -v
python3 -m pytest tests/unit/test_session_unit.py -v

# Integration tests
python3 -m pytest tests/integration/test_memory_integration.py -v

# All memory tests
python3 -m pytest tests/ -k memory -v
```

---

## See Also

- [User Guide](../README.md#memory-system-usage) - End-user memory system documentation
- [Specification](../../specs/002-007-memory-system/spec.md) - Complete technical specification
- [Implementation Plan](../../specs/002-007-memory-system/plan.md) - Development roadmap
