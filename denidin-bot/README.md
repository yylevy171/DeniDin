# DeniDin - WhatsApp AI Chatbot Passthrough

DeniDin is a WhatsApp chatbot that acts as a passthrough relay between a WhatsApp Business account and AI chat services (initially ChatGPT via OpenAI). The bot receives messages through Green API, forwards them to the AI service, and returns responses back to WhatsApp.

## Features (Phase 1)

- ✅ Receive WhatsApp messages via Green API polling mechanism
- ✅ Forward messages to ChatGPT (OpenAI)
- ✅ Send AI responses back to WhatsApp
- ✅ Sequential message processing (maintains order)
- ✅ Configurable polling interval and AI parameters
- ✅ Comprehensive error handling and logging
- ✅ Message truncation for long AI responses (4000 char limit)

## Requirements

- Python 3.8+ (Python 3.11 recommended)
- WhatsApp Business account with Green API credentials
- OpenAI API key

## Setup Instructions

> **Note for AI Assistants:** 
> - All commands must be run from `/Users/yaronl/personal/DeniDin/denidin-bot/` directory
> - Always prefix commands with: `cd /Users/yaronl/personal/DeniDin/denidin-bot &&`
> - Main git branch is `master`, not `main`

### 1. Clone and Navigate

```bash
cd denidin-bot/
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

Copy the example configuration file:

```bash
cp config/config.example.json config/config.json
```

Edit `config/config.json` and replace the placeholder values:

```json
{
  "green_api_instance_id": "YOUR_GREEN_API_INSTANCE_ID",
  "green_api_token": "YOUR_GREEN_API_TOKEN",
  "openai_api_key": "YOUR_OPENAI_API_KEY",
  "ai_model": "gpt-3.5-turbo",
  "system_message": "You are a helpful AI assistant named DeniDin.",
  "max_tokens": 1000,
  "temperature": 0.7,
  "log_level": "INFO",
  "poll_interval_seconds": 5,
  "max_retries": 3
}
```

**Configuration Options:**

- `green_api_instance_id`: Your Green API instance ID (from Green API dashboard)
- `green_api_token`: Your Green API token
- `openai_api_key`: Your OpenAI API key
- `ai_model`: OpenAI model to use (e.g., "gpt-3.5-turbo", "gpt-4o-mini")
- `system_message`: System prompt for the AI assistant
- `max_tokens`: Maximum tokens in AI response
- `temperature`: AI creativity level (0.0-1.0)
- `log_level`: Logging verbosity ("INFO" or "DEBUG")
- `poll_interval_seconds`: How often to check for new messages (default: 5)
- `max_retries`: Number of retry attempts for failed API calls

**⚠️ IMPORTANT:** Never commit `config/config.json` to version control! It's already in `.gitignore`.

### 5. Run the Bot

```bash
./run_denidin.sh
```

The bot will:
1. Load configuration from `config/config.json`
2. Check for existing bot instances (prevents duplicates)
3. Start polling Green API for incoming WhatsApp messages
4. Forward messages to ChatGPT
5. Send AI responses back to WhatsApp
6. Log all activity to `logs/bot.log`

**Alternative (manual start):**
```bash
python3 denidin.py
```

### 6. Stop the Bot

```bash
./stop_denidin.sh
```

This will gracefully shut down the bot (sends SIGTERM, waits for cleanup).

**Alternative:**
Press `Ctrl+C` if running manually, or use `kill -TERM <PID>`.

## Architecture

### System Overview

```
┌─────────────┐        ┌──────────────────┐        ┌──────────────┐
│  WhatsApp   │        │   DeniDin Bot    │        │   OpenAI     │
│   Business  │◄──────►│   (denidin.py)   │◄──────►│   ChatGPT    │
│   Account   │  Green │                  │  API   │              │
│             │  API   │                  │        │              │
└─────────────┘        └──────────────────┘        └──────────────┘
                              │
                              │ Manages
                              ▼
                    ┌────────────────────┐
                    │   Core Components  │
                    ├────────────────────┤
                    │ • WhatsAppHandler  │
                    │ • AIHandler        │
                    │ • Configuration    │
                    │ • Logger           │
                    │ • State Manager    │
                    └────────────────────┘
```

### Component Flow

```
1. WhatsApp Message Received (Green API Polling)
        ↓
2. WhatsAppHandler.process_notification()
        ↓
3. Validate message type (text only)
        ↓
4. Check group chat mention detection
        ↓
5. AIHandler.create_request()
        ↓
6. OpenAI API call (with retry logic)
        ↓
7. AIHandler.get_response()
        ↓
8. Truncate if >4000 chars
        ↓
9. WhatsAppHandler.send_response()
        ↓
10. Log message tracking (message_id, timestamp)
```

### Key Components

- **denidin.py**: Main entry point, bot initialization, signal handling
- **WhatsAppHandler**: Green API integration, message validation, response sending
- **AIHandler**: OpenAI integration, request formatting, error handling
- **BotConfiguration**: JSON/YAML config loading, validation
- **Logger**: Rotating file + console logging with INFO/DEBUG levels
- **MessageState**: Track last processed message to prevent duplicates

## Project Structure

```
denidin-bot/
├── denidin.py                  # Main entry point (223 lines)
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── DEPLOYMENT.md              # Production deployment guide
├── .gitignore                 # Git ignore rules
├── .pylintrc                  # Linter configuration
├── mypy.ini                   # Type checker configuration
├── config/
│   ├── config.example.json    # Example configuration (template)
│   └── config.json            # Actual credentials (gitignored)
├── src/                       # Source code (323 statements, 89% test coverage)
│   ├── handlers/
│   │   ├── ai_handler.py      # OpenAI API integration (91% coverage)
│   │   └── whatsapp_handler.py # Green API integration (71% coverage)
│   ├── models/
│   │   ├── config.py          # Configuration model (83% coverage)
│   │   ├── message.py         # Message models (100% coverage)
│   │   └── state.py           # State persistence (100% coverage)
│   └── utils/
│       ├── logger.py          # Logging setup (100% coverage)
│       └── state.py           # State utilities (100% coverage)
├── tests/                     # 142 tests (100% passing)
│   ├── unit/                  # 90 unit tests
│   ├── integration/           # 52 integration tests
│   └── fixtures/              # Test data (sample_messages.json)
├── logs/                      # Application logs (gitignored, 10MB rotation)
├── state/                     # Runtime state (gitignored)
└── htmlcov/                   # Coverage reports (generated by pytest-cov)
```

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
- Test Green API connection: `python3 -m pytest tests/integration/test_real_api_connectivity.py -v`
- Review `logs/denidin.log` for polling errors
- Ensure `poll_interval_seconds` is reasonable (5-10 seconds recommended)
- Check WhatsApp business account is logged in on phone

**Logs to check**: `grep "polling" logs/denidin.log` or `grep "ERROR" logs/denidin.log`

---

### AI responses not sent

**Problem**: Bot receives messages but doesn't respond

**Solutions**:
- Verify OpenAI API key is valid: check https://platform.openai.com/api-keys
- Check OpenAI account has credits: https://platform.openai.com/account/billing
- Review error logs for API quota/rate limit issues: `grep "OpenAI" logs/denidin.log`
- Test OpenAI connection: `python3 -m pytest tests/integration/test_real_api_connectivity.py::TestRealOpenAPIConnectivity -v`
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
A: Costs depend on message volume and OpenAI model:
- Green API: ~$10-20/month for WhatsApp Business API access
- OpenAI: ~$0.002 per 1K tokens (gpt-3.5-turbo) or ~$0.03 per 1K tokens (gpt-4o)
- For 100 messages/day with avg 500 tokens each: ~$3-150/month depending on model

**Q: Can I change the AI model?**  
A: Yes! Edit `ai_model` in `config/config.json`. Options: `gpt-4o-mini`, `gpt-3.5-turbo`, `gpt-4o`. Restart bot after changing.

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

