# DeniDin - WhatsApp AI Chatbot with Memory

DeniDin is a WhatsApp chatbot with a sophisticated two-tier memory system. It receives messages through Green API, forwards them to OpenAI with conversation context and semantic memory recall, and returns intelligent, context-aware responses.

## Features

### Core Features (v1.0)
- ✅ Receive WhatsApp messages via Green API polling mechanism
- ✅ Forward messages to ChatGPT (OpenAI GPT-4o-mini)
- ✅ Send AI responses back to WhatsApp
- ✅ Sequential message processing (maintains order)
- ✅ Configurable polling interval and AI parameters
- ✅ Comprehensive error handling and logging
- ✅ Message truncation for long AI responses (4000 char limit)

### Memory System (Phases 1-6 Complete)
- ✅ **Session Management**: Conversation history with UUID-based sessions
- ✅ **Long-term Memory**: Semantic memory using ChromaDB with OpenAI embeddings
- ✅ **Automatic Recall**: AI automatically recalls relevant memories during conversations
- ✅ **Session Expiration**: 24-hour session timeout with automatic transfer to long-term memory
- ✅ **Startup Recovery**: Recovers orphaned sessions on bot restart
- ✅ **Role-based Token Limits**: 4,000 tokens for clients, 100,000 for godfather
- ✅ **Commands**: `/reset` to manually clear session and transfer to long-term memory
- ✅ **Feature Flag**: Controlled by `enable_memory_system` flag for safe deployment

## Requirements

- Python 3.8+ (Python 3.11 recommended)
- WhatsApp Business account with Green API credentials
- OpenAI API key

## Setup Instructions

> **Note for AI Assistants:** 
> - All commands must be run from `/Users/yaronl/personal/DeniDin/apps/denidin-app/` directory
> - Always prefix commands with: `cd /Users/yaronl/personal/DeniDin/apps/denidin-app &&`
> - Main git branch is `master`, not `main`

### 1. Clone and Navigate

```bash
cd apps/denidin-app/
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# Activate virtual environment:
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Credentials

Copy the single example configuration template once per environment (see "Environments (dev/prod)" in the repo-root `CLAUDE.md`):

```bash
cp config/config.example.json config/config.dev.json
cp config/config.example.json config/config.prod.json
```

Edit `config/config.dev.json`/`config/config.prod.json` and replace the placeholder values:

```json
{
  "green_api_instance_id": "YOUR_GREEN_API_INSTANCE_ID",
  "green_api_token": "YOUR_GREEN_API_TOKEN",
  "openai_api_key": "YOUR_OPENAI_API_KEY",
  "ai_model": "gpt-5.6-luna",
  "ai_vision_model": "gpt-4o",
  "ai_embedding_model": "text-embedding-3-large",
  "system_message": "You are a helpful AI assistant named DeniDin.",
  "max_tokens": 1000,
  "log_level": "INFO"
}
```

**Configuration Options:**

- `green_api_instance_id`: Your Green API instance ID (from Green API dashboard)
- `green_api_token`: Your Green API token
- `openai_api_key`: Your OpenAI API key
- `ai_model`: OpenAI model for text conversations (e.g., "gpt-3.5-turbo", "gpt-4o-mini") — default "gpt-5.6-luna", not "gpt-4o-mini" or any other variant
- `ai_vision_model`: OpenAI model for image/PDF extraction (e.g., "gpt-4o-mini", "gpt-4o") — default "gpt-4o" (not mini: gpt-4o-mini was found to silently skip calling the ledger-event tool alongside extraction, Feature 024)
- `ai_embedding_model`: OpenAI embedding model for long-term memory search (e.g., "text-embedding-3-small", "text-embedding-3-large") — default "text-embedding-3-large"
- `system_message`: System prompt for the AI assistant
- `max_tokens`: Maximum tokens in AI response
- `log_level`: Logging verbosity ("INFO" or "DEBUG")
- `data_root`: Root directory for data storage (default: "data")
- `godfather_phone`: WhatsApp ID of godfather user (format: "PHONE@c.us")

**Memory System Configuration (Optional):**

```json
{
  "feature_flags": {
    "enable_memory_system": false
  },
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
      "top_k_results": 5,
      "min_similarity": 0.15
    }
  }
}
```

Memory system is **disabled by default** (`enable_memory_system: false`). To enable:
1. Set `enable_memory_system: true` in config
2. Configure `godfather_phone` with the admin WhatsApp ID
3. Restart the application

See [Memory System Usage](#memory-system-usage) section below for details.

**⚠️ IMPORTANT:** Never commit `config/config.dev.json`/`config/config.prod.json` to version control! They're already in `.gitignore`.

### 5. Run the Bot

Both apps run **only as Docker containers**, one environment at a time selected explicitly:

```bash
./run_denidin.sh dev    # or: prod
```

The bot will:
1. Build (if needed) and start the `denidin-app-<env>` container via `docker compose`
2. Load configuration from that environment's `config/config.<env>.json`
3. Start polling Green API for incoming WhatsApp messages
4. Forward messages to ChatGPT
5. Send AI responses back to WhatsApp
6. Log all activity to `logs/<env>/denidin.log`

**⚠️ dev and prod share one real Green API instance** (one paid WhatsApp number, no sandbox tier) — only one of `denidin-app-dev`/`denidin-app-prod` should be actively running at a time whenever real WhatsApp traffic could arrive. See `specs/019-env-separation/quickstart.md` for the hand-off procedure.

### 6. Stop the Bot

```bash
./stop_denidin.sh dev    # or: prod
```

This stops only that environment's container (`docker compose stop`) — the other environment, if running, is unaffected.

### Docker (what the scripts above wrap)

```bash
docker compose --project-directory ../.. -f ../../docker/docker-compose.dev.yml up -d denidin-app-dev    # or docker-compose.prod.yml / denidin-app-prod
```

## Architecture

### System Overview

```
┌─────────────┐        ┌──────────────────────┐        ┌──────────────┐
│  WhatsApp   │        │    DeniDin Bot       │        │   OpenAI     │
│   Business  │◄──────►│    (denidin.py)      │◄──────►│   ChatGPT    │
│   Account   │  Green │                      │  API   │              │
│             │  API   │  ┌────────────────┐  │        │              │
└─────────────┘        │  │ SessionManager │  │        └──────────────┘
                       │  │ (Conversation) │  │
                       │  └────────────────┘  │
                       │          │           │
                       │          ▼           │
                       │  ┌────────────────┐  │
                       │  │ MemoryManager  │  │
                       │  │  (ChromaDB)    │  │
                       │  └────────────────┘  │
                       └──────────────────────┘
```

### Component Flow (with Memory)

```
1. WhatsApp Message Received (Green API Polling)
        ↓
2. WhatsAppHandler.process_notification()
        ↓
3. Validate message type (text only)
        ↓
4. SessionManager.add_message(role="user")
        ↓
5. SessionManager.get_conversation_history()
        ↓
6. MemoryManager.recall() - Semantic search
        ↓
7. AIHandler.create_request() (with history + memories)
        ↓
8. OpenAI API call (with retry logic)
        ↓
9. SessionManager.add_message(role="assistant")
        ↓
10. AIHandler.get_response()
        ↓
11. Truncate if >4000 chars
        ↓
12. WhatsAppHandler.send_response()
        ↓
13. Log message tracking (message_id, timestamp)
```

### Key Components

- **denidin.py**: Main entry point, bot initialization, signal handling, /reset command
- **WhatsAppHandler**: Green API integration, message validation, response sending
- **AIHandler**: OpenAI integration, request formatting, error handling, memory integration
- **SessionManager**: Conversation history, token management, session expiration
- **MemoryManager**: ChromaDB semantic search, embedding generation, long-term storage
- **BotConfiguration**: JSON/YAML config loading, validation
- **Logger**: Rotating file + console logging with INFO/DEBUG levels
- **MessageState**: Track last processed message to prevent duplicates

## Project Structure

```
apps/denidin-app/
├── denidin.py                  # Main entry point (223 lines)
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── DEPLOYMENT.md              # Production deployment guide
├── .gitignore                 # Git ignore rules
├── .pylintrc                  # Linter configuration
├── mypy.ini                   # Type checker configuration
├── config/
│   ├── config.example.json                                  # Example configuration (single template, both envs)
│   └── config.dev.json / config.prod.json                   # Actual per-environment credentials (gitignored)
├── src/                       # Source code (500+ statements, 89% coverage)
│   ├── handlers/
│   │   ├── ai_handler.py      # OpenAI API + memory integration
│   │   └── whatsapp_handler.py # Green API integration
│   ├── memory/
│   │   ├── session_manager.py  # Conversation history
│   │   └── memory_manager.py   # ChromaDB semantic memory
│   ├── models/
│   │   ├── config.py          # Configuration model
│   │   ├── message.py         # Message models
│   │   └── state.py           # State persistence
│   └── utils/
│       ├── logger.py          # Logging setup
│       └── state.py           # State utilities
├── data/                      # Runtime data (gitignored)
│   ├── sessions/              # Session JSON files
│   ├── memory/                # ChromaDB database
│   └── constitution/          # Constitution files
├── tests/                     # 212 tests (100% passing)
│   ├── unit/                  # 145 unit tests
│   ├── integration/           # 67 integration tests
│   └── fixtures/              # Test data
├── logs/                      # Application logs (gitignored)
└── htmlcov/                   # Coverage reports
```

## Memory System Usage

### Overview

The memory system consists of two layers:

1. **Short-term Memory (SessionManager)**: Stores recent conversation history per session
   - Automatically manages conversation context
   - Role-based token limits (4K for clients, 100K for godfather)
   - 24-hour session timeout
   - JSON storage in `data/sessions/`

2. **Long-term Memory (MemoryManager)**: Semantic memory across all conversations
   - ChromaDB vector database
   - OpenAI embeddings (`ai_embedding_model`, default text-embedding-3-large)
   - Automatic recall based on message relevance
   - Persistent storage in `data/memory/`

### How It Works

**For Users:**
1. Send messages normally via WhatsApp
2. Bot automatically maintains conversation context
3. Relevant past information is recalled automatically
4. No special commands needed for basic usage

**Session Lifecycle:**
```
New Message → Create/Resume Session → Add to History
                      ↓
              Get Recent History (within token limit)
                      ↓
              Search Long-term Memory
                      ↓
              Send to AI (history + memories + new message)
                      ↓
              Store AI Response in Session
                      ↓
              After 24h inactive → Transfer to Long-term Memory
```

### Commands

#### `/reset` - Clear Session and Transfer to Memory

Manually ends the current session and transfers it to long-term memory.

**Usage:**
```
/reset
```

**What happens:**
1. Current session is cleared
2. All conversation messages are summarized
3. Summary is stored in long-term memory
4. Fresh session starts
5. Confirmation message sent

**When to use:**
- Want to start a completely fresh conversation
- Finished a major topic and moving to something new
- Session feels cluttered or confusing

**Note:** Sessions automatically expire after 24 hours of inactivity, so manual `/reset` is rarely needed.

### Configuration

**Enable Memory System:**
```json
{
  "feature_flags": {
    "enable_memory_system": true
  },
  "godfather_phone": "972501234567@c.us"
}
```

**Memory Settings:**
```json
{
  "memory": {
    "session": {
      "max_tokens_by_role": {
        "client": 4000,
        "godfather": 100000
      },
      "session_timeout_hours": 24
    },
    "longterm": {
      "enabled": true,
      "top_k_results": 5,
      "min_similarity": 0.7
    }
  }
}
```

**Key Settings:**
- `max_tokens_by_role`: Controls how much conversation history to include
  - Client: 4,000 tokens (~15-20 message exchanges)
  - Godfather: 100,000 tokens (~300-400 exchanges)
- `session_timeout_hours`: When to auto-expire sessions (default: 24)
- `top_k_results`: Max memories to recall (default: 5)
- `min_similarity`: Minimum relevance score for recall (default: 0.7)

### Data Storage

**Session Files:**
- Location: `data/sessions/{session_id}/session.json`
- Format: JSON with messages, timestamps, metadata
- Cleanup: Expired sessions moved to `data/sessions/expired/`

**Long-term Memory:**
- Location: `data/memory/chroma.sqlite3`
- Format: ChromaDB vector database
- Embeddings: OpenAI, model configurable via `ai_embedding_model` (default text-embedding-3-large)

**Backup Recommendations:**
- Backup `data/sessions/` for conversation history
- Backup `data/memory/` for long-term memories
- Both directories are gitignored by default

## Testing

### Running Tests

```bash
# Run all tests
python3 -m pytest tests/ -v

# Run unit tests only
python3 -m pytest tests/unit/ -v

# Run integration tests only
python3 -m pytest tests/integration/ -v

# Run with coverage report
python3 -m pytest tests/ --cov=src --cov-report=html
# View coverage: open htmlcov/index.html
```

### Manual Testing

Send a WhatsApp message to your business number. DeniDin should:
1. Receive the message via Green API
2. Forward it to ChatGPT
3. Send the AI response back to WhatsApp
4. Log the interaction in `logs/denidin.log`

## Code Quality

- **Pylint Score**: 8.35/10
- **Test Coverage**: 89% (323 statements, 37 missed)
- **Type Hints**: Comprehensive (mypy configuration included)
- **Documentation**: Google-style docstrings on all public methods

Run quality checks:
```bash
# Linter
python3 -m pylint src/ denidin.py --rcfile=.pylintrc

# Type checker
python3 -m mypy src/ --config-file=mypy.ini
```

## Logging

- **INFO level**: Application events, incoming/outgoing messages, errors
- **DEBUG level**: Detailed parsing, state changes, API request/response details
- **File**: `logs/denidin.log` (rotates at 10MB, keeps 5 backups)
- **Console**: stderr output with same format

Change `log_level` in `config/config.json` to switch between levels.

## Troubleshooting

### Bot doesn't start

**Problem**: Bot exits immediately with error message

**Solutions**:
- Check that `config/config.json` exists: `ls -la config/`
- Verify JSON syntax is valid: `python3 -m json.tool config/config.json`
- Ensure all required fields present: `green_api_instance_id`, `green_api_token`, `openai_api_key`
- Verify Python 3.8+ is installed: `python3 --version`
- Ensure virtual environment is activated: `which python3` should show venv path

**Logs to check**: stderr output shows validation errors

---

### Messages not received

**Problem**: Bot runs but doesn't respond to WhatsApp messages

**Solutions**:
- Verify Green API credentials are correct in `config/config.json`
- Check Green API instance status in dashboard (must be "authorized")
- Test Green API connection: `python3 -m pytest tests/billed/test_real_api_connectivity.py -m billed -v`
- Review `logs/denidin.log` for polling errors
- Check WhatsApp business account is logged in on phone

**Logs to check**: `grep "polling" logs/denidin.log` or `grep "ERROR" logs/denidin.log`

---

### AI responses not sent

**Problem**: Bot receives messages but doesn't respond

**Solutions**:
- Verify OpenAI API key is valid: check https://platform.openai.com/api-keys
- Check OpenAI account has credits: https://platform.openai.com/account/billing
- Review error logs for API quota/rate limit issues: `grep "OpenAI" logs/denidin.log`
- Test OpenAI connection: `python3 -m pytest tests/billed/test_real_api_connectivity.py::TestRealOpenAPIConnectivity -m billed -v`
- Verify `ai_model` in config is available (e.g., "gpt-4o-mini", "gpt-3.5-turbo")
- Check for network/firewall issues blocking api.openai.com

**Logs to check**: `grep "AI response" logs/denidin.log` or `grep "OpenAI API" logs/denidin.log`

---

### Long messages truncated

**Problem**: AI responses are cut off at 4000 characters

**Solution**: This is expected behavior to fit WhatsApp's message limit. The bot appends "..." to indicate truncation.

**Workaround**: Ask shorter questions or request summaries

**Future**: Multi-message splitting will be added in Phase 2

---

### Bot crashes or hangs

**Problem**: Bot stops responding or exits unexpectedly

**Solutions**:
- Check for unhandled exceptions in logs: `grep "Exception" logs/denidin.log`
- Verify sufficient disk space for logs: `df -h`
- Review memory usage: `ps aux | grep denidin`
- Test with DEBUG logging: set `log_level: "DEBUG"` in config
- Run integration tests: `python3 -m pytest tests/integration/ -v`

**Logs to check**: Last 50 lines of log: `tail -50 logs/denidin.log`

---

### Rate limiting errors

**Problem**: "Rate limit exceeded" errors in logs

**Solutions**:
- Wait 60 seconds before retrying (bot auto-retries with backoff)
- Reduce message volume or use a higher-tier OpenAI plan
- Check `max_retries` setting in config (default: 3)
- Monitor OpenAI usage dashboard

**Logs to check**: `grep "rate limit" logs/denidin.log`

---

### Group chat issues

**Problem**: Bot responds to all group messages or doesn't respond when mentioned

**Solutions**:
- Ensure bot name "DeniDin" appears in group messages to trigger response
- Check group chat detection: `grep "group" logs/denidin.log`
- Verify `is_bot_mentioned_in_group()` logic in `src/handlers/whatsapp_handler.py`
- Test with explicit mention: "Hey @DeniDin, ..."

**Logs to check**: `grep "mentioned" logs/denidin.log`

## FAQ

**Q: How much does it cost to run DeniDin?**  
A: Costs depend on message volume and OpenAI models used:
- Green API: ~$10-20/month for WhatsApp Business API access
- OpenAI text (`ai_model`, default `gpt-5.6-luna`): see OpenAI's current pricing page for this model — not `gpt-4o-mini` or any other variant
- OpenAI vision (`ai_vision_model`, default `gpt-4o`): ~$2.50/$10.00 per 1M input/output tokens, used for image/PDF extraction — not `gpt-4o-mini` (Feature 024: `gpt-4o-mini` was found to silently skip calling the ledger-event tool alongside extraction, so vision defaults to the stronger model despite the cost)
- OpenAI embeddings (`ai_embedding_model`, default `text-embedding-3-large`): ~$0.13 per 1M tokens, used for long-term memory search
- Actual monthly cost depends on message/image volume and current per-token pricing for the configured models — check OpenAI's pricing page for `gpt-5.6-luna` and `gpt-4o`

**Q: Can I change the AI models?**  
A: Yes! Three independently configurable models in `config/config.json`: `ai_model` (text), `ai_vision_model` (image/PDF extraction), `ai_embedding_model` (long-term memory embeddings). Restart bot after changing.

**Q: Why polling instead of webhooks?**  
A: Phase 1 uses polling for simplicity. Webhooks will be added in future phases for lower latency and resource usage.

**Q: How do I deploy to production?**  
A: See `DEPLOYMENT.md` for systemd service setup, log monitoring, and best practices.

**Q: Can DeniDin handle images or voice notes?**  
A: Not yet. Phase 1 only supports text messages. Media support planned for future phases.

## Next Steps (Future Phases)

- Phase 2: Conversation context and memory
- Phase 3: Multi-message splitting for long responses
- Phase 4: Enhanced error recovery and monitoring
- Phase 5: Webhook-based message reception
- Phase 6: Media support (images, voice notes, videos)

## License

[Your License Here]

## Support

For issues or questions, please refer to:
- Project documentation: `specs/001-whatsapp-chatbot-passthrough/`
- Deployment guide: `DEPLOYMENT.md`
- Contributing guidelines: `CONTRIBUTING.md`
- Test suite: `python3 -m pytest tests/ -v`

