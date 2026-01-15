# OpenAI API Contract

**Service**: OpenAI Chat Completions API  
**Purpose**: Generate AI responses using GPT models  
**Base URL**: `https://api.openai.com/v1`  
**Documentation**: https://platform.openai.com/docs/api-reference/chat

## Authentication

**Method**: Bearer token in `Authorization` header

```http
Authorization: Bearer sk-proj-...your-api-key...
```

**API Key Format**: Starts with `sk-` (user key) or `sk-proj-` (project key)

---

## Chat Completions (Main Endpoint)

### Method: `POST /chat/completions`

**Endpoint**: `https://api.openai.com/v1/chat/completions`

**Purpose**: Generate AI responses based on conversation messages

**Request Headers**:

```http
Content-Type: application/json
Authorization: Bearer YOUR_API_KEY
```

**Request Body** (DeniDin Configuration):

```json
{
  "model": "gpt-4o",
  "messages": [
    {
      "role": "system",
      "content": "You are DeniDin, a helpful AI assistant integrated with WhatsApp. Be concise and accurate."
    },
    {
      "role": "user",
      "content": "What is the capital of France?"
    }
  ],
  "max_tokens": 1000,
  "temperature": 0.7
}
```

**Request Fields**:

| Field | Type | Required | Description | DeniDin Value |
|-------|------|----------|-------------|---------------|
| `model` | `string` | Yes | AI model identifier | `"gpt-4o"` or `"gpt-3.5-turbo"` |
| `messages` | `array` | Yes | Conversation history | System message + user prompt |
| `max_tokens` | `integer` | No | Maximum tokens in response | `1000` (default) |
| `temperature` | `number` | No | Randomness (0.0-1.0) | `0.7` (default) |
| `top_p` | `number` | No | Nucleus sampling | Not used in Phase 1 |
| `n` | `integer` | No | Number of completions | `1` (default) |
| `stream` | `boolean` | No | Stream responses | `false` (Phase 1) |
| `stop` | `string/array` | No | Stop sequences | Not used in Phase 1 |
| `presence_penalty` | `number` | No | Penalty for repetition | Not used in Phase 1 |
| `frequency_penalty` | `number` | No | Penalty for frequency | Not used in Phase 1 |

---

### Message Roles

| Role | Purpose | DeniDin Usage |
|------|---------|---------------|
| `system` | Define AI behavior/personality | "You are DeniDin, a helpful AI assistant..." |
| `user` | User's input/question | WhatsApp message content |
| `assistant` | AI's previous responses | Not used in Phase 1 (stateless) |

**Phase 1 Message Array** (stateless, no conversation history):

```json
{
  "messages": [
    {"role": "system", "content": "System message from config"},
    {"role": "user", "content": "User's WhatsApp message"}
  ]
}
```

**Future Phases** (with conversation history):

```json
{
  "messages": [
    {"role": "system", "content": "System message"},
    {"role": "user", "content": "Previous message 1"},
    {"role": "assistant", "content": "Previous response 1"},
    {"role": "user", "content": "Previous message 2"},
    {"role": "assistant", "content": "Previous response 2"},
    {"role": "user", "content": "Current message"}
  ]
}
```

---

### Response (Success - 200 OK)

```json
{
  "id": "chatcmpl-123abc456def",
  "object": "chat.completion",
  "created": 1705329600,
  "model": "gpt-4o-2024-05-13",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "The capital of France is Paris."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 25,
    "completion_tokens": 8,
    "total_tokens": 33
  }
}
```

**Key Response Fields**:

| Field Path | Type | Description | DeniDin Usage |
|------------|------|-------------|---------------|
| `id` | `string` | Unique completion ID | Store in AIResponse.response_id |
| `model` | `string` | Model used (may differ from request) | Log for debugging |
| `choices[0].message.content` | `string` | AI-generated response | Send to WhatsApp |
| `choices[0].finish_reason` | `string` | Why generation stopped | Validate completion |
| `usage.total_tokens` | `integer` | Total tokens consumed | Track costs |
| `usage.prompt_tokens` | `integer` | Input tokens | Cost calculation |
| `usage.completion_tokens` | `integer` | Output tokens | Cost calculation |

---

### Finish Reasons

| Reason | Meaning | DeniDin Handling |
|--------|---------|------------------|
| `stop` | Natural completion | Normal - send response |
| `length` | Hit max_tokens limit | Warning - response may be truncated |
| `content_filter` | Content policy violation | Error - send generic fallback message |
| `function_call` | Tool/function call | Not used in Phase 1 |

---

### Error Responses

**401 Unauthorized** (Invalid API Key):

```json
{
  "error": {
    "message": "Incorrect API key provided",
    "type": "invalid_request_error",
    "param": null,
    "code": "invalid_api_key"
  }
}
```

**429 Too Many Requests** (Rate Limit):

```json
{
  "error": {
    "message": "Rate limit reached for requests",
    "type": "tokens",
    "param": null,
    "code": "rate_limit_exceeded"
  }
}
```

**400 Bad Request** (Invalid Parameters):

```json
{
  "error": {
    "message": "Invalid value for 'temperature': must be between 0 and 2",
    "type": "invalid_request_error",
    "param": "temperature",
    "code": null
  }
}
```

**500 Internal Server Error** (OpenAI Outage):

```json
{
  "error": {
    "message": "The server had an error while processing your request",
    "type": "server_error",
    "param": null,
    "code": null
  }
}
```

---

## Models

### Available Models for DeniDin

| Model | Context Window | Cost (per 1M tokens) | Speed | DeniDin Default |
|-------|----------------|----------------------|-------|-----------------|
| `gpt-4o` | 128k | $5 input / $15 output | Medium | ✅ Yes (balanced) |
| `gpt-4o-mini` | 128k | $0.15 input / $0.60 output | Fast | Alternative (cost-saving) |
| `gpt-3.5-turbo` | 16k | $0.50 input / $1.50 output | Very Fast | Alternative (legacy) |
| `gpt-4-turbo` | 128k | $10 input / $30 output | Slow | Not recommended |

**DeniDin Phase 1 Recommendation**: Use `gpt-4o` for quality, switch to `gpt-4o-mini` if cost is a concern.

**Cost Example** (100 messages/day, avg 50 tokens input + 100 tokens output):
- `gpt-4o`: ~$0.23/day (~$7/month)
- `gpt-4o-mini`: ~$0.01/day (~$0.30/month)

---

## Rate Limits

Rate limits vary by account tier and model:

| Tier | RPM (Requests/Min) | TPM (Tokens/Min) | RPD (Requests/Day) |
|------|--------------------|-----------------|--------------------|
| Free | 3 | 40,000 | 200 |
| Tier 1 | 500 | 200,000 | Unlimited |
| Tier 2 | 5,000 | 2,000,000 | Unlimited |
| Tier 3+ | Higher | Higher | Unlimited |

**DeniDin Handling**:
- Detect 429 errors
- Implement exponential backoff
- Fallback message if retries exhausted: "Sorry, I'm experiencing high demand. Please try again in a minute."

---

## Timeout Configuration

**OpenAI SDK Default Timeout**: 10 minutes (too long for WhatsApp users)

**DeniDin Recommendation**: Set explicit timeout

```python
from openai import OpenAI

client = OpenAI(
    api_key="your-api-key",
    timeout=30.0  # 30 seconds
)

try:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[...],
        max_tokens=1000
    )
except openai.APITimeoutError:
    # Send fallback message to WhatsApp
    return "Sorry, the AI service is taking too long to respond. Please try again."
```

---

## Error Handling Strategy

### Retry Logic

| Error Type | Retry? | Strategy | DeniDin Fallback Message |
|------------|--------|----------|--------------------------|
| 401 Unauthorized | No | Fail fast (invalid API key) | "Bot configuration error. Please contact support." |
| 400 Bad Request | No | Log and skip | "Sorry, I couldn't process that request." |
| 429 Rate Limit | Yes | Exponential backoff (3 retries) | "I'm currently at capacity. Please try again in a minute." |
| 500 Server Error | Yes | Retry after 5s (2 retries) | "The AI service is temporarily unavailable. Please try again later." |
| Timeout | Yes | Retry once after 10s | "Sorry, I'm having trouble connecting to my AI service. Please try again." |

### Python Implementation

```python
from openai import OpenAI, APIError, APITimeoutError, RateLimitError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

client = OpenAI(api_key=config.openai_api_key, timeout=30.0)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIError))
)
def get_ai_response(prompt: str, config: BotConfiguration) -> str:
    response = client.chat.completions.create(
        model=config.ai_model,
        messages=[
            {"role": "system", "content": config.system_message},
            {"role": "user", "content": prompt}
        ],
        max_tokens=config.max_tokens,
        temperature=config.temperature
    )
    return response.choices[0].message.content
```

---

## Token Counting

**Approximate Formula**: 
- English: ~1 token per 4 characters or 0.75 words
- Other languages: Varies (emoji = 1-2 tokens each)

**Example**:
- "Hello, how are you?" = ~5 tokens
- 4096 char WhatsApp message = ~1000 tokens (input)
- 1000 max_tokens = ~4000 characters (output)

**DeniDin Monitoring**:
- Log `usage.total_tokens` per request
- Alert if approaching rate limits (e.g., > 80% of TPM)
- Monthly cost tracking: `total_tokens * model_cost_per_million / 1,000,000`

---

## Content Policy

OpenAI filters requests and responses for:
- Violence, hate speech
- Self-harm, illegal activity
- Personal data, copyrighted content

**If `finish_reason` = "content_filter"**:
- AI refused to generate content (policy violation)
- DeniDin should send: "I cannot provide a response to that request due to content policies."

---

## Streaming (Future - Phase 2+)

Instead of waiting for the full response, stream tokens as they're generated:

```python
stream = client.chat.completions.create(
    model="gpt-4o",
    messages=[...],
    stream=True
)

for chunk in stream:
    if chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

**Benefit**: Lower perceived latency (user sees response building in real-time)  
**Challenge**: WhatsApp doesn't support live message updates (would need to send complete messages)

**DeniDin Phase 1**: No streaming (wait for full response, then send)

---

## Python SDK Usage Example

```python
from openai import OpenAI
from dataclasses import dataclass

@dataclass
class AIResponse:
    response_id: str
    response_text: str
    tokens_used: int
    finish_reason: str
    model: str

def create_ai_request(prompt: str, config: BotConfiguration) -> AIResponse:
    client = OpenAI(api_key=config.openai_api_key, timeout=30.0)
    
    try:
        response = client.chat.completions.create(
            model=config.ai_model,
            messages=[
                {"role": "system", "content": config.system_message},
                {"role": "user", "content": prompt}
            ],
            max_tokens=config.max_tokens,
            temperature=config.temperature
        )
        
        choice = response.choices[0]
        return AIResponse(
            response_id=response.id,
            response_text=choice.message.content,
            tokens_used=response.usage.total_tokens,
            finish_reason=choice.finish_reason,
            model=response.model
        )
    
    except Exception as e:
        # Log error and raise for retry logic
        logger.error(f"OpenAI API error: {e}")
        raise
```

---

## References

- [OpenAI Chat Completions API](https://platform.openai.com/docs/api-reference/chat)
- [OpenAI Python SDK](https://github.com/openai/openai-python)
- [OpenAI Rate Limits](https://platform.openai.com/docs/guides/rate-limits)
- [OpenAI Pricing](https://openai.com/pricing)
- [Content Policy](https://openai.com/policies/usage-policies)
