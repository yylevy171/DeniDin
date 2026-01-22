# Research: WhatsApp AI Chatbot Passthrough

**Phase**: 0 (Research & Feasibility)  
**Date**: 2026-01-15

## Green API Integration Research

### Overview

Green API provides a WhatsApp Business API integration that allows sending/receiving messages programmatically. The official demo chatbot (`whatsapp-demo-chatbot-python`) already integrates ChatGPT via OpenAI API.

**Repository**: https://github.com/green-api/whatsapp-demo-chatbot-python

### Key Findings

#### 1. Authentication & Setup

- Requires Green API account with instance ID and API token
- WhatsApp Business number must be linked to the instance
- Instance settings must enable webhooks for incoming/outgoing messages
- The library automatically configures instance settings on first run (takes ~5 minutes)

#### 2. Message Receiving Mechanism

The demo uses the `whatsapp-chatbot-python` library which provides:

```python
from whatsapp_chatbot_python import GreenAPIBot, Notification

bot = GreenAPIBot(id_instance, api_token_instance)

@bot.router.message(type_message=TEXT_TYPES, state=None)
def message_handler(notification: Notification) -> None:
    # Handle incoming message
    notification.answer("Response text")
```

**Webhook vs Polling**: 
- Library supports both HTTP webhooks and polling (receiveNotification API)
- For local development: Polling is simpler (no ngrok/public URL needed)
- For production: Webhooks are more efficient

#### 3. ChatGPT Integration (from demo)

The demo uses `WhatsappGptBot` class from `whatsapp-chatgpt-python`:

```python
from whatsapp_chatgpt_python import WhatsappGptBot

gpt_bot = WhatsappGptBot(
    id_instance=config.user_id,
    api_token_instance=config.api_token_id,
    openai_api_key=config.openai_api_key,
    model="gpt-4o",
    system_message="You are a helpful assistant...",
    max_history_length=10,
    temperature=0.7
)
```

**Configuration Parameters**:
- `model`: OpenAI model (default: "gpt-4o", can use "gpt-3.5-turbo" for cost savings)
- `system_message`: Sets AI behavior/personality
- `max_history_length`: Number of previous messages to maintain in context (Phase 1: set to 0 for stateless)
- `temperature`: Randomness (0.0 = deterministic, 1.0 = creative)

#### 4. Credentials Management

Demo uses `.env` file for debug mode:

```
DEBUG=True
DEBUG_USER_ID=<Instance ID>
DEBUG_API_TOKEN_ID=<API Token>
OPENAI_API_KEY=<OpenAI Key>
```

**Best Practice**: Use `python-dotenv` to load environment variables (already in demo's requirements.txt)

#### 5. Error Handling Patterns from Demo

- **API Errors**: Wrapped in try/except with logging
- **Timeout**: OpenAI SDK has default timeout (~30s)
- **Rate Limits**: Not explicitly handled in demo (needs addition)
- **Malformed Messages**: Demo only handles TEXT_TYPES, ignores others

#### 6. State Management

Demo maintains user state for:
- Language preference
- Last interaction timestamp (5-minute timeout)
- Menu navigation context

**For Phase 1**: 
- Strip out menu/language state (not needed for passthrough)
- Keep only `last_processed_message_id` to prevent duplicates on restart
- Use simple JSON file or pickle for persistence

#### 7. Dependencies (from requirements.txt)

```
whatsapp-chatbot-python>=0.5.1
whatsapp-api-client-python>=0.76.0
whatsapp-chatgpt-python>=0.0.1
openai>=1.12.0
python-dotenv>=1.0.0
PyYAML>=6.0
```

**Versions**: All dependencies actively maintained (latest updates within 6 months)

## Technical Decisions

### Decision 1: Use Green API Demo as Foundation ✅

**Reasoning**: 
- Already integrates both WhatsApp (Green API) and ChatGPT (OpenAI)
- Proven working code with proper library usage patterns
- Licensed under Creative Commons Attribution-NoDerivatives 4.0 (allows use, prohibits derivatives - need to verify fork/modification rights)

**Action**: Clone demo, then customize by removing menu logic and simplifying to passthrough

**Risk**: CC BY-ND 4.0 license may prohibit modification. **Mitigation**: Contact Green API for permission or use their libraries independently without copying demo code directly.

### Decision 2: Polling vs Webhooks for Phase 1

**Choice**: Use **polling** (receiveNotification API)

**Reasoning**:
- Simpler local development (no public URL required)
- Demo already implements polling via `whatsapp-chatbot-python` library
- Sufficient for MVP scale (single user, <100 msg/hr)

**Future**: Switch to webhooks for production deployment (lower latency, better scalability)

### Decision 3: Stateless Message Processing (Phase 1)

**Choice**: No conversation history maintained

**Reasoning**:
- Simpler implementation (no context window management)
- Aligns with "passthrough" concept (each message independent)
- Reduces memory usage and complexity

**Configuration**: Set `max_history_length=0` in WhatsappGptBot initialization

### Decision 4: Error Retry Strategy

**Strategy**: 
- Green API errors: Exponential backoff (1s, 2s, 4s, max 3 retries)
- OpenAI timeout: Single retry after 30s, then fallback message
- Network errors: 3 retries with 2s delay

**Implementation**: Use `tenacity` library for retry decorators (add to dependencies)

### Decision 5: Logging & Monitoring

**Approach**:
- Python `logging` module with file + console handlers
- Log levels: DEBUG (local), INFO (production)
- Log rotation: 10MB max file size, keep 5 backups
- Structured logs: timestamp, message ID, sender ID, error codes

**Library**: Python standard `logging` + `logging.handlers.RotatingFileHandler`

## Open Questions & Mitigations

### Q1: Can we modify the Green API demo under CC BY-ND 4.0 license?

**Risk**: License prohibits derivative works  
**Mitigation Options**:
1. Contact Green API for explicit permission
2. Rewrite from scratch using only their libraries (not demo code)
3. Use demo as reference only, implement independently

**Decision**: Proceed with option 2 (use libraries, reference demo architecture but write original code)

### Q2: How to handle WhatsApp's 4096 character limit when ChatGPT returns longer responses?

**Solution**: 
- Check response length before sending
- If > 4096 chars: Split into multiple messages (chunk at sentence boundaries)
- Add indicator: "1/3", "2/3", etc.

**Implementation**: Utility function `split_long_message(text: str, max_length: int = 4000) -> List[str]`

### Q3: How to detect and handle group chats vs 1-on-1 chats?

**Solution**:
- Green API notification includes `chatId` format: `{phone}@c.us` (1-on-1) or `{groupId}@g.us` (group)
- Check `chatId.endswith('@g.us')` to detect groups
- For groups: Only respond when bot is mentioned (check if message contains bot's name)

**Implementation**: Add `is_group_chat(chat_id: str) -> bool` helper function

### Q4: What if user sends unsupported media (image, voice, video)?

**Phase 1 Approach**: 
- Ignore non-text messages
- Optionally: Send auto-reply "I currently only support text messages"

**Future Phases**: 
- Images: Use OpenAI Vision API
- Voice: Transcribe with Whisper API, then process
- Video: Extract frames or reject with message

## Dependencies Analysis

| Dependency | Version | Purpose | Stability |
|------------|---------|---------|-----------|
| whatsapp-chatbot-python | 0.5.1+ | Bot framework, message routing | Stable, active repo |
| whatsapp-api-client-python | 0.76.0+ | Green API HTTP client | Stable, official SDK |
| whatsapp-chatgpt-python | 0.0.1+ | ChatGPT integration wrapper | New library, monitor for updates |
| openai | 1.12.0+ | OpenAI API client | Official, stable |
| python-dotenv | 1.0.0+ | Environment variable loader | Standard, stable |
| PyYAML | 6.0+ | YAML config parsing | Standard library |
| tenacity | 8.0+ (new) | Retry/backoff logic | Widely used, stable |
| pytest | 7.0+ (new) | Testing framework | Standard |

**Installation Command**:
```bash
pip install whatsapp-chatbot-python whatsapp-api-client-python whatsapp-chatgpt-python openai python-dotenv PyYAML tenacity pytest
```

## Performance Expectations

**Latency Breakdown** (estimated):
- WhatsApp → Green API webhook: <1s
- Bot receives notification (polling): 1-5s (depends on poll interval)
- Forward to OpenAI ChatGPT: 2-10s (model-dependent)
- ChatGPT response → Bot: instant
- Bot → WhatsApp via Green API: <1s

**Total End-to-End**: 5-20 seconds (within 30s requirement)

**Optimization Opportunities**:
- Use `gpt-3.5-turbo` instead of `gpt-4o` for faster responses (3-5s vs 5-10s)
- Reduce poll interval from 5s to 2s (trade-off: more API calls)
- Switch to webhooks for instant notification (removes polling delay)

## Security Considerations

1. **Credential Storage**: 
   - Never commit `.env` to git (add to .gitignore)
   - Use separate `.env.example` with placeholder values
   - Consider secrets manager for production (AWS Secrets Manager, HashiCorp Vault)

2. **API Key Exposure**:
   - Sanitize logs (never log full API keys)
   - Mask credentials in error messages
   - Use environment variables only, no hardcoded secrets

3. **Message Privacy**:
   - ChatGPT sees all messages (OpenAI data policy applies)
   - Consider adding disclaimer on first interaction
   - Future: Add opt-in/opt-out mechanism

4. **Rate Limit Protection**:
   - Implement per-user message throttling (max 10 msg/min)
   - Detect and block spam patterns
   - Monitor API quota usage

## Constraints & Limitations (Phase 1)

1. **Green API Free Tier**: 
   - Limited messages/day (check tier)
   - May have webhook restrictions
   - Action: Verify account tier supports requirements

2. **OpenAI Costs**:
   - GPT-4o: ~$0.01-0.03 per request (input+output tokens)
   - GPT-3.5-turbo: ~$0.001-0.002 per request
   - Budget monitoring recommended

3. **No Conversation Memory**:
   - Each message treated independently
   - No follow-up questions context
   - Users must provide full context each time

4. **Text-Only**:
   - Images, voice notes, videos ignored
   - May confuse users if they send media
   - Clear messaging needed

5. **Single Account**:
   - One WhatsApp business number
   - One ChatGPT account
   - No multi-tenancy

## Next Steps (Phase 1 Design)

1. Create `data-model.md` - Define WhatsAppMessage, AIRequest, AIResponse, BotConfiguration entities
2. Create `contracts/green-api.md` - Document Green API notification format and sending API
3. Create `contracts/openai-api.md` - Document ChatGPT API request/response structure
4. Create `quickstart.md` - Step-by-step local setup and first message test scenario
5. Finalize project structure in `plan.md`
6. Generate `tasks.md` via speckit.tasks command

## References

- [Green API Python Demo](https://github.com/green-api/whatsapp-demo-chatbot-python)
- [Green API Documentation](https://green-api.com/en/docs/)
- [whatsapp-chatbot-python Library](https://github.com/green-api/whatsapp-chatbot-python)
- [OpenAI Python SDK](https://github.com/openai/openai-python)
- [Green API Chatbot Tutorial](https://green-api.com/en/docs/chatbots/python/chatbot-demo/chatbot-demo-gpt-py/)
