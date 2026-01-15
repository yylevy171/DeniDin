# Data Model: WhatsApp AI Chatbot Passthrough

**Phase**: 1 (Design)  
**Date**: 2026-01-15

## Overview

This document defines the core entities and their relationships for the DeniDin chatbot. Since Phase 1 focuses on stateless message passthrough, the data model is intentionally minimal with no persistent database required.

## Core Entities

### 1. WhatsAppMessage

Represents an incoming message from a WhatsApp user via Green API notification.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `message_id` | `str` | Yes | Unique identifier from Green API (e.g., "true_123456789@c.us_ABC123") |
| `chat_id` | `str` | Yes | Chat identifier (format: `{phone}@c.us` for 1-on-1, `{groupId}@g.us` for groups) |
| `sender_id` | `str` | Yes | Sender's WhatsApp ID (phone number format) |
| `sender_name` | `str` | No | Sender's display name from WhatsApp profile |
| `text_content` | `str` | Yes | The actual message text |
| `timestamp` | `int` | Yes | Unix timestamp when message was sent |
| `message_type` | `str` | Yes | Type of message (Phase 1: only "textMessage" supported) |
| `is_group` | `bool` | Yes | True if message from group chat, False for 1-on-1 |

**Relationships**:
- One WhatsAppMessage generates one AIRequest
- One WhatsAppMessage receives one or more AIResponse(s) (if response split due to length)

**Python Representation**:

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class WhatsAppMessage:
    message_id: str
    chat_id: str
    sender_id: str
    text_content: str
    timestamp: int
    message_type: str
    sender_name: str | None = None
    is_group: bool = False
    
    @classmethod
    def from_notification(cls, notification: dict) -> 'WhatsAppMessage':
        """Create from Green API notification payload"""
        message_data = notification.get('messageData', {})
        return cls(
            message_id=message_data.get('idMessage'),
            chat_id=notification.get('senderData', {}).get('chatId'),
            sender_id=notification.get('senderData', {}).get('sender'),
            sender_name=notification.get('senderData', {}).get('senderName'),
            text_content=message_data.get('textMessageData', {}).get('textMessage', ''),
            timestamp=message_data.get('timestamp', 0),
            message_type=message_data.get('typeMessage'),
            is_group=notification.get('senderData', {}).get('chatId', '').endswith('@g.us')
        )
```

---

### 2. AIRequest

Represents a request sent to the AI service (ChatGPT).

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `request_id` | `str` | Yes | Unique identifier (UUID) for tracking |
| `prompt` | `str` | Yes | The text prompt sent to AI (same as WhatsAppMessage.text_content) |
| `source_message_id` | `str` | Yes | Reference to originating WhatsAppMessage.message_id |
| `timestamp` | `datetime` | Yes | When request was created |
| `model` | `str` | Yes | AI model used (e.g., "gpt-4o", "gpt-3.5-turbo") |
| `system_message` | `str` | No | System message defining AI behavior |
| `max_tokens` | `int` | No | Maximum tokens in response (default: 1000) |
| `temperature` | `float` | No | Randomness parameter (default: 0.7) |

**Relationships**:
- One AIRequest originates from one WhatsAppMessage
- One AIRequest produces one AIResponse

**Python Representation**:

```python
import uuid
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class AIRequest:
    prompt: str
    source_message_id: str
    model: str = "gpt-4o"
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.utcnow)
    system_message: str | None = None
    max_tokens: int = 1000
    temperature: float = 0.7
    
    def to_openai_payload(self) -> dict:
        """Convert to OpenAI API request format"""
        messages = []
        if self.system_message:
            messages.append({"role": "system", "content": self.system_message})
        messages.append({"role": "user", "content": self.prompt})
        
        return {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }
```

---

### 3. AIResponse

Represents a response received from the AI service.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `response_id` | `str` | Yes | AI service's response ID (from OpenAI) |
| `request_id` | `str` | Yes | Reference to originating AIRequest.request_id |
| `response_text` | `str` | Yes | The AI-generated text response |
| `timestamp` | `datetime` | Yes | When response was received |
| `tokens_used` | `int` | No | Total tokens consumed (input + output) |
| `finish_reason` | `str` | No | Completion reason ("stop", "length", "content_filter") |
| `model` | `str` | Yes | AI model that generated response |

**Relationships**:
- One AIResponse belongs to one AIRequest
- One AIResponse may be split into multiple WhatsApp messages (if > 4096 chars)

**Python Representation**:

```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class AIResponse:
    response_id: str
    request_id: str
    response_text: str
    model: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tokens_used: int | None = None
    finish_reason: str | None = None
    
    @classmethod
    def from_openai_response(cls, openai_response: dict, request_id: str) -> 'AIResponse':
        """Create from OpenAI API response"""
        choice = openai_response['choices'][0]
        return cls(
            response_id=openai_response['id'],
            request_id=request_id,
            response_text=choice['message']['content'],
            model=openai_response['model'],
            tokens_used=openai_response.get('usage', {}).get('total_tokens'),
            finish_reason=choice.get('finish_reason')
        )
    
    def split_for_whatsapp(self, max_length: int = 4000) -> list[str]:
        """Split long responses into WhatsApp-compatible chunks"""
        if len(self.response_text) <= max_length:
            return [self.response_text]
        
        # Split at sentence boundaries
        chunks = []
        current_chunk = ""
        sentences = self.response_text.split('. ')
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 2 <= max_length:
                current_chunk += sentence + '. '
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + '. '
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # Add chunk indicators
        total_chunks = len(chunks)
        if total_chunks > 1:
            return [f"[{i+1}/{total_chunks}] {chunk}" for i, chunk in enumerate(chunks)]
        return chunks
```

---

### 4. BotConfiguration

Represents the bot's runtime configuration (loaded from environment variables).

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `green_api_instance_id` | `str` | Yes | Green API instance ID |
| `green_api_token` | `str` | Yes | Green API authentication token |
| `openai_api_key` | `str` | Yes | OpenAI API key |
| `ai_model` | `str` | No | AI model to use (default: "gpt-4o") |
| `system_message` | `str` | No | AI behavior definition |
| `max_tokens` | `int` | No | Max response tokens (default: 1000) |
| `temperature` | `float` | No | AI temperature (default: 0.7) |
| `log_level` | `str` | No | Logging level (default: "INFO") |
| `poll_interval` | `int` | No | Seconds between notification polls (default: 3) |
| `max_retries` | `int` | No | Max retry attempts for failed requests (default: 3) |

**Relationships**:
- Singleton - one configuration per bot instance
- Used by all message handlers and AI service integrations

**Python Representation**:

```python
from dataclasses import dataclass
from os import getenv
from dotenv import load_dotenv

@dataclass
class BotConfiguration:
    green_api_instance_id: str
    green_api_token: str
    openai_api_key: str
    ai_model: str = "gpt-4o"
    system_message: str = "You are DeniDin, a helpful AI assistant integrated with WhatsApp. Be concise and accurate."
    max_tokens: int = 1000
    temperature: float = 0.7
    log_level: str = "INFO"
    poll_interval: int = 3
    max_retries: int = 3
    
    @classmethod
    def from_env(cls) -> 'BotConfiguration':
        """Load configuration from environment variables"""
        load_dotenv()
        
        required_vars = ['GREEN_API_INSTANCE_ID', 'GREEN_API_TOKEN', 'OPENAI_API_KEY']
        missing = [var for var in required_vars if not getenv(var)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        
        return cls(
            green_api_instance_id=getenv('GREEN_API_INSTANCE_ID'),
            green_api_token=getenv('GREEN_API_TOKEN'),
            openai_api_key=getenv('OPENAI_API_KEY'),
            ai_model=getenv('AI_MODEL', 'gpt-4o'),
            system_message=getenv('SYSTEM_MESSAGE', cls.system_message),
            max_tokens=int(getenv('MAX_TOKENS', '1000')),
            temperature=float(getenv('TEMPERATURE', '0.7')),
            log_level=getenv('LOG_LEVEL', 'INFO'),
            poll_interval=int(getenv('POLL_INTERVAL', '3')),
            max_retries=int(getenv('MAX_RETRIES', '3'))
        )
    
    def validate(self) -> None:
        """Validate configuration values"""
        if self.temperature < 0.0 or self.temperature > 1.0:
            raise ValueError("temperature must be between 0.0 and 1.0")
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be positive")
        if self.poll_interval < 1:
            raise ValueError("poll_interval must be at least 1 second")
```

---

### 5. MessageState (Optional - for duplicate prevention)

Simple state tracker to prevent processing the same message twice on bot restart.

**Attributes**:

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `last_processed_message_id` | `str` | Yes | ID of the last successfully processed message |
| `last_update_timestamp` | `datetime` | Yes | When state was last updated |

**Storage**: JSON file (`state/last_message.json`)

**Python Representation**:

```python
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class MessageState:
    last_processed_message_id: str
    last_update_timestamp: datetime
    
    STATE_FILE = Path("state/last_message.json")
    
    @classmethod
    def load(cls) -> 'MessageState':
        """Load state from file, or create new if doesn't exist"""
        if cls.STATE_FILE.exists():
            with open(cls.STATE_FILE, 'r') as f:
                data = json.load(f)
                return cls(
                    last_processed_message_id=data['last_processed_message_id'],
                    last_update_timestamp=datetime.fromisoformat(data['last_update_timestamp'])
                )
        return cls(last_processed_message_id="", last_update_timestamp=datetime.utcnow())
    
    def save(self) -> None:
        """Persist state to file"""
        self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(self.STATE_FILE, 'w') as f:
            json.dump({
                'last_processed_message_id': self.last_processed_message_id,
                'last_update_timestamp': self.last_update_timestamp.isoformat()
            }, f, indent=2)
    
    def update(self, message_id: str) -> None:
        """Update state with new message ID"""
        self.last_processed_message_id = message_id
        self.last_update_timestamp = datetime.utcnow()
        self.save()
```

---

## Entity Relationships Diagram

```
┌─────────────────────┐
│  BotConfiguration   │  (Singleton, loaded from .env)
└─────────────────────┘
          │
          │ configures
          ↓
┌─────────────────────┐      generates      ┌─────────────────────┐
│  WhatsAppMessage    │ ───────────────────→ │    AIRequest        │
├─────────────────────┤                      ├─────────────────────┤
│ - message_id        │                      │ - request_id        │
│ - chat_id           │                      │ - prompt            │
│ - sender_id         │                      │ - source_message_id │
│ - text_content      │                      │ - model             │
│ - timestamp         │                      │ - timestamp         │
│ - is_group          │                      └─────────────────────┘
└─────────────────────┘                               │
                                                      │ produces
                                                      ↓
                                             ┌─────────────────────┐
                                             │    AIResponse       │
                                             ├─────────────────────┤
                                             │ - response_id       │
                                             │ - request_id        │
                                             │ - response_text     │
                                             │ - tokens_used       │
                                             │ - timestamp         │
                                             └─────────────────────┘
                                                      │
                                                      │ split into
                                                      ↓
                                             ┌─────────────────────┐
                                             │  WhatsApp Messages  │
                                             │  (chunked responses)│
                                             └─────────────────────┘

┌─────────────────────┐
│   MessageState      │  (Persisted to JSON file)
├─────────────────────┤
│ - last_message_id   │
│ - last_timestamp    │
└─────────────────────┘
```

## Data Flow

1. **Incoming Message**:
   - Green API sends notification → Parse into `WhatsAppMessage`
   - Check `MessageState` to prevent duplicate processing
   - Validate message type (text only in Phase 1)

2. **AI Request**:
   - Create `AIRequest` from `WhatsAppMessage.text_content`
   - Apply `BotConfiguration` settings (model, temperature, etc.)
   - Send to OpenAI API

3. **AI Response**:
   - Receive OpenAI response → Parse into `AIResponse`
   - Check response length
   - Split if > 4096 characters

4. **Send Response**:
   - For each chunk, send via Green API to original `WhatsAppMessage.chat_id`
   - Update `MessageState` with processed message ID

## Validation Rules

### WhatsAppMessage
- `text_content` must not be empty (reject empty messages)
- `message_type` must be "textMessage" (ignore others in Phase 1)
- `chat_id` format must match `*@c.us` or `*@g.us` pattern

### AIRequest
- `prompt` max length: 10,000 characters (OpenAI input limit)
- `temperature` range: 0.0 to 1.0
- `max_tokens` range: 1 to 4096

### BotConfiguration
- All required fields must be non-empty strings
- `poll_interval` minimum: 1 second (avoid API hammering)
- `max_retries` range: 1 to 5

## Notes

- **No Database**: All entities are in-memory objects, except `MessageState` (JSON file)
- **No Conversation History**: Each `AIRequest` is independent (Phase 1 constraint)
- **Future Extensions**: 
  - Phase 2+: Add `ConversationContext` entity for multi-turn dialogues
  - Add `UserPreferences` for per-user settings
  - Add `MessageLog` for audit trail
