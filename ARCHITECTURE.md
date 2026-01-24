# DeniDin Architecture

**Version**: 1.0 | **Last Updated**: 2026-01-23 | **Status**: Production

## Overview

DeniDin is a WhatsApp AI assistant built on a multi-tier memory architecture with role-based access control. The system processes messages through a pipeline that includes session management, AI response generation, semantic memory recall, and automated background cleanup.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        WhatsApp User                             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Green API (WhatsApp)                          │
│  - Receives messages                                             │
│  - Sends responses                                               │
│  - Handles webhooks                                              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DeniDin Application                           │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              WhatsApp Handler                             │  │
│  │  - Message validation                                     │  │
│  │  - Type filtering (text, image, document)                 │  │
│  │  - Error handling & retries                               │  │
│  └─────────────────────┬─────────────────────────────────────┘  │
│                        │                                         │
│                        ▼                                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              User Manager (RBAC)                          │  │
│  │  - Role determination (Admin/Godfather/Client/Blocked)   │  │
│  │  - Permission checking                                    │  │
│  │  - Token limit enforcement                                │  │
│  │  - Memory scope filtering                                 │  │
│  └─────────────────────┬─────────────────────────────────────┘  │
│                        │                                         │
│                        ▼                                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │           Session Manager (Tier 1 Memory)                 │  │
│  │  - UUID-based session tracking                            │  │
│  │  - Message history persistence (JSON)                     │  │
│  │  - Token counting & pruning                               │  │
│  │  - 24-hour expiration tracking                            │  │
│  │  - Session archival (expired/YYYY-MM-DD/)                 │  │
│  └─────────────────────┬─────────────────────────────────────┘  │
│                        │                                         │
│                        ▼                                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              AI Handler (OpenAI)                          │  │
│  │  - GPT-4o-mini integration                                │  │
│  │  - GPT-4o Vision API (images/PDFs)                        │  │
│  │  - System prompt construction                             │  │
│  │  - Memory recall integration                              │  │
│  │  - Response generation                                    │  │
│  │  - Error handling & retries                               │  │
│  │  - Session transfer to long-term memory                   │  │
│  └───────┬──────────────────────────────────┬────────────────┘  │
│          │                                  │                   │
│          ▼                                  ▼                   │
│  ┌──────────────────┐          ┌──────────────────────────┐    │
│  │  Memory Manager  │          │  Media Extractors        │    │
│  │  (Tier 2 Memory) │          │  (Feature 003 Phase 4)   │    │
│  │                  │          │                          │    │
│  │  - ChromaDB      │          │  MediaExtractor Base:    │    │
│  │  - Vector search │          │  - ImageExtractor        │    │
│  │  - Embeddings    │          │    (Vision API)          │    │
│  │  - Per-entity    │          │  - PDFExtractor          │    │
│  │    collections   │          │    (page aggregation)    │    │
│  │  - Scopes:       │          │  - DOCXExtractor         │    │
│  │    PUBLIC,       │          │    (python-docx + AI)    │    │
│  │    PRIVATE,      │          │                          │    │
│  │    SYSTEM        │          │  Single AI call:         │    │
│  └──────────────────┘          │  text + analysis         │    │
│                                │  (~50% cost savings)     │    │
│                                └──────────────────────────┘    │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              Background Cleanup Thread                    │  │
│  │                                                           │  │
│  │  Monitors expired sessions (hourly)                      │  │
│  │                                                           │  │
│  │  4-step cleanup:                                         │  │
│  │  1. Archive files                                        │  │
│  │  2. Transfer to ChromaDB                                 │  │
│  │  3. Remove from index                                    │  │
│  │  4. Mark transferred                                     │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. WhatsApp Handler (`src/handlers/whatsapp_handler.py`)

**Responsibilities:**
- Message validation and type filtering
- Green API communication
- Error handling with exponential backoff
- Request/response logging

**Key Features:**
- Rejects non-text messages (images, audio, video)
- Retry logic for API failures (max 3 attempts)
- Message tracking with unique IDs
- Sender/recipient attribution

### 2. User Manager (`src/utils/user_manager.py`)

**Responsibilities:**
- User role determination based on phone number
- Permission enforcement
- Token limit retrieval
- Memory scope filtering

**Role Hierarchy:**
```
Admin (highest)
  ↓
Godfather
  ↓
Client (default)
  ↓
Blocked (lowest)
```

**Permissions Matrix:**

| Role | Token Limit | Memory Access | System Context |
|------|-------------|---------------|----------------|
| Admin | Unlimited | ALL (public, private, system) | ✅ Full |
| Godfather | 100,000 | ALL private + public | ❌ None |
| Client | 4,000 | Own private + public | ❌ None |
| Blocked | 0 | None | ❌ None |

### 3. Session Manager (`src/memory/session_manager.py`)

**Tier 1 Memory - Short-term conversation history**

**Responsibilities:**
- Session lifecycle management (create, load, save, archive)
- Message persistence in JSON format
- Token counting and pruning
- Expiration detection (24 hours from last activity)
- Conversation history retrieval

**Storage Structure:**
```
data/sessions/
├── {session_id}/
│   ├── session.json          # Session metadata
│   └── messages/
│       ├── {msg_id_1}.json
│       ├── {msg_id_2}.json
│       └── ...
└── expired/
    └── YYYY-MM-DD/
        └── {session_id}/     # Archived sessions
```

**Session Metadata:**
```json
{
  "session_id": "uuid",
  "whatsapp_chat": "phone@c.us",
  "message_ids": ["uuid1", "uuid2"],
  "message_counter": 10,
  "created_at": "ISO-8601",
  "last_active": "ISO-8601",
  "total_tokens": 1500,
  "transferred_to_longterm": false,
  "storage_path": "path/to/session"
}
```

### 4. Memory Manager (`src/memory/memory_manager.py`)

**Tier 2 Memory - Long-term semantic memory**

**Responsibilities:**
- ChromaDB persistent vector database
- OpenAI embedding generation (text-embedding-3-small)
- Semantic search and recall
- Per-entity collection management
- Memory scope enforcement

**Collection Architecture:**
```
ChromaDB Collections:
├── memory_{entity_id}               # Main collection per user
├── memory_{entity_id}_public        # Public memories
├── memory_{entity_id}_private       # Private memories
├── memory_system_context            # Global system context
└── memory_global_client_context     # Global client context
```

**Memory Document Structure:**
```json
{
  "id": "uuid",
  "text": "conversation summary or fact",
  "metadata": {
    "chat_id": "phone@c.us",
    "timestamp": "ISO-8601",
    "scope": "PUBLIC|PRIVATE|SYSTEM",
    "entity": "entity_id",
    "session_id": "uuid",
    "source": "chat|document|system"
  },
  "embedding": [float array]
}
```

### 5. AI Handler (`src/handlers/ai_handler.py`)

**Responsibilities:**
- OpenAI API integration (GPT-4o-mini)
- System prompt construction
- Memory recall and context injection
- Response generation
- Session transfer to long-term memory
- Error handling with retries

**Processing Flow:**
1. Receive message + user context
2. Recall relevant memories from MemoryManager
3. Build system prompt with:
   - Constitution rules
   - Role-specific context
   - Recalled memories (up to 5)
   - Recent conversation history
4. Call OpenAI API
5. Return response
6. Store message in SessionManager

**Retry Logic:**
- API timeout: 3 retries, 2s wait
- Rate limit: 3 retries, 5s wait
- Generic errors: 3 retries, 2s wait

### 6. Media Extractors (`src/handlers/extractors/`)

**Feature 003 Phase 4 Complete - Document Analysis Integration**

**Responsibilities:**
- Extract text from images, PDFs, and DOCX files
- Analyze documents using AI (type, summary, key points)
- Single AI call optimization (~50% cost savings)
- Hebrew text support with UTF-8 encoding
- Graceful degradation on failures

**Extractor Architecture:**

```
MediaExtractor (Abstract Base)
├── ImageExtractor
│   └── Single Vision API call → text + analysis
├── PDFExtractor
│   └── Multi-page → aggregate analyses
└── DOCXExtractor
    └── python-docx + optional AI analysis
```

**MediaExtractor Interface Contract:**
```python
{
  "extracted_text": str | List[str],  # Text content
  "document_analysis": {               # AI-generated insights
    "document_type": str,              # receipt, invoice, contract, etc.
    "summary": str,                    # 1-2 sentence summary
    "key_points": List[str]            # Important information
  },
  "extraction_quality": str,           # high, medium, low, failed
  "warnings": List[str],               # Issues encountered
  "model_used": str                    # AI model or library used
}
```

**ImageExtractor** (`image_extractor.py`):
- Uses GPT-4o Vision API for text extraction AND analysis
- Single API call requests: text + document_type + summary + key_points
- Hebrew text support via enhanced prompt
- Layout preservation with empty line detection
- Quality assessment: high, medium, low based on AI confidence

**PDFExtractor** (`pdf_extractor.py`):
- Converts PDF pages to images using PyMuPDF
- Delegates to ImageExtractor for per-page processing
- Aggregates document analysis from all pages:
  - Document type: Most common across pages
  - Summary: Combined from all pages
  - Key points: Merged and deduplicated
- Returns List[str] for per-page text

**DOCXExtractor** (`docx_extractor.py`):
- Uses python-docx for deterministic text extraction
- Optional AI analysis via `analyze` parameter (default=True)
- When analyze=True: AI analyzes extracted text
- When analyze=False: Skip AI call, return document_analysis=None
- Preserves paragraph structure with double newlines

**Test Coverage:**
- 37 tests passing (100% success rate)
- 5 base interface tests
- 10 ImageExtractor tests
- 10 PDFExtractor tests
- 12 DOCXExtractor tests

**Cost Optimization:**
- Before: 2 AI calls (text + analysis) = $0.02-0.04 per document
- After: 1 AI call (combined) = $0.01-0.02 per document
- Savings: ~50% cost reduction + faster processing

### 7. Background Cleanup Thread (`src/background_threads.py`)

**Responsibilities:**
- Monitor for expired sessions (hourly)
- Execute atomic cleanup process
- Transfer sessions to long-term memory
- Maintain system health

**Cleanup Process (4 Steps):**

1. **Archive**: Move session files to `expired/YYYY-MM-DD/`
   - Update `storage_path` in session metadata
   - Keep in active index (still queryable)

2. **Transfer**: Send to ChromaDB via AIHandler
   - Generate conversation summary
   - Create embedding
   - Store in appropriate collection
   - Set `transferred_to_longterm = true`

3. **Remove**: Delete from active session index
   - Session no longer accessible via `get_session()`
   - Files remain in expired archive

4. **Mark**: Update session flags
   - `transferred_to_longterm = true`
   - Prevents duplicate transfers

## Data Flow

### Message Processing Flow

```
1. User sends WhatsApp message
   ↓
2. Green API receives → webhook to DeniDin
   ↓
3. WhatsApp Handler validates message type
   ↓
4. User Manager determines role & permissions
   ↓
5. Session Manager loads/creates session
   ↓
6. AI Handler:
   a. Recalls relevant memories
   b. Builds context
   c. Calls OpenAI
   d. Gets response
   ↓
7. Session Manager:
   a. Stores user message
   b. Stores AI response
   c. Updates token count
   d. Prunes if needed
   ↓
8. WhatsApp Handler sends response to user
```

### Session Lifecycle

```
Session Created (first message)
   ↓
Active (messages exchanged)
   ↓ 24 hours of inactivity
Expired (marked for cleanup)
   ↓ Background thread runs
Archived (moved to expired/YYYY-MM-DD/)
   ↓
Transferred (sent to ChromaDB)
   ↓
Removed (deleted from active index)
```

## Configuration

### Application Configuration (`config/config.json`)

```json
{
  "greenapi_id_instance": "...",
  "greenapi_api_token_instance": "...",
  "openai_api_key": "...",
  "openai_model": "gpt-4o-mini",
  "temperature": 0.7,
  "max_tokens": 1000,
  "poll_interval_seconds": 5,
  "data_root": "data",
  "enable_memory_system": true,
  "session_ttl_hours": 24,
  "cleanup_interval_seconds": 3600,
  "roles": {
    "admin_phones": ["+1234567890"],
    "godfather_phones": ["+0987654321"],
    "blocked_phones": []
  },
  "token_limits": {
    "admin": -1,
    "godfather": 100000,
    "client": 4000,
    "blocked": 0
  }
}
```

## Error Handling

### Error Codes

- **ERR-MEMORY-001**: ChromaDB initialization failure
- **ERR-MEMORY-002**: Embedding generation failure
- **ERR-SESSION-001**: Session file corruption
- **ERR-AI-001**: OpenAI API timeout
- **ERR-AI-002**: OpenAI rate limit exceeded
- **ERR-RBAC-001**: Blocked user attempted access

### Error Recovery

- **API Failures**: Automatic retry with exponential backoff
- **Corrupt Sessions**: Create new session, log error
- **Memory Failures**: Disable memory system, continue without recall
- **ChromaDB Down**: Queue transfers, retry on next cycle

## Performance Characteristics

### Latency
- **Session Lookup**: < 10ms (in-memory index)
- **Memory Recall**: 50-200ms (ChromaDB semantic search)
- **OpenAI API**: 500-2000ms (depends on response length)
- **Total Response Time**: 1-3 seconds

### Scalability
- **Concurrent Users**: Limited by OpenAI API rate limits
- **Session Storage**: Filesystem-based, scales to 100K+ sessions
- **Memory Storage**: ChromaDB handles millions of vectors
- **Background Processing**: Single-threaded, processes 1 session/second

### Resource Usage
- **Memory**: ~200MB base + ~100KB per active session
- **Disk**: ~10KB per session + ~5KB per message
- **CPU**: < 5% during idle, 20-40% during message processing

## Testing

### Test Coverage: 92%

**100% Coverage:**
- Models (user, message, state, document, config)
- Utils (state, user_manager)
- Config (media_config)
- **Extractors (MediaExtractor, ImageExtractor, PDFExtractor, DOCXExtractor)** - 37 tests

**90%+ Coverage:**
- Memory Manager (96%)
- Session Manager (93%)
- Logger (93%)

**80%+ Coverage:**
- AI Handler (88%)

**Needs Improvement:**
- WhatsApp Handler (70%) - error paths
- Background Threads (66%) - cleanup logic

### Test Categories
- **Unit Tests**: 337+ tests for individual components
  - Extractors: 37 tests (5 base + 10 image + 10 pdf + 12 docx)
  - Core components: 300+ tests
- **Integration Tests**: 87 tests for cross-component workflows
- **RBAC Tests**: 40+ tests for permission enforcement
- **Memory Tests**: 50+ tests for storage and recall

## Deployment

### Production Environment
- **Platform**: Linux server
- **Python**: 3.9+
- **Data Directory**: Persistent volume mount
- **Logs**: Rotating file logs (100MB max)
- **Process Management**: systemd service
- **Monitoring**: Log-based health checks

### Startup Sequence
1. Load configuration
2. Initialize ChromaDB client
3. Initialize OpenAI client
4. Recover orphaned sessions
5. Start background cleanup thread
6. Start Green API webhook listener

### Shutdown Sequence
1. Stop accepting new messages
2. Complete in-flight message processing
3. Stop background cleanup thread
4. Save all active sessions
5. Close ChromaDB connection
6. Exit cleanly

## Security

### API Key Management
- All API keys in config.json (not in code)
- Config file in .gitignore
- Keys masked in logs

### Access Control
- Phone number-based authentication
- Role-based permissions
- Memory scope isolation
- No cross-user data leakage

### Data Privacy
- Private memories only accessible by owner + Godfather/Admin
- Public memories visible to all users
- System context only visible to Admin
- Session data isolated per user

## Future Enhancements

See `specs/in-definition/`, `specs/P0/`, `specs/P1/`, `specs/P2/` for planned features:

- **003**: Media & document processing
  - ✅ Phase 1-3: Media Model, Text Extractors (Complete)
  - ✅ Phase 4: Enhanced Extractors with Document Analysis (Complete - PR #64)
  - 📋 Phase 5: Document Retrieval (search and re-send)
  - 📋 Phase 6: WhatsApp Integration
- **013**: Proactive WhatsApp messaging
- **014**: Entity extraction from group messages
- **015**: Topic-based access control
- **005**: MCP morning green receipt integration
- **008**: Scheduled proactive chats
- **009**: Agentic workflow builder
