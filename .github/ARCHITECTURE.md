# DeniDin Architecture

**Version**: 1.1 | **Last Updated**: 2026-07-07 | **Status**: Production

## Overview

DeniDin is a WhatsApp AI assistant built on a multi-tier memory architecture with role-based access control. The system processes messages through a pipeline that includes session management, AI response generation, semantic memory recall, and automated background cleanup.

**Repo structure**: this document describes `apps/denidin-app/`, one of two independently deployable apps in this monorepo under `apps/`. The other, `apps/morning-mcp-app/`, is a much smaller standalone Morning/Green Invoice API client — see "Sibling App: morning-mcp-app" near the end of this document. All `src/...` paths below are relative to `apps/denidin-app/`.

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

### 2. User Manager (`src/managers/user_manager.py`)

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

### 3. Session Manager (`src/managers/session_manager.py`)

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

### 4. Memory Manager (`src/managers/memory_manager.py`)

**Tier 2 Memory - Long-term semantic memory**

**Responsibilities:**
- ChromaDB persistent vector database
- OpenAI embedding generation (model configurable via `config.ai_embedding_model`, default `text-embedding-3-large`)
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

### 4a. Timestamp Representation (all stores, both apps)

**One representation, everywhere: Israel local time (`Asia/Jerusalem`), timezone-aware.**
Established by bugfix-037 (2026-08-10), which replaced CONSTITUTION §II's former
UTC-everywhere rule — see that section for the binding rule and the reasoning.

| Where | Value | Notes |
|---|---|---|
| Log lines (both apps) | `2026-08-09 06:00:27+0300` | `LocalTimeFormatter`; the offset is always printed |
| `captured_at`, `message_timestamp` (ledger events) | `2026-08-09T06:00:27.399417+03:00` | full ISO-8601, real offset |
| Session `created_at` / `last_active` | ISO-8601 with offset | |
| `morning-mcp-app` status file `updated_at` | ISO-8601 with offset | read back by `morning_mcp_locator` |
| `event_date`, `event_time`, `event_id` (ledger events) | `09/08/2026`, `06:00`, `B09082606000` | Events.csv column formats — no offset field exists in that schema, and none is needed now that the whole system is local |
| Unix epoch fields (`Message.timestamp`, Green API's own `timestamp`) | integer seconds | unaffected — an epoch is an instant, not a representation |

All datetimes are **aware**; a naive local datetime is forbidden (it breaks comparisons and
gets DST wrong twice a year). `now_local()` / `to_local()` / `local_from_timestamp()` in each
app's `utils/time_utils.py` are the only sanctioned constructors.

**Pre-2026-08-10 records** still carry `+00:00`, and pre-2026-08-10 log lines are unlabelled
UTC. They stay valid and compare correctly against new records because both sides are aware —
this was a fix-forward change with no migration. Only the *log lines* from before that date
are genuinely ambiguous, since they carry no offset at all.

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

**Feature 003 - COMPLETE ✅ (All 7 Phases Implemented)**

**Responsibilities:**
- Extract text from images, PDFs, and DOCX files
- Analyze documents using AI (type, summary, key points)
- Business document processing (contracts, receipts, invoices, court resolutions)
- Single AI call optimization (~50% cost savings)
- Hebrew text support with UTF-8 encoding
- Graceful degradation on failures

**Extractor Architecture:**

```
MediaExtractor (Abstract Base)
├── ImageExtractor
│   └── Single Vision API call → text + analysis
├── PDFExtractor
│   └── Multi-page → aggregate analyses (max 10 pages)
└── DOCXExtractor
    └── python-docx + GPT-4o-mini analysis
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

### 7. Background Cleanup Thread (`src/services/cleanup_service.py`)

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

### Test Coverage (per-component figures below are historical/approximate - re-run `pytest --cov=src --cov-report=html` for current numbers)

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
As of 2026-07-30 (Feature 029 split the single `expensive` marker into `billed` + `expensive`): **618 total tests** (`pytest tests/ --collect-only -q`) - **563 run by default**, **46 marked `@pytest.mark.billed`** (real, text-only OpenAI API calls; cheap, can run freely - no approval/one-at-a-time restriction) and **9 marked `@pytest.mark.expensive`** (real vision/image/PDF/DOCX OpenAI API calls; costlier, require explicit human approval, run one at a time - see CONSTITUTION.md §VII and CLAUDE.md).
- Unit tests: `tests/unit/`
- Integration tests (E2E from external entry point, no mocking): `tests/integration/`
- Billed tests (real, text-only API calls): `tests/billed/`
- Expensive tests (real vision/image/PDF/DOCX API calls): `tests/expensive/`

## Deployment

Two supported deployment paths - Docker is the recommended default for new deployments; systemd remains valid for existing bare-metal hosts.

### Docker (recommended)
```bash
cd apps/denidin-app
docker build -t denidin-app .
docker run --rm \
  -v "$(pwd)/config:/app/config" \
  -v "$(pwd)/data:/app/data" \
  -v "$(pwd)/logs:/app/logs" \
  denidin-app
```
Or via the repo-root `docker-compose.yml`: `docker compose up denidin-app`. The container runs `denidin.py` directly as PID 1 (it already handles SIGINT/SIGTERM) - the PID-file scripts (`run_denidin.sh`/`stop_denidin.sh`) are bare-metal-only and are not used inside the container. `config/`, `data/`, and `logs/` are mounted volumes since `config/config.json` is gitignored and `data/`/`logs/` are mutable runtime state.

### Bare Metal / systemd
- **Platform**: Linux server
- **Python**: 3.9+
- **Data Directory**: Persistent volume mount
- **Logs**: Rotating file logs (100MB max)
- **Process Management**: systemd service
- **Monitoring**: Log-based health checks

See `apps/denidin-app/DEPLOYMENT.md` for the full systemd setup guide.

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

See `specs/in-progress/` and `specs/backlog/` for planned features:

- **003**: Media & document processing
  - ✅ Phase 1-3: Media Model, Text Extractors (Complete)
  - ✅ Phase 4: Enhanced Extractors with Document Analysis (Complete - PR #64)
  - 📋 Phase 5: Document Retrieval (search and re-send)
  - 📋 Phase 6: WhatsApp Integration
- **013**: Proactive WhatsApp messaging
- **014**: Entity extraction from group messages
- **015**: Topic-based access control
- **✅ 018**: DeniDin ↔ Morning MCP integration - godfather/admin invoicing via natural Hebrew, real remote MCP tool over the Responses API (Complete - MVP merged; audit logging + run-both-apps docs remain open in `specs/done/v0.0.1/018-denidin-morning-mcp-integration/tasks.md`)
- **005**: MCP morning green receipt integration (receipt *parsing*, not invoicing) - client library extracted to `apps/morning-mcp-app/`; still tracked in `specs/done/v0.0.1/005-mcp-morning-green-receipt/` - see "Sibling App: morning-mcp-app" below for the invoicing MCP server 018 already built
- **008**: Scheduled proactive chats
- **009**: Agentic workflow builder

## Sibling App: morning-mcp-app

`apps/morning-mcp-app/` is a separate, independently deployable app in this same monorepo (own `src/`, `tests/`, `config/`, `requirements.txt`, `Dockerfile`, `Makefile`) - it does **not** import from or share code with `apps/denidin-app/`. The two apps talk to each other only over HTTP: `apps/denidin-app` reaches this app's MCP server as a **remote MCP tool** via OpenAI's Responses API, over a real ngrok tunnel (never a direct import).

**Current state** (as of Feature 018):
- `src/denidin_mcp_morning/morning_client.py` - `MorningClient` (create/list/get invoices, `requests` + urllib3 retry/backoff)
- `src/denidin_mcp_morning/auth.py` - `MorningAuth` (API key ID/secret → JWT exchange, token refresh)
- `src/denidin_mcp_morning/server.py` - a FastMCP server (streamable-HTTP) registering 7 tools bound to one `MorningClient`: `create_invoice`, `list_invoices`, `get_invoice_details`, `update_invoice_status`, `add_client`, `get_financial_summary`, `download_invoice_pdf` (`send_invoice` from the original 8-tool design was dropped from scope). `build_asgi_app()` wraps it in `BearerTokenMiddleware` (single shared secret) plus an unauthenticated `/health` route used for tunnel-liveness checks.
- `./run_morning_mcp.sh` / `./stop_morning_mcp.sh` run the server as a standalone long-lived process (PID-file, single-instance enforced) alongside an ngrok tunnel, writing the live URL to `running_status.json` for `apps/denidin-app` (and this app's own billed E2E tests) to discover.
- Remaining polish (audit logging, run-both-apps docs) tracked in `specs/done/v0.0.1/018-denidin-morning-mcp-integration/tasks.md` Phase 4; the separate receipt-*parsing* feature (005) is still unbuilt.

**Testing**: `apps/morning-mcp-app/tests/integration/` hits the real Morning **sandbox** API (no mocking, per constitution) - config in its own `config/{config.example.json,config.test.json,config.json}` (flat shape: `api_key_id`/`api_key_secret`/`api_url`, plus an `mcp` block: `auth_token`/`ngrok_authtoken`/`status_file`). `tests/billed/test_openai_invokes_mcp_e2e.py` (real, text-only OpenAI calls - `@pytest.mark.billed` since Feature 029; `tests/expensive/` exists but currently has zero tests in this app) drives the server through a real OpenAI Responses API call, reusing an already-running standalone server's tunnel when one is live (see `discover_running_server()` in `tests/e2e_helpers.py`) rather than always spinning up a fresh tunnel, to avoid an ngrok cold-start flake.

**Deployment**: `apps/morning-mcp-app/Dockerfile` builds a lightweight `python:3.9-slim` image (`ENV PYTHONPATH=/app/src` so the package is importable). Runnable standalone or via the repo-root `docker-compose.yml`.
