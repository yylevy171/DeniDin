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
python denidin.py
```

The bot will:
1. Load configuration from `config/config.json`
2. Start polling Green API for incoming WhatsApp messages
3. Forward messages to ChatGPT
4. Send AI responses back to WhatsApp
5. Log all activity to `logs/denidin.log`

### 6. Stop the Bot

Press `Ctrl+C` to gracefully shut down the bot.

## Project Structure

```
denidin-bot/
├── denidin.py                  # Main entry point
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── .gitignore                  # Git ignore rules
├── config/
│   ├── config.example.json    # Example configuration (template)
│   └── config.json            # Actual credentials (gitignored)
├── src/
│   ├── handlers/              # Message handlers
│   ├── models/                # Data models
│   └── utils/                 # Utility functions
├── tests/
│   ├── unit/                  # Unit tests
│   ├── integration/           # Integration tests
│   └── fixtures/              # Test fixtures
├── logs/                      # Application logs (gitignored)
└── state/                     # Runtime state (gitignored)
```

## Testing

Send a WhatsApp message to your business number. DeniDin should:
1. Receive the message via Green API
2. Forward it to ChatGPT
3. Send the AI response back to WhatsApp
4. Log the interaction in `logs/denidin.log`

## Logging

- **INFO level**: Application events, incoming/outgoing messages, errors
- **DEBUG level**: Detailed parsing, state changes, API request/response details

Change `log_level` in `config/config.json` to switch between levels.

## Troubleshooting

### Bot doesn't start
- Check that `config/config.json` exists and has valid credentials
- Verify Python 3.8+ is installed: `python --version`
- Ensure virtual environment is activated

### Messages not received
- Verify Green API credentials are correct
- Check Green API instance status in dashboard
- Review `logs/denidin.log` for errors
- Ensure `poll_interval_seconds` is not too high

### AI responses not sent
- Verify OpenAI API key is valid
- Check OpenAI account has credits
- Review error logs for API quota/rate limit issues

### Long messages truncated
- This is expected behavior for responses >4000 characters
- Multi-message splitting will be added in Phase 2

## Next Steps (Future Phases)

- Phase 2: Conversation context and memory
- Phase 3: Multi-message splitting for long responses
- Phase 4: Enhanced error recovery and monitoring
- Phase 5: Webhook-based message reception

## License

[Your License Here]

## Support

For issues or questions, please refer to the project documentation in `specs/001-whatsapp-chatbot-passthrough/`.
