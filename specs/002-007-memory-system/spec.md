# Feature Spec: Memory System (Combined 002 + 007)

**Feature ID**: 002+007-memory-system  
**Priority**: P0 (Critical)  
**Status**: In Progress (Phase 1-2 Complete)  
**Created**: January 17, 2026  
**Updated**: January 18, 2026  
**Branch**: `002-007-memory-system`

**IMPLEMENTATION STATUS**:
- ✅ Phase 1 Complete: Foundation, dependencies, config
- ✅ Phase 2 Complete: SessionManager (UUID sessions, message persistence, cleanup)
- ⏳ Phase 3: MemoryManager (ChromaDB semantic memory) - Next
- **DEFERRED to Feature 006 (RBAC)**: Token limits, pruning, client_name, tokens field

## Terminology Glossary

**CRITICAL**: These terms are used consistently throughout this specification:

- **session_id**: Unique UUID identifier for a conversation session (primary key)
- **whatsapp_chat**: WhatsApp chat identifier (e.g., "1234567890@c.us" for individual, "group-id@g.us" for groups)
- **chat_id**: DEPRECATED - use `session_id` or `whatsapp_chat` explicitly
- **phone_number**: DEPRECATED - use `whatsapp_chat` instead
- **client_phone**: Extracted phone number from whatsapp_chat (e.g., "1234567890" from "1234567890@c.us")
- **user_role**: User's role in system - either "client" or "godfather" (determines token limits and permissions)
- **message_id**: Unique UUID identifier for a single message within a session
- **order_num**: Sequential message number within a session (1, 2, 3...)

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

### Role Identification

**REQ-ROLE-001**: User role determination
- **Godfather**: WhatsApp chat ID matches configured godfather phone number in `config.json`
- **Client**: Any other WhatsApp chat ID not matching godfather number
- **Default**: If role cannot be determined, default to "client" (more restrictive token limit)

**REQ-ROLE-002**: Configuration
- `config.json` MUST contain `godfather_phone` field (e.g., "972501234567@c.us")
- Format validation: Must match WhatsApp ID format (phone@c.us or phone@g.us)
- Case-sensitive exact match required

### Deferred to Phase 2

- Per-chat memory (separate from Godfather global)
- Document ingestion (PDF/DOCX text extraction)
- Advanced memory commands (`/memories`, `/forget`, `/search`)
- Memory categories/tags
- Automatic memory extraction from conversations

## Non-Functional Requirements

### Performance (NFR-PERF)

**NFR-PERF-001**: Session Load Time
- Session load from disk: ≤100ms (p95) for sessions with ≤1000 messages
- Session metadata load: ≤10ms (p95)
- Message file load: ≤5ms per message (p95)

**NFR-PERF-002**: Memory Query Latency
- ChromaDB semantic search: ≤500ms (p95) for collections ≤10K memories
- Embedding generation: ≤200ms per query (p95)
- Total memory recall (query + embedding): ≤700ms (p95)

**NFR-PERF-003**: Session Pruning
- Pruning operation: ≤50ms for sessions with 1000+ messages
- Non-blocking: Must not delay message response

**NFR-PERF-004**: Scalability Limits
- Maximum sessions: 10,000 active sessions (in-memory cache)
- Maximum messages per session: Unlimited (file-based, limited by token pruning)
- Maximum memories: 100,000 ChromaDB entries (Phase 1 target)
- Disk space planning: ~10KB per session, ~2KB per message, ~5KB per memory

### Security & Privacy (NFR-SEC)

**NFR-SEC-001**: Data Encryption at Rest
- Session files: Stored in plaintext (Phase 1 - local deployment only)
- Memory files: ChromaDB default storage (unencrypted)
- **Phase 2**: Implement encryption for production deployments

**NFR-SEC-002**: Access Control
- File system permissions: 600 (owner read/write only) for all data files
- Directory permissions: 700 (owner access only) for data/ directories
- No external access to data files (application-only access)

**NFR-SEC-003**: PII Handling
- `client_name`: Stored as-is (no encryption in Phase 1)
- `whatsapp_chat` (phone numbers): Stored as-is (required for routing)
- Message content: Stored as-is (contains user data)
- **Compliance**: GDPR compliance deferred to Phase 2 (manual deletion only)

**NFR-SEC-004**: Data Retention
- Sessions: Auto-expire after 24 hours of inactivity (configurable)
- Expired sessions: Moved to `data/sessions/expired/` (preserved for 30 days)
- Messages: Preserved indefinitely (no auto-deletion)
- Memories: Indefinite retention (manual `/forget` command only)

**NFR-SEC-005**: Audit Logging
- Memory operations (remember/forget): Logged with timestamp, user, content hash
- Session creation/expiration: Logged with session_id, whatsapp_chat
- Log retention: 90 days
- Log format: JSON structured logs in `logs/memory_audit.log`

### Reliability (NFR-REL)

**NFR-REL-001**: Data Consistency
- Session updates: Atomic writes (write to temp file, then atomic rename)
- Message saves: Independent files (failure of one doesn't affect others)
- No concurrent session updates: Single-threaded per session (queue-based)

**NFR-REL-002**: Durability
- File writes: fsync after critical operations (session save, message save)
- ChromaDB: Auto-persistence (commit after each operation)
- Recovery: All operations idempotent (can retry safely)

**NFR-REL-003**: Graceful Degradation
- If ChromaDB unavailable: Disable memory recall, continue with session history only
- If session load fails: Create new session, log error
- If disk full: Return error to user, prevent data corruption

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
    chat_id: str        # Parent session ID (UUID)
    order_num: int      # Sequential number within chat (1, 2, 3...) - from session.message_counter
    role: str           # "user" (from WhatsApp) or "assistant" (from OpenAI)
    content: str        # Message text
    sender: Optional[str]    # WhatsApp sender ID (e.g., "1234567890@c.us") or "assistant"
    recipient: Optional[str] # WhatsApp recipient ID (bot's ID) or WhatsApp phone number
    timestamp: str      # ISO format UTC timestamp
    received_at: str    # ISO format UTC timestamp
    was_received: bool  # Whether recipient acknowledged receipt (default: True)
    image_path: Optional[str] = None  # Path to image file (future use, deferred to Phase 3)
    
class Session:
    """Conversation session for a chat - messages stored separately."""
    session_id: str             # Unique session ID (UUID) - primary identifier
    whatsapp_chat: str          # WhatsApp chat ID (e.g., "1234567890@c.us") - matches sender/recipient in messages
    message_ids: List[str]      # List of message IDs (pointers to message files)
    message_counter: int        # Counter for order_num (auto-increment, starts at 0)
    created_at: str             # ISO format UTC timestamp
    last_active: str            # ISO format UTC timestamp
    total_tokens: int           # Reserved for future RBAC feature (006), currently unused
    
class SessionManager:
    """Manage conversation sessions with message persistence."""
    
    def __init__(
        self,
        storage_dir: str = "data/sessions",
        session_timeout_hours: int = 24,
        cleanup_interval_seconds: int = 3600
    ):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.session_timeout_hours = session_timeout_hours
        self.cleanup_interval_seconds = cleanup_interval_seconds
        self.chat_to_session: Dict[str, str] = {}  # Map: whatsapp_chat -> session_id
        
        # Load existing sessions from disk
        self._load_sessions()
        
        # Start background cleanup thread for expired sessions
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_running = True
        self._cleanup_thread.start()
    
    def get_session(self, chat_id: str) -> Session:
        """Get or create session for a WhatsApp chat ID."""
        
        # Check if session exists in index
        if chat_id in self.chat_to_session:
            session_id = self.chat_to_session[chat_id]
            session = self._load_session(session_id)
            
            # Update last_active timestamp
            session.last_active = datetime.now(timezone.utc).isoformat()
            self._save_session(session)
            return session
        
        # Create new session
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        session = Session(
            session_id=session_id,
            whatsapp_chat=chat_id,
            message_ids=[],
            message_counter=0,
            created_at=now,
            last_active=now,
            total_tokens=0
        )
        
        # Save to disk and index
        self._save_session(session)
        self.chat_to_session[chat_id] = session_id
        return session
    
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

## Error Handling & Exception Flows

### Session Manager Errors (ERR-SESSION)

**ERR-SESSION-001**: Session File Corrupted/Missing
- **Detection**: JSON parse error or file not found during `_load_sessions()`
- **Recovery**: Log error, skip corrupted file, create new session on next access
- **User Impact**: Previous conversation history lost for that session
- **Logging**: ERROR level with file path and exception details

**ERR-SESSION-002**: Disk Space Exhaustion
- **Detection**: `OSError` with errno 28 (ENOSPC) during session save
- **Response**: Return error to user, do NOT corrupt existing data
- **Recovery**: Admin must free disk space, application continues with in-memory sessions
- **User Message**: "⚠️ Cannot save conversation history - system storage full. Please contact administrator."

**ERR-SESSION-003**: JSON Serialization Failure
- **Detection**: `TypeError` or `ValueError` during `json.dump()`
- **Recovery**: Log error, skip problematic message, continue processing
- **Validation**: Pre-validate all serializable fields before writing
- **Logging**: ERROR level with data structure that failed

**ERR-SESSION-004**: Invalid Role Value
- **Detection**: Role not in ["user", "assistant"]
- **Response**: Raise `ValueError` with clear message
- **Recovery**: Caller must provide valid role
- **Validation**: Assert role in add_message() before processing

**ERR-SESSION-005**: Empty Message Content
- **Detection**: Content is empty string or only whitespace
- **Response**: Accept but log WARNING (valid for some use cases)
- **Behavior**: Store message normally (0 tokens)
- **Validation**: Strip whitespace for token counting

**ERR-SESSION-006**: Session Load Partial Failure
- **Detection**: Some message IDs in session don't have corresponding message files
- **Recovery**: Load available messages, log WARNING for missing ones, continue
- **Behavior**: Session appears with gaps in conversation
- **Logging**: WARNING level with list of missing message_ids

**ERR-SESSION-007**: Malformed WhatsApp Chat ID
- **Detection**: whatsapp_chat doesn't match expected format (xxx@c.us or xxx@g.us)
- **Response**: Accept and log WARNING (format may evolve)
- **Validation**: No strict validation (defensive programming)

### Memory Manager Errors (ERR-MEMORY)

**ERR-MEMORY-001**: ChromaDB Initialization Failure
- **Detection**: Exception during `PersistentClient()` or `get_or_create_collection()`
- **Response**: Log ERROR, set `memory_enabled = False` flag
- **Recovery**: Continue without memory features (graceful degradation per NFR-REL-003)
- **User Impact**: Memory commands return error, AI responses work without recall
- **User Message**: "⚠️ Memory system temporarily unavailable. Your message was processed without memory context."

**ERR-MEMORY-002**: Embedding Generation Failure
- **Detection**: OpenAI API error during `_create_embedding()`
- **Response**: Retry up to 3 times with exponential backoff (1s, 2s, 4s)
- **Recovery**: If all retries fail, log ERROR and return empty results for recall
- **User Impact**: Memory recall returns no results, `/remember` command fails with error message
- **User Message**: "/remember failed: Unable to generate embedding. Please try again."

**ERR-MEMORY-003**: ChromaDB Query Failure
- **Detection**: Exception during `collection.query()`
- **Response**: Log ERROR, return empty list (no memories)
- **Recovery**: Continue processing without memory context
- **Retry**: Single retry attempt, then fail gracefully

**ERR-MEMORY-004**: Memory Storage Failure
- **Detection**: Exception during `collection.add()` in remember()
- **Response**: Return error to user, do NOT confirm storage
- **User Message**: "❌ Failed to store memory. Please try again."
- **Logging**: ERROR level with content hash (not full content for privacy)

**ERR-MEMORY-005**: Duplicate Memory ID
- **Detection**: UUID collision (extremely rare)
- **Response**: Regenerate UUID and retry
- **Max Retries**: 3 attempts
- **Failure**: Log CRITICAL and return error to user

**ERR-MEMORY-006**: Invalid Metadata
- **Detection**: Metadata contains non-serializable objects
- **Response**: Log WARNING, filter out invalid fields, continue with valid metadata
- **Validation**: Convert datetime objects to ISO strings automatically

### Integration Errors (ERR-INTEGRATION)

**ERR-INTEGRATION-001**: Role Identification Failure
- **Detection**: Cannot determine if user is client or godfather
- **Response**: Default to "client" role (safer, more restrictive)
- **Logging**: WARNING level with whatsapp_chat ID
- **Behavior**: Apply 4,000 token limit

**ERR-INTEGRATION-002**: Feature Flag Configuration Missing
- **Detection**: `enable_memory_system` not in config
- **Response**: Default to `False` (disabled)
- **Logging**: WARNING level on startup

**ERR-INTEGRATION-003**: Configuration File Invalid
- **Detection**: JSON parse error in config.json
- **Response**: Use hardcoded defaults, log ERROR
- **Logging**: ERROR level with file path
- **Fallback**: memory_enabled = False, session_timeout = 24h, token limits default

**ERR-INTEGRATION-004**: Timestamp Timezone Missing
- **Detection**: datetime object without timezone info in legacy data
- **Response**: Assume UTC, log WARNING
- **Migration**: Add UTC timezone to naive datetimes
- **Logging**: WARNING with session_id

## Edge Cases & Boundary Conditions

### Edge Case Handling (EDGE)

**EDGE-001**: Zero-Message Session
- **Scenario**: Newly created session with no messages
- **Behavior**: Return empty list for `get_conversation_history()`
- **Validation**: Total tokens = 0, message_counter = 0
- **AI Impact**: No conversation context, only system prompt + memories

**EDGE-002**: Extremely Long Single Message
- **Scenario**: Message >10,000 tokens (exceeds client limit of 4,000)
- **Behavior**: Accept message, immediately prune oldest messages to fit limit
- **Result**: Only latest message(s) retained if long message consumes all tokens
- **Logging**: WARNING if single message exceeds token limit for role

**EDGE-003**: Rapid Message Burst
- **Scenario**: 10+ messages in <1 second from same chat
- **Behavior**: Queue-based processing (single-threaded per session)
- **Performance**: May cause delay in responses
- **Validation**: No rate limiting in Phase 1 (trust WhatsApp rate limits)

**EDGE-004**: Session Timeout Edge Case
- **Scenario**: Message arrives exactly at 24-hour timeout boundary
- **Behavior**: If `last_active + 24h <= now`, create new session
- **Precision**: Second-level precision (not millisecond)
- **Migration**: Previous session moved to `expired/` directory

**EDGE-005**: Memory Query Zero Results
- **Scenario**: Semantic search returns no memories above similarity threshold
- **Behavior**: Return empty list, AI proceeds without memory context
- **Logging**: DEBUG level (normal operation, not an error)
- **User Impact**: Response may be less contextual

**EDGE-006**: Concurrent Session Updates (Race Condition)
- **Scenario**: Two messages arrive simultaneously for same session
- **Mitigation**: Single-threaded message queue per session (Constitution architecture)
- **Behavior**: Messages processed sequentially in arrival order
- **Validation**: Message order_num increments correctly

**EDGE-007**: Storage Directory Permissions
- **Scenario**: Application cannot write to `data/` directory
- **Detection**: `PermissionError` during directory creation or file write
- **Response**: Log CRITICAL error, terminate startup
- **User Message**: "FATAL: Cannot access data directory. Check file permissions."
- **Recovery**: Admin must fix permissions and restart

**EDGE-008**: Image Path Without Image File
- **Scenario**: Message has `image_path` but file doesn't exist
- **Behavior**: Store path anyway, log WARNING
- **AI Impact**: Path included in message metadata but file unavailable
- **Future**: Phase 2 will validate image existence

**EDGE-009**: Session Expiration During Processing
- **Scenario**: Session expires while message is being processed
- **Behavior**: Complete current message processing, expire after response sent
- **Validation**: Check expiration before loading session, not during processing

**EDGE-010**: ChromaDB Collection Already Exists
- **Scenario**: Collection exists from previous run or manual creation
- **Behavior**: Use existing collection, log INFO
- **Migration**: No automatic schema migration in Phase 1
- **Validation**: Verify collection metadata matches expected format

## Recovery Procedures (RECOVERY)

**RECOVERY-001**: Rebuild Session from Message Files
- **Trigger**: Session file corrupted but message files intact
- **Procedure**:
  1. Scan `data/sessions/messages/` for messages matching session_id
  2. Sort by order_num
  3. Reconstruct Session object with correct metadata
  4. Recalculate total_tokens
  5. Save reconstructed session
- **Automation**: Manual procedure in Phase 1, tool in Phase 2

**RECOVERY-002**: ChromaDB Collection Corruption
- **Trigger**: Collection query fails consistently
- **Procedure**:
  1. Backup `data/memory/` directory
  2. Delete corrupted collection
  3. Recreate collection
  4. Restore from backup (manual re-import in Phase 1)
- **Data Loss**: Memories lost if no backup exists
- **Prevention**: Regular backups (external to application)

**RECOVERY-003**: Disk Space Recovery
- **Trigger**: Disk full error (ERR-SESSION-002)
- **Procedure**:
  1. Move expired sessions to compressed archive
  2. Delete sessions older than 30 days
  3. Truncate old message files if needed
  4. Resume normal operation
- **Automation**: Manual in Phase 1, automated cleanup in Phase 2

**RECOVERY-004**: Rollback Failed Message Addition
- **Trigger**: Error during message save after AI response generated
- **Procedure**:
  1. Log ERROR with message details
  2. Do NOT add message to session
  3. Return original error to user
  4. User can retry (idempotent operation)
- **Data Consistency**: Session remains in previous valid state

## Configuration

**REQ-CONFIG-001**: Configuration File Structure
```json
{
  "feature_flags": {
    "enable_memory_system": false
  },
  "godfather_phone": "972501234567@c.us",
  "memory": {
    "session": {
      "storage_dir": "data/sessions",
      "max_tokens_by_role": {
        "client": 4000,
        "godfather": 100000
      },
      "session_timeout_hours": 24
    },
    "longterm": {
      "enabled": true,
      "storage_dir": "data/memory",
      "collection_name": "godfather_memory",
      "embedding_model": "text-embedding-3-small",
      "top_k_results": 5,
      "min_similarity": 0.7
    }
  }
}
```

**REQ-CONFIG-002**: Required Fields
- `feature_flags.enable_memory_system` (boolean): Master switch for all memory features
- `godfather_phone` (string): WhatsApp ID for godfather role identification
- `memory.session.max_tokens_by_role` (object): Token limits per role
- `memory.longterm.embedding_model` (string): OpenAI embedding model name

**REQ-CONFIG-003**: Default Values (if missing)
- `enable_memory_system`: false (disabled for safety)
- `session_timeout_hours`: 24
- `top_k_results`: 5
- `min_similarity`: 0.7
- `max_tokens_by_role.client`: 4000
- `max_tokens_by_role.godfather`: 100000

## Dependencies

**DEP-001**: Python Version
- **Required**: Python ≥3.10 (for `datetime.timezone.utc` support)
- **Validation**: Check Python version on startup
- **Error**: Exit with error if Python <3.10

**DEP-002**: ChromaDB
- **Version**: >=0.4.22, <0.5.0
- **Purpose**: Vector database for semantic memory
- **Installation**: `pip install chromadb>=0.4.22`
- **Compatibility**: Tested with 0.4.22, may work with newer 0.4.x versions

**DEP-003**: OpenAI Python SDK
- **Version**: >=1.12.0
- **Purpose**: Embedding generation (text-embedding-3-small)
- **API Key**: Required in environment or config
- **Rate Limits**: Respect OpenAI API rate limits (retry with backoff)

**DEP-004**: File System
- **Writable Directory**: `data/` must be writable by application
- **Permissions**: Owner read/write (600 for files, 700 for directories)
- **Disk Space**: Recommend ≥1GB free for initial deployment
- **Validation**: Check write permissions on startup

```python
# requirements.txt additions
chromadb>=0.4.22,<0.5.0    # Vector database
openai>=1.12.0             # Embeddings API (Python 3.10+ required)
```

## Acceptance Criteria (Quantifiable)

### Session Management (AC-SESSION)

**AC-SESSION-001**: Session Creation
- **Given**: New WhatsApp chat ID "1234567890@c.us"
- **When**: First message received
- **Then**: 
  - Session file created at `data/sessions/{session_id}.json`
  - Session contains: session_id (UUID), whatsapp_chat, created_at (UTC), total_tokens=0
  - Returns session object in <10ms

**AC-SESSION-002**: Message Storage
- **Given**: Active session with 5 existing messages
- **When**: New message "Hello" added with role="user"
- **Then**:
  - Message file created at `data/sessions/messages/{message_id}.json`
  - Message contains: message_id, session_id, order_num=6, role="user", content="Hello", timestamp (UTC)
  - Session updated with message_id in message_ids array
  - Session total_tokens incremented by ~1 token (4 chars / 4)
  - Operation completes in <50ms

**AC-SESSION-003**: Token Limit Enforcement (Client)
- **Given**: Client session with 3,990 tokens
- **When**: New 50-token message added
- **Then**:
  - Oldest messages pruned until total_tokens ≤ 4,000
  - At least last 2 messages preserved
  - Pruned message IDs removed from session.message_ids
  - Message files remain on disk
  - Operation completes in <100ms

**AC-SESSION-004**: Token Limit Enforcement (Godfather)
- **Given**: Godfather session with 99,950 tokens  
- **When**: New 100-token message added
- **Then**:
  - Oldest messages pruned until total_tokens ≤ 100,000
  - At least last 2 messages preserved
  - Token limit correctly applied at 100,000 (not 4,000)

**AC-SESSION-005**: Session Expiration
- **Given**: Session with last_active = 24 hours ago
- **When**: New message arrives
- **Then**:
  - Old session moved to `data/sessions/expired/{session_id}.json`
  - New session created with fresh session_id
  - Old message history NOT included in new session
  - Operation completes in <100ms

**AC-SESSION-006**: Session Persistence
- **Given**: Session with 10 messages
- **When**: Application restarts
- **Then**:
  - Session loaded from disk with all message_ids intact
  - Session metadata (total_tokens, created_at, last_active) matches saved values
  - Conversation history retrievable
  - Load completes in <100ms for 10-message session

**AC-SESSION-007**: Conversation History Format
- **Given**: Session with messages: user="A", assistant="B", user="C"
- **When**: get_conversation_history() called
- **Then**:
  - Returns list: [{"role": "user", "content": "A"}, {"role": "assistant", "content": "B"}, {"role": "user", "content": "C"}]
  - Order preserved (chronological by order_num)
  - All messages within token limit included

### Memory Management (AC-MEMORY)

**AC-MEMORY-001**: Memory Storage (/remember command)
- **Given**: Godfather sends "/remember TestCorp owes ₪5000"
- **When**: Command processed
- **Then**:
  - Memory stored in ChromaDB with unique memory_id (UUID)
  - Embedding generated using text-embedding-3-small
  - Metadata includes: created_at (ISO), type="fact"
  - Returns success message: "✅ Remembered: TestCorp owes ₪5000"
  - Operation completes in <1000ms (including embedding generation)

**AC-MEMORY-002**: Memory Recall (Semantic Search)
- **Given**: Memory "TestCorp owes ₪5000 from invoice INV-001" stored
- **When**: User asks "What's the status with TestCorp?"
- **Then**:
  - ChromaDB query returns memory with similarity score ≥ 0.7
  - Memory included in top_k=5 results
  - Query completes in <500ms
  - Memory content accessible for AI context

**AC-MEMORY-003**: Memory Recall Accuracy
- **Given**: 10 memories about different companies stored
- **When**: Query "Tell me about TestCorp"
- **Then**:
  - TestCorp-related memories ranked in top 3 results
  - Irrelevant memories (other companies) have similarity < 0.7 or not in top_k
  - Precision ≥ 80% (relevant results / total results)

**AC-MEMORY-004**: Empty Memory Results
- **Given**: No memories stored
- **When**: Memory recall query executed
- **Then**:
  - Returns empty list []
  - No error raised
  - Query completes in <200ms
  - AI proceeds with response (no memory context)

**AC-MEMORY-005**: ChromaDB Initialization
- **Given**: Fresh installation, no data/memory/ directory
- **When**: MemoryManager instantiated
- **Then**:
  - Directory `data/memory/` created with permissions 700
  - ChromaDB collection "godfather_memory" created
  - Collection configured with metadata: {"hnsw:space": "cosine"}
  - Initialization completes in <2000ms

### Feature Flag Control (AC-FLAG)

**AC-FLAG-001**: Memory System Disabled
- **Given**: config.json has enable_memory_system=false
- **When**: User sends message
- **Then**:
  - Session management: DISABLED (no session files created)
  - Memory recall: DISABLED (no ChromaDB queries)
  - /remember command: Returns "Memory system is disabled"
  - AI responses work normally (no memory context)

**AC-FLAG-002**: Memory System Enabled
- **Given**: config.json has enable_memory_system=true
- **When**: User sends message
- **Then**:
  - Session history loaded and included in AI context
  - Memory recall executed before AI response
  - /remember command functional
  - All memory features active

### Role-Based Behavior (AC-ROLE)

**AC-ROLE-001**: Client Role Identification
- **Given**: Message from whatsapp_chat="1234567890@c.us", godfather_phone="9999999999@c.us"
- **When**: Message processed
- **Then**:
  - User identified as role="client"
  - Token limit applied: 4,000 tokens
  - Session pruned at 4,000 token threshold

**AC-ROLE-002**: Godfather Role Identification  
- **Given**: Message from whatsapp_chat="9999999999@c.us", godfather_phone="9999999999@c.us"
- **When**: Message processed
- **Then**:
  - User identified as role="godfather"
  - Token limit applied: 100,000 tokens
  - Session pruned at 100,000 token threshold

**AC-ROLE-003**: Role Default (Unknown)
- **Given**: godfather_phone not configured
- **When**: Message from any chat processed
- **Then**:
  - Default role="client" applied
  - Token limit: 4,000 tokens (more restrictive)
  - WARNING logged

### Error Handling (AC-ERROR)

**AC-ERROR-001**: Session File Corrupted
- **Given**: Session file contains invalid JSON
- **When**: Session load attempted
- **Then**:
  - Error logged with ERROR level
  - Corrupted session skipped
  - New session created on next message
  - Application continues normally

**AC-ERROR-002**: ChromaDB Unavailable
- **Given**: ChromaDB initialization fails
- **When**: Memory recall attempted
- **Then**:
  - memory_enabled flag set to False
  - Empty list returned for recall
  - AI response generated without memory context
  - User message: "⚠️ Memory system temporarily unavailable..."
  - Application continues normally (graceful degradation)

**AC-ERROR-003**: Embedding API Failure
- **Given**: OpenAI API returns error
- **When**: /remember command executed
- **Then**:
  - Retry 3 times with exponential backoff (1s, 2s, 4s)
  - If all fail: Return error to user "❌ Failed to store memory..."
  - Memory NOT confirmed as stored
  - Operation fails gracefully

**AC-ERROR-004**: Disk Space Full
- **Given**: Disk write returns ENOSPC error
- **When**: Session save attempted
- **Then**:
  - Error message returned: "⚠️ Cannot save conversation history..."
  - Existing session files NOT corrupted
  - Application continues with in-memory sessions
  - CRITICAL error logged

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
