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
   
   **Technology Choice: ChromaDB**
   - **Decision Date**: January 18, 2026
   - **Rationale**: 
     - Zero infrastructure setup (`pip install` and done)
     - Free forever (file-based, no cloud costs)
     - Semantic search essential for intelligent context retrieval
     - Scales to 1K-10K memories (our Phase 1-2 needs)
     - Python-native with simple API
     - Easy migration path: abstraction layer allows swapping to Pinecone/Qdrant later if needed
   - **Alternatives Considered**: Pinecone ($$), Qdrant (complex setup), pgvector (no semantic search optimization), JSON files (no semantic search)
   - **Migration Path**: If exceeding 10K memories or need distributed deployment, evaluate Qdrant Cloud or Pinecone

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
    """Single message in conversation - stored as separate file/object."""
    message_id: str     # Unique message ID (UUID)
    chat_id: str        # Parent session ID (UUID) ✨ NEW
    order_num: int      # Sequential number within chat (1, 2, 3...)
    role: str           # "user" (from WhatsApp) or "assistant" (from OpenAI)
    content: str        # Message text
    sender: str         # WhatsApp sender ID (e.g., "1234567890@c.us") or "assistant"
    recipient: str      # WhatsApp recipient ID (bot's ID) or WhatsApp phone number
    timestamp: datetime # When message was created (UTC)
    received_at: datetime # When message was received by recipient (UTC)
    was_received: bool  # Whether recipient acknowledged receipt
    tokens: int         # Estimated token count
    image_path: Optional[str] = None  # Path to image file (future use)
    
class Session:
    """Conversation session for a chat - messages stored separately."""
    session_id: str             # Unique session ID (UUID) - primary identifier
    whatsapp_chat: str          # WhatsApp chat ID (e.g., "1234567890@c.us") - matches sender/recipient in messages
    client_name: Optional[str]  # Client's display name from WhatsApp (for clients)
    message_ids: List[str]      # List of message IDs (pointers to message files)
    message_counter: int        # Counter for order_num (auto-increment)
    created_at: datetime        # UTC timestamp
    last_active: datetime       # UTC timestamp
    total_tokens: int           # Sum of all message tokens
    
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
        self.sessions: Dict[str, Session] = {}  # Key: session_id (UUID)
        self.chat_to_session: Dict[str, str] = {}  # Map: whatsapp_chat -> session_id
        
        os.makedirs(storage_dir, exist_ok=True)
        os.makedirs(os.path.join(storage_dir, "messages"), exist_ok=True)  # Individual message files
        os.makedirs(os.path.join(storage_dir, "images"), exist_ok=True)  # Future use
        self._load_sessions()
    
    def get_token_limit(self, user_role: str = "client") -> int:
        """Get token limit for user role."""
        return self.max_tokens_by_role.get(user_role, 4000)
    
    def get_session_by_chat(self, whatsapp_chat: str, client_name: Optional[str] = None) -> Session:
        """Get or create session for a WhatsApp chat ID."""
        
        # Look up session ID by WhatsApp chat ID
        session_id = self.chat_to_session.get(whatsapp_chat)
        
        # Check if session exists and is valid
        if session_id and session_id in self.sessions:
            session = self.sessions[session_id]
            
            # Update client_name if provided and different
            if client_name and session.client_name != client_name:
                session.client_name = client_name
            
            # Check if session expired
            if datetime.now() - session.last_active > self.session_timeout:
                logger.info(f"Session {session_id} expired, creating new")
                session = self._create_session(whatsapp_chat, client_name)
            
            session.last_active = datetime.now()
            return session
        
        # Create new session
        return self._create_session(whatsapp_chat, client_name)
    
    def get_session_by_id(self, session_id: str) -> Optional[Session]:
        """Get session by session ID."""
        return self.sessions.get(session_id)
    
    def add_message(
        self,
        whatsapp_chat: str,     # WhatsApp chat ID (e.g., "1234567890@c.us") - matches sender or recipient
        role: str,              # "user" or "assistant"
        content: str,
        sender: str,            # WhatsApp sender ID or "assistant"
        recipient: str,         # WhatsApp recipient ID (should match whatsapp_chat for one of them)
        user_role: str = "client",
        client_name: Optional[str] = None,  # Update session with client name if provided
        timestamp: Optional[datetime] = None,
        received_at: Optional[datetime] = None,
        was_received: bool = True,
        image_path: Optional[str] = None
    ) -> str:
        """Add message to session, managing role-based token limits. Returns message_id."""
        
        from datetime import timezone
        
        session = self.get_session_by_chat(whatsapp_chat, client_name)
        
        from datetime import timezone
        
        session = self.get_session(chat_id)
        token_limit = self.get_token_limit(user_role)
        
        # Increment message counter
        session.message_counter += 1
        
        # Estimate tokens (rough: 1 token ≈ 4 chars)
        tokens = len(content) // 4
        
        # Default timestamps to now (UTC)
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        if received_at is None:
            received_at = datetime.now(timezone.utc)
        
        message = Message(
            message_id=str(uuid.uuid4()),
            order_num=session.message_counter,
            role=role,
            content=content,
            sender=sender,
            recipient=recipient,
            timestamp=timestamp,
            received_at=received_at,
            was_received=was_received,
            tokens=tokens,
            image_path=image_path
        )
        
        session.messages.append(message)
        session.total_tokens += tokens
        session.last_active = datetime.now(timezone.utc)
        session.last_active = datetime.now()
        
        # Prune if exceeding limit
        self._prune_session(session, token_limit)
        
        # Save session to disk
        self._save_session(session)
        
    def get_conversation_history(
        self,
        whatsapp_chat: str,
        user_role: str = "client",
        max_messages: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """Get conversation history formatted for AI (respects role-based token limit)."""
        
        session = self.get_session_by_chat(whatsapp_chat)
        
        # Load messages from IDs (pointers)
        messages = []
        message_ids = session.message_ids
        if max_messages:
            message_ids = message_ids[-max_messages:]
        
        for msg_id in message_ids:
            msg = self._load_message(msg_id)
            if msg:
    def clear_session(self, whatsapp_chat: str):
        """Clear session (for /reset command) - messages remain on disk."""
        
        session_id = self.chat_to_session.get(whatsapp_chat)
        if session_id and session_id in self.sessions:
            # Preserve client info when clearing
            old_session = self.sessions[session_id]
            session = self._create_session(whatsapp_chat, old_session.client_name)
            self._save_session(session)
            logger.info(f"Session {session_id} cleared (messages preserved on disk)")
    def clear_session(self, chat_id: str):
        """Clear session (for /reset command)."""
    def _prune_session(self, session: Session, token_limit: int):
        """Remove old message IDs to stay under role-based token limit (messages remain on disk)."""
        
        while session.total_tokens > token_limit and len(session.message_ids) > 2:
            # Remove oldest message ID (keep at least last 2)
            # Messages remain on disk for future retrieval
            removed_id = session.message_ids.pop(0)
            removed_msg = self._load_message(removed_id)
            if removed_msg:
                session.total_tokens -= removed_msg.tokens
            
            logger.debug(
                f"Pruned message {removed_id} from session {session.session_id}, "
    def _create_session(self, phone_number: str, client_name: Optional[str] = None) -> Session:
        """Create new session with UUID identifier."""
        from datetime import timezone
        
        # Generate unique session ID
        session_id = str(uuid.uuid4())
        
        # Extract phone number (e.g., "1234567890@c.us" -> "1234567890")
        client_phone = None
        if '@c.us' in phone_number:  # Individual chat (not group)
            client_phone = phone_number.split('@')[0]
        
        session = Session(
            session_id=session_id,
            phone_number=phone_number,
            client_name=client_name,
            client_phone=client_phone,
            message_ids=[],
            message_counter=0,
            created_at=datetime.now(timezone.utc),
            last_active=datetime.now(timezone.utc),
            total_tokens=0
    def _save_session(self, session: Session):
        """Save session metadata to disk (messages stored separately)."""
        filepath = os.path.join(self.storage_dir, f"{session.session_id}.json")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                'session_id': session.session_id,
                'whatsapp_chat': session.whatsapp_chat,
                'client_name': session.client_name,
                'message_counter': session.message_counter,
                'message_ids': session.message_ids,  # Only store IDs (pointers)
                'created_at': session.created_at.isoformat(),
                'last_active': session.last_active.isoformat(),
                'total_tokens': session.total_tokens
            }, f, ensure_ascii=False, indent=2)
    
    def _save_message(self, message: Message):
        """Save individual message to separate file."""
        filepath = os.path.join(self.storage_dir, "messages", f"{message.message_id}.json")
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump({
                'message_id': message.message_id,
                'chat_id': message.chat_id,  # Parent session ID
                'order_num': message.order_num,
                'role': message.role,
                'content': message.content,
                'sender': message.sender,
                'recipient': message.recipient,
                'timestamp': message.timestamp.isoformat(),
                'received_at': message.received_at.isoformat(),
                'was_received': message.was_received,
                'tokens': message.tokens,
                'image_path': message.image_path
            }, f, ensure_ascii=False, indent=2)
    
    def _load_message(self, message_id: str) -> Optional[Message]:
    def _load_sessions(self):
        """Load all sessions from disk (messages loaded on-demand)."""
        
        if not os.path.exists(self.storage_dir):
            return
        
        for filename in os.listdir(self.storage_dir):
            if not filename.endswith('.json'):
                continue
            
            # Skip message files
            if filename.startswith('messages/'):
                continue
            
            filepath = os.path.join(self.storage_dir, filename)
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Handle both old format (chat_id/phone_number) and new format (session_id/whatsapp_chat)
                session_id = data.get('session_id', data.get('chat_id'))
                whatsapp_chat = data.get('whatsapp_chat', data.get('phone_number', data.get('chat_id')))
                
                session = Session(
                    session_id=session_id,
                    whatsapp_chat=whatsapp_chat,
                    client_name=data.get('client_name'),
                    message_counter=data.get('message_counter', 0),
                    message_ids=data.get('message_ids', []),  # Load message IDs only
                    created_at=datetime.fromisoformat(data['created_at']),
                    last_active=datetime.fromisoformat(data['last_active']),
                    total_tokens=data['total_tokens']
                )
                
                # Store in both indexes
                self.sessions[session_id] = session
                self.chat_to_session[whatsapp_chat] = session_id
                
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
