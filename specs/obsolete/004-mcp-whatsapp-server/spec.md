# Feature Spec: MCP WhatsApp Integration - Outbound Messaging

**Feature ID**: 004-mcp-whatsapp-server  
**Priority**: P1 (High)  
**Status**: Planning  
**Created**: January 17, 2026

## Problem Statement

Currently, DeniDin only *receives* and *responds* to WhatsApp messages. Users cannot proactively ask the bot to *send* messages to other contacts on their behalf.

**Desired Capability:**
- User (via any MCP client): "Send John a reminder that we're meeting tomorrow at 3pm"
- Bot: Identifies "John" in contacts → Sends WhatsApp message → Confirms delivery

## Use Cases

1. **Reminders**: "Send Sarah a reminder about the dentist appointment"
2. **Scheduling**: "Tell the team we're meeting at 2pm in room 301"
3. **Status Updates**: "Let Mike know I'm running 10 minutes late"
4. **Delegated Messaging**: "Send Mom 'Happy Birthday!' with a cake emoji"
5. **Broadcast**: "Send all project managers the latest status report"
6. **Follow-ups**: "Remind Lisa to send me the Q4 numbers"

## Solution Overview

Build an MCP (Model Context Protocol) server that:
1. Exposes WhatsApp messaging capabilities as MCP tools
2. Manages contact resolution (name → phone number)
3. Sends messages via Green API
4. Returns confirmation/status
5. Integrates with AI for natural language command parsing

## Architecture

```
MCP Client (Claude Desktop, Cline, etc.)
    ↓
MCP Protocol (stdio/HTTP)
    ↓
DeniDin MCP Server
    ↓
├─ Contact Resolver (name → phone)
├─ Message Composer
├─ Green API Client
└─ Delivery Tracker
    ↓
WhatsApp (via Green API)
```

## Technical Design

### 1. MCP Server Structure

```
denidin-mcp-server/
├── pyproject.toml
├── README.md
├── src/
│   └── denidin_mcp/
│       ├── __init__.py
│       ├── server.py           # Main MCP server
│       ├── tools.py            # MCP tool definitions
│       ├── contacts.py         # Contact management
│       └── whatsapp_client.py  # Green API integration
└── tests/
    └── test_server.py
```

### 2. MCP Tools

#### Tool 1: `send_whatsapp_message`

```python
{
    "name": "send_whatsapp_message",
    "description": "Send a WhatsApp message to a contact or phone number",
    "inputSchema": {
        "type": "object",
        "properties": {
            "recipient": {
                "type": "string",
                "description": "Contact name or phone number (with country code)"
            },
            "message": {
                "type": "string",
                "description": "Message text to send"
            },
            "urgent": {
                "type": "boolean",
                "description": "Whether this is urgent (affects delivery priority)",
                "default": false
            }
        },
        "required": ["recipient", "message"]
    }
}
```

**Example Usage:**
```
User: "Send John a reminder about tomorrow's meeting"

AI parses → Calls MCP tool:
{
  "recipient": "John",
  "message": "Reminder: We have a meeting tomorrow",
  "urgent": false
}

MCP Server → Resolves "John" → Sends via Green API → Returns confirmation
```

#### Tool 2: `send_whatsapp_to_group`

```python
{
    "name": "send_whatsapp_to_group",
    "description": "Send a message to a WhatsApp group",
    "inputSchema": {
        "type": "object",
        "properties": {
            "group_name": {
                "type": "string",
                "description": "Name of the WhatsApp group"
            },
            "message": {
                "type": "string",
                "description": "Message to send to the group"
            }
        },
        "required": ["group_name", "message"]
    }
}
```

#### Tool 3: `list_whatsapp_contacts`

```python
{
    "name": "list_whatsapp_contacts",
    "description": "Get list of WhatsApp contacts for recipient resolution",
    "inputSchema": {
        "type": "object",
        "properties": {
            "search": {
                "type": "string",
                "description": "Optional search term to filter contacts"
            }
        }
    }
}
```

#### Tool 4: `get_message_status`

```python
{
    "name": "get_message_status",
    "description": "Check delivery status of a sent message",
    "inputSchema": {
        "type": "object",
        "properties": {
            "message_id": {
                "type": "string",
                "description": "ID of the message to check"
            }
        },
        "required": ["message_id"]
    }
}
```

### 3. Contact Resolution

**Challenge**: Map natural language names to WhatsApp phone numbers

**Strategy 1: Contact Database (MVP)**
```python
# contacts.json
{
    "contacts": [
        {
            "name": "John Smith",
            "aliases": ["John", "Johnny"],
            "phone": "1234567890",
            "chat_id": "1234567890@c.us"
        },
        {
            "name": "Sarah Johnson",
            "aliases": ["Sarah", "SJ"],
            "phone": "9876543210",
            "chat_id": "9876543210@c.us"
        }
    ],
    "groups": [
        {
            "name": "Project Team",
            "aliases": ["team", "project team"],
            "chat_id": "120363024567890@g.us"
        }
    ]
}
```

**Strategy 2: Green API Contact Sync (Advanced)**
```python
class ContactResolver:
    def sync_contacts_from_whatsapp(self):
        """Fetch contacts from Green API and cache locally."""
        
    def resolve_recipient(self, name: str) -> str:
        """
        Resolve contact name to chat_id.
        Returns: chat_id (e.g., "1234567890@c.us")
        Raises: ContactNotFoundError if ambiguous or not found
        """
        
    def fuzzy_search(self, query: str) -> List[Contact]:
        """Find contacts with fuzzy matching."""
```

**Ambiguity Handling:**
```python
User: "Send John a message"
→ Multiple Johns found: ["John Smith", "John Doe"]
→ MCP returns: "Multiple contacts found: 1) John Smith, 2) John Doe. Please specify."
```

### 4. Message Composition

```python
class MessageComposer:
    def compose_message(
        self,
        recipient: str,
        message: str,
        urgent: bool = False
    ) -> dict:
        """
        Compose WhatsApp message payload for Green API.
        """
        return {
            "chatId": resolved_chat_id,
            "message": message,
            # Add formatting, emojis, etc.
        }
```

### 5. Green API Integration

```python
class WhatsAppClient:
    def __init__(self, instance_id: str, api_token: str):
        self.base_url = f"https://api.green-api.com/waInstance{instance_id}"
        self.api_token = api_token
        
    def send_message(self, chat_id: str, message: str) -> dict:
        """
        Send message via Green API.
        Returns: {"idMessage": "...", "status": "sent"}
        """
        endpoint = f"{self.base_url}/sendMessage/{self.api_token}"
        payload = {
            "chatId": chat_id,
            "message": message
        }
        response = requests.post(endpoint, json=payload)
        return response.json()
        
    def get_contacts(self) -> List[dict]:
        """Fetch contact list from Green API."""
        
    def get_message_status(self, message_id: str) -> dict:
        """Check if message was delivered/read."""
```

### 6. MCP Server Implementation

```python
# src/denidin_mcp/server.py

from mcp.server import Server
from mcp.types import Tool, TextContent
import mcp.server.stdio

app = Server("denidin-whatsapp")

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="send_whatsapp_message",
            description="Send a WhatsApp message to a contact",
            inputSchema={
                "type": "object",
                "properties": {
                    "recipient": {"type": "string"},
                    "message": {"type": "string"},
                    "urgent": {"type": "boolean", "default": False}
                },
                "required": ["recipient", "message"]
            }
        ),
        # ... other tools
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "send_whatsapp_message":
        recipient = arguments["recipient"]
        message = arguments["message"]
        urgent = arguments.get("urgent", False)
        
        # Resolve contact
        chat_id = contact_resolver.resolve_recipient(recipient)
        
        # Send message
        result = whatsapp_client.send_message(chat_id, message)
        
        return [TextContent(
            type="text",
            text=f"✅ Message sent to {recipient}. ID: {result['idMessage']}"
        )]
    
    # Handle other tools...

async def main():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )
```

## Configuration

### MCP Server Config

```json
// claude_desktop_config.json (or similar)
{
  "mcpServers": {
    "denidin-whatsapp": {
      "command": "python",
      "args": ["-m", "denidin_mcp"],
      "env": {
        "GREEN_API_INSTANCE": "7105257767",
        "GREEN_API_TOKEN": "your_token_here"
      }
    }
  }
}
```

### Contact Database

```json
// contacts.json
{
  "version": "1.0",
  "last_sync": "2026-01-17T10:00:00Z",
  "contacts": [...],
  "groups": [...]
}
```

## Dependencies

```toml
# pyproject.toml
[project]
name = "denidin-mcp"
version = "0.1.0"
dependencies = [
    "mcp>=0.1.0",
    "requests>=2.31.0",
    "pydantic>=2.0.0",
    "fuzzywuzzy>=0.18.0",  # Fuzzy contact matching
]

[project.scripts]
denidin-mcp = "denidin_mcp.server:main"
```

## Implementation Plan

### Phase 1: Basic MCP Server
- [ ] Set up MCP server project structure
- [ ] Implement `send_whatsapp_message` tool
- [ ] Create static contact database (JSON)
- [ ] Implement basic contact resolution
- [ ] Test with MCP Inspector
- [ ] Write unit tests

### Phase 2: Contact Management
- [ ] Implement `list_whatsapp_contacts` tool
- [ ] Add fuzzy contact matching
- [ ] Handle ambiguous contact resolution
- [ ] Sync contacts from Green API
- [ ] Add contact aliases support

### Phase 3: Group Messaging
- [ ] Implement `send_whatsapp_to_group` tool
- [ ] Group discovery from Green API
- [ ] Group name resolution

### Phase 4: Advanced Features
- [ ] Implement `get_message_status` tool
- [ ] Add message scheduling (future delivery)
- [ ] Batch messaging support
- [ ] Message templates
- [ ] Rate limiting per user

### Phase 5: Integration with DeniDin Bot
- [ ] Share contact database between bot and MCP server
- [ ] Unified configuration
- [ ] Cross-reference message history

## Usage Examples

### Example 1: Simple Message
```
User (in Claude Desktop): 
"Send John a reminder that we're meeting tomorrow at 3pm"

Claude → Calls MCP tool:
send_whatsapp_message(
  recipient="John",
  message="Reminder: We're meeting tomorrow at 3pm"
)

MCP Server → Resolves "John" → Sends via WhatsApp
Response: "✅ Message sent to John Smith. Message ID: ABC123"
```

### Example 2: Group Message
```
User: "Tell the project team we're pushing the deadline to Friday"

Claude → Calls:
send_whatsapp_to_group(
  group_name="Project Team",
  message="Update: We're pushing the deadline to Friday"
)

Response: "✅ Message sent to Project Team group (5 members)"
```

### Example 3: Ambiguous Contact
```
User: "Send Sarah a message saying I'll be late"

MCP resolves → Multiple Sarahs found
Response: "Found 2 contacts named Sarah:
1. Sarah Johnson (work)
2. Sarah Williams (friend)
Please specify which Sarah."

User: "Sarah Johnson"
→ Message sent
```

### Example 4: Status Check
```
User: "Did my message to John get delivered?"

Claude → Calls:
get_message_status(message_id="ABC123")

Response: "Message ABC123 to John Smith: ✓✓ Delivered at 2:45 PM"
```

## Security Considerations

- **Authentication**: Validate Green API credentials
- **Authorization**: Only send to contacts in approved list
- **Rate Limiting**: Prevent spam/abuse
- **Audit Log**: Track all sent messages
- **Privacy**: Don't expose phone numbers unnecessarily
- **Validation**: Sanitize message content

## Testing Strategy

### Unit Tests
- Contact resolution (exact match, fuzzy match)
- Message composition
- Ambiguity handling
- Error cases (contact not found, API failure)

### Integration Tests
- End-to-end message sending via Green API
- Contact sync from WhatsApp
- MCP tool invocation

### Manual Testing
1. Send message to individual contact
2. Send message to group
3. Handle ambiguous contact names
4. Test with invalid recipients
5. Verify message delivery status

## Success Metrics

- ✅ Successfully send messages via MCP tools
- ✅ 95%+ contact resolution accuracy
- ✅ Handle ambiguous names gracefully
- ✅ Message delivery confirmation
- ✅ <2 second response time
- ✅ 90%+ test coverage

## Error Handling

| Error | User Message |
|-------|--------------|
| Contact not found | "❌ Contact 'X' not found. Try: list_whatsapp_contacts" |
| Multiple matches | "Found N contacts: [list]. Please specify." |
| API failure | "❌ Failed to send message. Green API error: [details]" |
| Invalid phone | "❌ Invalid phone number format. Use +[country][number]" |
| Rate limited | "❌ Rate limit exceeded. Try again in X minutes." |

## Cost Implications

- **Green API**: Pay per message sent (~$0.01 per message)
- **Infrastructure**: Minimal (MCP server runs locally)

**Mitigation**:
- Daily message limits per user
- Confirmation prompts for batch sends
- Cost tracking and alerts

## Future Enhancements

- **Scheduling**: "Send John a reminder tomorrow at 9am"
- **Recurring**: "Send team standup reminder every weekday at 9am"
- **Templates**: "Use template 'meeting_reminder' for Sarah"
- **Attachments**: "Send Mike the Q4_report.pdf"
- **Rich Media**: Buttons, lists, location sharing
- **Two-way**: "Send John a message and wait for his reply"
- **Broadcast Lists**: Manage broadcast recipients
- **Analytics**: Track message open rates, response times

## Dependencies on Other Features

- **Optional**: Feature 002 (Chat Sessions) - Could reference session context
- **Optional**: Feature 003 (Media) - Send images/documents via MCP

---

**Next Steps**:
1. Review and approve spec
2. Set up MCP server project
3. Implement Phase 1 (basic send_whatsapp_message)
4. Test with MCP Inspector
5. Integrate with Claude Desktop
6. Create contact database
