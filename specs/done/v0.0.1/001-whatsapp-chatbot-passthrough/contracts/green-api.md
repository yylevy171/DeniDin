# Green API Contract

**Service**: Green API WhatsApp Business API  
**Purpose**: Send and receive WhatsApp messages programmatically  
**Base URL**: `https://api.green-api.com`

## Authentication

All requests require instance-specific authentication:

- **Instance ID**: Unique identifier for your WhatsApp instance
- **API Token**: Authentication token for the instance

**Authentication Method**: URL path parameters

```
https://api.green-api.com/waInstance{idInstance}/{method}/{apiTokenInstance}
```

**Example**:
```
https://api.green-api.com/waInstance1234567890/sendMessage/abc123def456
```

---

## Incoming Notifications (Receive Messages)

### Method: `receiveNotification`

**HTTP Method**: `GET`  
**Endpoint**: `/waInstance{idInstance}/receiveNotification/{apiTokenInstance}`

**Purpose**: Poll for incoming WhatsApp notifications (messages, status updates)

**Request**: No body required

**Response** (Success - 200 OK):

```json
{
  "receiptId": 123456789,
  "body": {
    "typeWebhook": "incomingMessageReceived",
    "instanceData": {
      "idInstance": 1234567890,
      "wid": "1234567890@c.us",
      "typeInstance": "whatsapp"
    },
    "timestamp": 1705329600,
    "idMessage": "true_1234567890@c.us_ABCD1234567890",
    "senderData": {
      "chatId": "1234567890@c.us",
      "chatName": "John Doe",
      "sender": "1234567890@c.us",
      "senderName": "John Doe",
      "senderContactName": "John"
    },
    "messageData": {
      "typeMessage": "textMessage",
      "textMessageData": {
        "textMessage": "Hello, DeniDin!"
      }
    }
  }
}
```

**Response** (No Messages - 200 OK):

```json
null
```

**Key Fields for DeniDin**:

| Field Path | Type | Description |
|------------|------|-------------|
| `receiptId` | `int` | Unique ID for this notification (use to delete after processing) |
| `body.idMessage` | `string` | Unique message identifier |
| `body.senderData.chatId` | `string` | Chat ID to reply to (`{phone}@c.us` or `{groupId}@g.us`) |
| `body.senderData.sender` | `string` | Sender's WhatsApp ID |
| `body.senderData.senderName` | `string` | Sender's display name |
| `body.messageData.typeMessage` | `string` | Message type (DeniDin only handles "textMessage") |
| `body.messageData.textMessageData.textMessage` | `string` | The actual message text |
| `body.timestamp` | `int` | Unix timestamp |

**Message Types** (Phase 1 - Only handle textMessage):

- `textMessage` - Plain text ✅
- `imageMessage` - Image ❌ (ignore)
- `videoMessage` - Video ❌ (ignore)
- `documentMessage` - Document ❌ (ignore)
- `audioMessage` - Audio/Voice ❌ (ignore)
- `locationMessage` - Location ❌ (ignore)
- `contactMessage` - Contact card ❌ (ignore)
- `pollMessage` - Poll ❌ (ignore)

---

### Method: `deleteNotification`

**HTTP Method**: `DELETE`  
**Endpoint**: `/waInstance{idInstance}/deleteNotification/{apiTokenInstance}/{receiptId}`

**Purpose**: Delete a notification after processing (prevents re-processing)

**Request**: No body required

**Response** (Success - 200 OK):

```json
{
  "result": true
}
```

**Usage in DeniDin**:
- Call immediately after successfully processing a message
- Prevents duplicate handling on next poll

---

## Outgoing Messages (Send Messages)

### Method: `sendMessage`

**HTTP Method**: `POST`  
**Endpoint**: `/waInstance{idInstance}/sendMessage/{apiTokenInstance}`

**Purpose**: Send a text message to a WhatsApp chat

**Request Body**:

```json
{
  "chatId": "1234567890@c.us",
  "message": "This is a response from DeniDin AI chatbot."
}
```

**Request Fields**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `chatId` | `string` | Yes | Chat ID from incoming notification |
| `message` | `string` | Yes | Message text (max 4096 characters) |
| `quotedMessageId` | `string` | No | Message ID to quote/reply to |
| `linkPreview` | `boolean` | No | Show link preview (default: true) |

**Response** (Success - 200 OK):

```json
{
  "idMessage": "true_1234567890@c.us_EFGH9876543210"
}
```

**Error Response** (400 Bad Request)**:

```json
{
  "error": "Bad Request",
  "message": "chatId is required"
}
```

**Error Response** (401 Unauthorized)**:

```json
{
  "error": "Unauthorized",
  "message": "Invalid apiTokenInstance"
}
```

**Error Response** (429 Too Many Requests)**:

```json
{
  "error": "Rate limit exceeded",
  "message": "Please try again later"
}
```

**Character Limit**: WhatsApp enforces a 4096 character limit per message. DeniDin must split longer AI responses into multiple messages.

---

## Instance Settings (One-time Setup)

### Method: `setSettings`

**HTTP Method**: `POST`  
**Endpoint**: `/waInstance{idInstance}/setSettings/{apiTokenInstance}`

**Purpose**: Configure instance to receive incoming message notifications

**Request Body** (DeniDin Required Settings):

```json
{
  "incomingWebhook": "yes",
  "outgoingMessageWebhook": "yes",
  "outgoingAPIMessageWebhook": "yes"
}
```

**Response** (Success - 200 OK):

```json
{
  "saveSettings": true
}
```

**Note**: The `whatsapp-chatbot-python` library automatically calls this on bot initialization. Takes ~5 minutes to apply.

---

## Webhook Alternative (Future - Phase 2+)

Instead of polling with `receiveNotification`, Green API can push notifications to a webhook URL.

**Setup**:
1. Configure webhook URL in Green API console
2. Receive POST requests with notification payload
3. No polling delay (instant notifications)

**Webhook Payload**: Same as `receiveNotification` response `body` field

**Advantages**:
- Lower latency (instant delivery)
- No polling overhead
- More scalable

**Disadvantages**:
- Requires public HTTPS endpoint
- More complex local development (need ngrok or similar)

**DeniDin Phase 1 Decision**: Use polling for simplicity

---

## Rate Limits

Green API rate limits vary by subscription tier:

| Tier | Messages/Day | Requests/Second |
|------|--------------|-----------------|
| Free | 100 | 1 |
| Starter | 1,000 | 3 |
| Business | 10,000 | 10 |
| Enterprise | Unlimited | 50 |

**DeniDin Handling**:
- Implement exponential backoff on 429 errors
- Monitor daily usage
- Log rate limit warnings

---

## Error Handling Strategy

### Retry Logic

| Error Code | Retry? | Strategy |
|------------|--------|----------|
| 400 Bad Request | No | Log and skip (malformed request) |
| 401 Unauthorized | No | Fail immediately (invalid credentials) |
| 429 Too Many Requests | Yes | Exponential backoff (1s, 2s, 4s, max 3 retries) |
| 500 Internal Server Error | Yes | Retry after 5s (max 2 retries) |
| 503 Service Unavailable | Yes | Retry after 10s (max 2 retries) |
| Network timeout | Yes | Retry after 3s (max 3 retries) |

### Python Implementation Pattern

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(requests.exceptions.RequestException)
)
def send_message(chat_id: str, message: str, config: BotConfiguration) -> dict:
    url = f"https://api.green-api.com/waInstance{config.green_api_instance_id}/sendMessage/{config.green_api_token}"
    response = requests.post(url, json={"chatId": chat_id, "message": message}, timeout=10)
    response.raise_for_status()
    return response.json()
```

---

## Library Abstraction (whatsapp-chatbot-python)

The `whatsapp-chatbot-python` library wraps these API calls:

```python
from whatsapp_chatbot_python import GreenAPIBot, Notification

bot = GreenAPIBot(
    id_instance="1234567890",
    api_token_instance="abc123def456"
)

# Automatically polls receiveNotification
@bot.router.message(type_message=["textMessage"])
def handle_message(notification: Notification) -> None:
    # notification.chat = chatId
    # notification.message_text = text content
    # notification.sender = sender ID
    
    # Send response
    notification.answer("Response text")
    # Internally calls sendMessage + deleteNotification
```

**DeniDin Usage**: Use library for message routing, but implement custom AI integration logic.

---

## References

- [Green API Documentation](https://green-api.com/en/docs/)
- [Receiving Methods](https://green-api.com/en/docs/api/receiving/)
- [Sending Methods](https://green-api.com/en/docs/api/sending/)
- [whatsapp-chatbot-python Library](https://github.com/green-api/whatsapp-chatbot-python)
