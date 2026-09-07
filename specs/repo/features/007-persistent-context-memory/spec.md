# Feature Spec: Persistent Context & Memory System

**Feature ID**: 007-persistent-context-memory  
**Priority**: P0 (Critical)  
**Status**: Planning  
**Created**: January 17, 2026

## Problem Statement

Current limitations:
- Chat sessions (Feature 002) only store recent conversation history
- No long-term memory of user preferences, facts, or important information
- Cannot remember things across days/weeks/months
- Godfather needs a "brain" that persists across all chats
- Cannot recall "you told me last month that..."

**Desired Capabilities:**

**Per-Chat Persistent Context:**
- "Remember that John's favorite color is blue"
- Days later: "What's John's favorite color?" → "Blue"
- Remembers user preferences, facts, context indefinitely

**Godfather Global Context:**
- Knowledge shared across ALL chats the Godfather has
- "Remember that Q4 deadline is March 15"
- In any chat: "When's the Q4 deadline?" → "March 15"
- Personal knowledge base that follows the Godfather everywhere

## Use Cases

### Per-Chat Memory
1. **Customer Preferences**: Remember client likes, dislikes, requirements
2. **Project Context**: Track ongoing project details per client
3. **Personal Details**: Remember birthdays, family info, preferences
4. **History**: "What did we discuss last week about the proposal?"

### Godfather Global Memory
1. **Cross-Chat Knowledge**: Facts learned in Chat A available in Chat B
2. **Personal Knowledge Base**: Your own AI-powered second brain
3. **Business Intelligence**: Remember deals, clients, opportunities across all conversations
4. **Task Tracking**: Remember todos mentioned anywhere

## Solution Approaches

We'll implement a **hybrid approach** combining multiple techniques:

### Approach 1: Simple Key-Value Facts (MVP)
### Approach 2: Vector Database (RAG)
### Approach 3: Graph Database (Knowledge Graph)
### Approach 4: AI Memory Services (Mem0, Zep)

Let's explore each:

---

## Approach 1: Simple Key-Value Facts (MVP - Quick Win)

**Concept**: Store explicit facts as key-value pairs per chat

### Architecture
```
User: "Remember that Sarah's birthday is June 15"
→ Parse: entity="Sarah", attribute="birthday", value="June 15"
→ Store: {chat_id: {facts: {"Sarah.birthday": "June 15"}}}

Later...
User: "When is Sarah's birthday?"
→ Query facts → Find "Sarah.birthday" → Return "June 15"
```

### Data Model
```python
# src/models/memory.py

class MemoryFact:
    fact_id: str                    # UUID
    chat_id: str                    # WhatsApp chat ID
    user_id: str                    # User who created fact
    entity: str                     # Subject (e.g., "Sarah", "Q4 Project")
    attribute: str                  # Property (e.g., "birthday", "deadline")
    value: str                      # Fact value
    created_at: datetime
    last_accessed: datetime
    access_count: int
    confidence: float               # 0.0 to 1.0
    source: str                     # How it was learned
    
class MemoryStore:
    chat_memories: Dict[str, List[MemoryFact]]      # Per-chat facts
    godfather_memory: List[MemoryFact]              # Godfather's global facts
```

### Storage
```json
// state/memory.json
{
  "chat_memories": {
    "972501234567@c.us": [
      {
        "fact_id": "uuid-1",
        "entity": "Sarah",
        "attribute": "birthday",
        "value": "June 15",
        "created_at": "2026-01-15T10:00:00Z",
        "confidence": 0.9
      },
      {
        "fact_id": "uuid-2",
        "entity": "Project Alpha",
        "attribute": "deadline",
        "value": "March 1, 2026",
        "created_at": "2026-01-10T14:00:00Z"
      }
    ]
  },
  "godfather_memory": [
    {
      "fact_id": "uuid-3",
      "entity": "Q4 Goals",
      "attribute": "revenue_target",
      "value": "$500K",
      "created_at": "2026-01-05T09:00:00Z"
    }
  ]
}
```

### Implementation
```python
class SimpleMemoryManager:
    def remember(self, chat_id: str, entity: str, attribute: str, value: str):
        """Store a fact."""
        fact = MemoryFact(
            fact_id=str(uuid4()),
            chat_id=chat_id,
            entity=entity,
            attribute=attribute,
            value=value,
            created_at=datetime.now()
        )
        self.chat_memories[chat_id].append(fact)
        self.save()
    
    def recall(self, chat_id: str, query: str) -> Optional[str]:
        """Search for relevant facts."""
        # Simple keyword matching
        facts = self.chat_memories.get(chat_id, [])
        for fact in facts:
            if query.lower() in f"{fact.entity} {fact.attribute}".lower():
                return fact.value
        return None
```

**Pros**: Simple, fast, no dependencies  
**Cons**: Limited to explicit "remember X" commands, no semantic search  
**Best For**: MVP, basic fact storage

---

## Approach 2: Vector Database + RAG (Recommended)

**Concept**: Convert all conversations to embeddings, store in vector DB, retrieve relevant context

### Architecture
```
Conversation → Embedding (OpenAI) → Vector DB (ChromaDB/Pinecone)
                                          ↓
Query → Embedding → Semantic Search → Top K relevant chunks
                                          ↓
                                    Add to GPT context
```

### Technology Stack

**Option A: ChromaDB (Local, Free)**
```python
import chromadb
from chromadb.config import Settings

client = chromadb.Client(Settings(
    chroma_db_impl="duckdb+parquet",
    persist_directory="state/chroma"
))

collection = client.create_collection("denidin_memory")
```

**Option B: Pinecone (Cloud, Scalable)**
```python
import pinecone

pinecone.init(api_key="xxx", environment="us-west1-gcp")
index = pinecone.Index("denidin-memory")
```

**Option C: Qdrant (Self-hosted or cloud)**
```python
from qdrant_client import QdrantClient

client = QdrantClient(path="state/qdrant")
```

### Data Model
```python
class MemoryChunk:
    chunk_id: str                   # UUID
    chat_id: str                    # WhatsApp chat
    user_id: str                    # User (for Godfather global)
    content: str                    # Text content
    embedding: List[float]          # Vector (1536 dims for OpenAI)
    metadata: dict                  # Timestamp, speaker, type, etc.
    timestamp: datetime
    
class VectorMemoryManager:
    def __init__(self, embedding_model: str = "text-embedding-3-small"):
        self.client = chromadb.Client()
        self.collection = self.client.get_or_create_collection("denidin")
        self.embedding_model = embedding_model
    
    def add_message(
        self,
        chat_id: str,
        user_id: str,
        role: str,
        content: str,
        is_godfather: bool = False
    ):
        """Add message to vector store."""
        # Generate embedding
        embedding = openai.embeddings.create(
            model=self.embedding_model,
            input=content
        ).data[0].embedding
        
        # Store in vector DB
        self.collection.add(
            ids=[str(uuid4())],
            embeddings=[embedding],
            documents=[content],
            metadatas=[{
                "chat_id": chat_id,
                "user_id": user_id,
                "role": role,
                "timestamp": datetime.now().isoformat(),
                "is_godfather": is_godfather,
                "scope": "global" if is_godfather else "chat"
            }]
        )
    
    def search_memory(
        self,
        query: str,
        chat_id: str,
        user_id: str,
        is_godfather: bool = False,
        top_k: int = 5
    ) -> List[dict]:
        """Search for relevant memories."""
        # Generate query embedding
        query_embedding = openai.embeddings.create(
            model=self.embedding_model,
            input=query
        ).data[0].embedding
        
        # Build filter
        where_filter = {"chat_id": chat_id}
        if is_godfather:
            # Godfather sees: own global memories + this chat's memories
            where_filter = {
                "$or": [
                    {"chat_id": chat_id},
                    {"user_id": user_id, "scope": "global"}
                ]
            }
        
        # Search
        results = self.collection.query(
            query_embeddings=[query_embedding],
            where=where_filter,
            n_results=top_k
        )
        
        return results["documents"][0]
    
    def get_relevant_context(
        self,
        query: str,
        chat_id: str,
        user_id: str,
        is_godfather: bool = False
    ) -> str:
        """Get relevant memories as context string."""
        memories = self.search_memory(query, chat_id, user_id, is_godfather)
        
        if not memories:
            return ""
        
        context = "Relevant memories:\n"
        for i, memory in enumerate(memories, 1):
            context += f"{i}. {memory}\n"
        
        return context
```

### Integration with AI Handler
```python
# src/handlers/ai_handler.py - Enhanced

def get_response(
    self,
    user_message: str,
    chat_id: str,
    user_id: str,
    is_godfather: bool = False
) -> AIResponse:
    """Get AI response with memory context."""
    
    # 1. Get relevant memories from vector DB
    memory_context = self.memory_manager.get_relevant_context(
        query=user_message,
        chat_id=chat_id,
        user_id=user_id,
        is_godfather=is_godfather
    )
    
    # 2. Get recent conversation history (Feature 002)
    conversation_history = self.session_manager.get_conversation_history(
        chat_id=chat_id,
        max_messages=20
    )
    
    # 3. Build enhanced system message
    system_message = self.config.system_message
    if memory_context:
        system_message += f"\n\n{memory_context}"
    
    # 4. Call OpenAI with full context
    messages = [
        {"role": "system", "content": system_message},
        *conversation_history,
        {"role": "user", "content": user_message}
    ]
    
    response = openai.chat.completions.create(
        model=self.config.model,
        messages=messages
    )
    
    # 5. Store this interaction in vector DB
    self.memory_manager.add_message(
        chat_id=chat_id,
        user_id=user_id,
        role="user",
        content=user_message,
        is_godfather=is_godfather
    )
    
    ai_content = response.choices[0].message.content
    
    self.memory_manager.add_message(
        chat_id=chat_id,
        user_id=user_id,
        role="assistant",
        content=ai_content,
        is_godfather=is_godfather
    )
    
    return AIResponse(content=ai_content, ...)
```

### Chunking Strategies

For long conversations, split into chunks:

```python
def chunk_conversation(messages: List[dict], chunk_size: int = 5):
    """Split conversation into overlapping chunks."""
    chunks = []
    for i in range(0, len(messages), chunk_size - 1):  # Overlap by 1
        chunk = messages[i:i + chunk_size]
        combined = "\n".join([f"{m['role']}: {m['content']}" for m in chunk])
        chunks.append(combined)
    return chunks
```

**Pros**: Semantic search, handles fuzzy queries, scalable  
**Cons**: Embedding costs, vector DB dependency  
**Best For**: Production-ready persistent memory

---

## Approach 3: Graph Database (Advanced)

**Concept**: Model knowledge as a graph of entities and relationships

### Architecture
```
Entities: [Sarah, Project Alpha, Q4 Goals]
Relationships: 
  - Sarah --[has_birthday]--> June 15
  - Project Alpha --[has_deadline]--> March 1
  - Godfather --[knows]--> Q4 Goals
```

### Technology: Neo4j

```python
from neo4j import GraphDatabase

class GraphMemoryManager:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def add_fact(self, entity: str, relation: str, value: str, chat_id: str):
        """Add knowledge triple to graph."""
        with self.driver.session() as session:
            session.run(
                """
                MERGE (e:Entity {name: $entity, chat_id: $chat_id})
                MERGE (v:Value {content: $value})
                MERGE (e)-[r:RELATION {type: $relation}]->(v)
                SET r.created_at = datetime()
                """,
                entity=entity,
                relation=relation,
                value=value,
                chat_id=chat_id
            )
    
    def query_fact(self, entity: str, relation: str, chat_id: str):
        """Query knowledge from graph."""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (e:Entity {name: $entity, chat_id: $chat_id})
                      -[r:RELATION {type: $relation}]->(v:Value)
                RETURN v.content as value
                """,
                entity=entity,
                relation=relation,
                chat_id=chat_id
            )
            return result.single()["value"] if result else None
```

**Pros**: Complex relationships, graph queries, knowledge graph  
**Cons**: Complex setup, overkill for simple use case  
**Best For**: Complex multi-entity knowledge management

---

## Approach 4: AI Memory Services (Easiest)

**Concept**: Use specialized memory services designed for LLMs

### Option A: Mem0 (Open Source)

```python
from mem0 import Memory

memory = Memory()

# Add memory
memory.add(
    "Sarah's favorite color is blue",
    user_id="godfather",
    metadata={"chat_id": "972501234567@c.us"}
)

# Search memories
results = memory.search(
    "What is Sarah's favorite color?",
    user_id="godfather"
)

# Get all memories for user
memories = memory.get_all(user_id="godfather")
```

**Features:**
- Automatic entity extraction
- Deduplication
- Temporal understanding
- Built-in vector store

### Option B: Zep (Cloud Service)

```python
from zep_python import ZepClient

client = ZepClient(api_key="xxx")

# Add memory
client.memory.add_memory(
    session_id=chat_id,
    messages=[{
        "role": "user",
        "content": "Remember that Sarah's birthday is June 15"
    }]
)

# Search memories
results = client.memory.search_memory(
    session_id=chat_id,
    query="When is Sarah's birthday?",
    limit=5
)
```

**Features:**
- Automatic fact extraction
- Long-term memory
- Session management
- Temporal search

**Pros**: Turnkey solution, well-tested, feature-rich  
**Cons**: External dependency, potential costs  
**Best For**: Fast implementation, production-ready

---

## Recommended Hybrid Approach

Combine multiple techniques for best results:

```python
class HybridMemorySystem:
    def __init__(self):
        # Layer 1: Simple facts (immediate recall)
        self.fact_store = SimpleMemoryManager()
        
        # Layer 2: Vector DB (semantic search)
        self.vector_store = VectorMemoryManager()
        
        # Layer 3: AI memory service (automatic extraction)
        self.mem0 = Memory()
    
    def remember(
        self,
        content: str,
        chat_id: str,
        user_id: str,
        is_godfather: bool = False
    ):
        """Store across all layers."""
        
        # Store in vector DB (always)
        self.vector_store.add_message(
            chat_id=chat_id,
            user_id=user_id,
            role="user",
            content=content,
            is_godfather=is_godfather
        )
        
        # Extract and store explicit facts
        if "remember that" in content.lower():
            # Use AI to extract entity-attribute-value
            fact = self._extract_fact(content)
            if fact:
                self.fact_store.remember(
                    chat_id=chat_id,
                    entity=fact["entity"],
                    attribute=fact["attribute"],
                    value=fact["value"]
                )
        
        # Store in Mem0 for automatic extraction
        self.mem0.add(
            content,
            user_id=user_id if is_godfather else chat_id,
            metadata={"chat_id": chat_id, "is_godfather": is_godfather}
        )
    
    def recall(
        self,
        query: str,
        chat_id: str,
        user_id: str,
        is_godfather: bool = False
    ) -> str:
        """Multi-layer memory retrieval."""
        
        context_parts = []
        
        # Layer 1: Check simple facts first (fastest)
        fact = self.fact_store.recall(chat_id, query)
        if fact:
            context_parts.append(f"Known fact: {fact}")
        
        # Layer 2: Semantic search in vector DB
        vector_results = self.vector_store.search_memory(
            query=query,
            chat_id=chat_id,
            user_id=user_id,
            is_godfather=is_godfather,
            top_k=3
        )
        if vector_results:
            context_parts.append("Related conversations:")
            context_parts.extend([f"- {r}" for r in vector_results])
        
        # Layer 3: Mem0 search
        mem0_results = self.mem0.search(
            query,
            user_id=user_id if is_godfather else chat_id,
            limit=3
        )
        if mem0_results:
            context_parts.append("Extracted memories:")
            context_parts.extend([f"- {m['memory']}" for m in mem0_results])
        
        return "\n".join(context_parts)
    
    def _extract_fact(self, content: str) -> Optional[dict]:
        """Use AI to extract structured fact."""
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "system",
                "content": """Extract entity, attribute, value from text.
                Example: "Remember that Sarah's birthday is June 15"
                Output: {"entity": "Sarah", "attribute": "birthday", "value": "June 15"}
                If no fact found, return null."""
            }, {
                "role": "user",
                "content": content
            }],
            response_format={"type": "json_object"}
        )
        
        try:
            return json.loads(response.choices[0].message.content)
        except:
            return None
```

## Implementation Plan

### Phase 1: Simple Facts (Quick Win)
- [ ] Implement SimpleMemoryManager with JSON storage
- [ ] Add "remember" command detection
- [ ] Add fact extraction using GPT
- [ ] Store and retrieve simple facts
- [ ] Test with basic use cases

### Phase 2: Vector Store Integration
- [ ] Install ChromaDB
- [ ] Implement VectorMemoryManager
- [ ] Auto-store all conversations
- [ ] Implement semantic search
- [ ] Test retrieval accuracy

### Phase 3: Godfather Global Memory
- [ ] Add user_id scoping to memories
- [ ] Implement global vs chat-specific filtering
- [ ] Test cross-chat memory retrieval
- [ ] Add Godfather memory commands

### Phase 4: Hybrid System
- [ ] Integrate Mem0 or Zep
- [ ] Combine all memory layers
- [ ] Optimize retrieval strategy
- [ ] Add memory management commands

### Phase 5: Advanced Features
- [ ] Memory summarization (compress old memories)
- [ ] Memory importance ranking
- [ ] Automatic fact deduplication
- [ ] Memory export/import

## Configuration

```json
{
  "memory": {
    "enabled": true,
    "storage": {
      "facts": "state/memory_facts.json",
      "vector_db": "state/chroma",
      "embedding_model": "text-embedding-3-small"
    },
    "godfather": {
      "global_memory": true,
      "user_id": "972501234567@c.us"
    },
    "retrieval": {
      "max_facts": 5,
      "max_vector_results": 3,
      "similarity_threshold": 0.7
    },
    "mem0": {
      "enabled": false,
      "api_key": "${MEM0_API_KEY}"
    }
  }
}
```

## Memory Commands

```
User: "Remember that Sarah's birthday is June 15"
→ Stores fact

User: "What's Sarah's birthday?"
→ Retrieves: "June 15"

User: "Show my memories"
→ Lists all stored facts for this chat

User (Godfather): "Remember globally that Q4 target is $500K"
→ Stores in global Godfather memory

User (Godfather in different chat): "What's our Q4 target?"
→ Retrieves: "$500K" (from global memory)

Admin: "/memories <chat_id>"
→ View all memories for specific chat

Admin: "/forget <chat_id> <fact_id>"
→ Delete specific memory
```

## Cost Analysis

### Option 1: Local Only (ChromaDB + Simple Facts)
- **Storage**: Free (local disk)
- **Embeddings**: ~$0.00002 per message (text-embedding-3-small)
- **Example**: 10,000 messages = $0.20

### Option 2: Cloud Vector DB (Pinecone)
- **Storage**: ~$0.096/GB/month
- **Operations**: Included in tier
- **Example**: 100K vectors ≈ $5-10/month

### Option 3: Mem0/Zep
- **Mem0**: Self-hosted (free) or cloud (pricing TBD)
- **Zep**: ~$29/month starter plan

**Recommendation**: Start with ChromaDB (local, free) + simple facts

## Testing Strategy

### Unit Tests
- Fact extraction accuracy
- Vector similarity search
- Memory retrieval relevance
- Godfather global vs chat-specific scoping

### Integration Tests
- End-to-end remember → recall flow
- Cross-chat memory for Godfather
- Memory persistence across restarts
- Concurrent access handling

### Manual Tests
1. Store and recall simple facts
2. Test semantic search with paraphrased queries
3. Godfather memory across multiple chats
4. Memory with long time gaps (days apart)
5. Handling conflicting memories

## Success Metrics

- ✅ 90%+ fact recall accuracy
- ✅ Semantic search finds relevant context
- ✅ Godfather memories work cross-chat
- ✅ <500ms memory retrieval latency
- ✅ Handles 100K+ memories efficiently
- ✅ No memory leaks or bloat

## Privacy & Data Management

- **Retention Policy**: Keep memories for N days/months
- **Deletion**: Support chat memory wipe
- **Export**: Allow users to export their memories
- **Anonymization**: Option to anonymize old memories
- **GDPR**: Right to be forgotten implementation

## Future Enhancements

- **Automatic Summarization**: Compress old conversations
- **Memory Consolidation**: Merge duplicate/similar memories
- **Temporal Queries**: "What did we discuss last month?"
- **Memory Sharing**: Share memories between users (with permission)
- **Visual Memory**: Remember images, documents
- **Voice Memory**: Remember voice note transcripts
- **Memory Analytics**: Show memory growth over time
- **Smart Forgetting**: Auto-delete low-value memories

## Dependencies on Other Features

- **Required**: Feature 002 (Chat Sessions) - Recent conversation context
- **Required**: Feature 006 (RBAC) - Godfather role identification
- **Enhanced by**: Feature 003 (Media) - Remember document contents
- **Enhanced by**: Feature 005 (Green Receipt) - Remember invoice contexts

---

**Recommended Tech Stack**:
1. **ChromaDB** for vector storage (free, local)
2. **OpenAI Embeddings** (text-embedding-3-small)
3. **Simple JSON** for explicit facts
4. **Optional**: Mem0 for advanced features

**Next Steps**:
1. Review and approve approach
2. Start with Phase 1 (Simple Facts)
3. Add Phase 2 (Vector Store) incrementally
4. Test with real conversations
5. Optimize retrieval quality
