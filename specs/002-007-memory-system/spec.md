# Feature Spec: Memory System (Combined 002 + 007)

**Feature ID**: 002+007-memory-system  
**Priority**: P0 (Critical)  
**Status**: Planning  
**Created**: January 17, 2026

## Overview

This feature combines session management (002) and persistent memory (007) into a unified memory system that enables DeniDin to remember conversations and maintain long-term context about the Godfather's business, clients, and preferences.

**Key Insight**: Session memory (short-term) and persistent memory (long-term) are two layers of the same system - they work together to provide contextual, intelligent responses.

## Problem Statement

Currently, DeniDin has **no memory**:
- Cannot remember what was discussed 2 messages ago
- Every conversation starts from scratch
- No knowledge of clients, projects, or preferences
- Cannot provide context-aware responses
- Value proposition is severely limited

**Without memory, DeniDin is just an API wrapper, not an intelligent assistant.**

## MVP Scope (Phase 1)

**Deployment Strategy**: Feature flag controlled (`enable_memory_system`) for safe incremental rollout.

### Must-Have Features

1. **Session Management (Short-term Memory)**
   - Remember conversation history within current chat
   - Role-based token limits: 4,000 for clients, 100,000 for godfather
   - Automatic pruning of old messages when approaching limits
   - Storage: `data/sessions/` (JSON files)
   - Future support for image references

2. **ChromaDB Long-term Memory (Godfather Global)**
   - Persistent storage across all chats and sessions
   - Semantic search using embeddings
   - AI automatically queries relevant memories when responding
   - Storage: `data/memory/` (ChromaDB)
   - Indefinite retention (manual deletion only via `/forget`)

3. **`/remember` Command**
   - Explicit way to store important facts
   - Example: `/remember TestCorp owes me ₪5000 from invoice INV-001`

4. **AI Automatic Recall**
   - Before responding, AI queries ChromaDB for relevant context
   - Seamlessly integrates memory into responses
   - No manual memory management needed

5. **Feature Flag Control**
   - All memory features behind `enable_memory_system` flag
   - Default: disabled (false) for safe deployment
   - Can enable incrementally per environment/user

### Deferred to Phase 2

- Per-chat memory (separate from Godfather global)
- Document ingestion (PDF/DOCX text extraction)
- Advanced memory commands (`/memories`, `/forget`, `/search`)
- Memory categories/tags
- Automatic memory extraction from conversations

## Technical Design

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Message Flow                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  1. Session Manager: Load conversation history               │
│     - Get last N messages from session storage               │
│     - Format for AI context window                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  2. Memory Manager: Query relevant long-term memories        │
│     - Generate embedding for user message                    │
│     - Search ChromaDB for similar memories                   │
│     - Return top K relevant memories                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  3. AI Handler: Generate response with full context          │
│     - System prompt + memories + conversation history        │
│     - User message                                           │
│     - Generate response                                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  4. Session Manager: Store message in history                │
│     - Add user message + AI response to session              │
│     - Prune if exceeding token limit                         │
└─────────────────────────────────────────────────────────────┘
```

### 1. Session Manager (Short-term Memory)

```python
# src/utils/session_manager.py

from typing import List, Dict, Optional
from datetime import datetime, timedelta
import json
import os

class Message:
    """Single message in conversation."""
    role: str           # "user" or "assistant"
    content: str
    timestamp: datetime
    tokens: int         # Estimated token count
    image_path: Optional[str] = None  # Path to image file (future use)
    
class Session:
    """Conversation session for a chat."""
    chat_id: str
    messages: List[Message]
    created_at: datetime
    last_active: datetime
    total_tokens: int
    
class SessionManager:
    """Manage conversation sessions with role-based token limits."""
    
    def __init__(
        self,
        storage_dir: str = "data/sessions",
        max_tokens_by_role: Dict[str, int] = None,  # {"client": 4000, "godfather": 100000}
        session_timeout_hours: int = 24
    ):
        self.storage_dir = storage_dir
        self.max_tokens_by_role = max_tokens_by_role or {"client": 4000, "godfather": 100000}
        self.session_timeout = timedelta(hours=session_timeout_hours)
        self.sessions: Dict[str, Session] = {}
        
        os.makedirs(storage_dir, exist_ok=True)
        os.makedirs(os.path.join(storage_dir, "images"), exist_ok=True)  # Future use
        self._load_sessions()
    
    def get_token_limit(self, user_role: str = "client") -> int:
        """Get token limit for user role."""
        return self.max_tokens_by_role.get(user_role, 4000)
    
    def get_session(self, chat_id: str) -> Session:
        """Get or create session for chat."""
        
        # Check if session exists and is valid
        if chat_id in self.sessions:
            session = self.sessions[chat_id]
            
            # Check if session expired
            if datetime.now() - session.last_active > self.session_timeout:
                logger.info(f"Session {chat_id} expired, creating new")
                session = self._create_session(chat_id)
            
            session.last_active = datetime.now()
            return session
        
        # Create new session
        return self._create_session(chat_id)
    
    def add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        user_role: str = "client",
        image_path: Optional[str] = None
    ):
        """Add message to session, managing role-based token limits."""
        
        session = self.get_session(chat_id)
        token_limit = self.get_token_limit(user_role)
        
        # Estimate tokens (rough: 1 token ≈ 4 chars)
        tokens = len(content) // 4
        
        message = Message(
            role=role,
            content=content,
            timestamp=datetime.now(),
            tokens=tokens,
            image_path=image_path
        )
        
        session.messages.append(message)
        session.total_tokens += tokens
        session.last_active = datetime.now()
        
        # Prune if exceeding limit
        self._prune_session(session, token_limit)
        
        # Save to disk
        self._save_session(session)
    
    def get_conversation_history(
        self,
        chat_id: str,
        user_role: str = "client",
        max_messages: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """Get conversation history formatted for AI (respects role-based token limit)."""
        
        session = self.get_session(chat_id)
        messages = session.messages
        
        if max_messages:
            messages = messages[-max_messages:]
        
        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
    
    def clear_session(self, chat_id: str):
        """Clear session (for /reset command)."""
        
        if chat_id in self.sessions:
            session = self._create_session(chat_id)
            self._save_session(session)
            logger.info(f"Session {chat_id} cleared")
    
    def _prune_session(self, session: Session, token_limit: int):
        """Remove old messages to stay under role-based token limit."""
        
        while session.total_tokens > token_limit and len(session.messages) > 2:
            # Remove oldest message (keep at least last 2)
            removed = session.messages.pop(0)
            session.total_tokens -= removed.tokens
            
            logger.debug(
                f"Pruned message from {session.chat_id}, "
                f"tokens: {session.total_tokens}/{token_limit}"
            )
    
    def _create_session(self, chat_id: str) -> Session:
        """Create new session."""
        session = Session(
            chat_id=chat_id,
            messages=[],
            created_at=datetime.now(),
            last_active=datetime.now(),
            total_tokens=0
        )
        self.sessions[chat_id] = session
        return session
    
    def _save_session(self, session: Session):
        """Save session to disk."""
        filepath = os.path.join(self.storage_dir, f"{session.chat_id}.json")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                'chat_id': session.chat_id,
                'messages': [
                    {
                        'role': msg.role,
                        'content': msg.content,
                        'timestamp': msg.timestamp.isoformat(),
                        'tokens': msg.tokens
                    }
                    for msg in session.messages
                ],
                'created_at': session.created_at.isoformat(),
                'last_active': session.last_active.isoformat(),
                'total_tokens': session.total_tokens
            }, f, ensure_ascii=False, indent=2)
    
    def _load_sessions(self):
        """Load all sessions from disk."""
        
        if not os.path.exists(self.storage_dir):
            return
        
        for filename in os.listdir(self.storage_dir):
            if not filename.endswith('.json'):
                continue
            
            filepath = os.path.join(self.storage_dir, filename)
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                session = Session(
                    chat_id=data['chat_id'],
                    messages=[
                        Message(
                            role=msg['role'],
                            content=msg['content'],
                            timestamp=datetime.fromisoformat(msg['timestamp']),
                            tokens=msg['tokens']
                        )
                        for msg in data['messages']
                    ],
                    created_at=datetime.fromisoformat(data['created_at']),
                    last_active=datetime.fromisoformat(data['last_active']),
                    total_tokens=data['total_tokens']
                )
                
                self.sessions[session.chat_id] = session
                
            except Exception as e:
                logger.error(f"Failed to load session {filename}: {e}")
```

### 2. Memory Manager (Long-term Memory)

```python
# src/utils/memory_manager.py

import chromadb
from chromadb.config import Settings
from openai import OpenAI
from typing import List, Dict, Optional
from datetime import datetime
import uuid

class Memory:
    """Single memory entry."""
    memory_id: str
    content: str
    metadata: Dict
    created_at: datetime

class MemoryManager:
    """Manage long-term memories with semantic search."""
    
    def __init__(
        self,
        storage_dir: str = "data/memory",
        collection_name: str = "godfather_memory",
        embedding_model: str = "text-embedding-3-small"
    ):
        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(
            path=storage_dir,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        # OpenAI for embeddings
        self.openai = OpenAI()
        self.embedding_model = embedding_model
    
    def remember(
        self,
        content: str,
        metadata: Optional[Dict] = None
    ) -> str:
        """Store a memory with semantic embedding."""
        
        # Generate unique ID
        memory_id = str(uuid.uuid4())
        
        # Create embedding
        embedding = self._create_embedding(content)
        
        # Default metadata
        if metadata is None:
            metadata = {}
        
        metadata.update({
            'created_at': datetime.now().isoformat(),
            'type': metadata.get('type', 'fact')
        })
        
        # Store in ChromaDB
        self.collection.add(
            ids=[memory_id],
            embeddings=[embedding],
            documents=[content],
            metadatas=[metadata]
        )
        
        logger.info(f"Stored memory: {memory_id}")
        return memory_id
    
    def recall(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.7
    ) -> List[Dict]:
        """Recall relevant memories using semantic search."""
        
        # Generate query embedding
        query_embedding = self._create_embedding(query)
        
        # Search ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        # Format results
        memories = []
        
        if results['ids'] and results['ids'][0]:
            for i, memory_id in enumerate(results['ids'][0]):
                distance = results['distances'][0][i]
                similarity = 1 - distance  # Cosine distance to similarity
                
                if similarity >= min_similarity:
                    memories.append({
                        'id': memory_id,
                        'content': results['documents'][0][i],
                        'metadata': results['metadatas'][0][i],
                        'similarity': similarity
                    })
        
        logger.debug(f"Recalled {len(memories)} memories for query: {query[:50]}")
        return memories
    
    def forget(self, memory_id: str):
        """Delete a memory."""
        self.collection.delete(ids=[memory_id])
        logger.info(f"Deleted memory: {memory_id}")
    
    def list_memories(
        self,
        limit: int = 100,
        memory_type: Optional[str] = None
    ) -> List[Dict]:
        """List all memories (for debugging/management)."""
        
        # Get all memories
        results = self.collection.get(
            limit=limit,
            include=['documents', 'metadatas']
        )
        
        memories = []
        for i, memory_id in enumerate(results['ids']):
            metadata = results['metadatas'][i]
            
            # Filter by type if specified
            if memory_type and metadata.get('type') != memory_type:
                continue
            
            memories.append({
                'id': memory_id,
                'content': results['documents'][i],
                'metadata': metadata
            })
        
        return memories
    
    def _create_embedding(self, text: str) -> List[float]:
        """Create embedding using OpenAI."""
        
        response = self.openai.embeddings.create(
            model=self.embedding_model,
            input=text
        )
        
        return response.data[0].embedding
```

### 3. Integration with AI Handler

```python
# src/handlers/ai_handler.py (updated)

class AIHandler:
    def __init__(self, config: Config):
        self.config = config
        self.client = OpenAI(api_key=config.openai.api_key)
        
        # Initialize memory components
        self.session_manager = SessionManager()
        self.memory_manager = MemoryManager()
    
    def create_request(
        self,
        user_message: str,
        chat_id: str,
        user_id: str
    ) -> str:
        """Create AI request with full memory context."""
        
        # 1. Get conversation history (short-term memory)
        conversation_history = self.session_manager.get_conversation_history(
            chat_id=chat_id,
            max_messages=20  # Last 20 messages
        )
        
        # 2. Query long-term memories
        relevant_memories = self.memory_manager.recall(
            query=user_message,
            top_k=5
        )
        
        # 3. Build system prompt with memories
        system_prompt = self._build_system_prompt(relevant_memories)
        
        # 4. Build messages array
        messages = [
            {"role": "system", "content": system_prompt},
            *conversation_history,
            {"role": "user", "content": user_message}
        ]
        
        # 5. Call OpenAI
        response = self.client.chat.completions.create(
            model=self.config.openai.model,
            messages=messages,
            temperature=0.7
        )
        
        assistant_message = response.choices[0].message.content
        
        # 6. Store in session history
        self.session_manager.add_message(chat_id, "user", user_message)
        self.session_manager.add_message(chat_id, "assistant", assistant_message)
        
        return assistant_message
    
    def _build_system_prompt(self, memories: List[Dict]) -> str:
        """Build system prompt with memory context."""
        
        base_prompt = """You are DeniDin, an AI assistant for the Godfather.
You help manage business operations, client relationships, and provide intelligent assistance.

You have access to long-term memory about the Godfather's business."""
        
        if memories:
            memory_context = "\n\n**Relevant Context from Memory:**\n"
            for mem in memories:
                memory_context += f"- {mem['content']}\n"
            
            base_prompt += memory_context
        
        return base_prompt
    
    def handle_remember_command(
        self,
        content: str,
        chat_id: str
    ) -> str:
        """Handle /remember command."""
        
        # Store in long-term memory
        memory_id = self.memory_manager.remember(
            content=content,
            metadata={
                'type': 'explicit',
                'chat_id': chat_id,
                'source': 'command'
            }
        )
        
        return f"✅ Remembered: {content}"
```

### 4. Message Handler Integration

```python
# src/handlers/message_handler.py (updated)

def handle_message(self, message: Message):
    """Handle incoming message with memory support."""
    
    chat_id = message.chat_id
    user_id = message.sender_id
    text = message.text
    
    # Check for commands
    if text.startswith('/remember '):
        content = text[10:].strip()  # Remove '/remember '
        response = self.ai_handler.handle_remember_command(content, chat_id)
        self.whatsapp_handler.send_message(chat_id, response)
        return
    
    if text == '/reset':
        self.ai_handler.session_manager.clear_session(chat_id)
        self.whatsapp_handler.send_message(
            chat_id,
            "🔄 Conversation history cleared. Starting fresh!"
        )
        return
    
    # Normal message - process with full memory context
    response = self.ai_handler.create_request(
        user_message=text,
        chat_id=chat_id,
        user_id=user_id
    )
    
    self.whatsapp_handler.send_message(chat_id, response)
```

## Configuration

```json
{
  "memory": {
    "session": {
      "storage_dir": "state/sessions",
      "max_tokens": 4000,
      "session_timeout_hours": 24
    },
    "longterm": {
      "storage_dir": "state/memory",
      "collection_name": "godfather_memory",
      "embedding_model": "text-embedding-3-small",
      "top_k_results": 5,
      "min_similarity": 0.7
    }
  }
}
```

## Dependencies

```python
# requirements.txt additions
chromadb>=0.4.22           # Vector database
openai>=1.12.0             # Embeddings API
```

## Example Usage

### Storing Memories

```
Godfather: "/remember TestCorp is a software company based in Tel Aviv, CEO is John Smith"
Bot: "✅ Remembered: TestCorp is a software company based in Tel Aviv, CEO is John Smith"

Godfather: "/remember TestCorp owes me ₪5,000 from invoice INV-001 dated January 10, 2026"
Bot: "✅ Remembered: TestCorp owes me ₪5,000 from invoice INV-001 dated January 10, 2026"
```

### Recalling Memories

```
[Later, in different chat or after restart]

Godfather: "What's the status with TestCorp?"
Bot: "TestCorp is a software company in Tel Aviv with CEO John Smith. 
      They currently have an outstanding invoice INV-001 for ₪5,000 from January 10th. 
      Would you like me to help you follow up with them?"
```

### Conversation History

```
Godfather: "I need to create an invoice for ABC Corp"
Bot: "I can help with that. What's the amount and services provided?"

Godfather: "₪10,000 for consulting services"
Bot: "Got it. For ABC Corp, ₪10,000 for consulting services. 
      What's the invoice date and payment terms?"

[Bot remembers the previous messages in this conversation]
```

## Success Metrics

- ✅ Session history persists across bot restarts
- ✅ Memories are recalled with >80% relevance
- ✅ AI responses include relevant context from memory
- ✅ `/remember` command stores facts successfully
- ✅ Token management keeps sessions under limits
- ✅ ChromaDB queries complete in <100ms
- ✅ 90%+ test coverage

## Testing Strategy

### Unit Tests
- Session manager: add/prune/load/save
- Memory manager: remember/recall/forget
- Embedding generation
- Token counting accuracy

### Integration Tests
- End-to-end message flow with memory
- Memory recall in AI responses
- Session expiration
- `/remember` and `/reset` commands

### Manual Tests
1. Store 5 different facts via `/remember`
2. Ask questions that require recalling those facts
3. Have multi-turn conversation, verify history works
4. Restart bot, verify memories persist
5. Test `/reset` clears session but keeps long-term memory

## Phase 2 Enhancements

- Per-chat memory (separate from Godfather global)
- Document ingestion (PDF/DOCX → extract text → remember)
- Auto-extraction: AI automatically identifies important facts from conversations
- Memory management: `/memories` (list), `/forget <id>` (delete), `/search <query>`
- Memory categories/tags for better organization
- Memory consolidation (merge similar memories)
- Export/import memory for backup

## Cost Estimate

**Embeddings**: `text-embedding-3-small`
- $0.020 per 1M tokens
- Average fact: ~50 tokens
- 1,000 memories: ~50K tokens = $0.001
- Queries: ~20 tokens each
- 10K queries: 200K tokens = $0.004

**Total monthly cost (estimated)**: ~$0.50 for moderate usage

## Dependencies on Other Features

- **Enhanced by**: Feature 006 (RBAC) - Per-user memory isolation
- **Enhanced by**: Feature 003 (Media Processing) - Document ingestion in Phase 2
- **Required for**: Feature 008 (Scheduled Chats) - Context-aware proactive messages
- **Required for**: Feature 009 (Workflows) - Memory-driven workflow decisions

---

**Next Steps**:
1. Review and approve MVP scope
2. Create feature branch `002-007-memory-system`
3. Implement SessionManager
4. Implement MemoryManager
5. Integrate with AI Handler
6. Write tests
7. Deploy and validate with real usage
